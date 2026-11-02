#!/usr/bin/env python3
"""Check a finished lesson before it is sent. Exit 0 = PASS (maybe with WARNs), 2 = FAIL.

    python3 qa_check.py out/04_components.mp4 --frames 6 --sheet out/04_sheet.jpg
    python3 qa_check.py out/04_components.mp4 --at 12,48,95 --project ~/projects/my-first-app

Checks: H.264 + yuv420p + AAC, 1920x1080 or 1280x720, fast start, size under --max-mb (16),
length inside --min/--max seconds (90-240), loudness near -16 LUFS with peaks under -1 dBTP,
silent stretches longer than --silence seconds (typing with nobody talking), black frames.
--frames/--at pull JPG frames + a contact sheet: LOOK at them (code readable, captions not
covering the code, no toasts/badges, preview showing the right thing).
--project runs `npm run build` in the lesson's project: the code shown must actually build.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tvs_util import ffmpeg, probe, run  # noqa: E402

res = {"fail": 0, "warn": 0}


def say(level, msg):
    if level == "FAIL":
        res["fail"] += 1
    elif level == "WARN":
        res["warn"] += 1
    print("%-4s %s" % (level, msg))


def mmss(t):
    return "%d:%04.1f" % (t // 60, t % 60)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--max-mb", type=float, default=16.0)
    ap.add_argument("--min", type=float, default=90.0)
    ap.add_argument("--max", type=float, default=240.0)
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--silence", type=float, default=3.0)
    ap.add_argument("--frames", type=int, default=0, help="N frames spread over the video")
    ap.add_argument("--at", help="comma list of seconds to grab")
    ap.add_argument("--sheet", help="contact sheet path (jpg)")
    ap.add_argument("--project", help="npm project to build")
    ap.add_argument("--json", help="write the results here")
    a = ap.parse_args()

    info = probe(a.video)
    fmt = info["format"]
    dur = float(fmt["duration"])
    mb = int(fmt["size"]) / 1024 / 1024
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    au = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)

    say("PASS" if mb < a.max_mb else "FAIL", "size %.2f MB (limit %.0f MB)" % (mb, a.max_mb))
    if a.min <= dur <= a.max:
        say("PASS", "length %s" % mmss(dur))
    else:
        say("WARN", "length %s is outside %s-%s" % (mmss(dur), mmss(a.min), mmss(a.max)))
    if not v:
        say("FAIL", "no video stream")
    else:
        ok = v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p"
        say("PASS" if ok else "FAIL", "video %s %s %sx%s" % (v["codec_name"], v.get("pix_fmt"), v["width"], v["height"]))
        if (v["width"], v["height"]) not in ((1920, 1080), (1280, 720)):
            say("WARN", "not 1080p/720p")
    if not au:
        say("FAIL", "no audio stream")
    else:
        say("PASS" if au["codec_name"] == "aac" else "WARN", "audio %s %s Hz" % (au["codec_name"], au.get("sample_rate")))

    with open(a.video, "rb") as f:
        head = f.read(256 * 1024)
    mo, md = head.find(b"moov"), head.find(b"mdat")
    say("PASS" if mo != -1 and (md == -1 or mo < md) else "WARN", "fast start (moov before mdat)")

    r = run(["ffmpeg", "-nostdin", "-hide_banner", "-i", a.video, "-map", "0:a:0?", "-af", "ebur128=peak=true",
             "-f", "null", "-"], 600, check=False, quiet=True)
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
    if I:
        li = float(I[-1])
        say("PASS" if abs(li - a.lufs) <= 1.5 else "WARN", "loudness %.1f LUFS (target %.0f)" % (li, a.lufs))
    if TP:
        tp = float(TP[-1])
        say("PASS" if tp <= -1.0 else "WARN", "true peak %.1f dBTP" % tp)

    r = run(["ffmpeg", "-nostdin", "-hide_banner", "-i", a.video, "-map", "0:a:0?", "-af",
             "silencedetect=noise=-38dB:d=%g" % a.silence, "-f", "null", "-"], 600, check=False, quiet=True)
    ss = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    se = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", r.stderr)]
    gaps = []
    for i, s in enumerate(ss):
        e = se[i] if i < len(se) else dur
        if s > 4.0 and e < dur - 1.0:  # the title card and the outro may be quiet
            gaps.append((s, e))
    if gaps:
        say("WARN", "silent stretches: " + ", ".join("%s-%s" % (mmss(s), mmss(e)) for s, e in gaps[:8])
            + "  (screen busy with no voice? add a line, speed the typing, or cut)")
    else:
        say("PASS", "no silent stretch over %.0f s" % a.silence)

    r = run(["ffmpeg", "-nostdin", "-hide_banner", "-i", a.video, "-vf", "blackdetect=d=0.5:pix_th=0.08", "-an",
             "-f", "null", "-"], 900, check=False, quiet=True)
    bl = re.findall(r"black_start:([\d.]+)", r.stderr)
    say("WARN" if bl else "PASS", "black frames at %s" % ", ".join(mmss(float(b)) for b in bl[:5]) if bl else "no black frames")

    shots = []
    ts = []
    if a.at:
        ts = [float(x) for x in a.at.split(",") if x.strip()]
    elif a.frames:
        ts = [dur * (i + 0.5) / a.frames for i in range(a.frames)]
    if ts:
        base = os.path.splitext(a.video)[0]
        for t in ts:
            p = "%s_f%05.1f.jpg" % (base, t)
            ffmpeg(["-ss", "%.2f" % t, "-i", a.video, "-frames:v", "1", "-q:v", "3", p], 60)
            shots.append(p)
        print("FRAMES " + " ".join(shots))
        if a.sheet and shots:
            ins = []
            for p in shots:
                ins += ["-i", p]
            n = len(shots)
            cols = 3 if n > 4 else n
            flt = "".join("[%d:v]scale=640:-2[s%d];" % (i, i) for i in range(n))
            pads = "".join("[s%d]" % i for i in range(n))
            ffmpeg(ins + ["-filter_complex", flt + pads + "xstack=inputs=%d:layout=%s[o]" % (n, layout(n, cols)),
                          "-map", "[o]", "-frames:v", "1", "-q:v", "3", a.sheet], 60)
            print("SHEET " + a.sheet)

    if a.project:
        pj = os.path.expanduser(a.project)
        r = run(["bash", "-lc", "cd %s && npm run build --silent" % json.dumps(pj)], 300, check=False, quiet=True)
        if r.returncode == 0:
            say("PASS", "project builds (npm run build)")
        else:
            say("FAIL", "project does not build:\n" + (r.stdout + r.stderr)[-800:])

    if a.json:
        json.dump({"fail": res["fail"], "warn": res["warn"], "duration": dur, "mb": mb, "frames": shots}, open(a.json, "w"), indent=1)
    print("RESULT %s (%d fail, %d warn)" % ("FAIL" if res["fail"] else "PASS", res["fail"], res["warn"]))
    sys.exit(2 if res["fail"] else 0)


def layout(n, cols):
    out = []
    for i in range(n):
        r, c = divmod(i, cols)
        x = "+".join(["w0"] * c) if c else "0"
        y = "+".join(["h0"] * r) if r else "0"
        out.append("%s_%s" % (x, y))
    return "|".join(out)


if __name__ == "__main__":
    main()
