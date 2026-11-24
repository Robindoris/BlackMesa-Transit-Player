"""Browser pairing and desktop shortcuts for the local dashboard."""
import hashlib
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path


def pairing_key(install, origin):
    if sys.platform == "win32":
        data = Path(os.environ["LOCALAPPDATA"])
    else:
        data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    directory = data / "BlackMesaTransit" / "pairing"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    identity = hashlib.sha256(f"{install.resolve()}\n{origin}".encode()).hexdigest()
    path = directory / identity
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        key = path.read_text().strip()
        if len(key) != 64:
            raise ValueError(f"Invalid browser pairing key in {path}")
        return key
    key = secrets.token_hex(32)
    with os.fdopen(fd, "w") as output:
        output.write(key)
    return key


def open_installed(origin):
    # Chromium hashes the manifest ID twice to derive its desktop shortcut ID.
    manifest_hash = hashlib.sha256((origin + "/").encode()).digest()
    digest = hashlib.sha256(manifest_hash).hexdigest()[:32]
    app_id = digest.translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
    try:
        if sys.platform.startswith("linux") and shutil.which("gio"):
            data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
            for shortcut in sorted((data / "applications").glob(f"*-{app_id}-*.desktop")):
                if subprocess.run(["gio", "launch", str(shortcut)], timeout=5).returncode == 0:
                    return True
        elif sys.platform == "win32":
            # Chrome and Edge place named shortcuts under the user's Start menu.
            script = r"""
$ws = New-Object -ComObject WScript.Shell
$links = Get-ChildItem ([Environment]::GetFolderPath('Programs')) -Filter '*.lnk' -Recurse
foreach ($link in $links) {
    $shortcut = $ws.CreateShortcut($link.FullName)
    if (($shortcut.Arguments -split '\s+') -contains ('--app-id=' + $env:TRANSIT_PWA_ID)) {
        Start-Process -FilePath $link.FullName -ErrorAction Stop
        exit 0
    }
}
exit 1
"""
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                env={**os.environ, "TRANSIT_PWA_ID": app_id}, timeout=10)
            return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        pass
    return False
