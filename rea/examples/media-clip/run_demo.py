#!/usr/bin/env python3
"""End-to-end REA demo on media (offline): an "original" clip and two rebuilt replicas, made with
ffmpeg test sources so nothing is downloaded.

  python run_demo.py

  original    4 s, 320x180 at 25 fps, test pattern + 440 Hz tone that beeps once a second
  clean       rebuilt with other encoder settings (CRF 30, other preset) - should pass
  bug         same as clean but the cut starts 0.2 s late (deliberate mismatch) - must be caught,
              and the timeline check must name the shift
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "..", "scripts")
PY = sys.executable


def make(out, start=0.0, crf=18, preset="medium"):
    v = f"testsrc2=size=320x180:rate=25:duration={4 + start}"
    au = f"sine=frequency=440:beep_factor=4:sample_rate=48000:duration={4 + start}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", v, "-f", "lavfi", "-i", au,
                    "-ss", str(start), "-t", "4", "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", out], check=True)


def sh(*args, ok=(0,)):
    p = subprocess.run([PY, *map(str, args)], capture_output=True, text=True)
    if p.returncode not in ok:
        raise SystemExit(f"failed ({p.returncode}): {args}\n{p.stdout}\n{p.stderr}")
    return p.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(HERE, "results"))
    a = ap.parse_args()
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        print("SKIP: ffmpeg/ffprobe not found")
        return None
    work = tempfile.mkdtemp(prefix="rea-media-")
    try:
        files = {"original": os.path.join(work, "original.mp4"), "clean": os.path.join(work, "clean.mp4"),
                 "bug": os.path.join(work, "bug.mp4")}
        make(files["original"])
        make(files["clean"], crf=30, preset="veryfast")
        make(files["bug"], start=0.2, crf=30, preset="veryfast")
        out = {}
        for label in ("clean", "bug"):
            d = os.path.join(a.results, label)
            os.makedirs(d, exist_ok=True)
            cmp_ = os.path.join(d, "compare.json")
            print(sh(os.path.join(S, "media_compare.py"), files["original"], files[label], "--out", cmp_, ok=(0, 2)))
            print(sh(os.path.join(S, "triage.py"), cmp_, "--out", os.path.join(d, "triage.md"), "--json", os.path.join(d, "triage.json")))
            print(sh(os.path.join(S, "report.py"), "--compare", cmp_, "--triage", os.path.join(d, "triage.json"),
                     "--title", f"Media replica ({label})",
                     "--metric", "check pass rate: container facts, frames every 0.25 s (32x18 grey, mean diff <= 6), audio RMS every 0.25 s (<= 1.5 dB)",
                     "--untested", "colour accuracy (frames are compared in grey)", "--untested", "fine detail below 32x18 (see ssim/psnr info)",
                     "--untested", "audio pitch and timbre (only loudness per window is compared)", "--untested", "subtitles, chapters, metadata tags",
                     "--out", os.path.join(d, "report.md"), "--json", os.path.join(d, "report.json"), ok=(0, 3)))
            r = json.load(open(os.path.join(d, "report.json")))
            info = json.load(open(cmp_))["info"]
            out[label] = {x: r[x] for x in ("passed", "compared", "pass_rate", "lower_bound", "verdict")}
            out[label].update(ssim=info.get("ssim"), psnr_db=info.get("psnr_db"), timeline=info.get("timeline"))
        out["bug_caught"] = out["bug"]["passed"] < out["bug"]["compared"]
        with open(os.path.join(a.results, "summary.json"), "w") as f:
            json.dump(out, f, indent=2)
        print(json.dumps(out, indent=2))
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
