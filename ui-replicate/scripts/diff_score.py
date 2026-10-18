#!/usr/bin/env python3
"""Score how close a build screenshot is to a reference image.

Prints and writes (JSON) four numbers plus the worst regions:
  ssim     perceptual structure match on greyscale at --work-width (detail, text, edges)
  layout   SSIM on a blurred 1/8-size copy (block positions, sizes, big shapes; ignores text)
  colour   100 - mean CIE76 delta-E on a 1/16-size copy, clipped to 0..100 (palette and fills)
  pixels   share of pixels that differ by more than --pixel-tol (like pixelmatch)
Exit code 0 when all three pass the preset (or --min-*) thresholds, else 2.
Presets: restyle (same design, your own content; default) and clone (same design and content).

Usage:
  diff_score.py REF.png BUILD.png [--out report.json] [--heatmap heat.png] [--grid 6x4]
                [--fit crop|resize] [--preset restyle|clone] [--min-ssim N] [--min-layout N] [--min-colour N]
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imgutil import load_rgb, to_float, gray, ssim_map, srgb_to_lab  # noqa: E402


def align(ref, build, fit):
    """Bring build to the ref's width; then crop both to the common height (or resize)."""
    notes = []
    if build.size == ref.size:
        return ref, build, notes
    if fit == "resize":
        notes.append(f"build {build.size} resized to ref {ref.size} (aspect changes distort the score)")
        return ref, build.resize(ref.size, Image.LANCZOS), notes
    if build.width != ref.width:
        h = round(build.height * ref.width / build.width)
        notes.append(f"build scaled {build.size} -> {(ref.width, h)} to match ref width")
        build = build.resize((ref.width, h), Image.LANCZOS)
    if build.height != ref.height:
        hh = min(build.height, ref.height)
        notes.append(f"heights differ (ref {ref.height}, build {build.height}); compared the top {hh}px only")
        ref, build = ref.crop((0, 0, ref.width, hh)), build.crop((0, 0, build.width, hh))
    return ref, build, notes


def resize_w(im, w):
    if im.width <= w:
        return im
    return im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)


