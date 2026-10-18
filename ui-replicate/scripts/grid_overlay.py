#!/usr/bin/env python3
"""Draw a labelled pixel grid over a reference so boxes can be measured by eye (or by a vision model).

Usage:
  grid_overlay.py REF.png --out ref_grid.png [--step 40] [--major 200] [--crop x0,y0,x1,y1] [--zoom 2]

Minor lines every --step px, labelled major lines every --major px. Coordinates are the image's own
pixels (after --crop they stay in full-image coordinates), so a box read off the grid can go straight
into the spec. Use --crop + --zoom 2 to read a small component (a button, a pill) to +-2 px.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imgutil import load_rgb  # noqa: E402
from side_by_side import font  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--out", required=True)
    ap.add_argument("--step", type=int, default=40)
    ap.add_argument("--major", type=int, default=200)
    ap.add_argument("--crop", help="x0,y0,x1,y1")
    ap.add_argument("--zoom", type=float, default=1.0)
    a = ap.parse_args()

    im = load_rgb(a.image)
    ox = oy = 0
    if a.crop:
        ox, oy, x1, y1 = (int(v) for v in a.crop.split(","))
        im = im.crop((ox, oy, x1, y1))
    z = a.zoom
    if z != 1:
        im = im.resize((round(im.width * z), round(im.height * z)), Image.NEAREST)
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    f = font(max(11, int(12 * min(z, 2))))
    first = lambda o: ((o + a.step - 1) // a.step) * a.step  # noqa: E731
    for gx in range(first(ox), ox + round(im.width / z) + 1, a.step):
        X = round((gx - ox) * z)
        major = gx % a.major == 0
        d.line([(X, 0), (X, im.height)], fill=(255, 0, 90, 150 if major else 55), width=2 if major else 1)
        if major:
            d.text((X + 3, 3), str(gx), fill=(255, 0, 90, 255), font=f)
    for gy in range(first(oy), oy + round(im.height / z) + 1, a.step):
        Y = round((gy - oy) * z)
        major = gy % a.major == 0
        d.line([(0, Y), (im.width, Y)], fill=(0, 120, 255, 150 if major else 55), width=2 if major else 1)
        if major:
            d.text((3, Y + 3), str(gy), fill=(0, 120, 255, 255), font=f)
    out = Image.alpha_composite(im.convert("RGBA"), over).convert("RGB")
    out.save(a.out)
    print("wrote", a.out, out.size)


if __name__ == "__main__":
    main()
