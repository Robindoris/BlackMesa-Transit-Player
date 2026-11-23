import hashlib
import json
import re
import socket
import time
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from shared.core import MODES, address

PORTAL = "https://brut.me/lgsl/index_portal.php"
LIST = "https://brut.me/lgsl/"
# Public GoldSrc entries from brut-dashboard/app.py and their game-pack directories.
PACK_SERVERS = {
    "hl": ("valve", 27015, "Half-Life DeathMatch"),
    "hltp": ("valve", 27020, "Half-Life TeamPlay"),
    "op4": ("gearbox", 27016, "Opposing Force DeathMatch"),
    "cs": ("cstrike", 27017, "Counter-Strike 1.6 Classic"),
    "csgg": ("cstrike", 27019, "Counter-Strike 1.6 GunGame"),
    "wanted": ("wantedsp", 27018, "Wanted! DeathMatch"),
    "sven": ("svencoop", 27024, "Sven Co-Op 4.8 Classic"),
}
KNOWN = {f"95.170.247.153:{port}": (mode, name) for mode, port, name in PACK_SERVERS.values()}


def card(endpoint, name, mode, **stats):
    return {"id": "lgsl-" + hashlib.sha256(endpoint.encode()).hexdigest()[:16],
            "address": endpoint, "mode": mode, "name": name, "status": "Unavailable", **stats}


