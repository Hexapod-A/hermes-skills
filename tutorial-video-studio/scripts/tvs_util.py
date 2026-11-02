"""Shared helpers for tutorial-video-studio (stdlib only).

Every external command goes through run(), which wraps it in `timeout -k 5 N`
so a hung ffmpeg or npm can never hold the agent forever.
"""
import json
import os
import random
import shutil
import subprocess
import sys

WHATSAPP_MB = 16.0


def run(cmd, t=600, check=True, quiet=False):
    """Run a command with a hard deadline (SIGTERM at t, SIGKILL 5 s later)."""
    if shutil.which("timeout"):
        cmd = ["timeout", "-k", "5", str(int(t))] + list(cmd)
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode and not quiet:
        sys.stderr.write("command failed (%s): %s\n%s\n" % (r.returncode, " ".join(cmd[:8]), r.stderr[-1500:]))
    if check and r.returncode:
        raise RuntimeError("command failed: %s" % " ".join(cmd[:6]))
    return r


def ffmpeg(args, t=900, threads=2):
    """ffmpeg with no stdin, quiet logs and a thread cap (weak boxes)."""
    return run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-threads", str(threads)] + list(args), t)


def duration(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], 60)
    return float(r.stdout.strip() or 0)


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate,sample_rate,channels",
             "-of", "json", path], 60)
    return json.loads(r.stdout)


def video_kbps(total_s, target_mb=15.0, audio_kbps=96, cap_kbps=2500, floor_kbps=350):
    """Video bitrate that keeps the whole file under target_mb.

    size_bits = (video + audio) * seconds, so video = target*8*1024*1024/s - audio,
    minus ~4 % for container overhead. Capped: screen recordings look clean at
    1.5-2.5 Mbit/s at 1080p because most frames barely change.
    """
    total_s = max(total_s, 1.0)
    budget = target_mb * 8 * 1024 * 1024 / total_s / 1000.0  # kbit/s for everything
    v = budget * 0.96 - audio_kbps
    return int(max(floor_kbps, min(cap_kbps, v)))


def typing_delays(text, budget_s=None, min_ms=28, max_ms=140, seed=None):
    """Per-character delays (seconds) that look like a person typing.

    - base speed fits the budget when one is given (clamped to min/max)
    - jitter on every key, a longer pause after newlines and after ; { } ( )
    - an occasional 'thinking' pause on a new line
    Returns (delays, total_seconds).
    """
    rnd = random.Random(seed)
    n = max(1, len(text))
    base = 70.0
    if budget_s:
        # newline and punctuation pauses add roughly 35 % on code; leave room for them
        base = budget_s * 1000.0 / n / 1.35
    base = max(min_ms, min(max_ms, base))
    out = []
    for i, ch in enumerate(text):
        d = base * rnd.uniform(0.55, 1.45)
        if ch == "\n":
            d += base * rnd.uniform(2.0, 4.0)
            if rnd.random() < 0.12:
                d += rnd.uniform(0.35, 0.8) * 1000  # stop and think
        elif ch in ";{}()":
            d += base * rnd.uniform(0.6, 1.4)
        elif ch == " " and i and text[i - 1] == " ":
            d = base * 0.35  # indentation goes fast
        out.append(d / 1000.0)
    return out, sum(out)


def load_json(path):
    with open(os.path.expanduser(path)) as f:
        return json.load(f)


def save_json(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)
