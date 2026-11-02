#!/usr/bin/env python3
"""Generate the narration for a lesson, one clip per beat, in the cloned voice.

    python3 narrate.py lesson.json --voice voice/voice.json --out work/04_components
    python3 narrate.py lesson.json --provider dummy --out work/04_components   # offline dry run

Reads every beat's "say" line, speaks it with the provider named in voice.json
(elevenlabs | minimax | dummy), trims dead air at both ends, and writes
<out>/narration.json: [{"i": 0, "text": "...", "clip": ".../n00_ab12cd.wav", "dur": 4.81}, ...]
Clips are cached by (voice, model, speed, text): change one line and only that line is re-spoken,
and a re-voice with a new voice id never reuses old clips.

Keys come from the environment only: ELEVENLABS_API_KEY, FAL_KEY.
"""
import argparse
import concurrent.futures as cf
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tvs_util import duration, ffmpeg, load_json, save_json  # noqa: E402

ELEVEN = "https://api.elevenlabs.io/v1"
FAL = "https://fal.run"


def _requests():
    import requests  # in the repo requirements
    return requests


def _post_retry(url, tries=6, **kw):
    rq = _requests()
    last = None
    for a in range(tries):
        try:
            r = rq.post(url, timeout=kw.pop("timeout", 180), **kw)
        except Exception as e:  # network blip
            last = str(e)
            time.sleep(3 + a * 3)
            continue
        if r.status_code == 200:
            return r
        last = "%s %s" % (r.status_code, r.text[:300])
        if r.status_code not in (408, 409, 429, 500, 502, 503, 504):
            break
        time.sleep(min(30, 4 + a * 4))
    raise RuntimeError("TTS request failed: " + str(last))


def speak(text, path, voice, speed=None):
    """Write `text` spoken in `voice` (dict from voice.json) to `path` (mp3/wav)."""
    prov = voice.get("provider", "dummy")
    speed = speed or voice.get("speed") or 1.0
    if prov == "elevenlabs":
        key = os.environ["ELEVENLABS_API_KEY"]
        body = {"text": text, "model_id": voice.get("model") or "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.85, "style": 0.0,
                                   "use_speaker_boost": True, "speed": speed}}
        r = _post_retry("%s/text-to-speech/%s?output_format=mp3_44100_128" % (ELEVEN, voice["voice_id"]),
                        headers={"xi-api-key": key, "Content-Type": "application/json"}, json=body)
        data = r.content
    elif prov == "minimax":
        key = os.environ["FAL_KEY"]
        body = {"text": text,
                "voice_setting": {"voice_id": voice["voice_id"], "speed": speed, "vol": 1, "pitch": 0},
                "audio_setting": {"format": "mp3", "sample_rate": 44100, "bitrate": 128000, "channel": 1},
                "output_format": "url", "language_boost": voice.get("language_boost", "English")}
        model = voice.get("model") or "speech-02-hd"
        r = _post_retry("%s/fal-ai/minimax/%s" % (FAL, model), headers={"Authorization": "Key " + key}, json=body)
        data = _requests().get(r.json()["audio"]["url"], timeout=120).content
    elif prov == "dummy":
        # offline stand-in: soft pink noise as long as the line would take to say (~2.6 words/s)
        secs = max(1.0, len(text.split()) / 2.6 / speed)
        ffmpeg(["-f", "lavfi", "-i", "anoisesrc=color=pink:amplitude=0.25:duration=%.2f" % secs,
                "-ac", "1", "-ar", "44100", path], 60)
        return path
    else:
        raise SystemExit("unknown provider: %s" % prov)
    if len(data) < 1000:
        raise RuntimeError("TTS returned an empty clip for: " + text[:60])
    with open(path, "wb") as f:
        f.write(data)
    return path


def trim(src, dst):
    """Cut leading/trailing silence so clip length = speech length (timing math depends on it)."""
    ffmpeg(["-i", src, "-af",
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.10,areverse",
            "-ac", "1", "-ar", "44100", dst], 120)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lesson")
    ap.add_argument("--voice", help="voice.json written by voice_clone.py")
    ap.add_argument("--provider", help="override: dummy for an offline dry run")
    ap.add_argument("--speed", type=float, help="1.0 natural; 1.05-1.1 for 'fast' tutorials")
    ap.add_argument("--out", required=True, help="work folder for this video")
    ap.add_argument("--jobs", type=int, default=3)
    args = ap.parse_args()

    lesson = load_json(args.lesson)
    voice = load_json(args.voice) if args.voice else {}
    if args.provider:
        voice["provider"] = args.provider
    voice.setdefault("provider", "dummy")
    speed = args.speed or voice.get("speed") or 1.0
    out = os.path.expanduser(args.out)
    aud = os.path.join(out, "aud")
    os.makedirs(aud, exist_ok=True)

    beats = lesson["beats"]

    def one(i):
        text = (beats[i].get("say") or "").strip()
        if not text:
            return {"i": i, "text": "", "clip": None, "dur": 0.0}
        h = hashlib.md5(("%s|%s|%s|%s|%s" % (voice["provider"], voice.get("voice_id"), voice.get("model"), speed, text)).encode()).hexdigest()[:10]
        final = os.path.join(aud, "n%02d_%s.wav" % (i, h))
        if not (os.path.exists(final) and os.path.getsize(final) > 1000):
            rawp = os.path.join(aud, "raw_%s.%s" % (h, "wav" if voice["provider"] == "dummy" else "mp3"))
            speak(text, rawp, voice, speed)
            trim(rawp, final)
            os.remove(rawp)
        return {"i": i, "text": text, "clip": final, "dur": round(duration(final), 3)}

    with cf.ThreadPoolExecutor(max(1, args.jobs)) as ex:
        rows = list(ex.map(one, range(len(beats))))
    save_json({"voice": {k: voice.get(k) for k in ("provider", "voice_id", "model")}, "speed": speed, "lines": rows},
              os.path.join(out, "narration.json"))
    tot = sum(r["dur"] for r in rows)
    print("%d lines, %.1f s of narration (%d:%02d) -> %s" % (len(rows), tot, tot // 60, tot % 60, os.path.join(out, "narration.json")))
    if tot < 80:
        print("NOTE under ~1:30 of speech: the video will be short unless the screen work adds time")
    if tot > 230:
        print("NOTE over ~3:50 of speech: split the section or tighten the lines (target 1.5-4 min)")


if __name__ == "__main__":
    main()
