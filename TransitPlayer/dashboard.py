import argparse
import json
import mimetypes
import os
import secrets
import shutil
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from shared.core import require
from player.updater import update
from player.service import Player
from player.webapp import open_installed, pairing_key

BASE = Path(__file__).resolve().parent


def apply_launcher_icons(install):
    if not sys.platform.startswith("linux") or not shutil.which("gio"):
        return
    icon_uri = (BASE / "ui/art/lambda.png").as_uri()
    for name in ("Half-Life Launcher.sh", "Half-Life Launcher.bat"):
        script = install.parent / name
        if script.is_file():
            try:
                subprocess.run(["gio", "set", str(script), "metadata::custom-icon", icon_uri],
                               stderr=subprocess.DEVNULL, timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass  # Desktop metadata is optional for dashboard startup.


def run(install):
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["player"])
    parser.add_argument("--game", type=Path, default=install.parent)
    parser.add_argument("--port", type=int, default=27080)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    apply_launcher_icons(install)
    service = Player(args.game, install / "catalog-url.txt")
    token = secrets.token_urlsafe(32)
    guard = threading.Lock()
    shutdown_action = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, content, mime="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(content)

        def valid(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

        def do_GET(self):
            path = urlsplit(self.path).path
            if not self.valid():
                return self.reply(403, b"{}")
            if path == "/session":
                credential = self.headers.get("X-Session", "")
                if credential == token:
                    return self.reply(200, json.dumps({"session": token, "pairing": pairing}).encode())
                if credential == pairing:
                    return self.reply(200, json.dumps({"session": token}).encode())
                return self.reply(403, b"{}")
            if path == "/manifest.webmanifest":
                return self.reply(200, (BASE / "ui/manifest.webmanifest").read_bytes(),
                                  "application/manifest+json")
            if path == "/api":
                if self.headers.get("X-Session") != token:
                    return self.reply(403, b"{}")
                with guard:
                    return self.reply(200, json.dumps(service.state()).encode())
            root = BASE / "ui"
            file = (root / (path.lstrip("/") or "index.html")).resolve()
            if not file.is_relative_to(root) or not file.is_file():
                return self.reply(404, b"{}")
            self.reply(200, file.read_bytes(), mimetypes.guess_type(file)[0] or "application/octet-stream")

        def do_POST(self):
            nonlocal shutdown_action
            origin = self.headers.get("Origin")
            if not self.valid() or self.headers.get("X-Session") != token or (origin and origin != url):
                return self.reply(403, b"{}")
            try:
                route = urlsplit(self.path)
                size = int(self.headers["Content-Length"])
                with guard:
                    if shutdown_action:
                        return self.reply(503, b'{"error":"Launcher is shutting down."}')
                    require(0 < size < 16000, "Invalid request.")
                    data = json.loads(self.rfile.read(size))
                    if route.path in ("/update", "/restart", "/stop"):
                        if route.path == "/update" and not update(install, BASE):
                            return self.reply(200, b'{"message":"Your dashboard is up to date."}')
                        shutdown_action = "stop" if route.path == "/stop" else "restart"
                        try:
                            self.reply(200, json.dumps({"restarting": shutdown_action == "restart"}).encode())
                        finally:
                            self.server.shutdown()
                        return
                    require(route.path == "/action", "Invalid request.")
                    service.action(data.pop("action"), data)
                    self.reply(200, json.dumps(service.state()).encode())
            except Exception as exc:
                self.reply(400, json.dumps({"error": str(exc) or type(exc).__name__}).encode())

    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        parser.exit(1, f"Cannot start the dashboard on port {args.port}: {exc}\n")
    with server:
        url = f"http://127.0.0.1:{server.server_port}"
        pairing = pairing_key(install, url)
        link = url + "/#" + token
        print("Open this dashboard on this computer:\n" + link + "\nClose this terminal to stop.", flush=True)
        if not args.no_browser and not open_installed(url):
            webbrowser.open(link)
        server.serve_forever()
    if shutdown_action == "restart":
        # Keep the terminal and any running game-history monitors alive.
        command = [sys.executable, str(install / "launcher.py"), args.role,
                   "--game", str(args.game), "--port", str(server.server_port), "--no-browser"]
        if os.name == "posix" and threading.active_count() == 1:
            os.execv(sys.executable, command)
        raise SystemExit(subprocess.call(command))
