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
ps5_front=Path(sys.argv[1])/"case-07-ps5-missing-front.png"
ps5_back=Path(sys.argv[1])/"case-08-ps5-genuine-back.png"
ps5_front_original=Path(sys.argv[1])/"case-09-ps5-genuine-front.png"
ps5_back_fallback=Path(sys.argv[1])/"case-10-ps5-missing-back.png"
ps4_front=Path(sys.argv[1])/"case-11-ps4-fallback-front.png"
ps4_back=Path(sys.argv[1])/"case-12-ps4-fallback-back.png"
if not all(p.exists() for p in (ps5_front,ps5_back,ps5_front_original,
                                 ps5_back_fallback,ps4_front,ps4_back)):
    raise SystemExit("Missing mixed official/fallback PS5 captures")
menu_r1=Path(sys.argv[1])/"case-05-r1-menu.png"
if not menu_r1.exists():raise SystemExit("Missing R1 tab navigation capture")
detail=Path(sys.argv[1])/"case-06-touchpad-details.png"
if not detail.exists():raise SystemExit("Missing touchpad details capture")
if not fallback.exists():raise SystemExit("Missing no-retail-art homebrew case preview")
frames=[Image.open(p).convert("RGB").crop((1160,90,1850,760)) for p in required]
changes=[]
for x,y in zip(frames,frames[1:]):
    delta=sum(ImageStat.Stat(ImageChops.difference(x,y)).mean)
    changes.append(delta)
# R1 must change the active menu tab but NOT change the daily wallpaper.
# The two captures are adjacent frames, avoiding time-of-day drift.
with Image.open(menu_r1) as _after_image, Image.open(required[0]) as _before_image:
    _after=_after_image.convert("RGB")
    _before=_before_image.convert("RGB")
    _tab_region=(70,50,1320,164)
    _tab_change=sum(ImageStat.Stat(ImageChops.difference(
        _before.crop(_tab_region),_after.crop(_tab_region))).mean)
    if _tab_change<0.25:
        raise SystemExit("R1 did not visibly switch the menu tab")
    _wall_region=(865,205,1115,470)
    _wall_change=sum(ImageStat.Stat(ImageChops.difference(
        _before.crop(_wall_region),_after.crop(_wall_region))).mean)
    if _wall_change>3.5:
        raise SystemExit("R1 unexpectedly changed the daily wallpaper")
# Touchpad must open the NiakPS5 detail sheet (large in-panel overlay),
# not the upstream English developer panel or an inert screen.
with Image.open(detail) as touch,Image.open(fallback) as before_touch:
    region=(140,595,1770,1010)
    change=sum(ImageStat.Stat(ImageChops.difference(
        touch.convert("RGB").crop(region),
        before_touch.convert("RGB").crop(region))).mean)
    if change<11:raise SystemExit("Touchpad click did not open NiakPS5 details")
# Missing front vs genuine back must be distinguishable in OpenGL.
with Image.open(ps5_front) as a, Image.open(ps5_back) as b:
    left=a.convert("RGB").crop((1200,120,1800,580))
    right=b.convert("RGB").crop((1200,120,1800,580))
    diff=sum(ImageStat.Stat(ImageChops.difference(left,right)).mean)
    if diff<6:raise SystemExit("Missing-front and official-back faces rendered identically")
# The other PS5 title shows its TRUE front and a generated missing back.
with Image.open(ps5_front_original) as original,Image.open(ps5_back_fallback) as rebuilt:
    crop=(1200,120,1800,580)
    gap=sum(ImageStat.Stat(ImageChops.difference(
        original.convert("RGB").crop(crop),rebuilt.convert("RGB").crop(crop))).mean)
    if gap<6:raise SystemExit("Genuine-front / fallback-back previews indistinguishable")
# Missing BOTH PS4 faces must still have different front/back compositions.
with Image.open(ps4_front) as a,Image.open(ps4_back) as b:
    region=(1200,120,1800,580)
    different=sum(ImageStat.Stat(ImageChops.difference(
        a.convert("RGB").crop(region),b.convert("RGB").crop(region))).mean)
    if different<6:raise SystemExit("PS4 fallback front/back are indistinguishable")
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
