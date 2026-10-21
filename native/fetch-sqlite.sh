#!/usr/bin/env bash
# Pinned SQLite amalgamation; never fetch a moving branch while building.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p vendor
EXPECTED="eaa24a131073ed708f03da967f4cbb3686e10168"
URL="https://raw.githubusercontent.com/itsPLK/ps5-pkg-manager/914311f945d14a555e1c09635346bb069c3368e8/src/sqlite3.c"
if test -f vendor/sqlite3.c && test "$(git hash-object vendor/sqlite3.c)" = "$EXPECTED"; then
  exit 0
fi
tmp="$(mktemp vendor/sqlite3.XXXXXX)"
trap 'rm -f "$tmp"' EXIT
curl --fail --location --retry 3 --max-time 180 "$URL" -o "$tmp"
test "$(git hash-object "$tmp")" = "$EXPECTED" || { echo "SQLite source mismatch"; exit 1; }
mv "$tmp" vendor/sqlite3.c
echo "Pinned SQLite amalgamation ready."
