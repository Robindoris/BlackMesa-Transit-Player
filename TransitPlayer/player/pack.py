"""Install a browser-downloaded game pack beside a copy of the active dashboard."""
import shutil
import tempfile
import zipfile
from pathlib import Path

from shared.core import component, require

GAME_FOLDER = "BRUT.me Half-Life"
LAUNCHERS = ("Half-Life Launcher.sh", "Half-Life Launcher.bat", "Brutmepacklauncher.exe")


def prepare(folder, install):
    root = Path(folder).expanduser()
    require(root.is_absolute(), "Enter a full folder path.")
    root = root.resolve()
    require(not root.is_relative_to(install), "Choose a folder outside TransitPlayer.")
    target = root / GAME_FOLDER
    require(not target.exists() and not target.is_symlink(), "The game folder already exists. Choose another destination.")
    require(not (root / "hl.exe").exists(), "This folder already contains Half-Life. Choose another destination.")
    root.mkdir(parents=True, exist_ok=True)
    return root, set(root.iterdir())


def completed_zip(folder, previous, selected):
    if selected:
        path = Path(selected).expanduser()
        require(path.is_absolute() and path.is_file() and path.suffix.lower() == ".zip",
                "Enter the full path to a downloaded ZIP.")
        require(zipfile.is_zipfile(path), "The ZIP is incomplete or invalid.")
        return path
    candidates = [p for p in folder.iterdir() if p not in previous and p.suffix.lower() == ".zip"
                  and not p.is_symlink() and p.is_file() and zipfile.is_zipfile(p)]
    require(len(candidates) <= 1, "Several ZIPs were found. Enter the full path to the pack ZIP.")
    return next(iter(candidates), None)


def install_pack(archive, folder, install):
    target = folder / GAME_FOLDER
    with tempfile.TemporaryDirectory(dir=folder) as tmp, zipfile.ZipFile(archive) as z:
        stage = Path(tmp) / "game"
        stage.mkdir()
        entries = z.infolist()
        require(len(entries) <= 150000, "The pack contains too many files.")
        names = {entry.filename for entry in entries}
        roots = [name[:-6] for name in names if name.split("/")[-1] == "hl.exe"
                 and name[:-6] + "valve/liblist.gam" in names]
        require(len(roots) == 1, "The ZIP must contain one Half-Life pack with hl.exe and valve/liblist.gam.")
        prefix = roots[0]
        protected = {name.casefold() for name in (*LAUNCHERS, "TransitPlayer")}
        size = sum(entry.file_size for entry in entries)
        require(size <= 32 * 1024**3 and size < shutil.disk_usage(folder).free,
                "The pack exceeds the unpacked size limit or available disk space.")
        seen = {}
        for entry in entries:
            if not entry.filename.startswith(prefix):
                continue
            relative = entry.filename[len(prefix):].rstrip("/")
            if not relative:
                continue
            parts = relative.split("/")
            require(all(component(p) for p in parts) and
                    (entry.external_attr >> 16) & 0o170000 in (0, 0o040000, 0o100000),
                    "Unsupported path or link in ZIP.")
            if parts[0].casefold() in protected:
                continue
            for i in range(1, len(parts) + 1):
                name = "/".join(parts[:i])
                require(seen.setdefault(name.casefold(), name) == name, "Conflicting filename case in ZIP.")
            output = stage.joinpath(*parts)
            if entry.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                with z.open(entry) as src, output.open("xb") as dst:
                    shutil.copyfileobj(src, dst)
        require((stage / "hl.exe").is_file() and (stage / "valve/liblist.gam").is_file(),
                "Incomplete Half-Life pack.")
        shutil.copytree(install, stage / "TransitPlayer", ignore=shutil.ignore_patterns("__pycache__"))
        for name in LAUNCHERS:
            if (install.parent / name).is_file():
                shutil.copy2(install.parent / name, stage / name)
        require(not target.exists() and not target.is_symlink(), "The game folder already exists. Choose another destination.")
        stage.rename(target)
    return target
