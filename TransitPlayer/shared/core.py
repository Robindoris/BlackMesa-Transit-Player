import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

MODES = {
    "valve": "Half-Life", "gearbox": "Opposing Force", "bshift_unlocked": "Blue Shift",
    "cstrike": "Counter Strike 1.6", "svencoop": "Sven Co-Op 4.8", "uplink": "Half-Life Uplink",
    "redempt": "Absolute Redemption", "wantedsp": "Wanted!",
}
LIMIT = 4 * 1024**3
CATALOG = "catalog.json"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def component(s):
    return (isinstance(s, str) and 0 < len(s) <= 200 and
            not any(ord(c) < 32 or c in '<>:"/\\|?*' for c in s) and
            not s.endswith((" ", ".")) and not PureWindowsPath(s).is_reserved())


def mode_id(s):
    require(isinstance(s, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,47}", s) and component(s),
            "Use a lowercase mod folder name with letters, digits and underscores.")
    return s


def label(s):
    require(isinstance(s, str) and 0 < len(s.strip()) <= 100, "Enter a name of 1–100 characters.")
    return s.strip()


def address(s):
    m = re.fullmatch(r"([a-zA-Z0-9.-]+):([0-9]{1,5})", s)
    require(m and all(re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", p)
                      for p in m[1].split(".")) and 0 < int(m[2]) <= 65535,
            "Enter a host and port such as hl.example.org:27015.")
    return s


def public_url(s):
    url = urlsplit(s.strip())
    require(url.scheme in ("http", "https") and url.hostname and not url.username and
            not url.password and not url.query and not url.fragment, "Enter the public HTTP(S) folder URL.")
    return s.strip().rstrip("/")


def empty():
    return {"version": 1, "mods": {}, "servers": []}


def catalog(data):
    require(isinstance(data, dict) and data.get("version") == 1 and isinstance(data.get("mods"), dict)
            and isinstance(data.get("servers"), list), "Unsupported catalog.")
    for key, mod in data["mods"].items():
        mode_id(key)
        label(mod["name"])
        require(key not in MODES and re.fullmatch("[a-f0-9]{64}", mod["sha256"]) and
                0 < mod["bytes"] <= LIMIT, "Invalid package metadata.")
    ids = set()
    for server in data["servers"]:
        label(server["name"])
        address(server["address"])
        require(server["mode"] in MODES or server["mode"] in data["mods"], "Unknown server mode.")
        require(re.fullmatch("[a-f0-9]{32}", server["id"]) and server["id"] not in ids, "Invalid server ID.")
        ids.add(server["id"])
    return data


def save(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        f.write(json.dumps(data, indent=2).encode())
    os.replace(f.name, path)


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def extract(path, folder):
    with zipfile.ZipFile(path) as z:
        entries = z.infolist()
        require(0 < len(entries) <= 80000 and sum(e.file_size for e in entries) <= LIMIT,
                "Mod exceeds the file or unpacked size limit.")
        seen = {}
        for e in entries:
            parts = e.filename.rstrip("/").split("/")
            require(all(component(p) for p in parts) and ((e.external_attr >> 16) & 0o170000)
                    in (0, 0o100000, 0o040000), "Unsupported path or link in ZIP.")
            for i in range(1, len(parts) + 1):
                name = "/".join(parts[:i])
                require(seen.setdefault(name.casefold(), name) == name, "Conflicting filename case in ZIP.")
            out = folder.joinpath(*parts)
            if e.is_dir():
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(e) as src, out.open("xb") as dst:
                    shutil.copyfileobj(src, dst)
        require((folder / "liblist.gam").is_file(), "ZIP the contents of the mod folder with liblist.gam at the top level.")
