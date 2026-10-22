#!/usr/bin/env python3
"""Validate real host OpenGL captures, rather than a mockup."""
from pathlib import Path
from PIL import Image,ImageStat
import sys
files=sorted(Path(sys.argv[1]).glob("*.png"))
if len(files)<2:raise SystemExit("Missing native UI previews")
digests=set()
for file in files:
    with Image.open(file) as image:
        if image.size!=(1920,1080):raise SystemExit("Wrong screenshot size")
        rgb=image.convert("RGB")
        if sum(ImageStat.Stat(rgb.resize((64,36))).stddev)<10:
            raise SystemExit("Blank UI screenshot")
        digests.add(rgb.resize((48,27)).tobytes())
# The retail case only rotates CLOSED: front / spine / back / return.
required=[Path(sys.argv[1]) / f"case-{i:02d}-{suffix}.png" for i,suffix in
          enumerate(("front","spine","back","return"))]
if not all(p.exists() for p in required):raise SystemExit("Missing rotating case C++ frames")
from PIL import ImageChops
frames=[Image.open(p).convert("RGB").crop((1160,90,1850,760)) for p in required]
changes=[]
for x,y in zip(frames,frames[1:]):
    delta=sum(ImageStat.Stat(ImageChops.difference(x,y)).mean)
    changes.append(delta)
if any(d<5.5 for d in changes):
    raise SystemExit(f"3D case does not visibly rotate in actual GPU capture: {changes}")
# Fail if daily wallpaper becomes so bright that white UI text is unreadable.
# Measure the left hero copy zone across the true host OpenGL captures.
with Image.open(Path(sys.argv[1]) / "01-aurora.png") as _home:
    _hero = _home.convert("RGB").crop((65,135,980,600))
    _means = ImageStat.Stat(_hero.resize((90,46))).mean
    if sum(_means) / 3 > 105:
        raise SystemExit(f"Wallpaper washes out NiakPS5 hero text area: {_means}")
if len(digests)<2:raise SystemExit("No distinct UI screenshots")
print("NIAK_NATIVE_OPENGL_PREVIEW: PASS")
