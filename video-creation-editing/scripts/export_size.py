#!/usr/bin/env python3
"""Re-encode a video so it fits under a file-size limit (WhatsApp 16 MB, email 25 MB, ...), with the
best quality that fits. Two-pass H.264 at a computed bitrate, AAC audio, yuv420p, fast start.

Usage:
  python3 export_size.py IN.mp4 --mb 15 [--out out.mp4] [--max-height 1920] [--audio-kbps 128]
                         [--fps 30] [--aspect 9:16|1:1|16:9|keep] [--fit crop|pad|blur]

If the bitrate it would need is too low for the frame size (blocky picture), it steps the size down
(1080p -> 720p) and says so. --aspect re-frames before encoding (crop, pad, or blurred background).
"""
import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vutil import duration, ff, has_audio, need, video_stream  # noqa: E402

ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080), "4:5": (1080, 1350)}


def reframe(aspect, fit, w, h):
    W, H = ASPECTS[aspect]
    if fit == "pad":
        return f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2", (W, H)
    if fit == "blur":
        return (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:4[bg];"
                f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2"), (W, H)
    return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", (W, H)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--mb", type=float, default=15.0, help="target size in MB (MiB). WhatsApp: 15")
    ap.add_argument("--out")
    ap.add_argument("--max-height", type=int, default=None)
    ap.add_argument("--audio-kbps", type=int, default=128)
    ap.add_argument("--fps", type=int, default=None)
    ap.add_argument("--aspect", default="keep", choices=["keep"] + list(ASPECTS))
    ap.add_argument("--fit", default="crop", choices=["crop", "pad", "blur"])
    ap.add_argument("--min-bpp", type=float, default=0.045, help="bits per pixel below which the size steps down")
    a = ap.parse_args()
    need("ffmpeg")
    src = a.input
    out = a.out or os.path.splitext(src)[0] + f"_{int(a.mb)}mb.mp4"
    dur = duration(src)
    vs = video_stream(src)
    w, h = int(vs["width"]), int(vs["height"])
    fps = a.fps or 30
    audio = has_audio(src)
    akbps = a.audio_kbps if audio else 0
    total_kbits = a.mb * 1048576 * 8 / 1000 * 0.96  # 4% for container overhead
    vkbps = int(total_kbits / dur - akbps)
    if vkbps < 150:
        raise SystemExit(f"{dur:.1f}s cannot fit in {a.mb} MB at watchable quality ({vkbps} kbps). Cut it shorter or split it.")
    vf = ""
    if a.aspect != "keep":
        vf, (w, h) = reframe(a.aspect, a.fit, w, h)
    if a.max_height and h > a.max_height:
        sc = a.max_height / h
        w, h = int(w * sc) // 2 * 2, a.max_height
        vf = (vf + "," if vf else "") + f"scale={w}:{h}"
    notes = []
    while vkbps * 1000 / (w * h * fps) < a.min_bpp and min(w, h) > 720:
        sc = 720 / min(w, h)
        w, h = int(w * sc) // 2 * 2, int(h * sc) // 2 * 2
        vf = (vf + "," if vf else "") + f"scale={w}:{h}"
        notes.append(f"stepped down to {w}x{h} so {vkbps} kbps still looks clean")
    vf = (vf + "," if vf else "") + f"fps={fps},format=yuv420p"
    filt = ["-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]"] if "[a]" in vf or "split" in vf else ["-vf", vf]
    with tempfile.TemporaryDirectory() as td:
        log = os.path.join(td, "x264")
        common = ["-i", src] + filt + ["-c:v", "libx264", "-preset", "slow", "-b:v", f"{vkbps}k",
                                       "-maxrate", f"{int(vkbps * 1.5)}k", "-bufsize", f"{vkbps * 2}k",
                                       "-passlogfile", log]
        if "-map" in filt and audio:
            common += ["-map", "0:a?"]
        ff(common + ["-pass", "1", "-an", "-f", "mp4", os.devnull])
        aud = ["-c:a", "aac", "-b:a", f"{akbps}k", "-ar", "48000", "-ac", "2"] if audio else ["-an"]
        ff(common + ["-pass", "2"] + aud + ["-movflags", "+faststart", out])
    size = os.path.getsize(out) / 1048576
    print(json.dumps({"out": out, "size_mb": round(size, 2), "target_mb": a.mb, "video_kbps": vkbps,
                      "size": f"{w}x{h}", "fits": size < a.mb, "notes": notes}))
    sys.exit(0 if size < a.mb else 2)


if __name__ == "__main__":
    main()
