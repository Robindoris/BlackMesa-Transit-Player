"""Start the selected player dashboard using the installed Python runtime."""
import os
import re
import sys
from pathlib import Path


def main():
    install = Path(__file__).resolve().parent
    # Fresh Windows profiles may not have fetched the roots OpenSSL needs yet.
    if sys.platform == "win32" and (install / "runtime/cacert.pem").is_file():
        os.environ.setdefault("SSL_CERT_FILE", str(install / "runtime/cacert.pem"))
    updates = install / ".dashboard-updates"
    active = install
    marker = updates / "current"
    if marker.is_file():
        version = marker.read_text().strip()
        if re.fullmatch("[0-9a-f]{40}", version) and (updates / version / "dashboard.py").is_file():
            active = updates / version
    sys.path.insert(0, str(active))
    # Keep the optional desktop launcher available after a pack relocation,
    # including when the selected dashboard is an upstream update.
    from player import pack
    desktop = ("Brutmepacklauncher-Desktop.exe", "WebView2Loader.dll")
    if all((install.parent / name).is_file() for name in desktop):
        pack.LAUNCHERS = tuple(dict.fromkeys((*pack.LAUNCHERS, *desktop)))
    if os.environ.get("BRUT_TRANSIT_DESKTOP") == "1":
        # Rust supplies the authenticated URL again after every restart. Keep
        # pairing for this ephemeral port private to this server process.
        from functools import cache
        import secrets
        from player import webapp

        @cache
        def desktop_pairing(install_path, origin):
            return secrets.token_hex(32)

        webapp.pairing_key = desktop_pairing
    from dashboard import run
    run(install)


if __name__ == "__main__":
    main()
