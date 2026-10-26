#!/usr/bin/env python3
"""Stage a single drag-and-drop FTP tree. The owner copies data/ into FTP /.

No commands, installer, or PLDmgr edits are required for transfer. The
pre-existing autoload.txt is NOT supplied, modified, or fabricated.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

TITLE="PPSA99386"
OWN_PAYLOAD="niakps5"
REQUIRED=("eboot.bin","sce_module/libc.prx","sce_sys/param.json",
          "tools/niakps5/niakps5.elf","tools/niakps5/niakps5.elf.json")

def _owned_paths(tree:Path):
    for path in tree.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlinks forbidden in FTP drag-and-drop archive")
        if not (path.is_file() or path.is_dir()):
            raise ValueError("Unsupported FTP entry")
        if path.name in ("autoload.txt","pldmgr_config.txt"):
            raise ValueError("Never bundle user's PLDmgr configuration")
    return sorted(tree.rglob("*"))

def stage(title:Path,output:Path):
    title=title.resolve(strict=True)
    output=output.absolute()
    if title.name!=TITLE or not title.is_dir() or title.is_symlink():
        raise ValueError("Need built title folder PPSA99386")
    if output==title or output.is_relative_to(title) or title.is_relative_to(output):
        raise ValueError("Output must be separate from title folder")
    _owned_paths(title)
    for part in REQUIRED:
        p=title/part
        if not p.is_file() or p.is_symlink() or p.stat().st_size==0:
            raise ValueError(f"Missing required file {part}")
    meta=json.loads((title/"sce_sys/param.json").read_text("utf-8"))
    if meta.get("titleId")!=TITLE:raise ValueError("Wrong PS5 title ID")
    elf=title/"tools/niakps5/niakps5.elf"
    if elf.open("rb").read(4)!=b"\x7fELF":
        raise ValueError("Invalid bundled companion ELF")
    sidecar=json.loads((title/"tools/niakps5/niakps5.elf.json").read_text("utf-8"))
    if (sidecar.get("filename")!=elf.name or
        sidecar.get("checksum")!=hashlib.sha256(elf.read_bytes()).hexdigest()):
        raise ValueError("Companion ELF metadata/checksum mismatch")
    if output.exists():
        shutil.rmtree(output)
    app=output/"data/homebrew"/TITLE
    slot=output/"data/pldmgr/payloads"/OWN_PAYLOAD
    shutil.copytree(title,app,symlinks=False)
    # PS5 launcher files must remain in the registered title mount.
    # Persistent writable NiakPS5 state belongs under a distinct, human-
    # readable /data/NiakPS5 root, never inside the title installation.
    runtime=output/"data/NiakPS5"
    for subdir in ("assets","cache","inventory","logs","state"):
        folder=runtime/subdir
        folder.mkdir(parents=True,exist_ok=True)
        (folder/"README.txt").write_text("NiakPS5 "+subdir+" runtime directory\\n",encoding="utf-8")
    (runtime/"README.txt").write_text(
        "NiakPS5 persistent runtime files. Do not delete PPSA99386 while "
        "it is the mounted PS5 executable title.\\n",encoding="utf-8")
    slot.mkdir(parents=True,exist_ok=True)
    for name in ("niakps5.elf","niakps5.elf.json"):
        shutil.copy2(title/"tools/niakps5"/name,slot/name)
    for directory in (output,output/"data",runtime,*(runtime/p for p in ("assets","cache","inventory","logs","state")),output/"data/homebrew",
                      output/"data/pldmgr",output/"data/pldmgr/payloads",slot):
        directory.chmod(0o755)
    # Some FTP clients preserve these POSIX flags; the ZIP metadata also
    # requests executable rights, though server behavior still varies.
    (slot/"niakps5.elf").chmod(0o755)
    (slot/"niakps5.elf.json").chmod(0o644)
    (app/"eboot.bin").chmod(0o755)
    _owned_paths(output)
    paths={p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
    if (any(path.startswith("data/pldmgr/") and not
            path.startswith("data/pldmgr/payloads/niakps5/") for path in paths)
        or len([p for p in paths if p.startswith("data/pldmgr/")])!=2
        or any("autoload" in p.lower() for p in paths)):
        raise ValueError("Unexpected PLDmgr file in drag-and-drop tree")
    print("FTP drop-in staged: copy data/ to PS5 FTP / (merge existing folders)")
    print("The package does NOT include or change autoload.txt.")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--title",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    stage(args.title,args.output)
