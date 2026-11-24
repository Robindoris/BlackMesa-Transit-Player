#!/usr/bin/env bash
set -euo pipefail

scripts=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$scripts" rev-parse --show-toplevel)
output=${1:-"$root/dist"}
mkdir -p "$output"
output=$(cd "$output" && pwd)
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

# Package only the committed dashboard. Local settings and profiles stay private.
git -C "$root" archive HEAD TransitPlayer | tar -x -C "$stage"
for component in launcher setup; do
  makensis -V2 "-DBUILD=$output" "-DPAYLOAD=$stage" "$scripts/$component.nsi"
done
