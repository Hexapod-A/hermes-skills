#!/usr/bin/env python3
"""Read the editing of a reference video: where the cuts are, how long each shot lasts, the pacing.

Usage:
  python3 scene_cuts.py REF.mp4 [--threshold 0.3] [--min-shot 0.15] [--sheet cuts.jpg] [--json cuts.json]
                        [--start 0] [--end 30]

Prints one line per shot (start, end, length) and a summary: number of cuts, cuts per second,
average/median shot length, the fastest 5 s window, and an edit-list skeleton you can fill in to
copy the rhythm (see assemble.py). --sheet saves one frame from the middle of every shot, labelled
with its time, so you can see the shot types (close-up, wide, text card, product).

How it works: ffmpeg's scene score (select='gt(scene,T)') marks frames that differ a lot from the
previous one. 0.3 suits most edits; use 0.2 for soft footage or fades, 0.4+ for shaky handheld or
flashing graphics that make false cuts. Cross-fades are often missed: check the sheet.
"""
import argparse
import json
import os
import re
import statistics
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vutil import contact_sheet, duration, ff, fmt_t, need  # noqa: E402


def detect(path, threshold=0.3, start=0.0, end=None):
    args = []
    if start:
        args += ["-ss", str(start)]
    if end:
        args += ["-to", str(end)]
    args += ["-i", path, "-an", "-vf", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"]
    err = ff(args)
    times = [float(m.group(1)) + (start or 0.0) for m in re.finditer(r"pts_time:([0-9.]+)", err)]
    return sorted(set(round(t, 3) for t in times))


def shots_from(cuts, total, start=0.0, min_shot=0.15):
    edges = [start] + [c for c in cuts if c > start] + [total]
    shots = []
    for a, b in zip(edges, edges[1:]):
        if b - a < min_shot and shots:  # merge flicker into the previous shot
            shots[-1] = (shots[-1][0], b)
            continue
        shots.append((a, b))
    return shots


def summary(shots):
    lens = [b - a for a, b in shots]
    total = shots[-1][1] - shots[0][0] if shots else 0
    fastest = None
    if total > 5:
        best = None
        t = shots[0][0]
        while t + 5 <= shots[-1][1] + 1e-6:
            n = sum(1 for a, _ in shots[1:] if t <= a < t + 5)
            if best is None or n > best[0]:
                best = (n, t)
            t += 0.5
        fastest = {"start": round(best[1], 2), "cuts": best[0]}
    return {
        "shots": len(shots),
        "cuts": max(0, len(shots) - 1),
        "duration": round(total, 2),
        "cuts_per_second": round((len(shots) - 1) / total, 2) if total else 0,
        "avg_shot": round(statistics.mean(lens), 2) if lens else 0,
        "median_shot": round(statistics.median(lens), 2) if lens else 0,
        "shortest": round(min(lens), 2) if lens else 0,
        "longest": round(max(lens), 2) if lens else 0,
        "fastest_5s_window": fastest,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--threshold", type=float, default=0.3)
    ap.add_argument("--min-shot", type=float, default=0.15, help="merge shots shorter than this (flashes)")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--sheet", help="save a contact sheet JPEG: one frame per shot")
    ap.add_argument("--json", help="save the result as JSON")
    a = ap.parse_args()
    need("ffmpeg")
    total = a.end or duration(a.video)
    cuts = detect(a.video, a.threshold, a.start, a.end)
    shots = shots_from(cuts, total, a.start, a.min_shot)
    s = summary(shots)
    for i, (x, y) in enumerate(shots, 1):
        print(f"shot {i:3d}  {fmt_t(x)} -> {fmt_t(y)}  {y - x:5.2f}s")
    print(json.dumps(s))
    skeleton = [{"src": "TODO.mp4", "in": 0, "out": round(y - x, 2), "note": f"ref shot {i} ({y - x:.2f}s)"}
                for i, (x, y) in enumerate(shots, 1)]
    result = {"video": a.video, "threshold": a.threshold, "summary": s,
              "shots": [{"start": round(x, 3), "end": round(y, 3), "length": round(y - x, 3)} for x, y in shots],
              "edl_skeleton": skeleton}
    if a.sheet and shots:
        with tempfile.TemporaryDirectory() as td:
            frames, labels = [], []
            for i, (x, y) in enumerate(shots[:60]):
                f = os.path.join(td, f"s{i:03d}.jpg")
                ff(["-ss", f"{(x + y) / 2:.3f}", "-i", a.video, "-frames:v", "1", "-vf", "scale=480:-2", f])
                if os.path.exists(f):
                    frames.append(f)
                    labels.append(f"{i + 1}  {fmt_t(x)}  {y - x:.2f}s")
            contact_sheet(frames, a.sheet, cols=6, width=2400, labels=labels)
        result["sheet"] = a.sheet
        print(f"sheet: {a.sheet}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(result, fh, indent=2)
        print(f"json: {a.json}")


if __name__ == "__main__":
    main()
