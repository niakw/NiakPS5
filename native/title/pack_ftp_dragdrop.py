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
import stat

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
    slot.mkdir(parents=True,exist_ok=True)
    for name in ("niakps5.elf","niakps5.elf.json"):
        shutil.copy2(title/"tools/niakps5"/name,slot/name)
    for directory in (output,output/"data",output/"data/homebrew",
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

def package_zip(folder:Path,destination:Path):
    """Keep executable bits in an *inner* ZIP: GitHub artifact ZIP resets them.

    The owner only extracts archives in the file manager, then drags data/ into
    FTP root. Never executes a script to install the application on the PS5.
    """
    from zipfile import ZipFile,ZipInfo,ZIP_DEFLATED,ZIP_STORED
    folder=folder.resolve(strict=True)
    destination=destination.absolute()
    if not (folder/"data/homebrew"/TITLE/"eboot.bin").is_file():
        raise ValueError("Staged drop-in tree missing")
    if destination.is_relative_to(folder):
        raise ValueError("Archive destination inside staging tree")
    _owned_paths(folder)
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix(".zip.tmp")
    try:
        with ZipFile(temporary,"w",compression=ZIP_DEFLATED,compresslevel=6) as z:
            for p in [folder/"data",*sorted((folder/"data").rglob("*"))]:
                directory=p.is_dir()
                name=p.relative_to(folder).as_posix()+("/" if directory else "")
                mode=(stat.S_IFDIR|0o755 if directory else
                      stat.S_IFREG|(0o755 if p.name in
                              ("eboot.bin","niakps5.elf","sandbox-elevator.elf")
                              else 0o644))
                meta=ZipInfo(name,(2026,1,1,0,0,0))
                meta.create_system=3
                meta.external_attr=(mode<<16)|(0x10 if directory else 0)
                meta.compress_type=ZIP_STORED if directory else ZIP_DEFLATED
                if directory:z.writestr(meta,b"")
                else:z.write(p,arcname=name,compress_type=ZIP_DEFLATED,
                             compresslevel=6)
        with ZipFile(temporary) as z:
            names=z.namelist()
            if z.testzip() is not None or len(names)!=len(set(names)):
                raise ValueError("Invalid drag-and-drop ZIP")
            if not all(name.startswith("data/") for name in names):
                raise ValueError("Unexpected ZIP root")
            if any(name=="data/pldmgr/autoload.txt" or
                   name=="data/pldmgr/pldmgr_config.txt" for name in names):
                raise ValueError("PLDmgr configuration bundled unexpectedly")
            for path in ("data/homebrew/PPSA99386/eboot.bin",
                         "data/pldmgr/payloads/niakps5/niakps5.elf",
                         "data/pldmgr/payloads/niakps5/niakps5.elf.json"):
                if path not in names:raise ValueError("Missing required FTP path")
            for path in ("data/homebrew/PPSA99386/eboot.bin",
                         "data/pldmgr/payloads/niakps5/niakps5.elf"):
                if (z.getinfo(path).external_attr>>16)&0o777!=0o755:
                    raise ValueError("Lost executable file permissions")
        os.replace(temporary,destination)
    finally:
        if temporary.exists():temporary.unlink()
    print(f"FTP no-command ZIP with executable metadata: {destination}")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--title",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--archive",type=Path)
    args=p.parse_args()
    stage(args.title,args.output)
    if args.archive:package_zip(args.output,args.archive)
