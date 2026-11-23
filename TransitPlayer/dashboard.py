import argparse
import json
import mimetypes
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from shared.core import require
from player.updater import update
from player.service import Player

BASE = Path(__file__).resolve().parent


def run(install):
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["player"])
    parser.add_argument("--game", type=Path, default=install.parent)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    service = Player(args.game, install / "catalog-url.txt")
    token = secrets.token_urlsafe(32)
    guard = threading.Lock()

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
            origin = self.headers.get("Origin")
            if not self.valid() or self.headers.get("X-Session") != token or (origin and origin != url):
                return self.reply(403, b"{}")
            try:
                route = urlsplit(self.path)
                size = int(self.headers["Content-Length"])
                with guard:
                    require(0 < size < 16000, "Invalid request.")
                    data = json.loads(self.rfile.read(size))
                    if route.path == "/update":
                        result = update(install, BASE)
                        return self.reply(200, json.dumps({"message": result}).encode())
                    require(route.path == "/action", "Invalid request.")
                    service.action(data.pop("action"), data)
                    self.reply(200, json.dumps(service.state()).encode())
            except Exception as exc:
                self.reply(400, json.dumps({"error": str(exc) or type(exc).__name__}).encode())

    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        link = url + "/#" + token
        print("Open this dashboard on this computer:\n" + link + "\nClose this terminal to stop.", flush=True)
        if not args.no_browser:
            webbrowser.open(link)
        server.serve_forever()
