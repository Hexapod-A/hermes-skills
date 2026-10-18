#!/usr/bin/env python3
"""Compare a media replica with its original: container facts, a frame-by-frame timeline and audio
loudness per window. Writes a compare.json that report.py and triage.py read like any other run.

  python media_compare.py original.mp4 replica.mp4 --out compare.json [--fps 4] [--frame-tol 6]
                          [--audio-win 0.25] [--audio-tol 1.5] [--max-shift 2.0]

Checks (each is one "case" in the output, tagged by source):
  meta   duration (within one sample frame), width, height, frame rate, audio sample rate, channels
  frame  every 1/fps seconds: both frames scaled to 32x18 grey; pass when mean abs diff <= frame-tol (0-255)
  audio  every audio-win seconds: RMS level in dB; pass when |delta| <= audio-tol dB (silence floor -60 dB)
It also reports (not as cases): whole-file SSIM and PSNR from ffmpeg, and the best time shift of the
replica's timeline vs the original (a cut that starts late or early shows up here first).
Needs ffmpeg and ffprobe on PATH.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rea_lib import lower_bound, write_json  # noqa: E402

W, H = 32, 18


def ffprobe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
                       capture_output=True, text=True, check=True)
    d = json.loads(p.stdout)
    out = {"duration": float(d["format"].get("duration", 0))}
    for s in d["streams"]:
        if s["codec_type"] == "video" and "width" not in out:
            num, den = s.get("avg_frame_rate", "0/1").split("/")
            out.update(width=s["width"], height=s["height"], fps=round(float(num) / float(den or 1), 3), vcodec=s["codec_name"])
        if s["codec_type"] == "audio" and "sample_rate" not in out:
            out.update(sample_rate=int(s["sample_rate"]), channels=s["channels"], acodec=s["codec_name"])
    return out


def frames(path, fps):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},scale={W}:{H}:flags=area,format=gray",
                        "-f", "rawvideo", "-"], capture_output=True, check=True)
    n = W * H
    return [p.stdout[i:i + n] for i in range(0, len(p.stdout) - n + 1, n)]


def rms_windows(path, win):
    sr = 8000
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                       capture_output=True)
    if p.returncode != 0 or not p.stdout:
        return []
    import array
    a = array.array("h")
    a.frombytes(p.stdout[: len(p.stdout) // 2 * 2])
    step = int(sr * win)
    out = []
    for i in range(0, len(a) - step + 1, step):
        chunk = a[i:i + step]
        ms = sum(x * x for x in chunk) / len(chunk)
        db = 20 * math.log10(math.sqrt(ms) / 32768) if ms > 0 else -120.0
        out.append(max(db, -60.0))
    return out


def mad(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def best_shift(fo, fr, fps, max_shift):
    k = int(max_shift * fps)
    best = (float("inf"), 0)
    for s in range(-k, k + 1):
        pairs = [(fo[i], fr[i + s]) for i in range(len(fo)) if 0 <= i + s < len(fr)]
        if len(pairs) < max(3, len(fo) // 2):
            continue
        m = sum(mad(x, y) for x, y in pairs) / len(pairs)
        if m < best[0] - 1e-9:
            best = (m, s)
    sh = round(best[1] / fps, 3)
    meaning = ("no shift found" if sh == 0 else
               f"replica content runs {abs(sh)} s {'ahead of' if sh < 0 else 'behind'} the original "
               f"(its cut starts {'late' if sh < 0 else 'early'}); resolution {round(1 / fps, 3)} s, raise --fps for finer")
    return {"shift_s": sh, "mean_frame_diff_at_shift": round(best[0], 2), "meaning": meaning}


def ssim_psnr(a, b):
    out = {}
    for flt, key, rx in (("ssim", "ssim", r"All:([0-9.]+)"), ("psnr", "psnr_db", r"average:([0-9.inf]+)")):
        p = subprocess.run(["ffmpeg", "-v", "info", "-i", b, "-i", a, "-lavfi",
                            f"[0:v][1:v]scale2ref[r][o];[r][o]{flt}", "-f", "null", "-"], capture_output=True, text=True)
        m = re.findall(rx, p.stderr)
        out[key] = (float(m[-1]) if m[-1] != "inf" else float("inf")) if m else None
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("replica")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=4)
    ap.add_argument("--frame-tol", type=float, default=6)
    ap.add_argument("--audio-win", type=float, default=0.25)
    ap.add_argument("--audio-tol", type=float, default=1.5)
    ap.add_argument("--max-shift", type=float, default=2.0)
    a = ap.parse_args()
    mo, mr = ffprobe(a.original), ffprobe(a.replica)
    results = []

    def add(cid, source, ok, diffs, inp):
        results.append({"id": cid, "status": "pass" if ok else "fail", "diffs": [] if ok else diffs,
                        "tags": {"source": source}, "input": inp})

    for key in ("width", "height", "fps", "sample_rate", "channels"):
        if key in mo or key in mr:
            add(f"meta.{key}", "meta", mo.get(key) == mr.get(key),
                [{"path": key, "kind": "value", "original": mo.get(key), "replica": mr.get(key)}], {"check": key})
    dur_tol = 1.0 / (mo.get("fps") or 25)
    add("meta.duration", "meta", abs(mo["duration"] - mr["duration"]) <= dur_tol,
        [{"path": "duration", "kind": "value", "original": mo["duration"], "replica": mr["duration"], "note": f"tolerance {dur_tol:.3f}s"}],
        {"check": "duration", "tolerance_s": dur_tol})
    fo, fr = frames(a.original, a.fps), frames(a.replica, a.fps)
    for i in range(max(len(fo), len(fr))):
        t = round(i / a.fps, 3)
        if i >= len(fo) or i >= len(fr):
            add(f"frame@{t:07.3f}", "frame", False, [{"path": "frame", "kind": "missing_in_replica" if i >= len(fr) else "extra_in_replica",
                                                     "original": t if i < len(fo) else None, "replica": t if i < len(fr) else None}], {"t": t})
            continue
        d = mad(fo[i], fr[i])
        add(f"frame@{t:07.3f}", "frame", d <= a.frame_tol,
            [{"path": "frame_mad", "kind": "value", "original": 0, "replica": round(d, 2), "note": f"mean abs grey diff, tol {a.frame_tol}"}], {"t": t})
    ao, ar = rms_windows(a.original, a.audio_win), rms_windows(a.replica, a.audio_win)
    for i in range(max(len(ao), len(ar))):
        t = round(i * a.audio_win, 3)
        if i >= len(ao) or i >= len(ar):
            add(f"audio@{t:07.3f}", "audio", False, [{"path": "rms_db", "kind": "missing_in_replica" if i >= len(ar) else "extra_in_replica"}], {"t": t})
            continue
        add(f"audio@{t:07.3f}", "audio", abs(ao[i] - ar[i]) <= a.audio_tol,
            [{"path": "rms_db", "kind": "value", "original": round(ao[i], 2), "replica": round(ar[i], 2), "note": f"tol {a.audio_tol} dB"}], {"t": t})
    n = len(results)
    k = sum(1 for r in results if r["status"] == "pass")
    dims = {}
    for r in results:
        src = r["tags"]["source"]
        d = dims.setdefault(src, {"passed": 0, "total": 0})
        d["total"] += 1
        d["passed"] += r["status"] == "pass"
    for d in dims.values():
        d["pass_rate"] = d["passed"] / d["total"]
    info = {"original": mo, "replica": mr, "timeline": best_shift(fo, fr, a.fps, a.max_shift) if fo and fr else None}
    if info["timeline"] and info["timeline"]["shift_s"] != 0:
        for r in results:
            for d in r["diffs"]:
                if d["path"] in ("frame_mad", "rms_db"):
                    d["note"] = d.get("note", "") + f"; timeline: {info['timeline']['meaning']}"
    info.update(ssim_psnr(a.original, a.replica))
    summary = {"cases_total": n, "cases_compared": n, "passed": k, "failed": n - k, "harness_errors": 0,
               "pass_rate": k / n if n else 0, "confidence": 0.95, "lower_bound": lower_bound(k, n), "dimensions": dims}
    rules = {"why": f"frames at {a.fps} fps, 32x18 grey, tol {a.frame_tol}; audio RMS per {a.audio_win}s, tol {a.audio_tol} dB; duration tol {dur_tol:.3f}s"}
    write_json(a.out, {"summary": summary, "rules": rules, "results": results, "info": info})
    print(f"media compare: {k}/{n} checks pass | " + ", ".join(f"{s} {d['passed']}/{d['total']}" for s, d in dims.items()) +
          f" | ssim {info.get('ssim')} psnr {info.get('psnr_db')} | best shift {info['timeline']} -> {a.out}")
    return 0 if k == n else 2


if __name__ == "__main__":
    sys.exit(main())
