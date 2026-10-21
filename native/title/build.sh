#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Build a native PS5 *title folder*, not a Payload Manager SDL ELF.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
kit_repo=https://github.com/mihawk-99/PS5_VKHomebrewUI.git
kit_revision=2188642afbcc8d84d36149124f3d9e39dc1b1a05
title=PPSA99386
stage="$root/.build/ps5-title-kit"
command -v git >/dev/null
command -v python3 >/dev/null
if [[ ! -d "$stage/.git" ]]; then
  mkdir -p "$(dirname "$stage")"
  git clone --depth=1 "$kit_repo" "$stage"
fi
git -C "$stage" fetch --depth=1 origin "$kit_revision"
git -C "$stage" checkout --detach --force "$kit_revision"
git -C "$stage" reset --hard "$kit_revision"
test "$(git -C "$stage" rev-parse HEAD)" = "$kit_revision"
# This checkout is ephemeral and only prepared for our own GPU UI.
python3 "$root/native/title/prepare.py" --kit "$stage" --project "$root"
# Best-effort recent games from Steam; offline/error => original animated smoke.
python3 "$root/native/title/fetch_daily_games.py" --output "$stage/assets/niak-daily"
python3 "$root/native/title/patch_home.py" --kit "$stage"
# Upstream ps5-opengl release URL was withdrawn; use a mirrored archive
# ONLY if it passes the *original upstream* pinned archive and manifest SHA-256.
python3 - "$stage/tools/fetch-opengl-sdk.sh" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
src=p.read_text()
old='https://github.com/blackbearreloaded/ps5-opengl/releases/download/v$version/ps5-opengl-sdk-$version.tar.gz'
new='https://github.com/MyLuxy/overdrive-deps/releases/download/ps5-opengl-v$version/ps5-opengl-sdk-$version.tar.gz'
if src.count(old)!=1: raise SystemExit("Pinned OpenGL fetch URL changed; review required")
p.write_text(src.replace(old,new))
PY
# Keep the reference kit's asset / runtime inputs and attribution.
make -C "$stage" init TITLE_ID="$title" APP_NAME=NiakPS5 APP_CATEGORY=game
# See PacBrew docs: SQLite is a read-only static link, no .db modification.
make -C "$stage" USE_CCACHE=0 PACBREW_INCLUDE_PATHS=include PACBREW_STATIC_ARCHIVES=lib/libsqlite3.a
test -f "$stage/dist/$title/eboot.bin"
test -f "$stage/dist/$title/sce_module/libc.prx"
test -f "$stage/dist/$title/sce_sys/param.json"
# Autostart is a separate, opt-in, non-GUI one-shot payload.
sdk="$stage/.deps/native/ps5-payload-sdk"
if [[ -x "$sdk/bin/prospero-clang" ]]; then
  mkdir -p "$root/dist/autostart"
  "$sdk/bin/prospero-clang" -std=c11 -O2 -Wall -Wextra \
    -o "$root/dist/autostart/niakps5_autostart.elf" \
    "$root/native/title/autostart.c" \
    -lSceSystemService -lSceUserService -lkernel_sys
  test -s "$root/dist/autostart/niakps5_autostart.elf"
else
  echo "Autostart helper not built: pinned SDK compiler absent" >&2
fi
out="$root/dist/$title"
mkdir -p "$root/dist"
rm -rf "$out"
cp -a "$stage/dist/$title" "$out"
(cd "$root/dist" && zip -qr "NiakPS5-title-$title.zip" "$title")
if [[ -s "$root/dist/autostart/niakps5_autostart.elf" ]]; then
  cp "$root/native/title/AUTOSTART.md" "$root/dist/README-AUTOSTART.md"
  (cd "$root/dist" && zip -qr "NiakPS5-AutoHome-$title.zip" \
    "$title" autostart/niakps5_autostart.elf README-AUTOSTART.md)
fi
echo "Built native NiakPS5 app folder: $out"
echo "Install the entire $title directory under /data/homebrew/."
