---
name: video-creation-editing
description: Plan, edit and check short videos with ffmpeg.
version: 1.0.0
author: John (Hexapod-A)
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [video, editing, ffmpeg, reels, shorts, tiktok, captions, transitions, color-grade, loudness, whatsapp]
    category: media
    related_skills: [video-clipper, flyer-studio, persistent-problem-solving]
---

# Video Creation & Editing Skill

Makes finished short videos (ads, reels, promos, explainers, edits that copy a reference's style) from a brief, a reference video, or raw footage and photos. The method: read the brief and the reference, write a shot list, get real footage first, build from an edit list with `assemble.py`, then check the file with `vcheck.py` and by looking at frames before sending. All local, open-source tools.

`video-clipper` cuts shorts out of one long video. This skill builds a new edit from many pieces.

## When to Use

- "Make a 20-second reel/ad/promo from these clips/photos."
- "Edit it like this video" (copy pacing, cuts, text style, transitions of a reference).
- Adding text, captions, music, voice-over, colour grade, speed ramps, Ken Burns motion to photos.
- Changing aspect ratio (9:16, 1:1, 4:5, 16:9) or shrinking a video under a size limit (WhatsApp 16 MB).
- Checking a video before sending: right size, audio level, no black or silent gaps.

## Prerequisites

- `ffmpeg` and `ffprobe` (5.1 or newer, with libx264, libass, freetype): `sudo apt install -y ffmpeg` or `brew install ffmpeg`. Check: `ffmpeg -filters | grep -E "xfade|subtitles|drawtext"`.
- Python 3.9+ with `Pillow` (repo venv, already in `requirements.txt`) for contact sheets.
- `yt-dlp` (in `requirements.txt`) to fetch a reference video or stock clips from a link.
- A bold font file for titles. The scripts find one with `fc-match`; set `FONT_FILE=/path/Font-Bold.ttf` or `"font"` in the edit list for the brand font.

## How to Run

    S=${HERMES_SKILL_DIR}/scripts; PY=${HERMES_SKILL_DIR}/../.venv/bin/python
    # 1. read a reference edit (cuts, shot lengths, pacing) + one frame per shot
    yt-dlp -f "bv*[height<=1080]+ba/b" -o ~/vid/ref.%(ext)s "https://www.instagram.com/reel/..."
    $PY $S/scene_cuts.py ~/vid/ref.mp4 --sheet ~/vid/ref_shots.jpg --json ~/vid/ref_cuts.json
    # 2. write ~/vid/edit.json (see examples/edit.example.json), then build
    $PY $S/assemble.py ~/vid/edit.json --out ~/vid/final.mp4
    # 3. check it
    $PY $S/vcheck.py ~/vid/final.mp4 --target vertical --sheet ~/vid/final_sheet.jpg
    # 4. fit under WhatsApp's 16 MB when needed
    $PY $S/export_size.py ~/vid/final.mp4 --mb 15 --out ~/vid/final_wa.mp4

## Quick Reference

| Script | Does |
|---|---|
| `scene_cuts.py REF` | Cut times, shot lengths, cuts per second, fastest 5 s window, an edit-list skeleton with the same rhythm. `--sheet` = one labelled frame per shot. `--threshold 0.2` for soft footage, `0.4` for shaky/flashy. |
| `assemble.py edit.json` | Builds the video: cuts, `speed`, `ramp` (speed ramps), photos with `kenburns`, `color` title cards, `text` overlays with fade, `transition` (cut, fade, any xfade name: slideleft, wipeup, circleopen...), `grade` (eq or a .cube LUT), `voiceover`, `music` with auto-ducking under speech, burned `captions` (.srt), two-pass loudness to -14 LUFS, H.264 + AAC + fast start. `--dry-run` checks the list. |
| `vcheck.py OUT` | Size, codec, fps, pixel format, fast start, LUFS + true peak, silence, black frames, frozen frames, contact sheet. `--target vertical|square|landscape|whatsapp`. Exit 2 on any FAIL. |
| `export_size.py IN --mb 15` | Two-pass encode at the bitrate that fits; steps down to 720p if 1080p would look blocky. `--aspect 9:16 --fit crop|pad|blur` re-frames too. |
| `references/ffmpeg-recipes.md` | One-line commands for everything else: trims, freeze frames, reverse, zoom punch-ins, LUTs, J/L cuts, beat timing, GIFs, thumbnails. |
| `references/editing-guide.md` | Pacing, hooks, shot lists, text on screen, music, sourcing footage, platform specs. |

## Procedure

1. **Understand the brief.** Who is it for, where it will play (Reels/TikTok 9:16, feed 1:1 or 4:5, YouTube 16:9, WhatsApp), length, the one message, the call to action, brand font and colours. If a reference video is given, the reference sets the style: download it and look at it before planning.
2. **Read the reference.** `scene_cuts.py` gives the rhythm (e.g. 0.9 cuts/s, median shot 0.8 s). Look at the `--sheet` with `vision_analyze`: shot types (close-up, wide, screen, product, text card), text style and position, colour look, transitions. Listen for music style and where the beat drops. Write this down in 5-10 lines.
3. **Shot list.** One row per shot: time, length, what is on screen, text on screen, sound. Match the reference's pacing. Open with the strongest shot in the first second (the hook). Keep each shot doing one job. See `references/editing-guide.md`.
4. **Get the footage, real first.** Order: the user's own footage and photos → free stock (Pexels, Pixabay, Mixkit, Coverr; fetch with `yt-dlp` or the site's download link at the highest quality) → screen recordings → generated footage only when nothing real fits, and say so. Keep a `sources.txt` with each file's link and licence. Download more than needed so you can pick.
5. **Write the edit list** (`edit.json`). Start from `scene_cuts.py`'s `edl_skeleton` when copying a reference. Use real in/out points (scrub with frame grabs: `ffmpeg -ss 12.4 -i clip.mp4 -frames:v 1 f.jpg`). Put the brand font in `"font"`.
6. **Build** with `assemble.py`. First a fast draft (`"preset": "veryfast"`), then the final.
7. **Check, then fix.** `vcheck.py --sheet` and look at the sheet and 3-4 single frames at full size: text inside the safe area (not under the platform buttons: keep important text out of the top 12% and bottom 20% on 9:16), text readable on a phone, no black flashes, faces not cut off, colours consistent across shots. Listen: music not louder than speech, no clicks at cuts, ending not cut mid-note. Fix and rebuild until clean.
8. **Export** for the place it will be posted (`export_size.py` for WhatsApp/email). Run `vcheck.py --target whatsapp` on the exported file.
9. **Deliver** the file with: length, size, what footage came from where, and anything you could not match from the reference.

