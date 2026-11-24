#!/usr/bin/env bash
# Build with Bash, Rust's Windows GNU target, MinGW-w64, curl and NSIS 3.
# Usage: bash build.sh /path/to/BlackMesa-Transit-Player /path/to/output
set -euo pipefail
src=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$1" && pwd)
mkdir -p "$2"
out=$(cd "$2" && pwd)
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
git -C "$repo" archive "$(cat "$src/source-commit")" | tar -x -C "$stage"
cp -R "$src/desktop" "$stage/desktop"
cp "$src/launcher.py" "$stage/TransitPlayer/"
cp "$src/runtime/"* "$stage/TransitPlayer/runtime/"
cargo build --locked --release --manifest-path "$stage/desktop/Cargo.toml" --target x86_64-pc-windows-gnu
binaries="$stage/desktop/target/x86_64-pc-windows-gnu/release"
cp "$binaries/brut-transit-desktop.exe" "$out/Brutmepacklauncher-Desktop.exe"
x86_64-w64-mingw32-strip "$out/Brutmepacklauncher-Desktop.exe"
cp "$binaries/WebView2Loader.dll" "$out/"
curl --fail --location --silent --show-error 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -o "$out/MicrosoftEdgeWebview2Setup.exe"
makensis -V2 "-DBUILD=$out" "-DPAYLOAD=$stage" "$stage/packaging/windows/launcher.nsi"
makensis -V2 "-DBUILD=$out" "-DPAYLOAD=$stage" "$src/desktop-setup.nsi"
