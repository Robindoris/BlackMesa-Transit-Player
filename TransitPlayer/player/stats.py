import os
import subprocess
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path

from player.scores import player_score
from shared.servers import KNOWN


class History:
    def __init__(self, profile_path=None):
        base = (os.environ.get("LOCALAPPDATA") if os.name == "nt" else os.environ.get("XDG_STATE_HOME"))
        root = (Path(base) if base else Path.home() / ".local" / "state") / "BlackMesaTransit"
        root.mkdir(parents=True, exist_ok=True)
        self.games = set()
        self.portable = profile_path is not None
        self.path = profile_path or root / "stats.sqlite3"
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("""CREATE TABLE IF NOT EXISTS sessions
                       (id INTEGER PRIMARY KEY, started INTEGER NOT NULL, server TEXT, seconds INTEGER DEFAULT 0)""")

            if "mode" not in {row[1] for row in db.execute("PRAGMA table_info(sessions)")}:
                db.execute("ALTER TABLE sessions ADD COLUMN mode TEXT NOT NULL DEFAULT 'valve'")

            columns = {row[1] for row in db.execute("PRAGMA table_info(sessions)")}
            for field, definition in (("uid","TEXT"), ("revision","INTEGER DEFAULT 1"),
                                      ("dirty","INTEGER DEFAULT 1"), ("nickname","TEXT DEFAULT ''"),
                                      ("imported_by","TEXT")):
                if field not in columns:
                    db.execute(f"ALTER TABLE sessions ADD COLUMN {field} {definition}")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS session_uid ON sessions(uid)")

            db.execute("""CREATE TABLE IF NOT EXISTS session_maps
                       (session_id INTEGER NOT NULL, map TEXT NOT NULL, peak INTEGER NOT NULL,
                        score INTEGER NOT NULL, sampled REAL NOT NULL, PRIMARY KEY(session_id, map))""")

            db.execute("""CREATE TABLE IF NOT EXISTS server_maps (
                       server TEXT, mode TEXT, map TEXT, players INTEGER, peak INTEGER,
                       PRIMARY KEY(server, mode, map))""")
            db.execute("""CREATE TABLE IF NOT EXISTS leaderboard (
                       server TEXT, nickname TEXT, peak INTEGER, PRIMARY KEY(server, nickname))""")

    def player_name(self):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT value FROM preferences WHERE key='player_name'").fetchone()
            return row[0] if row else ""

    def set_player_name(self, name):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR REPLACE INTO preferences VALUES ('player_name', ?)", (name,))

    def save_observations(self, maps, scores=()):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executemany("""INSERT INTO server_maps VALUES(?,?,?,?,?)
                           ON CONFLICT(server,mode,map) DO UPDATE SET
                           players=coalesce(max(players,excluded.players),players,excluded.players),
                           peak=coalesce(max(peak,excluded.peak),peak,excluded.peak)""", maps)
            db.executemany("""INSERT INTO leaderboard VALUES(?,?,?)
                           ON CONFLICT(server,nickname) DO UPDATE SET peak=max(peak,excluded.peak)""", scores)

    def start(self, process, server, mode="valve", nickname=""):
        started = time.time()
        start = time.monotonic()
        with closing(sqlite3.connect(self.path)) as db, db:
            key = db.execute("INSERT INTO sessions(started,server,mode,uid,nickname) VALUES(?,?,?,?,?)",
                             (int(started), server, mode, uuid.uuid4().hex, nickname)).lastrowid

        self.games = {done for done in self.games if not done.is_set()}
        recorded = threading.Event()
        self.games.add(recorded)
        finished = threading.Event()

        def collect_scores():
            while not finished.wait(2):
                try:
                    sample = player_score(server, nickname, started)
                except (OSError, ValueError, KeyError, TypeError):
                    sample = None
                if sample and process.poll() is None:
                    stamp, level, score = sample
                    with closing(sqlite3.connect(self.path)) as db, db:
                        db.execute("""INSERT INTO session_maps(session_id,map,peak,score,sampled)
                                      VALUES(?,?,?,?,?) ON CONFLICT(session_id,map) DO UPDATE SET
                                      peak=max(peak, excluded.peak), score=excluded.score, sampled=excluded.sampled
                                      WHERE excluded.sampled > sampled""", (key, level, score, score, stamp))
                        db.execute("UPDATE sessions SET revision=revision+1, dirty=1 WHERE id=?", (key,))
                if finished.wait(13):
                    return

        def monitor():
            while not finished.is_set():
                try:
                    process.wait(timeout=5)
                    finished.set()
                except subprocess.TimeoutExpired:
                    pass
                with closing(sqlite3.connect(self.path)) as db, db:
                    db.execute("UPDATE sessions SET seconds=?, revision=revision+1, dirty=1 WHERE id=?", (int(time.monotonic()-start), key))
            recorded.set()
        if server in KNOWN and nickname:
            threading.Thread(target=collect_scores, daemon=True).start()
        threading.Thread(target=monitor, daemon=True).start()

    def summary(self):
        with closing(sqlite3.connect(self.path)) as db:
            total, joins, seconds = db.execute("SELECT count(*), count(server), coalesce(sum(seconds),0) FROM sessions").fetchone()
            # Include sessions that began before the calendar but continued into it.
            activity = db.execute("""SELECT started, seconds FROM sessions
                                  WHERE started + seconds >= ?""",
                                  (int(time.time()) - 372 * 86400,)).fetchall()
            db.row_factory = sqlite3.Row
            recent = db.execute("""SELECT started, server, seconds, mode,
                                (SELECT score FROM session_maps WHERE session_id=sessions.id
                                 ORDER BY sampled DESC LIMIT 1) AS score
                                FROM sessions ORDER BY started DESC,id DESC LIMIT 10""").fetchall()
            servers = db.execute("SELECT * FROM server_maps ORDER BY server,map").fetchall()
            scores = db.execute("SELECT * FROM leaderboard ORDER BY peak DESC,server").fetchall()
            if self.portable:
                servers = db.execute("""SELECT server,mode,map,NULL AS players,max(peak) AS peak
                                        FROM sessions JOIN session_maps ON sessions.id=session_id
                                        WHERE server IS NOT NULL GROUP BY server,mode,map
                                        ORDER BY server,map""").fetchall()
                scores = db.execute("""SELECT server,nickname,max(peak) AS peak
                                       FROM sessions JOIN session_maps ON sessions.id=session_id
                                       WHERE server IS NOT NULL GROUP BY server,nickname
                                       ORDER BY peak DESC""").fetchall()
            maps = db.execute("""SELECT mode,map,sum(sessions) AS sessions,max(peak) AS peak FROM (
                              SELECT mode, map, count(*) AS sessions, max(peak) AS peak
                              FROM session_maps JOIN sessions ON session_id=sessions.id
                              GROUP BY mode,map
                              UNION ALL SELECT mode,map,0,peak FROM server_maps WHERE peak IS NOT NULL)
                              GROUP BY mode,map ORDER BY sessions DESC, peak DESC, mode,map""").fetchall()
        return {"launches": total, "joins": joins, "seconds": seconds,
                "serverMaps": list(map(dict, servers)), "leaderboard": list(map(dict, scores)),
                "activity": activity, "recent": list(map(dict, recent)), "maps": list(map(dict, maps))}
