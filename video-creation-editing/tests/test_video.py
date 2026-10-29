#!/usr/bin/env python3
"""End-to-end test for the video-creation-editing scripts on synthetic media (no network).
Needs ffmpeg + Pillow. Run:  python3 video-creation-editing/tests/test_video.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "scripts")
PY = sys.executable
ok = 0


def sh(args, expect=(0,)):
    p = subprocess.run(args, capture_output=True, text=True, timeout=900)
    if p.returncode not in expect:
        print(p.stdout[-2000:], p.stderr[-3000:])
        raise SystemExit(f"FAIL: {' '.join(args[:3])} exited {p.returncode}")
    return p.stdout


def check(name, cond, extra=""):
    global ok
    if not cond:
        raise SystemExit(f"FAIL: {name} {extra}")
    ok += 1
    print(f"PASS {name} {extra}")


def ffgen(*args):
    sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + list(args))


with tempfile.TemporaryDirectory() as td:
    j = lambda *p: os.path.join(td, *p)  # noqa: E731
    # synthetic sources: two landscape clips with tones, one photo, a voice-like tone, a music bed, captions
    ffgen("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=6", "-f", "lavfi", "-i", "sine=f=440:d=6",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", j("a.mp4"))
    ffgen("-f", "lavfi", "-i", "smptehdbars=s=1920x1080:r=25:d=5", "-f", "lavfi", "-i", "sine=f=660:d=5",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", j("b.mp4"))
    ffgen("-f", "lavfi", "-i", "mandelbrot=s=1600x1200", "-frames:v", "1", j("photo.jpg"))
    ffgen("-f", "lavfi", "-i", "sine=f=220:d=3", "-af", "volume=0.8", j("vo.wav"))
    ffgen("-f", "lavfi", "-i", "anoisesrc=d=20:c=pink:a=0.3", j("music.mp3"))
    with open(j("subs.srt"), "w") as fh:
        fh.write("1\n00:00:00,200 --> 00:00:01,800\nFirst caption\n\n2\n00:00:02,000 --> 00:00:03,500\nSecond caption\n")
    edl = {
        "size": "1080x1920", "fps": 30,
        "grade": {"eq": "contrast=1.05:saturation=1.1"},
        "clips": [
            {"color": "#101010", "dur": 1.0, "text": {"t": "Title card\nline two", "size": 90}},
            {"src": "a.mp4", "in": 0.5, "out": 1.5, "text": {"t": "Hook", "pos": "top"}},
            {"src": "b.mp4", "in": 0, "out": 2.0, "speed": 2.0, "fit": "blur"},
            {"src": "photo.jpg", "dur": 1.2, "kenburns": "in", "transition": {"type": "fade", "dur": 0.2}},
            {"src": "a.mp4", "in": 2, "ramp": [[0.6, 1.0], [1.2, 3.0], [0.4, 0.5]]},
            {"src": "b.mp4", "in": 3, "out": 4, "fit": "pad", "transition": {"type": "slideleft", "dur": 0.2}},
        ],
        "voiceover": {"src": "vo.wav", "at": 0.5},
        "music": {"src": "music.mp3", "volume": 0.4, "duck": True},
        "captions": "subs.srt",
        "loudness": -14,
        "out": "final.mp4",
    }
    json.dump(edl, open(j("edit.json"), "w"))
    out = sh([PY, os.path.join(S, "assemble.py"), j("edit.json")])
    res = json.loads(out.strip().splitlines()[-1])
    # expected: 1 + 1 + 1 + 1.2 + (0.6 + 0.4 + 0.8) + 1 - 0.2 - 0.2 = 6.6
    check("assemble builds the video", os.path.exists(j("final.mp4")), f"{res['duration']}s")
    check("assemble duration matches the edit list", abs(res["duration"] - 6.6) < 0.25, f"{res['duration']} vs 6.6")

    rep_out = sh([PY, os.path.join(S, "vcheck.py"), j("final.mp4"), "--target", "vertical", "--sheet", j("sheet.jpg"),
                  "--json", j("rep.json")], expect=(0, 2))
    rep = json.load(open(j("rep.json")))
    check("vcheck reads 1080x1920 h264 yuv420p", rep["video"]["width"] == 1080 and rep["video"]["height"] == 1920
          and rep["video"]["codec"] == "h264" and rep["video"]["pix_fmt"] == "yuv420p")
    check("final is fast-start", rep["faststart"] is True)
    L = rep["loudness"]["integrated_lufs"]
    check("loudness normalised near -14 LUFS", abs(L + 14) < 1.5, f"{L} LUFS")
    check("vcheck has no FAIL", not any(c["level"] == "FAIL" for c in rep["checks"]), rep_out.strip().splitlines()[-2])
    check("contact sheet written", os.path.getsize(j("sheet.jpg")) > 10000)

    sc = sh([PY, os.path.join(S, "scene_cuts.py"), j("final.mp4"), "--json", j("cuts.json"), "--sheet", j("cuts.jpg")])
    cuts = json.load(open(j("cuts.json")))
    n = cuts["summary"]["shots"]
    check("scene_cuts finds the shots", 5 <= n <= 9, f"{n} shots, {cuts['summary']['cuts_per_second']} cuts/s")
    check("scene_cuts writes an edit-list skeleton", len(cuts["edl_skeleton"]) == n)

    ffgen("-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=20", "-f", "lavfi", "-i", "anoisesrc=d=20:a=0.2",
          "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", j("big.mp4"))
    es = sh([PY, os.path.join(S, "export_size.py"), j("big.mp4"), "--mb", "2", "--aspect", "9:16", "--fit", "blur",
             "--out", j("small.mp4")])
    r = json.loads(es.strip().splitlines()[-1])
    check("export_size fits the limit", r["fits"] and r["size_mb"] < 2, f"{r['size_mb']} MB at {r['size']}")
    sh([PY, os.path.join(S, "vcheck.py"), j("small.mp4"), "--target", "whatsapp"])
    check("whatsapp export passes vcheck", True)

print(f"all passed ({ok} checks)")
