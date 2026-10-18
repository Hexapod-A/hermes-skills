#!/usr/bin/env python3
"""Turn a raw reference into a target-viewport reference: crop the UI out of the presentation, scale
it to the viewport width, and print the viewport to render the build at.

Usage:
  prep_ref.py RAW.png --out ref_1440.png [--width 1440] [--crop x0,y0,x1,y1] [--trim] [--tol 12]

--crop is in RAW pixels. --trim cuts a flat border (the plain backdrop many Dribbble shots sit on)
by comparing against the corner colour. Then the UI is scaled to --width with Lanczos.
The printed "viewport" line is what screenshot.mjs must use so the two images line up 1:1.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imgutil import load_rgb  # noqa: E402


def trim_box(im, tol=12):
    a = np.asarray(im, dtype=np.int16)
    corner = np.median(np.stack([a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]]), axis=0)
    diff = np.abs(a - corner).max(-1) > tol
    rows, cols = np.where(diff.any(1))[0], np.where(diff.any(0))[0]
    if len(rows) == 0:
        return (0, 0, im.width, im.height)
    return (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--crop")
    ap.add_argument("--trim", action="store_true")
    ap.add_argument("--tol", type=int, default=12)
    a = ap.parse_args()
    im = load_rgb(a.image)
    print("raw", im.size)
    if a.crop:
        box = tuple(int(v) for v in a.crop.split(","))
        im = im.crop(box)
        print("crop", box)
    if a.trim:
        box = trim_box(im, a.tol)
        im = im.crop(box)
        print("trim", box)
    scale = a.width / im.width
    im = im.resize((a.width, round(im.height * scale)), Image.LANCZOS)
    im.save(a.out)
    print(f"scale {scale:.4f} (1 ref px = {1 / scale:.2f} raw px)")
    print(f"wrote {a.out} {im.size}")
    print(f"viewport: --width {im.width} --height {im.height}")


if __name__ == "__main__":
    main()
