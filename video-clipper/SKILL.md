---
name: video-clipper
description: Vertical captioned shorts from long videos.
version: 1.0.0
author: John (Hexapod-A), 3xAgentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [video, ffmpeg, yt-dlp, whisper, captions, shorts, reels]
    category: media
    related_skills: [flyer-studio]
---

# Video Clipper Skill

Turns a long video (YouTube/any yt-dlp link or a local file) into 9:16 shorts: downloads, finds the moments from a timestamped transcript, cuts them frame-accurately, reframes to 1080×1920 (crop or blurred background), and burns in word-timed captions with the current word in the brand accent. All local, open-source tools; no AI video generation.

## When to Use

- "Clip the best 30 seconds of this podcast/interview for Reels/TikTok/Shorts."
- Adding captions to a video, or converting landscape to vertical.
- Pulling a transcript with timestamps from a video.

## Prerequisites

- `ffmpeg` (with libass), `yt-dlp`, and the repo venv with `faster-whisper` (see README). First run downloads the Whisper model (~75 MB `tiny`, ~250 MB `base`, ~500 MB `small`).
- Only clip content John owns or has the rights to use.

## How to Run

    PY=${HERMES_SKILL_DIR}/../.venv/bin/python
    # 1. get the file
    $PY ${HERMES_SKILL_DIR}/scripts/clip.py download "https://www.youtube.com/watch?v=..." --out ~/clips/src
    # 2. transcript with timestamps -> pick moments
    $PY ${HERMES_SKILL_DIR}/scripts/clip.py transcribe ~/clips/src/video.mp4 --model small --out ~/clips/src/transcript.json
    # 3. make the short
    $PY ${HERMES_SKILL_DIR}/scripts/clip.py make --input ~/clips/src/video.mp4 --start 00:12:05 --end 00:12:41 --vertical crop --x 0.5 --captions --out ~/clips/short-01.mp4

## Quick Reference

| Flag | Meaning |
|---|---|
| `--vertical crop` | fill 9:16 by cropping; aim with `--x` (0 = left edge, 0.5 = centre, 1 = right) |
| `--vertical blur` | whole frame centred over a blurred copy (good for screen shares, two-person shots) |
| `--vertical none` | keep the original aspect |
| `--captions` | word-timed burned-in captions; `--words 3` per line; `--accent FF9900` |
| `--model tiny\|base\|small\|medium` | Whisper size: bigger = more accurate, slower |
| `--font`, `--font-dir` | caption font (defaults to the 3xAgentic Plus Jakarta Sans files in flyer-studio) |

## Procedure

1. **Source.** Download with `clip.py download` (or use the local file the user sent).
2. **Find moments.** Run `transcribe`, read the JSON with `read_file`, and pick 1–3 self-contained moments of 20–60 s: a strong first sentence (hook), one idea, a clean ending. Prefer starting on a sentence start and ending after a full stop.
3. **Frame.** Check where the speaker sits: extract a frame (`ffmpeg -ss <t> -i in.mp4 -frames:v 1 frame.png` via `terminal`) and look at it with `vision_analyze` if available. Set `--x` so the face is centred; use `blur` if two people or a screen must stay in view.
4. **Make** each short with `--captions`.
5. **Check.** The script prints width/height/duration and the caption count. Pull a frame from the middle and view it: captions readable, not covering the face, inside the safe area (lower third, above the platform UI). Spot-read the transcript JSON for misheard names and re-run with a bigger `--model` if needed.
6. **Deliver** the MP4 path(s) with the start/end times used and the hook line.

## Pitfalls

- YouTube sometimes blocks server IPs or needs cookies: run `yt-dlp --cookies-from-browser` or pass `--cookies cookies.txt` (export from John's browser). Never commit cookies.
- `crop` on a wide two-person shot cuts someone off; use `blur` or two separate clips.
- Whisper mishears brand names (e.g. "3xAgentic"); fix by editing the transcript words and regenerating, or use `--language en` and a bigger model.
- Long sources: transcribe once and reuse the JSON; don't re-transcribe for every clip.

## Verification

- `ffprobe -v error -show_entries stream=width,height -of csv=p=0 short.mp4` prints `1080,1920`.
- A middle frame shows captions with one word in orange.
