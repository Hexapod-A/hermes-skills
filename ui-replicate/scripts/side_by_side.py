#!/usr/bin/env python3
"""Put a reference and a build next to each other (and optionally a heatmap) in one image.

Usage:
  side_by_side.py REF.png BUILD.png --out sbs.jpg [--heatmap heat.png] [--labels "Reference,Build"]
                  [--max-width 3000] [--blend blend.png]

--blend also writes a 50/50 onion-skin overlay: misplaced edges show up as double lines.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imgutil import load_rgb  # noqa: E402

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def font(size):
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref")
    ap.add_argument("build")
    ap.add_argument("--out", required=True)
    ap.add_argument("--heatmap", help="third panel, e.g. the PNG from diff_score.py --heatmap")
    ap.add_argument("--labels", default="Reference,Build,Mismatch")
    ap.add_argument("--max-width", type=int, default=3000, help="downscale the sheet to this width")
    ap.add_argument("--blend", help="also write a 50/50 overlay of ref and build here")
    a = ap.parse_args()

    ref, build = load_rgb(a.ref), load_rgb(a.build)
    if build.width != ref.width:  # same width so px line up across panels
        build = build.resize((ref.width, round(build.height * ref.width / build.width)), Image.LANCZOS)
    panels = [ref, build]
    if a.heatmap:
        panels.append(load_rgb(a.heatmap).resize(ref.size, Image.LANCZOS))
    labels = [s.strip() for s in a.labels.split(",")]

    gap, head = 40, 64
    H = max(p.height for p in panels)
    Wd = sum(p.width for p in panels) + gap * (len(panels) - 1)
    sheet = Image.new("RGB", (Wd, H + head), "white")
    d = ImageDraw.Draw(sheet)
    f = font(30)
    x = 0
    for i, p in enumerate(panels):
        sheet.paste(p, (x, head))
        d.text((x + 12, 16), labels[i] if i < len(labels) else "", fill=(20, 20, 20), font=f)
        x += p.width + gap
    if sheet.width > a.max_width:
        sheet = sheet.resize((a.max_width, round(sheet.height * a.max_width / sheet.width)), Image.LANCZOS)
    kw = {"quality": 88} if a.out.lower().endswith((".jpg", ".jpeg")) else {}
    sheet.save(a.out, **kw)
    print("wrote", a.out, sheet.size)

    if a.blend:
        h = min(ref.height, build.height)
        Image.blend(ref.crop((0, 0, ref.width, h)), build.crop((0, 0, ref.width, h)), 0.5).save(a.blend)
        print("wrote", a.blend)


if __name__ == "__main__":
    main()
