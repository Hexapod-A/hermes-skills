"""Small shared helpers for the video-creation-editing scripts (ffmpeg/ffprobe wrappers)."""
import json
import os
import shutil
import subprocess


def need(tool):
    if not shutil.which(tool):
        raise SystemExit(f"{tool} not found. Install ffmpeg (sudo apt install -y ffmpeg).")


def run(cmd, timeout=3600):
    """Run a command, return (code, stdout, stderr). Never hangs past `timeout` seconds."""
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def ff(args, timeout=3600):
    """Run ffmpeg with -y and quiet banner; raise with the last lines of stderr on failure."""
    code, out, err = run(["ffmpeg", "-hide_banner", "-nostdin", "-y"] + args, timeout=timeout)
    if code != 0:
        tail = "\n".join(err.strip().splitlines()[-15:])
        raise RuntimeError(f"ffmpeg failed ({code}):\n{tail}")
    return err


def probe(path):
    """ffprobe as a dict: format + streams."""
    code, out, err = run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", path], timeout=120)
    if code != 0:
        raise RuntimeError(f"ffprobe could not read {path}: {err.strip()[:300]}")
    return json.loads(out)


def duration(path):
    d = probe(path)
    dur = d.get("format", {}).get("duration")
    if dur in (None, "N/A"):
        for s in d.get("streams", []):
            if s.get("duration") not in (None, "N/A"):
                return float(s["duration"])
        return 0.0
    return float(dur)


def has_audio(path):
    return any(s.get("codec_type") == "audio" for s in probe(path).get("streams", []))


def video_stream(path):
    for s in probe(path).get("streams", []):
        if s.get("codec_type") == "video":
            return s
    return None


def fps_of(stream):
    num, _, den = (stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1").partition("/")
    try:
        return float(num) / float(den or 1)
    except ZeroDivisionError:
        return 0.0


def default_font():
    """A bold sans font file for drawtext. Override with --font or FONT_FILE."""
    if os.environ.get("FONT_FILE"):
        return os.environ["FONT_FILE"]
    if shutil.which("fc-match"):
        code, out, _ = run(["fc-match", "-f", "%{file}", "sans:bold"], timeout=20)
        if code == 0 and out.strip() and os.path.exists(out.strip()):
            return out.strip()
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/Library/Fonts/Arial Bold.ttf"]:
        if os.path.exists(p):
            return p
    return None


def fmt_t(sec):
    m, s = divmod(max(0.0, sec), 60)
    return f"{int(m):02d}:{s:05.2f}"


def contact_sheet(frames, out, cols=4, width=1600, labels=None):
    """Tile image files into one JPEG with a time label under each (needs Pillow)."""
    from PIL import Image, ImageDraw, ImageFont
    ims = [Image.open(f).convert("RGB") for f in frames]
    if not ims:
        return None
    cols = max(1, min(cols, len(ims)))
    tw = width // cols
    th = int(tw * ims[0].height / ims[0].width)
    lab = 28
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + lab)), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(default_font() or "", 18)
    except Exception:
        font = ImageFont.load_default()
    for i, im in enumerate(ims):
        x, y = (i % cols) * tw, (i // cols) * (th + lab)
        sheet.paste(im.resize((tw, th)), (x, y))
        if labels:
            d.text((x + 6, y + th + 4), labels[i], fill=(235, 235, 235), font=font)
    sheet.save(out, quality=88)
    return out
