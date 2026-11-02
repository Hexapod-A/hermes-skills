#!/usr/bin/env python3
"""Offline test of the tutorial pipeline (no API keys, no display, no editor).

    python3 tests/test_pipeline.py

Builds a 24 s synthetic 'screen recording', speaks a 4-beat lesson with the dummy voice
(one line deliberately longer than its stretch of screen), assembles it with a title card,
and runs qa_check on the result. Prints PASS lines and `all passed`.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, S)
from tvs_util import duration, ffmpeg, typing_delays, video_kbps  # noqa: E402

fails = 0


def check(ok, msg):
    global fails
    print(("PASS " if ok else "FAIL ") + msg)
    fails += 0 if ok else 1


def sh(*cmd):
    r = subprocess.run([sys.executable] + list(cmd), capture_output=True, text=True, timeout=600)
    if r.returncode not in (0,):
        print(r.stdout[-1500:], r.stderr[-1500:])
    return r


def main():
    # pure helpers
    code = "function Welcome() {\n  return <h2>Welcome to class!</h2>;\n}\n\nexport default Welcome;\n"
    d, tot = typing_delays(code, budget_s=6.0, seed=1)
    check(len(d) == len(code) and 4.0 < tot < 8.5, "typing plan fits a 6 s budget (%.1f s for %d chars)" % (tot, len(code)))
    check(all(x > 0 for x in d), "every keystroke has a delay")
    vk = video_kbps(240, 15)
    check((vk + 96) * 240 / 8 / 1024 < 15.5, "bitrate math keeps 4:00 under 16 MB (%d kbit/s video)" % vk)

    w = tempfile.mkdtemp(prefix="tvs_test_")
    raw = os.path.join(w, "raw.mkv")
    ffmpeg(["-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=25:d=24", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", raw], 300)
    lesson = {"slug": "t", "beats": [
        {"say": "Welcome to the test lesson. Short line."},
        {"say": "This line is deliberately long so that it runs past the next beat start and forces a hold "
                "on the last frame of its segment while the narration finishes speaking every word."},
        {"say": "Third beat, typing some code."},
        {"say": "Last beat. Your turn, see you next time."}]}
    lp = os.path.join(w, "lesson.json")
    json.dump(lesson, open(lp, "w"))
    r = sh(os.path.join(S, "narrate.py"), lp, "--provider", "dummy", "--out", w)
    narr = json.load(open(os.path.join(w, "narration.json")))["lines"]
    check(r.returncode == 0 and len(narr) == 4 and all(n["dur"] > 0.8 for n in narr), "dummy narration: 4 clips")

    starts = [0.5, 5.0, 10.0, 17.0]
    json.dump({"raw": raw, "total": 24.0, "beats": [{"i": i, "t": t, "dur": narr[i]["dur"], "clip": narr[i]["clip"]}
                                                     for i, t in enumerate(starts)]}, open(os.path.join(w, "timeline.json"), "w"))
    out = os.path.join(w, "final.mp4")
    r = sh(os.path.join(S, "assemble.py"), w, "--out", out, "--title", "Test Lesson", "--kicker", "Lesson 0")
    check(r.returncode == 0 and os.path.exists(out), "assemble.py built the video")
    a = json.load(open(os.path.join(w, "assembled.json")))
    hold = a["holds"][1]
    dd = duration(out)
    check(hold > 1.0, "long line got a %.1f s hold" % hold)
    check(abs(dd - (24 + 3 + sum(a["holds"]))) < 0.6, "length = recording + title + holds (%.1f s)" % dd)
    check(a["starts"][2] - a["starts"][1] >= narr[1]["dur"], "next line starts after the long line ends")

    r = sh(os.path.join(S, "qa_check.py"), out, "--min", "10", "--frames", "4", "--sheet", os.path.join(w, "sheet.jpg"))
    print(r.stdout)
    check(r.returncode == 0, "qa_check passes")
    check("PASS loudness" in r.stdout, "loudness on target")
    check(os.path.exists(os.path.join(w, "sheet.jpg")), "contact sheet written")

    subprocess.run(["rm", "-rf", w])
    print("all passed" if not fails else "%d FAILED" % fails)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
