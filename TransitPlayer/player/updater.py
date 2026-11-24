"""Stage a complete player dashboard from the public repository."""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

API = "https://api.github.com/repos/Robindoris/BlackMesa-Transit-Player"
REQUIRED = {"dashboard.py", "ui/index.html", "ui/app.js", "ui/style.css",
            "player/service.py", "player/updater.py", "shared/core.py"}


def fetch(path, limit, accept="application/vnd.github+json"):
    request = Request(API + path, headers={"User-Agent": "BlackMesaTransit-Player", "Accept": accept})
    with urlopen(request, timeout=20) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Dashboard download exceeds the size limit.")
    return data


def matches(data, sha):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == sha


def published_dashboard():
    tree = json.loads(fetch("/git/trees/main?recursive=1", 2**20))
    version = tree["sha"]
    if tree.get("truncated") or not re.fullmatch("[0-9a-f]{40}", version):
        raise ValueError("GitHub returned an incomplete dashboard version.")
    files = {}
    for item in tree["tree"]:
        path = item["path"].removeprefix("TransitPlayer/")
        if not item["path"].startswith("TransitPlayer/") or item["type"] != "blob":
            continue
        if not (path == "dashboard.py" or path.startswith(("player/", "shared/", "ui/"))):
            continue
        if item["mode"] != "100644" or not all(re.fullmatch(r"[\w-][\w.-]*", p) for p in path.split("/")):
            raise ValueError("Unsupported dashboard file in update.")
        files[path] = item["sha"]
    if not REQUIRED.issubset(files):
        raise ValueError("GitHub returned an incomplete dashboard package.")
    return version, files


def has_changes(active, version, files):
    if active.name == version and active.parent.name == ".dashboard-updates":
        return False
    local = {p.relative_to(active).as_posix() for folder in ("player", "shared", "ui")
             for p in (active / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    if local | {"dashboard.py"} != files.keys():
        return True
    return any(not matches((active / path).read_bytes(), sha) for path, sha in files.items())


def update_available(active):
    return has_changes(active, *published_dashboard())


def update(install, active):
    version, files = published_dashboard()
    if not has_changes(active, version, files):
        return False
    updates = install / ".dashboard-updates"
    updates.mkdir(exist_ok=True)
    destination = updates / version
    with tempfile.TemporaryDirectory(dir=updates) as temporary:
        stage = Path(temporary) / "dashboard"
        if not destination.exists():
            for path, sha in files.items():
                source = active / path
                data = source.read_bytes() if source.is_file() else b""
                if not source.is_file() or not matches(data, sha):
                    data = fetch("/git/blobs/" + sha, 16 * 2**20, "application/vnd.github.raw+json")
                    if not matches(data, sha):
                        raise ValueError("Dashboard download failed verification. Try again.")
                output = stage / path
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(data)
            try:
                stage.rename(destination)
            except OSError:
                if not destination.is_dir():
                    raise
        marker = Path(temporary) / "current"
        marker.write_text(version)
        os.replace(marker, updates / "current")
    return True
