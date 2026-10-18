#!/usr/bin/env python3
"""Sample the colour palette of a reference image (or compare it with a build).

Usage:
  palette.py REF.png [--k 12] [--json out.json]           dominant colours with their share of the image
  palette.py REF.png --at 120,64 --at 700,300             exact colour at points (median of a 5x5 patch)
  palette.py REF.png --compare BUILD.png                  each ref colour vs the closest build colour (delta-E)
  palette.py REF.png --crop 0,0,1440,90                   only a region (x0,y0,x1,y1), e.g. the top bar

Delta-E (CIE76) guide: < 2 same to the eye, 2-5 close, > 10 clearly a different colour.
Gradients and photos split into many near colours; sample those with --at instead.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imgutil import load_rgb, hex_of, srgb_to_lab  # noqa: E402


def palette(im, k=12, min_share=0.004):
    small = im.copy()
    small.thumbnail((480, 480), Image.BOX)
    q = small.quantize(colors=k * 2, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    out = []
    for c, idx in counts:
        rgb = pal[idx * 3: idx * 3 + 3]
        share = c / total
        if share < min_share:
            continue
        # merge colours closer than delta-E 3 into the bigger one
        lab = srgb_to_lab(np.array(rgb, dtype=float)[None, None] / 255)[0, 0]
        for o in out:
            if np.linalg.norm(o["_lab"] - lab) < 3:
                o["share"] += share
                break
        else:
            out.append({"hex": hex_of(rgb), "share": share, "_lab": lab})
    out = sorted(out, key=lambda o: -o["share"])[:k]
    for o in out:
        L = o["_lab"][0]
        o["lightness"] = round(float(L), 1)
        o["share"] = round(o["share"], 4)
    return out


def at(im, x, y, r=2):
    a = np.asarray(im)
    patch = a[max(0, y - r): y + r + 1, max(0, x - r): x + r + 1].reshape(-1, 3)
    return hex_of(np.median(patch, axis=0))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--k", type=int, default=12)
    ap.add_argument("--at", action="append", default=[], help="x,y in image px; repeatable")
    ap.add_argument("--crop", help="x0,y0,x1,y1")
    ap.add_argument("--compare", help="build screenshot to compare against")
    ap.add_argument("--json", help="write results as JSON")
    a = ap.parse_args()

    im = load_rgb(a.image)
    if a.crop:
        im = im.crop(tuple(int(v) for v in a.crop.split(",")))
    result = {"image": os.path.abspath(a.image), "size": list(im.size)}

    if a.at:
        result["points"] = []
        for s in a.at:
            x, y = (int(v) for v in s.split(","))
            h = at(im, x, y)
            result["points"].append({"x": x, "y": y, "hex": h})
            print(f"{x},{y}  {h}")
    else:
        pal = palette(im, a.k)
        result["palette"] = [{k: v for k, v in o.items() if k != "_lab"} for o in pal]
        print("hex       share   L*")
        for o in pal:
            print(f"{o['hex']}  {o['share'] * 100:5.1f}%  {o['lightness']:5.1f}")
        if a.compare:
            other = load_rgb(a.compare)
            if a.crop:
                other = other.crop(tuple(int(v) for v in a.crop.split(",")))
            opal = palette(other, a.k * 2, min_share=0.001)
            print("\nref colour -> closest build colour (delta-E)")
            result["compare"] = []
            for o in pal:
                best = min(opal, key=lambda b: np.linalg.norm(b["_lab"] - o["_lab"]))
                de = float(np.linalg.norm(best["_lab"] - o["_lab"]))
                flag = "ok" if de < 3 else ("close" if de < 8 else "OFF")
                print(f"{o['hex']} ({o['share'] * 100:4.1f}%) -> {best['hex']}  dE {de:5.1f}  {flag}")
                result["compare"].append({"ref": o["hex"], "build": best["hex"], "delta_e": round(de, 1), "flag": flag})
    if a.json:
        with open(a.json, "w") as f:
            json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
