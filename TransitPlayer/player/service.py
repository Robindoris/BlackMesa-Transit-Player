import json
import os
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen
from shared.core import CATALOG, MODES, address, catalog, digest, empty, extract, mode_id, public_url, require, save


from shared.servers import Directory, KNOWN, PACK_SERVERS, dashboard_api
from player.stats import History
from player.scores import configured_name, personal_name, personal_leaderboard, roster_score


class Player:
    def __init__(self, root, settings):
        self.root = root.resolve()
        self.settings = settings
        self.url = settings.read_text().strip() if settings.exists() else ""
        self.data = empty()
        self.directory = Directory()
        self.history = History()
        self.personal_checked = -float("inf")
        self.cache = settings.with_suffix(".cache")
        if self.url and self.cache.exists():
            try:
                saved = json.loads(self.cache.read_bytes())
                if saved["url"] == self.url:
                    self.data = catalog(saved["catalog"])
            except (ValueError, KeyError, TypeError):
                pass

    def refresh(self):
        with urlopen(public_url(self.url) + "/" + CATALOG, timeout=12) as response:
            data = catalog(json.loads(response.read(2**20 + 1)))
        save(self.cache, {"url": self.url, "catalog": data})
        self.data = data

    def servers(self):
        return self.directory.merge(self.data["servers"])

    def state(self):
        modes = {**MODES, **{k: v["name"] for k, v in self.data["mods"].items()}}
        network = self.directory.network()
        stats = self.history.summary()
        return {"role": "player", "url": self.url, **self.data, "servers": self.servers(),
                "stats": stats, "network": network, "serverCheck": self.directory.checked, "modes": [
            {"id": k, "name": v, "installed": (self.root / k / "liblist.gam").is_file()}
            for k, v in modes.items()]}

    def capture_history(self, personal):
        maps = []
        for server in self.directory.entries.values():
            if server.get("status") == "Online" and server.get("map"):
                mode = server["mode"]
                score = roster_score(server.get("roster") or [], personal_name(self.root, mode))
                name = KNOWN.get(server["address"], (mode, server["name"]))[1]
                maps.append((name, mode, server["map"], server.get("players"), score))
        scores = []
        if personal and time.monotonic() - self.personal_checked >= 300:
            self.personal_checked = time.monotonic()
            try:
                boards = dashboard_api("/leaderboard?limit=all")["leaderboard"]
                scores = personal_leaderboard(self.root, boards, PACK_SERVERS)
            except (OSError, ValueError, KeyError, TypeError):
                pass
            try:
                snapshots = dashboard_api("/history?hours=24")["snapshots"]
                for snapshot in snapshots:
                    for key, data in snapshot["servers"].items():
                        if key in PACK_SERVERS and data.get("online") and data.get("map"):
                            mode, _, server = PACK_SERVERS[key]
                            maps.append((server, mode, data["map"], data.get("players"), None))
            except (OSError, ValueError, KeyError, TypeError):
                pass
        self.history.save_observations(maps, scores)

    def install(self, key):
        mod = self.data["mods"][key]
        dest = self.root / mode_id(key)
        require(not dest.exists(), "The destination folder already exists.")
        with tempfile.TemporaryDirectory(dir=self.root) as td:
            stage = Path(td)
            archive = stage / "release.zip"
            with urlopen(public_url(self.url) + "/" + mod["sha256"] + ".zip", timeout=60) as src, archive.open("wb") as dst:
                size = 0
                while chunk := src.read(1024 * 1024):
                    size += len(chunk)
                    require(size <= mod["bytes"], "Download exceeded the published size.")
                    dst.write(chunk)
            require(size == mod["bytes"] and digest(archive) == mod["sha256"], "Package verification failed.")
            extract(archive, stage / "mod")
            require(not dest.exists(), "Mod folder already exists.")
            (stage / "mod").rename(dest)

    def command(self, key, server_id):
        args = ["-nomaster", "-steam", "-noforcemparms", "-noforcemaccel", "-num_edicts", "4096"]
        if key == "default" or key in MODES:
            bat = "!! --== PLAY ==-- !!" if key == "default" else MODES[key]
            script = (self.root / (bat + ".bat")).read_text(encoding="cp1252")
            line = next((line for line in script.splitlines() if line.lower().startswith("start hl.exe ")), "")
            require(line, "The pack launch script has an unsupported format.")
            args = shlex.split(line)[2:]
        else:
            require(key in self.data["mods"], "Unknown mod.")
            args = ["-game", mode_id(key), *args]
        require((self.root / "hl.exe").is_file() and (self.root / ("valve" if key == "default" else key)
                / "liblist.gam").is_file(), "This game mode is missing from the pack.")
        if server_id:
            server = next((s for s in self.servers() if s["id"] == server_id and s["mode"] == key), None)
            require(server, "This server is unavailable for the selected mode.")
            args.extend(["+connect", address(server["address"])])
            # Some pack modes inherit an empty valve.rc, so GoldSrc skips +connect.
            startup = self.root / key / "valve.rc"
            if not startup.is_file():
                startup = self.root / "valve" / "valve.rc"
            if startup.is_file() and not startup.read_bytes().strip():
                startup.write_bytes(b"stuffcmds\r\n")
        if os.name == "nt":
            return [str(self.root / "hl.exe"), *args]
        wrapper = self.root / "run-half-life.sh"
        return ["bash", str(wrapper), *args] if wrapper.is_file() else ["wine", "./hl.exe", *args]

    def action(self, action, data):
        if action == "configure":
            url = public_url(data["url"])
            if url != self.url:
                self.data = empty()
            self.settings.write_text(url)
            self.url = url
            self.refresh()
        elif action == "refresh":
            self.refresh()
        elif action == "liveServers":
            self.directory.refresh(history=data.get("history") is True)
            self.capture_history(data.get("personal") is True)
        elif action == "install":
            self.install(data["mode"])
        elif action == "launch":
            command = self.command(data["mode"], data.get("server"))
            process = subprocess.Popen(command, cwd=self.root)
            joined = next((s["address"] for s in self.servers() if s["id"] == data.get("server")), None)
            mode = "valve" if data["mode"] == "default" else data["mode"]
            self.history.start(process, joined, mode, configured_name(self.root, mode))
        else:
            raise ValueError("Unknown player action.")
