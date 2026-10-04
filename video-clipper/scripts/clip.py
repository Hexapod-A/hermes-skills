#!/usr/bin/env python3
"""Clip long videos into vertical, captioned shorts with yt-dlp + ffmpeg + faster-whisper.

Commands:
  clip.py download URL [--out DIR]                       -> best MP4 (<=1080p) path
  clip.py transcribe FILE [--model small] [--out t.json]  -> timestamped transcript (find the good moments)
  clip.py make (--input FILE | --url URL) --start 00:01:05 --end 00:01:40
               [--vertical crop|blur|none] [--x 0.5] [--captions] [--model small]
               [--words 3] [--font-dir DIR] [--font "Plus Jakarta Sans"] [--accent FF9900] [--out short.mp4]

Notes: --x picks the horizontal crop centre (0=left, 1=right) for --vertical crop.
Captions are word-timed, burned in, with the current word in the accent colour.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_FONT_DIR = HERE.parent.parent / "flyer-studio" / "brands" / "3xagentic" / "fonts"


def run(cmd):
    print("+", " ".join(str(c) for c in cmd), file=sys.stderr)
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"command failed ({p.returncode}): {' '.join(map(str, cmd[:3]))} ...\n{p.stderr[-2000:]}")
    return p.stdout


def need(binary):
    if not shutil.which(binary): sys.exit(f"{binary} not found. Install it (see README).")


def ytdlp():
    # prefer the yt-dlp installed next to this Python (the repo venv), else the one on PATH
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        need("yt-dlp"); return ["yt-dlp"]


def download(url, out_dir):
    Y = ytdlp()
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    tpl = str(out_dir / "%(title).80B [%(id)s].%(ext)s")
    run(Y + ["-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b", "--merge-output-format", "mp4",
         "--no-playlist", "--restrict-filenames", "-o", tpl, url])
    path = run(Y + ["--no-playlist", "--restrict-filenames", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b",
                "--merge-output-format", "mp4", "-o", tpl, "--print", "filename", url]).strip().splitlines()[-1]
    if not Path(path).exists():
        cands = sorted(out_dir.glob("*.mp4"), key=os.path.getmtime)
        path = str(cands[-1]) if cands else path
    return path


def probe(path):
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path])
    j = json.loads(out)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    return {"width": int(v["width"]) if v else None, "height": int(v["height"]) if v else None,
            "duration": float(j["format"].get("duration", 0)), "has_audio": a is not None}


def transcribe(path, model="small", language=None):
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="auto", compute_type="auto")
    segs, info = m.transcribe(path, word_timestamps=True, vad_filter=True, language=language)
    out = []
    for s in segs:
        out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                    "words": [{"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word.strip()} for w in (s.words or [])]})
    return {"language": info.language, "segments": out}


def ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def ass_from_words(words, path, width, height, font, accent_hex, per_line):
    # ASS colours are &HBBGGRR
    acc = f"&H00{accent_hex[4:6]}{accent_hex[2:4]}{accent_hex[0:2]}".upper()
    size = int(height * 0.05)
    margin_v = int(height * 0.22)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{font},{size},&H00F1F1F1,&H00F1F1F1,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{max(3, size // 12)},0,2,{int(width*0.08)},{int(width*0.08)},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    chunks = [words[i:i + per_line] for i in range(0, len(words), per_line)]
    for ci, ch in enumerate(chunks):
        if not ch: continue
        chunk_end = chunks[ci + 1][0]["start"] if ci + 1 < len(chunks) and chunks[ci + 1] else ch[-1]["end"] + 0.3
        for wi, w in enumerate(ch):
            start = w["start"]; end = ch[wi + 1]["start"] if wi + 1 < len(ch) else min(chunk_end, ch[-1]["end"] + 0.6)
            if end <= start: end = start + 0.05
            txt = "  ".join((f"{{\\c{acc}}}{x['word'].upper()}{{\\c&H00F1F1F1&}}" if j == wi else x["word"].upper()) for j, x in enumerate(ch))
            lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{txt}")
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def make(a):
    need("ffmpeg"); need("ffprobe")
    src = a.input or download(a.url, a.workdir or tempfile.mkdtemp(prefix="clip-"))
    info = probe(src)
    work = Path(tempfile.mkdtemp(prefix="clipwork-"))
    cut = work / "cut.mp4"
    # 1. accurate cut (re-encode so the first frame is exact)
    cmd = ["ffmpeg", "-y", "-ss", a.start, "-i", src]
    if a.end: cmd += ["-to", str(dur(a.end) - dur(a.start))]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(cut)]
    run(cmd)
    # 2. reframe filter
    W, H = (1080, 1920) if a.vertical != "none" else (info["width"], info["height"])
    if a.vertical == "crop":
        vf = f"crop='min(iw,ih*9/16)':ih:'(iw-min(iw,ih*9/16))*{a.x}':0,scale={W}:{H}:flags=lanczos,setsar=1"
    elif a.vertical == "blur":
        vf = (f"split[m][b];[b]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,eq=brightness=-0.15[bg];"
              f"[m]scale={W}:-2:flags=lanczos[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1")
    else:
        vf = "null"
    # 3. captions
    n_caps = 0
    if a.captions:
        if not probe(str(cut))["has_audio"]: sys.exit("clip has no audio track; cannot caption")
        t = transcribe(str(cut), a.model, a.language)
        words = [w for s in t["segments"] for w in s["words"] if w["word"]]
        (work / "transcript.json").write_text(json.dumps(t, indent=2))
        ass = work / "captions.ass"
        n_caps = ass_from_words(words, ass, W, H, a.font, a.accent.lstrip("#"), a.words)
        font_dir = a.font_dir or str(DEFAULT_FONT_DIR)
        sub = f"ass={str(ass)}:fontsdir={font_dir}".replace("\\", "/")
        vf = f"{vf},{sub}" if vf != "null" else sub
    out = Path(a.out or Path(src).with_suffix("").as_posix() + "-short.mp4")
    run(["ffmpeg", "-y", "-i", str(cut), "-filter_complex" if ";" in vf or "[" in vf else "-vf", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(out)])
    res = probe(str(out)); res.update(output=str(out), captions=n_caps, transcript=str(work / "transcript.json") if a.captions else None)
    print(json.dumps(res, indent=2))


def dur(t):
    t = str(t)
    if ":" not in t: return float(t)
    parts = [float(p) for p in t.split(":")]
    while len(parts) < 3: parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    d = sp.add_parser("download"); d.add_argument("url"); d.add_argument("--out", default=".")
    t = sp.add_parser("transcribe"); t.add_argument("file"); t.add_argument("--model", default="small"); t.add_argument("--language"); t.add_argument("--out")
    m = sp.add_parser("make")
    g = m.add_mutually_exclusive_group(required=True); g.add_argument("--input"); g.add_argument("--url")
    m.add_argument("--start", default="0"); m.add_argument("--end"); m.add_argument("--vertical", choices=["crop", "blur", "none"], default="crop")
    m.add_argument("--x", type=float, default=0.5); m.add_argument("--captions", action="store_true"); m.add_argument("--model", default="small")
    m.add_argument("--language"); m.add_argument("--words", type=int, default=3); m.add_argument("--font", default="Plus Jakarta Sans")
    m.add_argument("--font-dir"); m.add_argument("--accent", default="FF9900"); m.add_argument("--out"); m.add_argument("--workdir")
    a = ap.parse_args()
    if a.cmd == "download": print(download(a.url, a.out))
    elif a.cmd == "transcribe":
        r = transcribe(a.file, a.model, a.language)
        s = json.dumps(r, indent=2, ensure_ascii=False)
        if a.out: Path(a.out).write_text(s); print(a.out)
        else: print(s)
    else: make(a)


if __name__ == "__main__":
    main()
