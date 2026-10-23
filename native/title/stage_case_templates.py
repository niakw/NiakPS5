#!/usr/bin/env python3
"""Stage PS4/PS5 immutable platform strips for a drag-and-drop installation.

Uses the existing six WebP preview pieces already tracked in the public
repository; this does not redistribute private high-resolution originals.
Resamples platform strips to accepted PS5 texture sizes so the runtime does
not reject the low-res preview dimensions. The user's original PNGs remain
the preferred replacement when manually copied into the same FTP folder.
"""
from __future__ import annotations
from base64 import b64decode
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from PIL import Image

EXPECTED={
    "ps4-front":(949,136),"ps4-back":(647,362),
    "ps4-spine":(72,800),"ps5-front":(1487,209),
    "ps5-back":(1000,411),"ps5-spine":(85,1000),
}
SOURCE_SHA256="cd3383fa7705ec19ebfbb5923d67d75c9c9c3fd2c290b91edd562c2792c0ecc4"

def stage(folder:Path):
    folder=Path(folder)
    if folder.name!="PPSA99386" or not folder.is_dir():
        raise ValueError("Need the built PPSA99386/ folder")
    parts=Path(__file__).resolve().parent/"assets"/"preview-blocks"
    blocks=[parts/f"{i:02}.b64" for i in range(6)]
    if not all(path.is_file() for path in blocks):
        raise ValueError("Six user-derived PS4/PS5 preview blocks missing")
    data=b64decode("".join(path.read_text("ascii").strip() for path in blocks),
                   validate=True)
    if sha256(data).hexdigest()!=SOURCE_SHA256:
        raise ValueError("Fixed template source hash mismatch")
    output=folder/"assets"/"niak-templates"
    output.mkdir(parents=True,exist_ok=True)
    with ZipFile(BytesIO(data)) as zipfile:
        if zipfile.testzip() is not None or set(zipfile.namelist())!={
            name+".webp" for name in EXPECTED
        }:raise ValueError("Unexpected fixed PS4/PS5 art in archive")
        for name,size in EXPECTED.items():
            with zipfile.open(name+".webp") as file:
                image=Image.open(file)
                image.load()
                if image.format!="WEBP":
                    raise ValueError("Invalid fixed PS4/PS5 WebP")
                # Same artwork, no synthetic logos/images. Resample to PS5
                # runtime-required dimensions; private full-res PNGs may
                # replace these six paths later over FTP.
                image=image.convert("RGB").resize(size,Image.Resampling.LANCZOS)
                dest=output/(name+".png")
                if not dest.is_file():
                    image.save(dest,"PNG",optimize=True)
    if len(list(output.glob("*.png")))!=6:
        raise ValueError("Incomplete six-template default installation")
    print("Six original-derived PS4/PS5 strips staged for drag-and-drop.")

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--folder",required=True,type=Path)
    stage(p.parse_args().folder)
