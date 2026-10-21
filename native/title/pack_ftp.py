#!/usr/bin/env python3
"""Create ONE FTP-ready PPSA99386.zip.

Archive root: PPSA99386/ only. No nested ZIP, no optional payload, no README.
Store POSIX modes: directory 0755, eboot.bin 0755, other files 0644.
Also apply the same modes to the staging folder for FTP clients using it
directly (FTP servers may not preserve ZIP metadata on extraction).
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import stat
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED, ZIP_STORED

TITLE_ID = "PPSA99386"
REQUIRED = ("eboot.bin", "sce_module/libc.prx", "sce_sys/param.json")

def package(folder: Path, destination: Path) -> None:
    folder = folder.absolute()
    destination = destination.absolute()
    if folder.name != TITLE_ID or not folder.is_dir() or folder.is_symlink():
        raise ValueError("Expected a real PPSA99386 directory")
    for name in REQUIRED:
        target = folder / name
        if not target.is_file() or target.is_symlink() or not target.stat().st_size:
            raise ValueError(f"Missing required title file: {name}")
    info = json.loads((folder / "sce_sys/param.json").read_text("utf-8"))
    if info.get("titleId") != TITLE_ID:
        raise ValueError("Title identifier does not match the install directory")
    if destination.is_relative_to(folder):
        raise ValueError("Output archive may not be inside the install directory")
    files = sorted(folder.rglob("*"))
    if any(p.is_symlink() for p in files):
        raise ValueError("No symlinks allowed in FTP title package")
    if any(p.is_file() and p.suffix.lower() in (".zip", ".elf") for p in files):
        raise ValueError("No nested ZIPs or separate ELF payloads in title package")
    # Path structure and permissions must survive a ZIP extractor.
    for p in [folder, *files]:
        if not (p.is_dir() or p.is_file()):
            raise ValueError(f"Unsupported path: {p}")
        p.chmod(0o755 if p.is_dir() or p.name == "eboot.bin" else 0o644)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".zip.tmp")
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for path in [folder, *files]:
                is_dir = path.is_dir()
                name = f"{TITLE_ID}/" + ("" if path == folder else path.relative_to(folder).as_posix())
                if is_dir and not name.endswith("/"):
                    name += "/"
                mode = (stat.S_IFDIR | 0o755) if is_dir else (
                    stat.S_IFREG | (0o755 if path.name == "eboot.bin" else 0o644))
                meta = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                meta.create_system = 3
                meta.external_attr = (mode << 16) | (0x10 if is_dir else 0)
                meta.compress_type = ZIP_STORED if is_dir else ZIP_DEFLATED
                if is_dir:
                    archive.writestr(meta, b"")
                else:
                    archive.write(path, arcname=name, compress_type=ZIP_DEFLATED,
                                  compresslevel=6)
        with ZipFile(temporary) as archive:
            names = archive.namelist()
            if archive.testzip() is not None or len(names) != len(set(names)):
                raise ValueError("ZIP integrity check failed")
            if any(not n.startswith(f"{TITLE_ID}/") or n.lower().endswith(".zip")
                   for n in names):
                raise ValueError("Unexpected archive root or nested ZIP")
            if any(f"{TITLE_ID}/{p}" not in names for p in REQUIRED):
                raise ValueError("A required file is not packaged")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"FTP package: {destination} ({destination.stat().st_size} bytes)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package(args.folder, args.output)