class Listing(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.stack.append({"cells": [], "attrs": [], "cell": False})
        if not self.stack:
            return
        row = self.stack[-1]
        if tag in ("td", "th"):
            row["cells"].append([])
            row["cell"] = True
        row["attrs"].extend(value for _, value in attrs if value)

    def handle_data(self, text):
        if self.stack and self.stack[-1]["cell"]:
            self.stack[-1]["cells"][-1].append(text)

    def handle_endtag(self, tag):
        if self.stack and tag in ("td", "th"):
            self.stack[-1]["cell"] = False
        if self.stack and tag == "tr":
            self.rows.append(self.stack.pop())


def parse_listing(html):
    parser = Listing()
    parser.feed(html)
    found = {}
    for row in parser.rows:
        cells = [" ".join(" ".join(c).split()) for c in row["cells"]]
        attrs = " ".join(row["attrs"])
        game = re.search(r"\bgame\s*:\s*([a-z0-9_]+)", attrs, re.I)
        if not game or game[1].lower() not in MODES:
            continue
        for i, cell in enumerate(cells):
            if not re.fullmatch(r"[\w.-]+:\d+", cell) or len(cells) < i + 4:
                continue
            try:
                address(cell)
            except ValueError:
                continue
            count = re.fullmatch(r"(\d+)\s*/\s*(\d+)", cells[i+3])
            status = re.search(r"\b(ONLINE|OFFLINE)\b", attrs, re.I)
            if not status and not count:
                continue
            found[cell] = card(cell, cells[i+1] or cell, game[1].lower(), map=cells[i+2], source="BRUT.me LGSL",
                               status=status[1].title() if status else "Listed",
                               players=int(count[1]) if count else None, capacity=int(count[2]) if count else None)
    return found


def query_game(endpoint):
    host, port = endpoint.split(":")
    prefix = b"\xff\xff\xff\xff"
    request = prefix + b"TSource Engine Query\x00"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(1.5)
        sock.connect((host, int(port)))
        sock.send(request)
        reply = sock.recv(8192)
        if reply.startswith(prefix + b"A") and len(reply) == 9:
            sock.send(request + reply[5:])
            reply = sock.recv(8192)
    if reply.startswith(prefix + b"I"):
        name, level, game, _, rest = reply[6:].split(b"\x00", 4)
        counts = rest[2:4]
    elif reply.startswith(prefix + b"m"):
        _, name, level, game, _, rest = reply[5:].split(b"\x00", 5)
        counts = rest[:2]
    else:
        raise ValueError("Unsupported server response")
    mode = game.decode("ascii").lower()
    if mode not in MODES or len(counts) != 2:
        raise ValueError("Missing Half-Life server information")
    return card(endpoint, name.decode("latin1"), mode, map=level.decode("latin1"), players=counts[0],
                capacity=counts[1], source="Game server", status="Online")


API = "https://brut.myprox.eu/api"



def dashboard_api(path):
    request = Request(API + path, headers={"User-Agent": "BlackMesaTransit/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=8) as response:
        return json.loads(response.read(4 * 1024**2))


def dashboard_cards(payload):
    found = {}
    for srv in payload["servers"]:
        if srv["key"] not in PACK_SERVERS or srv["type"] != "goldsrc":
            continue
        endpoint = address(f"{srv['host']}:{srv['port']}")
        online = srv["online"]
        rules = srv.get("rules") or {}
        found[endpoint] = card(endpoint, srv.get("server_name") or srv["name"], PACK_SERVERS[srv["key"]][0],
                               status="Online" if online else "Offline", map=srv.get("map") if online else None,
                               players=srv.get("players") if online else None,
                               capacity=srv.get("max_players") if online else None,
                               bots=srv.get("bots") if online else None, ping=srv.get("ping") if online else None,
                               timeLeft=rules.get("time_left"), nextMap=rules.get("next_map"),
                               roster=srv.get("player_list") if online else None, source="BRUT.me dashboard")
    return found


def hourly_peaks(payload, now):
    # Use aligned UTC hours so the labels describe the same buckets on every computer.
    start = int(now // 3600) * 3600 - 23 * 3600
    groups = {"all": list(PACK_SERVERS)}
    for key, (mode, _, _) in PACK_SERVERS.items():
        groups.setdefault(mode, []).append(key)
    buckets = {mode: [{"start": start + hour * 3600, "peak": None} for hour in range(24)] for mode in groups}
    for row in payload["snapshots"]:
        index = int((row["ts"] - start) // 3600)
        if not 0 <= index < 24 or row["ts"] > now:
            continue
        servers = row["servers"]
        for mode, keys in groups.items():
            if all(isinstance(servers.get(k, {}).get("players"), int) for k in keys):
                total = sum(servers[k]["players"] for k in keys)
                bucket = buckets[mode][index]
                bucket["peak"] = max(bucket["peak"] or 0, total)
    return buckets


class Directory:
    def __init__(self):
        self.entries = {k: card(k, name, mode) for k, (mode, name) in KNOWN.items()}
        self.checked = 0
        self.history_checked = 0
        self.peaks = {}

    def network(self):
        return {"servers": list(self.entries.values()), "checked": self.checked, "peaks": self.peaks}

    def refresh(self, history=False):
        if history and time.time() - self.history_checked >= 300:
            self.history_checked = time.time()
            try:
                self.peaks = hourly_peaks(dashboard_api("/history?hours=24"), self.history_checked)
            except (OSError, ValueError, KeyError, TypeError):
                self.peaks = {}
        if time.time() - self.checked < 45:
            return
        try:
            payload = dashboard_api("/status")
            age = time.time() - payload["timestamp"]
            fresh = dashboard_cards(payload) if -120 <= age <= 300 else {}
        except (OSError, ValueError, KeyError, TypeError):
            fresh = {}
        for url in (PORTAL, LIST):
            if fresh:
                break
            try:
                with urlopen(Request(url, headers={"User-Agent": "BlackMesaTransit/1.0"}), timeout=3) as r:
                    fresh = parse_listing(r.read(1024**2).decode("utf8", "replace"))
                if fresh:
                    break
            except (OSError, ValueError):
                continue
        for endpoint, (mode, name) in KNOWN.items():
            if endpoint not in fresh:
                try:
                    fresh[endpoint] = query_game(endpoint)
                except (OSError, ValueError):
                    fresh[endpoint] = card(endpoint, name, mode)
        self.entries, self.checked = fresh, int(time.time())

    def merge(self, published):
        rows = []
        matched = set()
        for server in published:
            live = self.entries.get(server["address"])
            if live and live["mode"] == server["mode"]:
                rows.append({**live, **server})
                matched.add(server["address"])
            else:
                rows.append(server)
        rows.extend(s for k, s in self.entries.items() if k not in matched)
        return rows
