"""Start the selected player dashboard using the installed Python runtime."""
import re
import sys
from pathlib import Path


def main():
    install = Path(__file__).resolve().parent
    updates = install / ".dashboard-updates"
    active = install
    marker = updates / "current"
    if marker.is_file():
        version = marker.read_text().strip()
        if re.fullmatch("[0-9a-f]{40}", version) and (updates / version / "dashboard.py").is_file():
            active = updates / version
    sys.path.insert(0, str(active))
    from dashboard import run
    run(install)


if __name__ == "__main__":
    main()
