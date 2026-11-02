# Voice guide: sample, clone, narration

## The message to send for a sample

Short, on the channel the person already uses (voice notes work fine):

> Send me voice notes here:
> - 2 to 3 minutes in total (three notes of about a minute is fine)
> - a quiet room: no fan, generator, TV or traffic
> - phone about a hand away from your mouth, not touching your lips
> - talk the way you teach: read part of the course out loud at your normal speed

Reading the actual course material is the best sample: same words, same rhythm, same accent as the finished videos.

## What makes a good sample

| Good | Bad |
|---|---|
| One speaker, steady distance | Moving around, phone in a pocket |
| Natural teaching pace with normal pauses | Rushed reading, or shouting |
| 1-3 minutes of speech after cleaning | Under 45 s (thin, generic clone) |
| Quiet, soft room (curtains, sofa) | Bathroom/kitchen echo |
| Peaks below 0 dB | Clipping (crackles on loud words) |

More than ~3 minutes does not make an instant clone better. If the first sample is noisy, ask for one more note in a quieter room rather than denoising hard: heavy denoise leaves a watery sound that the clone copies.

## Cleaning (voice_prep.py)

`highpass=80` removes rumble and knocks, `lowpass=9000` removes hiss, `afftdn=nf=-25` is a light denoise (`--denoise -20` stronger, `0` off), `silenceremove` shortens long pauses, `loudnorm=I=-18` evens the level. Output: mono 44.1 kHz MP3 192k.

## Cloning (voice_clone.py)

1. **ElevenLabs Instant Voice Clone**: `POST https://api.elevenlabs.io/v1/voices/add` (multipart: `name`, `files`), header `xi-api-key`. Returns `voice_id`. Speak with `POST /v1/text-to-speech/{voice_id}` and the `eleven_multilingual_v2` model, which keeps accents well. Accounts have a cap on custom voices; when it is full the API refuses with `voice_limit_reached`: delete an old clone in the dashboard or use the fallback.
2. **Fallback: MiniMax voice clone on fal.ai**: `POST https://fal.run/fal-ai/minimax/voice-clone` with header `Authorization: Key $FAL_KEY` and `audio_url` (a data URI of the sample works). Returns `custom_voice_id`; speak with `fal-ai/minimax/speech-02-hd` (`voice_setting.voice_id`, `speed`, `language_boost: English`). A custom voice there can expire when unused for about a week; keep the sample and re-clone.
3. `--auto` tries 1 then 2 and saves whichever worked in `voice.json`. The preview line is written next to it: listen before voicing a course.

Only clone a voice with its owner's permission. A stock voice is the last resort, and the user is told before videos go out with it.

## Writing lines for TTS

- One to three short sentences per beat. Each line explains what is on screen during that beat.
- Write code the way it is said: "App dot J S X", "use State", "curly braces", "arrow function". Avoid symbols the model reads literally (`=>`, `{}`, `/`).
- Use the teacher's own examples and words from the source; keep their way of speaking.
- `--speed 1.05-1.1` for a "fast tutorial"; above 1.15 the clone starts to sound rushed.
- Change one line and only that line is regenerated (clips are cached per voice + text).
