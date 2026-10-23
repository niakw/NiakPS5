#!/usr/bin/env python3
"""Strict six-image OpenGL preview contract for missing PS4/PS5 case faces."""
from pathlib import Path
from PIL import Image, ImageStat, ImageChops
import sys

EXPECTED_FILES={
    "ps4-front.png","ps4-back.png","ps4-spine.png",
    "ps5-front.png","ps5-back.png","ps5-spine.png",
}
if len(sys.argv)!=2:
    raise SystemExit("Usage: validate_preview.py build/niak-preview")
root=Path(sys.argv[1])
found={p.name for p in root.glob("*.png")}
if found!=EXPECTED_FILES:
    raise SystemExit(
        f"Expected exactly 6 PNG captures; "
        f"missing={sorted(EXPECTED_FILES-found)} extra={sorted(found-EXPECTED_FILES)}")

def image(filename):
    with Image.open(root/filename) as im:
        if im.size!=(1920,1080):
            raise SystemExit(f"{filename}: expected 1920x1080")
        rgb=im.convert("RGB")
        if sum(ImageStat.Stat(rgb.resize((64,36))).stddev)<10:
            raise SystemExit(f"{filename}: blank OpenGL capture")
        return rgb

def difference(a,b):
    region=(1160,90,1850,760)
    return sum(ImageStat.Stat(ImageChops.difference(
        a.crop(region),b.crop(region))).mean)

for platform in ("ps4","ps5"):
    front=image(f"{platform}-front.png")
    back=image(f"{platform}-back.png")
    spine=image(f"{platform}-spine.png")
    if min(difference(front,back),difference(front,spine),
           difference(back,spine))<7:
        raise SystemExit(f"{platform}: front/back/spine are not distinguishable")
    # The back's PRINTED artwork gallery must contain actual image details,
    # rather than an opaque empty field or plastic. Crop within the case,
    # away from its edge, footer and the wallpaper.
    gallery=back.crop((1450,230,1680,465)).resize((48,48))
    if sum(ImageStat.Stat(gallery).stddev)<12:
        raise SystemExit(f"{platform}: reconstructed back artwork block missing")
print("NIAK_NATIVE_OPENGL_PREVIEW: PASS — exactly 6 case captures")
