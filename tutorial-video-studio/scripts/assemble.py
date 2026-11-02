#!/usr/bin/env python3
"""Turn a silent screen recording + per-line narration into the finished lesson video.

    python3 assemble.py ~/tutorial-work/04_components --out out/04_components.mp4 \
        --title "Components" --kicker "Lesson 4"

Reads <work>/timeline.json (when each beat started on screen) and <work>/narration.json
(one clip per beat) and:
  1. cuts the recording at every beat start; where a line runs longer than its stretch of
     screen, HOLDS the last frame (tpad clone) so the picture waits for the voice;
  2. optionally puts a title card in front (dark card, kicker + title, ~3 s);
  3. places every clip at its beat start with adelay, mixes them with amix, pads to length,
     normalises loudness (-16 LUFS integrated, -1.5 dBTP);
  4. encodes H.264 1080p (or --height 720) + AAC mono, fast start, at a bitrate worked out
     from the length so the file stays under --target-mb (WhatsApp takes 16 MB).
Re-voicing an old video = run narrate.py with the new voice into the same work folder, then
run this again on the SAME raw.mkv and timeline.json: holds absorb the new line lengths.
"""
import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tvs_util import duration, ffmpeg, load_json, save_json, video_kbps  # noqa: E402

FPS = 25


def font_file(bold=True):
    env = os.environ.get("FONT_FILE")
    if env and os.path.exists(env):
        return env
    try:
        r = subprocess.run(["fc-match", "-f", "%{file}", "DejaVu Sans:bold" if bold else "DejaVu Sans"],
                           capture_output=True, text=True, timeout=10)
        if r.stdout and os.path.exists(r.stdout):
            return r.stdout
    except Exception:
        pass
    return "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def esc(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019").replace("%", "\\%")


def loudnorm_2pass(src, dst, target=-16.0, tp=-1.5, lra=11):
    """Measure, then normalise with the measured values (linear gain when possible).

    One-pass loudnorm on speech with long pauses lands several LU off target; two passes land
    within ~0.5 LU. Integrated loudness is gated, so the silence between lines does not count.
    """
    import json as _j
    import re as _re
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", src, "-af",
                        "loudnorm=I=%g:TP=%g:LRA=%g:print_format=json" % (target, tp, lra), "-f", "null", "-"],
                       capture_output=True, text=True, timeout=600)
    m = _re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    if not m:
        ffmpeg(["-i", src, "-af", "loudnorm=I=%g:TP=%g:LRA=%g,aresample=44100" % (target, tp, lra), "-ac", "1", dst], 600)
        return
    v = _j.loads(m.group(0))
    af = ("loudnorm=I=%g:TP=%g:LRA=%g:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true,"
          "aresample=44100" % (target, tp, lra, v["input_i"], v["input_tp"], v["input_lra"], v["input_thresh"], v["target_offset"]))
    ffmpeg(["-i", src, "-af", af, "-ac", "1", "-c:a", "pcm_s16le", dst], 600)


