#!/usr/bin/env python3
"""Offline tests for the ui-replicate image scripts (no network, no browser). Run:
    python3 ui-replicate/tests/test_scripts.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, S)
from diff_score import score  # noqa: E402


def mock(path, shift=(0, 0), card="#f4d6ff", bg="#f8f8f7"):
    im = Image.new("RGB", (720, 480), bg)
    d = ImageDraw.Draw(im)
    dx, dy = shift
    d.rectangle([0 + dx, 0 + dy, 720 + dx, 56 + dy], fill="#000000")
    d.rounded_rectangle([40 + dx, 96 + dy, 340 + dx, 300 + dy], 24, fill=card)
    d.rounded_rectangle([380 + dx, 96 + dy, 680 + dx, 300 + dy], 24, fill="#dbfadd")
    for i in range(6):
        d.rectangle([60 + dx, 120 + dy + i * 26, 260 + dx, 132 + dy + i * 26], fill="#222222")
    d.rounded_rectangle([40 + dx, 330 + dy, 680 + dx, 440 + dy], 24, fill="#ffffff", outline="#e3e6e4")
    im.save(path)
    return path


def run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


def main():
    t = tempfile.mkdtemp(prefix="uir-test-")
    ref = mock(os.path.join(t, "ref.png"))
    same = mock(os.path.join(t, "same.png"))
    shifted = mock(os.path.join(t, "shifted.png"), shift=(0, 24))
    recolour = mock(os.path.join(t, "recolour.png"), card="#2050ff")
    fails = 0

    def check(name, ok, detail=""):
        nonlocal fails
        print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))
        fails += 0 if ok else 1

    r, _, _ = score(ref, same)
    check("identical images score 1.0", r["ssim"] > 0.999 and r["layout"] > 0.999 and r["colour"] > 99.9)
    r, _, _ = score(ref, shifted)
    # whole page 24px lower, e.g. a reference cropped 24px too high
    check("shifted layout drops the layout score", r["layout"] < 0.97, f"layout {r['layout']}")
    check("offset finder sees the build 24px lower", bool(r["offset"]) and r["offset"]["dy"] == 24, json.dumps(r["offset"]))
    r, _, _ = score(ref, recolour)
    check("wrong card colour drops the colour score", r["colour"] < 97, f"colour {r['colour']}")
    worst = r["worst_tiles"][0]["box"]
    check("worst tile sits on the recoloured card", worst[0] < 360 and worst[1] < 300, str(worst))

    p = run(os.path.join(S, "diff_score.py"), ref, shifted, "--preset", "clone", "--heatmap", os.path.join(t, "h.png"))
    check("diff_score.py exits 2 on a failing clone check", p.returncode == 2, p.stdout.splitlines()[-1])
    p = run(os.path.join(S, "palette.py"), ref, "--at", "10,10", "--at", "300,200")
    check("palette.py --at reads exact colours", "#000000" in p.stdout and "#f4d6ff" in p.stdout, p.stdout.strip().replace("\n", " | "))
    p = run(os.path.join(S, "palette.py"), ref, "--compare", recolour, "--k", "6")
    check("palette.py --compare flags the changed colour", "OFF" in p.stdout)
    p = run(os.path.join(S, "side_by_side.py"), ref, same, "--out", os.path.join(t, "sbs.jpg"), "--heatmap", os.path.join(t, "h.png"))
    check("side_by_side.py writes a 3-panel sheet", p.returncode == 0 and Image.open(os.path.join(t, "sbs.jpg")).width > 2000)
    p = run(os.path.join(S, "grid_overlay.py"), ref, "--out", os.path.join(t, "g.png"), "--crop", "0,0,360,240", "--zoom", "2")
    check("grid_overlay.py writes a zoomed crop", p.returncode == 0 and Image.open(os.path.join(t, "g.png")).size == (720, 480))
    framed = Image.new("RGB", (900, 700), "#c9c9ff")
    framed.paste(Image.open(ref), (90, 110))
    framed.save(os.path.join(t, "framed.png"))
    p = run(os.path.join(S, "prep_ref.py"), os.path.join(t, "framed.png"), "--trim", "--width", "1440", "--out", os.path.join(t, "prepped.png"))
    check("prep_ref.py --trim removes the backdrop", "trim (90, 110, 810, 590)" in p.stdout, p.stdout.splitlines()[1])

    shutil.rmtree(t, ignore_errors=True)
    print("all passed" if not fails else f"{fails} failed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
