"""Portable player identities and incremental replication of session snapshots."""
import json
import os
import re
import sqlite3
import tempfile
import threading
import uuid
from contextlib import closing
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from player.stats import History

ORIGIN = "https://brutnameservice.myprox.eu"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class Expired(ValueError):
    pass


def request(route, data, credential=""):
    headers = {"Content-Type": "application/json"}
    if credential:
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", credential):
            raise Expired("Invalid or expired profile token.")
        headers["Authorization"] = "Bearer " + credential
    req = Request(ORIGIN + "/v1/" + route, json.dumps(data).encode(), headers)
    try:
        with build_opener(NoRedirect()).open(req, timeout=8) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 401:
            raise Expired("Invalid or expired profile token.") from None
        raise ValueError("Profile request failed.") from None
    except OSError:
        raise ValueError("Profile service unavailable.") from None


def session_batch(db):
    rows = db.execute("""SELECT id,uid,revision,started,seconds,mode,server,nickname FROM sessions
                         WHERE dirty=1 ORDER BY id LIMIT 16""").fetchall()
    batch = []
    for row in rows:
        event = dict(row)
        key = event.pop("id")
        event["maps"] = db.execute("""SELECT map,peak,score,sampled FROM session_maps
                                      WHERE session_id=?""", (key,)).fetchall()
        event["maps"] = [tuple(sample) for sample in event["maps"]]
        batch.append(event)
    return batch


def merge(db, event):
    old = db.execute("SELECT id,revision FROM sessions WHERE uid=?", (event["uid"],)).fetchone()
    if old and old[1] >= event["revision"]:
        return
    db.execute("""INSERT INTO sessions(uid,revision,started,seconds,mode,server,nickname,dirty)
                  VALUES(:uid,:revision,:started,:seconds,:mode,:server,:nickname,0)
                  ON CONFLICT(uid) DO UPDATE SET revision=excluded.revision,seconds=excluded.seconds,
                  dirty=0""", event)
    key = db.execute("SELECT id FROM sessions WHERE uid=?", (event["uid"],)).fetchone()[0]
    db.executemany("INSERT OR REPLACE INTO session_maps VALUES(?,?,?,?,?)",
                   [(key,*sample) for sample in event["maps"]])


class Profile:
    def __init__(self, directory, identity):
        self.id = identity["id"]
        if not re.fullmatch(r"[a-f0-9]{32}", self.id):
            raise ValueError("Invalid profile ID.")
        self.name = identity["name"]
        self.device = identity["device"]
        self.history = History(directory / (self.id + ".sqlite3"))
        self.status = "Sync pending"
        self.lock = threading.Lock()

    def sync(self):
        with self.lock, closing(sqlite3.connect(self.history.path)) as db:
            db.row_factory = sqlite3.Row
            while True:
                with db:
                    db.execute("BEGIN")
                    cursor = db.execute("SELECT value FROM preferences WHERE key='cursor'").fetchone()
                    events = session_batch(db)
                result = request("sync", {"cursor": int(cursor[0]) if cursor else 0, "sessions":events}, self.device)
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    db.executemany("UPDATE sessions SET dirty=0 WHERE uid=:uid AND revision=:revision", events)
                    for event in result["sessions"]:
                        merge(db, event)
                    db.execute("INSERT OR REPLACE INTO preferences VALUES('cursor',?)", (result["cursor"],))
                self.name = result["name"]
                if len(events) < 16 and not result["more"]:
                    self.status = "Synced"
                    break

    def try_sync(self):
        try:
            self.sync()
        except Expired:
            self.status = "Sign in again to sync."
        except (ValueError, OSError, sqlite3.Error):
            self.status = "Offline · changes saved on this computer"


class Profiles:
    def __init__(self, guest):
        self.guest = guest
        self.directory = guest.path.parent / "profiles"
        self.directory.mkdir(mode=0o700, exist_ok=True)
        self.file = self.directory / "device.json"
        self.active = None
        self.wake = threading.Event()
        self.stop = threading.Event()
        if self.file.exists():
            self.active = Profile(self.directory, json.loads(self.file.read_bytes()))
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

    def worker(self):
        while not self.stop.is_set():
            profile = self.active
            if profile:
                profile.try_sync()
            self.wake.wait(15)
            self.wake.clear()

    def activate(self, route, data):
        result = request(route, {"name":data.get("playerName","")} if route=="create" else {},
                         data.get("token","").strip() if route=="login" else "")
        profile = Profile(self.directory, result)
        profile.sync()
        self.leave()
        if data.get("remember") == "on":
            values = {k:result[k] for k in ("id","name","device")}
            with tempfile.NamedTemporaryFile(dir=self.directory, delete=False, mode="w") as f:
                json.dump(values, f)
            os.replace(f.name, self.file)
        self.active = profile
        return {"profileToken":result["token"]} if route == "create" else {}

    def leave(self):
        old = self.active
        self.active = None
        self.file.unlink(missing_ok=True)
        if old:
            games = tuple(old.history.games)
            if any(not game.is_set() for game in games):
                threading.Thread(target=self.finish, args=(old,games), daemon=True).start()
            else:
                self.finish(old, ())

    @staticmethod
    def finish(old, games):
        for game in games:
            game.wait()
        old.try_sync()
        try:
            request("logout", {}, old.device)
        except ValueError:
            pass

    def importable(self):
        with closing(sqlite3.connect(self.guest.path)) as db:
            return db.execute("""SELECT count(*),coalesce(sum(seconds),0)
                                 FROM sessions WHERE imported_by IS NULL""").fetchone()

    def import_guest(self):
        profile = self.active
        with closing(sqlite3.connect(profile.history.path)) as db, db:
            db.execute("ATTACH DATABASE ? AS guest", (str(self.guest.path),))
            db.execute("BEGIN IMMEDIATE")
            for key, in db.execute("SELECT id FROM guest.sessions WHERE imported_by IS NULL").fetchall():
                uid = uuid.uuid4().hex
                new = db.execute("""INSERT INTO main.sessions(started,server,seconds,mode,nickname,uid)
                                    SELECT started,server,seconds,mode,nickname,? FROM guest.sessions WHERE id=?""",
                                 (uid,key)).lastrowid
                db.execute("""INSERT INTO main.session_maps SELECT ?,map,peak,score,sampled
                              FROM guest.session_maps WHERE session_id=?""", (new,key))
                db.execute("UPDATE guest.sessions SET imported_by=? WHERE id=?", (profile.id,key))
        self.wake.set()