def plan(beats, total, lines, margin, lead_margin_last=0.8):
    """Per segment hold lengths and the new start time of every line."""
    starts = [b["t"] for b in beats]
    bounds = [0.0] + starts[1:] + [total]
    exts, new_starts, shift = [], [], 0.0
    for i, b in enumerate(beats):
        d = lines[i]["dur"] if i < len(lines) else 0.0
        slot = bounds[i + 1] - starts[i]
        need = d + (margin if i < len(beats) - 1 else lead_margin_last)
        ext = max(0.0, need - slot) if d else 0.0
        new_starts.append(starts[i] + shift)
        exts.append(round(ext, 3))
        shift += ext
    return bounds, exts, new_starts, total + shift


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("work", help="folder holding raw.mkv, timeline.json, narration.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw", help="recording to use (default: timeline's raw, e.g. an older final to re-voice)")
    ap.add_argument("--title")
    ap.add_argument("--kicker", default="")
    ap.add_argument("--title-secs", type=float, default=3.0)
    ap.add_argument("--margin", type=float, default=0.35, help="min gap after a line before the next beat")
    ap.add_argument("--target-mb", type=float, default=15.0)
    ap.add_argument("--height", type=int, default=1080, choices=[720, 1080])
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--keep-temp", action="store_true")
    args = ap.parse_args()

    work = os.path.expanduser(args.work)
    tl = load_json(os.path.join(work, "timeline.json"))
    lines = load_json(os.path.join(work, "narration.json"))["lines"]
    raw = os.path.expanduser(args.raw or tl["raw"])
    total = duration(raw)
    beats = tl["beats"]
    if len(lines) != len(beats):
        raise SystemExit("narration has %d lines but timeline has %d beats" % (len(lines), len(beats)))

    bounds, exts, new_starts, new_total = plan(beats, total, lines, args.margin)
    title_s = args.title_secs if args.title else 0.0
    final_total = new_total + title_s
    vk = video_kbps(final_total, args.target_mb, audio_kbps=96)
    held = sum(exts)
    print("recording %.1f s, holds %.1f s on %d beats, title %.1f s -> %.1f s at %d kbit/s video"
          % (total, held, sum(1 for e in exts if e > 0.01), title_s, final_total, vk))

    tmp = os.path.join(work, "tmp_assemble")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    W, H = (1920, 1080) if args.height == 1080 else (1280, 720)
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-maxrate", "%dk" % vk, "-bufsize", "%dk" % (vk * 2),
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-g", str(FPS * 4), "-an"]
    seglist = []

    if title_s:
        f = font_file()
        vf = ("drawtext=fontfile='%s':text='%s':fontsize=40:fontcolor=0x61dafb:x=(w-tw)/2:y=h/2-120," % (f, esc(args.kicker.upper()))
              + "drawtext=fontfile='%s':text='%s':fontsize=96:fontcolor=white:x=(w-tw)/2:y=h/2-30," % (f, esc(args.title))
              + "fade=t=in:st=0:d=0.4,fade=t=out:st=%.2f:d=0.4,scale=%d:%d" % (title_s - 0.4, W, H))
        p = os.path.join(tmp, "s_title.mp4")
        ffmpeg(["-f", "lavfi", "-i", "color=c=0x0d1b2a:s=1920x1080:r=%d:d=%.2f" % (FPS, title_s), "-vf", vf] + enc + [p], 120, args.threads)
        seglist.append(p)

    # one segment per beat when something must be held, else the whole recording in one go
    cuts = [(bounds[i], bounds[i + 1], exts[i]) for i in range(len(beats))] if held > 0.01 else [(0.0, total, 0.0)]
    for n, (a, b, e) in enumerate(cuts):
        if b - a < 0.04 and e < 0.01:
            continue
        vf = ("tpad=stop_mode=clone:stop_duration=%.3f," % e if e > 0.01 else "") + "fps=%d,scale=%d:%d" % (FPS, W, H)
        p = os.path.join(tmp, "s%03d.mp4" % n)
        ffmpeg(["-ss", "%.3f" % a, "-t", "%.3f" % (b - a), "-i", raw, "-vf", vf] + enc + [p], 900, args.threads)
        seglist.append(p)
    with open(os.path.join(tmp, "list.txt"), "w") as fl:
        for p in seglist:
            fl.write("file '%s'\n" % p)

    # narration: every clip at its (shifted) start, one mix, one loudness pass
    inputs, flt, k = [], [], 0
    for st, ln in zip(new_starts, lines):
        if not ln.get("clip"):
            continue
        ms = int(round((st + title_s) * 1000))
        inputs += ["-i", ln["clip"]]
        flt.append("[%d:a]aresample=44100,aformat=channel_layouts=mono,adelay=%d:all=1[a%d]" % (k, ms, k))
        k += 1
    wav = os.path.join(tmp, "voice.wav")
    if k:
        pre = os.path.join(tmp, "voice_pre.wav")
        mix = "".join("[a%d]" % i for i in range(k)) + (
            "amix=inputs=%d:normalize=0:dropout_transition=0,apad=whole_dur=%.3f,atrim=0:%.3f[aout]" % (k, final_total, final_total))
        ffmpeg(inputs + ["-filter_complex", ";".join(flt + [mix]), "-map", "[aout]", "-ac", "1", "-c:a", "pcm_s16le", pre], 600, args.threads)
        loudnorm_2pass(pre, wav, args.lufs)
    else:
        ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "%.3f" % final_total, wav], 60)

    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    ffmpeg(["-f", "concat", "-safe", "0", "-i", os.path.join(tmp, "list.txt"), "-i", wav, "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-ac", "1", "-movflags", "+faststart", "-t", "%.3f" % final_total, out], 600, args.threads)

    mb = os.path.getsize(out) / 1024 / 1024
    if mb > args.target_mb:  # rare: busy screens. One tighter re-encode.
        vk2 = int(vk * args.target_mb / mb * 0.9)
        print("%.1f MB is over %.1f MB: re-encoding at %d kbit/s" % (mb, args.target_mb, vk2))
        tmp_out = out + ".tmp.mp4"
        ffmpeg(["-i", out, "-c:v", "libx264", "-preset", "veryfast", "-b:v", "%dk" % vk2, "-maxrate", "%dk" % vk2,
                "-bufsize", "%dk" % (vk2 * 2), "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", tmp_out], 900, args.threads)
        os.replace(tmp_out, out)
        mb = os.path.getsize(out) / 1024 / 1024

    save_json({"out": out, "total": round(final_total, 3), "title_secs": title_s, "holds": exts,
               "starts": [round(s + title_s, 3) for s in new_starts]}, os.path.join(work, "assembled.json"))
    if not args.keep_temp:
        shutil.rmtree(tmp, ignore_errors=True)
    d = duration(out)
    print("done %s  %d:%02d  %.1f MB" % (out, d // 60, d % 60, mb))


if __name__ == "__main__":
    main()
