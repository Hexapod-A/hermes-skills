#!/usr/bin/env python3
"""Clean and join a voice sample (WhatsApp/phone voice notes) for instant voice cloning.

    python3 voice_prep.py note1.ogg note2.ogg note3.ogg --out voice/sample_clean.mp3

What it does, in one ffmpeg pass per file then one join:
  highpass 80 Hz (rumble, desk knocks) -> lowpass 9 kHz (hiss) -> light FFT denoise
  -> shorten pauses longer than 0.8 s -> join -> loudness -18 LUFS, peak -2 dBTP
  -> mono 44.1 kHz MP3 192k (what the clone APIs like best).
Prints the clean length and warns when the sample is too short, too long or clipped.
Do not over-denoise: the clone copies whatever is left, including watery artefacts.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tvs_util import duration, ffmpeg, run  # noqa: E402


def peak_db(path):
    r = run(["ffmpeg", "-nostdin", "-hide_banner", "-i", path, "-af", "volumedetect", "-f", "null", "-"], 120, check=False, quiet=True)
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="voice notes in any format ffmpeg reads (ogg/opus, m4a, mp3, wav)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--denoise", type=float, default=-25, help="afftdn noise floor in dB (-20 stronger, -30 lighter, 0 = off)")
    args = ap.parse_args()

    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    tmpdir = os.path.join(os.path.dirname(os.path.abspath(out)), ".voice_tmp")
    os.makedirs(tmpdir, exist_ok=True)

    raw_total = 0.0
    parts = []
    for i, src in enumerate(args.inputs):
        src = os.path.expanduser(src)
        raw_total += duration(src)
        pk = peak_db(src)
        if pk is not None and pk > -0.3:
            print("WARN %s peaks at %.1f dB: may be clipped - listen for crackle; if it crackles ask for a new note with the phone a bit further away" % (os.path.basename(src), pk))
        chain = ["highpass=f=80", "lowpass=f=9000"]
        if args.denoise:
            chain.append("afftdn=nf=%g" % args.denoise)
        chain.append("silenceremove=stop_periods=-1:stop_duration=0.8:stop_threshold=-40dB")
        p = os.path.join(tmpdir, "part%02d.wav" % i)
        ffmpeg(["-i", src, "-af", ",".join(chain), "-ac", "1", "-ar", "44100", p], 300)
        parts.append(p)

    inputs = []
    for p in parts:
        inputs += ["-i", p]
    join = "".join("[%d:a]" % i for i in range(len(parts))) + "concat=n=%d:v=0:a=1," % len(parts)
    ffmpeg(inputs + ["-filter_complex", join + "loudnorm=I=-18:TP=-2:LRA=11[a]", "-map", "[a]",
                     "-ac", "1", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "192k", out], 300)
    for p in parts:
        os.remove(p)
    os.rmdir(tmpdir)

    d = duration(out)
    print("raw %.1f s -> clean %.1f s: %s" % (raw_total, d, out))
    if d < 45:
        print("WARN under 45 s of speech: ask for more (2-3 minutes total is the sweet spot)")
    elif d > 300:
        print("NOTE over 5 min: instant clones do not get better past ~3 min; the first 3 min are enough")
    else:
        print("OK length is fine for an instant clone")


if __name__ == "__main__":
    main()