def score(ref_path, build_path, work_width=1440, fit="crop", grid=(6, 4), pixel_tol=25):
    ref0, build0 = load_rgb(ref_path), load_rgb(build_path)
    ref, build, notes = align(ref0, build0, fit)

    # 1. detail SSIM on greyscale
    r, b = resize_w(ref, work_width), resize_w(build, work_width)
    smap = ssim_map(gray(to_float(r)), gray(to_float(b)))
    ssim = float(smap.mean())

    # 2. layout SSIM: 1/8 size + blur -> only blocks and big shapes survive
    small = (max(8, ref.width // 8), max(8, ref.height // 8))
    rl = ref.resize(small, Image.BOX).filter(ImageFilter.GaussianBlur(2))
    bl = build.resize(small, Image.BOX).filter(ImageFilter.GaussianBlur(2))
    layout = float(ssim_map(gray(to_float(rl)), gray(to_float(bl))).mean())

    # global offset check: does the build line up better when shifted? (1/4 size, up to +-40 px,
    # mean absolute difference; reported only when the shift cuts the difference by 15% or more)
    q4 = (max(8, ref.width // 4), max(8, ref.height // 4))
    gr = gray(to_float(ref.resize(q4, Image.BOX)))
    gb = gray(to_float(build.resize(q4, Image.BOX)))
    m = 10
    core = (slice(m, gr.shape[0] - m), slice(m, gr.shape[1] - m))
    base_mad = float(np.abs(gr[core] - gb[core]).mean())
    best = (base_mad, 0, 0)
    if gr.shape[0] > 3 * m and gr.shape[1] > 3 * m:
        for dy in range(-m, m + 1):
            for dx in range(-m, m + 1):
                shifted = gb[m + dy: gb.shape[0] - m + dy, m + dx: gb.shape[1] - m + dx]
                v = float(np.abs(gr[core] - shifted).mean())
                if v < best[0]:
                    best = (v, dx, dy)
    offset = None
    if (best[1] or best[2]) and best[0] < base_mad * 0.85:
        offset = {"dx": best[1] * 4, "dy": best[2] * 4,
                  "mean_abs_diff": round(base_mad, 4), "mean_abs_diff_if_aligned": round(best[0], 4)}
        notes.append(f"build content sits about dx={offset['dx']:+d}px dy={offset['dy']:+d}px from the reference "
                     "(+ = right/down): fix outer margins / frame first, or re-crop the reference")

    # block-level map for the heatmap: 1/4 size, light blur (text detail fades, card edges stay)
    q = (max(8, ref.width // 4), max(8, ref.height // 4))
    rq = ref.resize(q, Image.BOX).filter(ImageFilter.GaussianBlur(1.5))
    bq = build.resize(q, Image.BOX).filter(ImageFilter.GaussianBlur(1.5))
    block_map = ssim_map(gray(to_float(rq)), gray(to_float(bq)))

    # 3. colour: mean delta-E at 1/16 size
    tiny = (max(4, ref.width // 16), max(4, ref.height // 16))
    lab_r = srgb_to_lab(to_float(ref.resize(tiny, Image.BOX)))
    lab_b = srgb_to_lab(to_float(build.resize(tiny, Image.BOX)))
    de = np.sqrt(((lab_r - lab_b) ** 2).sum(-1))
    colour = float(np.clip(100 - de.mean(), 0, 100))

    # 4. pixel mismatch share at full size
    ra, ba = np.asarray(ref, dtype=np.int16), np.asarray(build, dtype=np.int16)
    diff_px = np.abs(ra - ba).max(-1) > pixel_tol
    pixels = float(diff_px.mean())

    # 5. worst regions on a grid (in ref pixel coordinates)
    gx, gy = grid
    H, Wd = smap.shape
    sx, sy = ref.width / Wd, ref.height / H
    tiles = []
    for j in range(gy):
        for i in range(gx):
            x0, x1 = i * Wd // gx, (i + 1) * Wd // gx
            y0, y1 = j * H // gy, (j + 1) * H // gy
            t_ssim = float(smap[y0:y1, x0:x1].mean())
            tx0, tx1 = i * de.shape[1] // gx, (i + 1) * de.shape[1] // gx
            ty0, ty1 = j * de.shape[0] // gy, (j + 1) * de.shape[0] // gy
            t_de = float(de[ty0:ty1, tx0:tx1].mean()) if tx1 > tx0 and ty1 > ty0 else 0.0
            tiles.append({
                "tile": f"r{j + 1}c{i + 1}",
                "box": [round(x0 * sx), round(y0 * sy), round(x1 * sx), round(y1 * sy)],
                "ssim": round(t_ssim, 3),
                "delta_e": round(t_de, 1),
            })
    worst = sorted(tiles, key=lambda t: t["ssim"] - t["delta_e"] / 100)[:5]

    return {
        "ref": os.path.abspath(ref_path),
        "build": os.path.abspath(build_path),
        "ref_size": list(ref0.size),
        "build_size": list(build0.size),
        "compared_size": list(ref.size),
        "notes": notes,
        "ssim": round(ssim, 4),
        "layout": round(layout, 4),
        "colour": round(colour, 2),
        "pixels_differ": round(pixels, 4),
        "offset": offset,
        "worst_tiles": worst,
        "tiles": tiles,
    }, block_map, (ref, build)


def heatmap(smap, ref, out):
    """Ref in light grey, red where the block-level (1/4 size) SSIM is low."""
    h = np.clip((1 - smap - 0.15) / 0.6, 0, 1)  # ignore small differences
    h = Image.fromarray((h * 255).astype(np.uint8)).resize(ref.size, Image.BILINEAR)
    base = Image.blend(ref.convert("L").convert("RGB"), Image.new("RGB", ref.size, "white"), 0.45)
    red = Image.new("RGB", ref.size, (220, 20, 20))
    mask = h.point(lambda v: min(200, int(v * 1.2)))
    Image.composite(red, base, mask).save(out)
    return out


def draw_tiles(img_path, worst):
    im = Image.open(img_path).convert("RGB")
    d = ImageDraw.Draw(im)
    for n, t in enumerate(worst, 1):
        d.rectangle(t["box"], outline=(255, 160, 0), width=4)
        d.text((t["box"][0] + 8, t["box"][1] + 6), f"#{n} {t['tile']}", fill=(255, 160, 0))
    im.save(img_path)


# Calibrated on the pow-platform dashboard (Oct 2026): the accepted restyle scored ssim 0.75 / layout 0.85 /
# colour 94.9; an unrelated dashboard design against the same ref scored 0.63 / 0.51 / 83.3.
PRESETS = {
    "restyle": {"ssim": 0.72, "layout": 0.84, "colour": 92.0},
    "clone": {"ssim": 0.90, "layout": 0.95, "colour": 97.0},
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref")
    ap.add_argument("build")
    ap.add_argument("--out", help="write the JSON report here")
    ap.add_argument("--heatmap", help="write a heatmap PNG (ref in grey, red = mismatch, orange boxes = worst tiles)")
    ap.add_argument("--fit", choices=["crop", "resize"], default="crop")
    ap.add_argument("--grid", default="6x4", help="tiles across x down, for the worst-region list")
    ap.add_argument("--work-width", type=int, default=1440)
    ap.add_argument("--pixel-tol", type=int, default=25, help="0-255 per channel")
    ap.add_argument("--preset", choices=["restyle", "clone"], default="restyle",
                    help="restyle = same design, your own content (default); clone = same design and same content")
    ap.add_argument("--min-ssim", type=float, help="override the preset")
    ap.add_argument("--min-layout", type=float, help="override the preset")
    ap.add_argument("--min-colour", type=float, help="override the preset")
    a = ap.parse_args()
    preset = PRESETS[a.preset]
    a.min_ssim = preset["ssim"] if a.min_ssim is None else a.min_ssim
    a.min_layout = preset["layout"] if a.min_layout is None else a.min_layout
    a.min_colour = preset["colour"] if a.min_colour is None else a.min_colour
    gx, gy = (int(v) for v in a.grid.lower().split("x"))
    rep, smap, (ref, _b) = score(a.ref, a.build, a.work_width, a.fit, (gx, gy), a.pixel_tol)
    rep["thresholds"] = {"preset": a.preset, "min_ssim": a.min_ssim, "min_layout": a.min_layout, "min_colour": a.min_colour}
    rep["pass"] = rep["ssim"] >= a.min_ssim and rep["layout"] >= a.min_layout and rep["colour"] >= a.min_colour
    if a.heatmap:
        heatmap(smap, ref, a.heatmap)
        draw_tiles(a.heatmap, rep["worst_tiles"])
        rep["heatmap"] = os.path.abspath(a.heatmap)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(rep, f, indent=2)
    for n in rep["notes"]:
        print("note:", n)
    print(f"ssim {rep['ssim']:.4f} | layout {rep['layout']:.4f} | colour {rep['colour']:.1f}/100 | "
          f"pixels differ {rep['pixels_differ'] * 100:.1f}%")
    print("worst tiles (x0,y0,x1,y1 in ref px):")
    for t in rep["worst_tiles"]:
        print(f"  {t['tile']:6} {t['box']}  ssim {t['ssim']:.3f}  dE {t['delta_e']}")
    print("PASS" if rep["pass"] else
          f"FAIL ({a.preset}: need ssim >= {a.min_ssim}, layout >= {a.min_layout}, colour >= {a.min_colour})")
    sys.exit(0 if rep["pass"] else 2)


if __name__ == "__main__":
    main()