## Pitfalls

- **Mixed sources break joins.** Different sizes, frame rates, sample rates or SAR make concat/xfade fail. `assemble.py` normalises every clip first; do the same by hand (`scale,fps,setsar=1,format=yuv420p` and `aresample=48000`) when you build your own command.
- **Odd sizes.** H.264 yuv420p needs even width and height. Use `scale=-2:1080`, never `-1`.
- **Seeking.** `-ss` before `-i` is fast and accurate when re-encoding. With `-c copy` it snaps to the nearest keyframe, so cuts land early; re-encode for exact cuts.
- **Cross-fades shorten the video.** Each fade overlaps two clips by its length. Plan durations with that in mind (`assemble.py` prints the real length).
- **Loudness.** Platforms turn loud audio down and leave quiet audio quiet. Aim for -14 LUFS integrated and a true peak under -1 dBTP. Normalise the final mix, not each clip.
- **Music drowning speech.** Use ducking (`"duck": true`) or keep music around -20 to -25 dB under the voice.
- **Text too small or under UI.** On 9:16 at 1080 wide, body text at least 54 px, titles 80-110 px; 2 lines max; keep 6-8% side margins.
- **Ken Burns jitter.** zoompan on a small image shakes. Upscale first (the script renders at 3x then scales down).
- **Stock that looks fake.** Pick footage with real light and real people; avoid over-graded or AI-looking clips; match colour across shots with one grade.
- **Copyright.** Use music and footage you have rights to (royalty-free libraries, the user's own). Note licences in `sources.txt`.
- **WhatsApp.** Video limit is 16 MB, H.264 + AAC, yuv420p. Bigger files go as documents or a link.

## Verification

- `python3 ${HERMES_SKILL_DIR}/tests/test_video.py` builds a 6.6 s 9:16 video from synthetic clips (cuts, fade, slide, speed ramp, Ken Burns, title card, captions, voice-over, ducked music), checks it is 1080x1920 H.264 yuv420p with fast start at -14 LUFS, finds its shots, and squeezes a 20 s 1080p clip under 2 MB. It prints 11 PASS lines and `all passed`.
- On a real job, `vcheck.py` prints `PASS: all checks passed` or only WARN lines you have looked at and accepted.
