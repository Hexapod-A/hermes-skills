#!/usr/bin/env python3
"""Build a finished video from an edit list (JSON): cuts, speed and speed ramps, photos with
Ken Burns motion, title cards, text overlays, transitions, colour grade, music with ducking under
speech, voice-over, burned captions, and loudness normalised to -14 LUFS.

Usage:
  python3 assemble.py edit.json [--out final.mp4] [--keep-temp] [--dry-run]

Edit list (all keys except "clips" are optional; times are seconds):
{
  "size": "1080x1920", "fps": 30, "crf": 20,
  "transition": {"type": "cut"},                  # or {"type": "fade", "dur": 0.25}; any xfade name works
  "grade": {"eq": "contrast=1.06:saturation=1.12", "lut": "look.cube"},
  "clips": [
    {"src": "a.mp4", "in": 3.2, "out": 5.0},                       # plain cut
    {"src": "a.mp4", "in": 9.0, "out": 10.5, "speed": 2.0},       # 2x faster (audio pitch kept)
    {"src": "b.mp4", "in": 0, "ramp": [[1.0, 1.0], [1.5, 3.0], [1.0, 0.5]]},  # speed ramp: [source secs, speed]...
    {"src": "photo.jpg", "dur": 2.0, "kenburns": "in"},          # in | out | left | right | up | down | none
    {"color": "#0d0d0d", "dur": 1.2, "text": {"t": "Big idea\nin two lines", "size": 96}},
    {"src": "c.mp4", "in": 4, "out": 6, "fit": "blur", "x": 0.5, "volume": 0.0,
     "transition": {"type": "slideleft", "dur": 0.3},
     "text": {"t": "Hook line", "pos": "top", "size": 72, "color": "white", "box": true, "from": 0.2, "to": 1.8}}
  ],
  "voiceover": {"src": "vo.wav", "at": 0.0, "volume": 1.0},
  "music": {"src": "bed.mp3", "volume": 0.35, "duck": true, "start": 0, "fade_in": 0.5, "fade_out": 1.5},
  "captions": "subs.srt",            # burned in (needs ffmpeg with libass)
  "caption_style": "FontName=DejaVu Sans,FontSize=13,Bold=1,Outline=2,Shadow=0,MarginV=60",
  "loudness": -14,                   # null to skip
  "out": "final.mp4"
}
fit: crop (fill the frame, aim with x/y 0..1), pad (whole frame, black bars), blur (whole frame
over a blurred copy). Text pos: top | center | bottom | lower-third, or a number = y in px.
Relative paths are read from the edit list's folder.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vutil import default_font, duration, ff, has_audio, need  # noqa: E402

IMG = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def atempo(speed):
    """atempo only takes 0.5..2.0 per stage in older ffmpeg; chain stages for other speeds."""
    parts, s = [], speed
    while s > 2.0:
        parts.append("atempo=2.0"); s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5"); s /= 0.5
    parts.append(f"atempo={s:.5f}")
    return ",".join(parts)


def esc(path):
    """Escape a path for use inside an ffmpeg filter argument."""
    return path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


def fit_chain(fit, W, H, x=0.5, y=0.5):
    if fit == "pad":
        return f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black"
    if fit == "stretch":
        return f"scale={W}:{H}"
    return (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}:(iw-{W})*{x}:(ih-{H})*{y}")


def kenburns(kind, W, H, fps, dur):
    N = max(1, round(dur * fps))
    pre = f"scale={W * 3}:{H * 3}:force_original_aspect_ratio=increase,crop={W * 3}:{H * 3}"
    zc = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    z = {
        "in": f"z='1+0.18*on/{N}':{zc}",
        "out": f"z='1.18-0.18*on/{N}':{zc}",
        "left": f"z='1.15':x='(iw-iw/zoom)*(1-on/{N})':y='ih/2-(ih/zoom/2)'",
        "right": f"z='1.15':x='(iw-iw/zoom)*on/{N}':y='ih/2-(ih/zoom/2)'",
        "up": f"z='1.15':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(1-on/{N})'",
        "down": f"z='1.15':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*on/{N}'",
        "none": f"z='1':{zc}",
    }[kind or "in"]
    return f"{pre},zoompan={z}:d={N}:s={W}x{H}:fps={fps}"


def text_filters(spec, W, H, dur, td, idx, font):
    if not spec:
        return []
    if isinstance(spec, str):
        spec = {"t": spec}
    lines = str(spec["t"]).split("\n")
    size = int(spec.get("size", round(W * 0.066)))
    color = spec.get("color", "white")
    a, b = float(spec.get("from", 0)), float(spec.get("to", dur))
    fade = float(spec.get("fade", 0.15))
    gap = int(size * 0.28)
    block = len(lines) * size + (len(lines) - 1) * gap
    pos = spec.get("pos", "center")
    if isinstance(pos, (int, float)):
        y0 = int(pos)
    else:
        y0 = {"top": int(H * 0.14), "center": (H - block) // 2, "bottom": int(H * 0.80) - block,
              "lower-third": int(H * 0.68)}.get(pos, (H - block) // 2)
    out = []
    for i, line in enumerate(lines):
        tf = os.path.join(td, f"text_{idx}_{i}.txt")
        with open(tf, "w") as fh:
            fh.write(line)
        alpha = f"if(lt(t\\,{a + fade:.3f})\\,(t-{a:.3f})/{fade:.3f}\\,if(gt(t\\,{b - fade:.3f})\\,({b:.3f}-t)/{fade:.3f}\\,1))" if fade > 0 else "1"
        f = (f"drawtext=fontfile='{esc(font)}':textfile='{esc(tf)}':fontsize={size}:fontcolor={color}"
             f":x=(w-text_w)/2:y={y0 + i * (size + gap)}:alpha='{alpha}':enable='between(t\\,{a:.3f}\\,{b:.3f})'")
        if spec.get("box", True):
            f += f":box=1:boxcolor={spec.get('boxcolor', 'black@0.45')}:boxborderw={max(8, size // 4)}"
        else:
            f += f":borderw={max(2, size // 18)}:bordercolor=black@0.8"
        out.append(f)
    return out


def expand(clips):
    """Turn a clip with "ramp" into consecutive sub-clips joined by hard cuts."""
    out = []
    for c in clips:
        if "ramp" not in c:
            out.append(c)
            continue
        t = float(c.get("in", 0))
        for j, (secs, speed) in enumerate(c["ramp"]):
            sub = {k: v for k, v in c.items() if k not in ("ramp", "text", "transition")}
            sub.update({"in": t, "out": t + float(secs), "speed": float(speed)})
            if j == 0:
                if "text" in c:
                    sub["text"] = c["text"]
                if "transition" in c:
                    sub["transition"] = c["transition"]
            else:
                sub["transition"] = {"type": "cut"}
            out.append(sub)
            t += float(secs)
    return out


def render_segment(c, i, cfg, td, base, font):
    W, H = cfg["W"], cfg["H"]
    fps = cfg["fps"]
    seg = os.path.join(td, f"seg_{i:03d}.mp4")
    grade = []
    g = cfg.get("grade") or {}
    if g.get("eq"):
        grade.append(f"eq={g['eq']}")
    if g.get("lut"):
        grade.append(f"lut3d=file='{esc(os.path.join(base, g['lut']))}'")
    args, fc = [], []
    if "color" in c:
        dur = float(c.get("dur", 2.0))
        args += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"color=c={c['color']}:s={W}x{H}:r={fps}"]
        vchain = ["setsar=1"]
        src_audio = False
    else:
        src = os.path.join(base, c["src"])
        if not os.path.exists(src):
            raise SystemExit(f"clip {i + 1}: file not found: {src}")
        if src.lower().endswith(IMG):
            dur = float(c.get("dur", 2.0))
            args += ["-i", src]
            vchain = [kenburns(c.get("kenburns", "in"), W, H, fps, dur), "setsar=1"]
            src_audio = False
        else:
            a, b = float(c.get("in", 0)), c.get("out")
            b = float(b) if b is not None else duration(src)
            speed = float(c.get("speed", 1.0))
            dur = (b - a) / speed
            args += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src]
            vchain = []
            if c.get("fit") == "blur":
                vchain = None
            else:
                vchain.append(fit_chain(c.get("fit", "crop"), W, H, c.get("x", 0.5), c.get("y", 0.5)))
            src_audio = has_audio(src) and float(c.get("volume", 1.0)) > 0
    # video graph
    post = ([f"setpts=PTS/{float(c.get('speed', 1.0))}"] if float(c.get("speed", 1.0)) != 1.0 else [])
    post += [f"fps={fps}"] + grade + text_filters(c.get("text"), W, H, dur, td, i, font) + ["setsar=1", "format=yuv420p"]
    if vchain is None:  # blurred background fill
        fc.append(f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"boxblur=40:4,eq=brightness=-0.06[bg];[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
                  f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,{','.join(post)}[v]")
    else:
        fc.append(f"[0:v]{','.join(vchain + post)}[v]")
    # audio graph
    if src_audio:
        ach = ["aresample=48000", "aformat=sample_fmts=fltp:channel_layouts=stereo"]
        if float(c.get("speed", 1.0)) != 1.0:
            ach.append(atempo(float(c["speed"])))
        if float(c.get("volume", 1.0)) != 1.0:
            ach.append(f"volume={float(c['volume'])}")
        ach.append("apad")
        fc.append(f"[0:a]{','.join(ach)}[a]")
    else:
        args += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        fc.append("[1:a]anull[a]")
    ff(args + ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "256k",
               "-ar", "48000", "-ac", "2", seg])
    return seg, duration(seg)


def join(segs, clips, cfg, td):
    out = os.path.join(td, "joined.mp4")
    glob_t = cfg.get("transition") or {"type": "cut"}
    trans = []
    for c in clips[1:]:
        t = c.get("transition", glob_t)
        trans.append(t if t.get("type", "cut") != "cut" and float(t.get("dur", 0.25)) > 0 else None)
    if not any(trans):
        lst = os.path.join(td, "list.txt")
        with open(lst, "w") as fh:
            fh.writelines(f"file '{p}'\n" for p, _ in segs)
        ff(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
        return out
    args, fc = [], []
    for k, (p, _) in enumerate(segs):
        args += ["-i", p]
        # same timebase everywhere, or xfade refuses to join the streams
        fc.append(f"[{k}:v]settb=AVTB,setpts=PTS-STARTPTS,setsar=1[iv{k}]")
        fc.append(f"[{k}:a]asetpts=PTS-STARTPTS[ia{k}]")
    vprev, aprev, L = "iv0", "ia0", segs[0][1]
    for k in range(1, len(segs)):
        t, dk = trans[k - 1], segs[k][1]
        vo, ao = f"v{k}", f"a{k}"
        if t:
            d = min(float(t.get("dur", 0.25)), dk / 2, L / 2)
            name = "fade" if t["type"] in ("fade", "crossfade", "dissolve") else t["type"]
            fc.append(f"[{vprev}][iv{k}]xfade=transition={name}:duration={d:.3f}:offset={L - d:.3f}[{vo}]")
            fc.append(f"[{aprev}][ia{k}]acrossfade=d={d:.3f}[{ao}]")
            L += dk - d
        else:
            fc.append(f"[{vprev}][{aprev}][iv{k}][ia{k}]concat=n=2:v=1:a=1[{vo}][{ao}]")
            L += dk
        vprev, aprev = vo, ao
    ff(args + ["-filter_complex", ";".join(fc), "-map", f"[{vprev}]", "-map", f"[{aprev}]",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "256k", out])
    return out


def mix_audio(joined, cfg, td, base):
    total = duration(joined)
    mix = os.path.join(td, "mix.wav")
    args = ["-i", joined]
    fc = ["[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[prog]"]
    speech = "prog"
    n = 1
    vo = cfg.get("voiceover")
    if vo:
        args += ["-i", os.path.join(base, vo["src"])]
        delay = int(float(vo.get("at", 0)) * 1000)
        fc.append(f"[{n}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                  f"volume={float(vo.get('volume', 1.0))},adelay={delay}|{delay}[vo]")
        fc.append("[prog][vo]amix=inputs=2:normalize=0:duration=first[sp]")
        speech, n = "sp", n + 1
    mu = cfg.get("music")
    final = speech
    if mu:
        args += ["-stream_loop", "-1", "-ss", f"{float(mu.get('start', 0)):.3f}", "-i", os.path.join(base, mu["src"])]
        fo = float(mu.get("fade_out", 1.5))
        fi = float(mu.get("fade_in", 0.3))
        fc.append(f"[{n}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:{total:.3f},"
                  f"asetpts=PTS-STARTPTS,volume={float(mu.get('volume', 0.35))},afade=t=in:d={fi},"
                  f"afade=t=out:st={max(0, total - fo):.3f}:d={fo}[mus]")
        if mu.get("duck", True):
            fc.append(f"[{speech}]asplit=2[sp1][sp2]")
            fc.append("[mus][sp2]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350:makeup=1[duck]")
            fc.append("[sp1][duck]amix=inputs=2:normalize=0:duration=first[mixed]")
        else:
            fc.append(f"[{speech}][mus]amix=inputs=2:normalize=0:duration=first[mixed]")
        final = "mixed"
    ff(args + ["-filter_complex", ";".join(fc), "-map", f"[{final}]", "-t", f"{total:.3f}",
               "-c:a", "pcm_s16le", "-ar", "48000", mix])
    return mix


def measure_loudness(path, target):
    import re
    err = ff(["-i", path, "-af", f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    return json.loads(m.group(0)) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl")
    ap.add_argument("--out")
    ap.add_argument("--keep-temp", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="validate the edit list and print the plan only")
    a = ap.parse_args()
    need("ffmpeg"); need("ffprobe")
    base = os.path.dirname(os.path.abspath(a.edl))
    cfg = json.load(open(a.edl))
    W, H = (int(x) for x in str(cfg.get("size", "1080x1920")).lower().split("x"))
    if W % 2 or H % 2:
        raise SystemExit("size must be even numbers, e.g. 1080x1920")
    cfg.update(W=W, H=H, fps=int(cfg.get("fps", 30)))
    clips = expand(cfg["clips"])
    out = os.path.abspath(a.out or os.path.join(base, cfg.get("out", "final.mp4")))
    font = cfg.get("font") or default_font()
    if any("text" in c for c in clips) and not font:
        raise SystemExit("no font found for text overlays: set \"font\": \"/path/Font-Bold.ttf\"")
    if a.dry_run:
        for i, c in enumerate(clips, 1):
            print(i, json.dumps(c))
        print(f"{len(clips)} clips -> {out} at {W}x{H} {cfg['fps']}fps")
        return
    td = tempfile.mkdtemp(prefix="assemble_")
    try:
        segs = []
        for i, c in enumerate(clips):
            segs.append(render_segment(c, i, cfg, td, base, font))
            print(f"clip {i + 1}/{len(clips)}: {segs[-1][1]:.2f}s", flush=True)
        joined = join(segs, clips, cfg, td)
        mix = mix_audio(joined, cfg, td, base)
        af = ["aresample=48000"]
        target = cfg.get("loudness", -14)
        if target is not None:
            m = measure_loudness(mix, target)
            if m and float(m["input_i"]) > -70:
                af = [f"loudnorm=I={target}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
                      f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}"
                      f":linear=true", "aresample=48000"]
        vf = []
        if cfg.get("captions"):
            style = cfg.get("caption_style", "FontName=DejaVu Sans,FontSize=13,Bold=1,Outline=2,Shadow=0,MarginV=60")
            vf = ["-vf", f"subtitles='{esc(os.path.join(base, cfg['captions']))}':force_style='{style}'"]
        ff(["-i", joined, "-i", mix, "-map", "0:v", "-map", "1:a"] + vf +
           ["-af", ",".join(af), "-c:v", "libx264", "-preset", cfg.get("preset", "medium"),
            "-crf", str(cfg.get("crf", 20)), "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", out])
        print(json.dumps({"out": out, "duration": round(duration(out), 2), "size_mb": round(os.path.getsize(out) / 1048576, 2),
                          "clips": len(clips)}))
    finally:
        if a.keep_temp:
            print(f"temp: {td}")
        else:
            shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    main()
