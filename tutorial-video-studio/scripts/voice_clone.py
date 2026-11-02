#!/usr/bin/env python3
"""Create an instant voice clone from a clean sample and save voice.json.

    export ELEVENLABS_API_KEY=...            # primary
    python3 voice_clone.py voice/sample_clean.mp3 --name "Instructor voice" --out voice/voice.json

    export FAL_KEY=...                       # fallback when the first account is full or refuses
    python3 voice_clone.py voice/sample_clean.mp3 --provider minimax --out voice/voice.json

    python3 voice_clone.py --auto voice/sample_clean.mp3 --out voice/voice.json   # try elevenlabs, then minimax

Then it speaks one preview line in the new voice (voice/preview.mp3) - LISTEN to it before
voicing a whole course. Only clone a voice whose owner asked for it.
"""
import argparse
import base64
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from narrate import ELEVEN, FAL, _post_retry, _requests, speak  # noqa: E402
from tvs_util import save_json  # noqa: E402

PREVIEW = "Hello, and welcome. In this lesson we will build it step by step, together."


def clone_elevenlabs(sample, name, desc):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    rq = _requests()
    with open(sample, "rb") as f:
        r = rq.post(ELEVEN + "/voices/add", headers={"xi-api-key": key},
                    files={"files": (os.path.basename(sample), f, "audio/mpeg")},
                    data={"name": name, "description": desc, "remove_background_noise": "false"}, timeout=180)
    if r.status_code != 200:
        # a full account answers 400 with voice_limit_reached: delete an old clone or use the fallback
        raise RuntimeError("elevenlabs clone refused: %s %s" % (r.status_code, r.text[:300]))
    return {"provider": "elevenlabs", "voice_id": r.json()["voice_id"], "model": "eleven_multilingual_v2"}


def clone_minimax(sample, name, desc):
    key = os.environ.get("FAL_KEY")
    if not key:
        raise RuntimeError("FAL_KEY is not set")
    data_uri = "data:audio/mpeg;base64," + base64.b64encode(open(sample, "rb").read()).decode()
    r = _post_retry(FAL + "/fal-ai/minimax/voice-clone", tries=3, timeout=300,
                    headers={"Authorization": "Key " + key},
                    json={"audio_url": data_uri, "noise_reduction": True, "need_volume_normalization": True,
                          "text": PREVIEW, "model": "speech-02-hd"})
    # NOTE: this provider may drop a custom voice that goes unused for about a week: keep the sample, re-clone when needed
    return {"provider": "minimax", "voice_id": r.json()["custom_voice_id"], "model": "speech-02-hd", "language_boost": "English"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sample", help="clean mp3 from voice_prep.py")
    ap.add_argument("--provider", choices=["elevenlabs", "minimax"], default="elevenlabs")
    ap.add_argument("--auto", action="store_true", help="try elevenlabs, fall back to minimax")
    ap.add_argument("--name", default="Tutorial narrator")
    ap.add_argument("--description", default="Calm, clear teaching voice")
    ap.add_argument("--speed", type=float, default=1.05)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    order = ["elevenlabs", "minimax"] if args.auto else [args.provider]
    voice, errors = None, []
    for p in order:
        try:
            voice = (clone_elevenlabs if p == "elevenlabs" else clone_minimax)(args.sample, args.name, args.description)
            break
        except Exception as e:
            errors.append("%s: %s" % (p, e))
            print("clone failed on", p, "->", e)
    if not voice:
        raise SystemExit("no clone made. Tried: " + " | ".join(errors))

    voice.update({"speed": args.speed, "sample": os.path.abspath(args.sample),
                  "created": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")})
    out = os.path.expanduser(args.out)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    save_json(voice, out)
    prev = os.path.join(os.path.dirname(os.path.abspath(out)), "preview.mp3")
    speak(PREVIEW, prev, voice)
    print("cloned on %s, voice id saved to %s; preview: %s" % (voice["provider"], out, prev))


if __name__ == "__main__":
    main()
