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
fallback=Path(sys.argv[1])/"case-04-homebrew-fallback.png"
if not fallback.exists():raise SystemExit("Missing no-retail-art homebrew case preview")
frames=[Image.open(p).convert("RGB").crop((1160,90,1850,760)) for p in required]
changes=[]
for x,y in zip(frames,frames[1:]):
    delta=sum(ImageStat.Stat(ImageChops.difference(x,y)).mean)
    changes.append(delta)
# A fallback case must be distinguishable from the commercial scan.
with Image.open(fallback) as _fallback:
    _box=_fallback.convert("RGB").crop((1160,90,1850,760))
    _difference=sum(ImageStat.Stat(ImageChops.difference(frames[0],_box)).mean)
    if _difference<8:
        raise SystemExit("Homebrew without box art did not use a distinct physical-case fallback")
if any(d<5.5 for d in changes):
    raise SystemExit(f"3D case does not visibly rotate in actual GPU capture: {changes}")
# A 90-degree side view MUST be much narrower than the face. Pixel-level
# verification catches wrong painter order, a wide blue face hiding the spine,
# and accidentally capturing the back instead of the edge.
def vivid_blue_width(path):
    with Image.open(path) as image:
        band=image.convert("RGB").crop((1280,100,1780,540))
        pixels=band.load()
        xs=[]
        for y in range(band.height):
            for x in range(band.width):
                red,green,blue=pixels[x,y]
                if blue>125 and red<155 and blue>red*1.4 and blue>green*1.05:
                    xs.append(x)
        return max(xs)-min(xs)+1 if xs else 0
front_width=vivid_blue_width(required[0])
spine_width=vivid_blue_width(required[1])
back_width=vivid_blue_width(required[2])
if front_width<150 or back_width<150 or not 8<=spine_width<front_width*0.45:
    raise SystemExit(
        f"Incorrect closed-case silhouette: front={front_width}, "
        f"spine={spine_width}, back={back_width}")
# Fail if daily wallpaper becomes so bright that white UI text is unreadable.
# Measure the left hero copy zone across the true host OpenGL captures.
with Image.open(Path(sys.argv[1]) / "01-aurora.png") as _home:
    _hero = _home.convert("RGB").crop((65,135,980,600))
    _means = ImageStat.Stat(_hero.resize((90,46))).mean
    if sum(_means) / 3 > 105:
        raise SystemExit(f"Wallpaper washes out NiakPS5 hero text area: {_means}")
if len(digests)<2:raise SystemExit("No distinct UI screenshots")
print("NIAK_NATIVE_OPENGL_PREVIEW: PASS")
