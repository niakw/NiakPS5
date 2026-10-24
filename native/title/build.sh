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
python3 "$root/native/title/prepare.py" --kit "$stage" --project "$root" --revision "$(git -C "$root" rev-parse --short=12 HEAD)"
# Best-effort recent games from Steam; offline/error => original animated smoke.
python3 "$root/native/title/fetch_daily_games.py" --output "$stage/assets/niak-daily"
# Exact LaunchBox PlayStation 4/5 regional metadata; no retail scans
# redistributed in public CI artifacts. Fail over to system catalogue.
if ! python3 "$root/native/title/launchbox_index.py" --download \
    --titles "$root/native/title/ps_titles.tsv" \
    --output "$stage/assets/niak-launchbox-cases.tsv"; then
  echo "LaunchBox index unavailable; keeping public PlayStation title metadata" >&2
  printf '# title\tOverview\tFront\tBack\tSpine\tLogo\tLaunchBoxID\n' \
    > "$stage/assets/niak-launchbox-cases.tsv"
fi
# A successfully downloaded LaunchBox database with thousands of matches
# MUST contain at least some real short overviews. Do not ship an empty
# description catalogue again when a field name changes upstream.
python3 - "$stage/assets/niak-launchbox-cases.tsv" <<'PY'
from pathlib import Path
import sys
rows=Path(sys.argv[1]).read_text(encoding="utf8").splitlines()
if len(rows)>1000:
    actual=sum(1 for row in rows[1:] if len(row.split("\t"))>=10 and row.split("\t")[1]!="-")
    if actual<50:
        raise SystemExit(f"LaunchBox overviews missing: {actual} of {len(rows)-1} matches")
    print(f"LaunchBox indexed descriptions: {actual}/{len(rows)-1}")
    # The real public metadata feed must populate independent back sources.
    # Catch upstream type/field drift BEFORE producing a "green" package
    # with empty backs. Nothing is downloaded to a private console here.
    counts=[sum(1 for row in rows[1:] if len(row.split("\t"))>=10
                and row.split("\t")[field]!="-") for field in (6,7,8)]
    print("LaunchBox back slots [fanart, screenshot1, screenshot2]:",counts)
    if min(counts)<100:
        raise SystemExit(f"LaunchBox back artwork index empty: {counts}")
PY
python3 "$root/native/title/patch_home.py" --kit "$stage"
python3 "$root/native/title/polish.py" --kit "$stage"
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
# The pinned OpenGL kit does not yet expose APP_WRAP_SYMBOLS.
# Its linker can wrap fcntl using the proven PS5-native libcurl socket shim.
# Patch only the disposable, SHA-pinned staging checkout (never upstream).
python3 - "$stage/tools/build.sh" <<'PY'
from pathlib import Path
import sys
f=Path(sys.argv[1])
s=f.read_text()
old="wrap_options=()"
if s.count(old)!=1:
    raise SystemExit("Pinned native linker wrap anchor changed")
f.write_text(s.replace(old,"wrap_options=(--wrap=fcntl)",1))
PY
# Keep the reference kit's asset / runtime inputs and attribution.
make -C "$stage" init TITLE_ID="$title" APP_NAME=NiakPS5 APP_CATEGORY=game
# See PacBrew docs: SQLite is a read-only static link, no .db modification.
make -C "$stage" USE_CCACHE=0 PACBREW_PACKAGES=libcurl PACBREW_INCLUDE_PATHS=include PACBREW_STATIC_ARCHIVES=lib/libsqlite3.a
test -f "$stage/dist/$title/eboot.bin"
test -f "$stage/dist/$title/sce_module/libc.prx"
test -f "$stage/dist/$title/sce_sys/param.json"
out="$root/dist/$title"
mkdir -p "$root/dist"
rm -rf "$out"
cp -a "$stage/dist/$title" "$out"
# The owner only copies folders via FTP. Every six immutable PS4/PS5
# overlay pieces must already exist in the delivered native title.
python3 "$root/native/title/stage_case_templates.py" --folder "$out"
# Ready-to-copy PLDmgr slot ships inside the SAME single-ZIP title package.
# Copy tools/niakps5/ into /data/pldmgr/payloads/ after copying the title.
mkdir -p "$out/tools/niakps5"
sdk="$stage/.deps/native/ps5-payload-sdk"
test -x "$sdk/bin/prospero-clang"
"$sdk/bin/prospero-clang" -std=c11 -O2 -Wall -Wextra \
  -I "$root/native" \
  -o "$out/tools/niakps5/niakps5.elf" "$root/native/title/autostart.c" \
  -lSceSystemService -lSceUserService -lkernel_sys
# One-shot sandbox elevation helper adapted from Eden Encore.
# Only an already-active, local elfldr at 127.0.0.1:9021 can run it.
"$sdk/bin/prospero-clang++" -std=c++20 -O2 -Wall -Wextra -Werror \
  -o "$out/sandbox-elevator.elf" \
  "$root/native/title/elevation/helper/main.cpp"
test -s "$out/sandbox-elevator.elf"
python3 - "$out/tools/niakps5/niakps5.elf" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
elf = Path(sys.argv[1])
meta = {
    "name": "NiakPS5",
    "filename": elf.name,
    "description": "NiakPS5 local-only PS5 home launcher and title launch broker",
    "version": "local-build",
    "source": "https://github.com/niakw/NiakPS5",
    "category": "Utilities",
    "checksum": hashlib.sha256(elf.read_bytes()).hexdigest(),
    "install_source": "local",
    "install_source_detail": "Bundled in NiakPS5 PPSA99386"
}
elf.with_suffix(".elf.json").write_text(
    json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
cp "$root/native/title/ftp_install.py" "$out/tools/ftp_install.py"
cp "$root/native/title/cover_sources.py" "$out/tools/cover_sources.py"
cp "$root/native/title/launchbox_index.py" "$out/tools/launchbox_index.py"
cp "$root/native/title/translate_overviews.py" "$out/tools/translate_overviews.py"
cp "$root/native/title/AUTOSTART.md" "$out/tools/AUTOSTART.md"
# GitHub automatically creates ONE downloadable ZIP from dist/ftp-dropin.
# Do not produce extra ZIP layers or include archive files in FTP /data.
python3 "$root/native/title/pack_ftp_dragdrop.py" \
  --title "$out" --output "$root/dist/ftp-dropin"
echo "Built single-level FTP folder $root/dist/ftp-dropin/data"
echo "Copy data/ to FTP /, MERGING existing directories."
