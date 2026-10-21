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
if len(digests)<2:raise SystemExit("No distinct UI screenshots")
print("NIAK_NATIVE_OPENGL_PREVIEW: PASS")
