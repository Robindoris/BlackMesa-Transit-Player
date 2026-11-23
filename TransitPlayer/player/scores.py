import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from shared.servers import KNOWN, LIST, dashboard_api, dashboard_cards


def configured_name(root, mode):
    for directory in dict.fromkeys((mode, "valve")):
        try:
            config = (root / directory / "config.cfg").read_bytes()
        except OSError:
            continue
        names = re.findall(rb'^\s*name\s+(?:"([^"\r\n]+)"|(\S+))', config, re.I | re.M)
        if names:
            raw = next(part for part in names[-1] if part)
            try:
                return raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                return raw.decode("cp1252", "replace").strip()
    return ""


def personal_name(root, mode, preferred=""):
    name = preferred or configured_name(root, mode)
    return "" if name.casefold() in {"<brut.me> player", "player"} else name


def lgsl_roster(endpoint):
    host, port = endpoint.split(":")
    params = urlencode(dict(type="halflife", ip=host, c_port=port, q_port=port, request="sp", xml=1))
    request = Request(LIST + "lgsl_files/lgsl_feed.php?" + params, headers={"User-Agent": "BlackMesaTransit/1.0"})
    with urlopen(request, timeout=3) as response:
        data = ElementTree.fromstring(response.read(256 * 1024))
    if data.findtext("b/status") != "1" or data.find("p") is None:
        raise ValueError("Roster unavailable")
    players = [dict(name=p.findtext("name"), score=p.findtext("score")) for p in data.findall("p/player")]
    return float(data.findtext("s/cache_time") or 0), data.findtext("s/map"), players


def player_score(endpoint, nickname, started):
    if endpoint not in KNOWN or not nickname:
        return
    try:
        stamp, level, players = lgsl_roster(endpoint)
        if not level or not max(started, time.time() - 90) <= stamp <= time.time():
            raise ValueError("No recent LGSL sample")
    except (OSError, ValueError, ElementTree.ParseError):
        payload = dashboard_api("/status")
        stamp = payload["timestamp"]
        if not max(started, time.time() - 90) <= stamp <= time.time():
            return
        server = dashboard_cards(payload).get(endpoint, {})
        level, players = server.get("map"), server.get("roster") or []
    score = roster_score(players, nickname)
    if level and score is not None:
        return stamp, level, score


def roster_score(players, nickname):
    if not nickname:
        return None
    matches = [p for p in players if (p.get("name") or "").strip().casefold() == nickname.casefold()]
    if len(matches) == 1 and re.fullmatch(r"-?\d+", str(matches[0].get("score"))):
        return int(matches[0]["score"])


def personal_leaderboard(root, boards, pack, preferred=""):
    rows = []
    for key, (mode, _, server) in pack.items():
        nickname = personal_name(root, mode, preferred)
        if not nickname:
            continue
        matches = [p for p in boards.get(key, []) if p["name"].casefold() == nickname.casefold()]
        exact = [p for p in matches if p["name"] == nickname]
        candidates = exact or matches
        if len(candidates) == 1 and isinstance(candidates[0].get("best_score"), int):
            rows.append((server, nickname, candidates[0]["best_score"]))
    return rows
