---
name: tutorial-video-studio
description: Turn course notes or a PDF into screen-recorded coding tutorial videos, narrated in the teacher's own cloned voice.
version: 1.0.0
author: John (Hexapod-A)
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [video, tutorial, screen-recording, voice-clone, tts, elevenlabs, code-server, vscode, vite, react, ffmpeg, xvfb, playwright, whatsapp]
    category: media
    related_skills: [video-creation-editing, video-clipper, frontend-build, persistent-problem-solving]
---

# Tutorial Video Studio Skill

Makes a series of real coding tutorial videos from a course document: one video per section, the code typed live in VS Code like a person types it, commands run in a real terminal, the result shown in a browser next to the editor, and the narration spoken in the teacher's own cloned voice. Everything runs on a headless Linux box: a virtual screen (Xvfb), VS Code in the browser (code-server), the project's dev server, Chromium, Playwright to drive the keyboard and mouse, and ffmpeg to record and assemble.

Worked example used below: a "React for Absolute Beginners" PDF turned into 12 videos (Before You Start, Set Up a Vite project, JSX, Components, Props, State, Events, Conditions and Lists, Forms, useEffect, a Todo App project, Common Mistakes), each 1.5-4 min, 2.5-5.5 MB, 1080p, sent one by one on WhatsApp.

## When to Use

- "Turn this PDF / these notes into tutorial videos", "one video per section", "make it a fast tutorial".
- "Use my voice for the voiceover", "here is a voice sample, clone it".
- "Type the code like a human and run the commands in the terminal, it must show in the video."
- Re-voicing videos that were made with a stock voice, without recording the screen again.

Not for: talking-head videos, slides-only explainers (use `video-creation-editing`), or cutting clips from a long recording (use `video-clipper`).

## Prerequisites

- Debian/Ubuntu: `sudo apt install -y xvfb ffmpeg fonts-dejavu curl` (ffmpeg 5.1+ with libx264).
- code-server (VS Code in the browser): `curl -fsSL https://code-server.dev/install.sh | sh`.
- Node 18+ and npm for the course project (`npm create vite@latest my-first-app -- --template react`).
- Python 3.9+ with `requests` and `playwright` (both in the repo `requirements.txt`). Chromium: `python -m playwright install chromium`, or any Chrome/Chromium on the box (`CHROME=/path/to/chrome`).
- Voice keys in `~/.hermes/.env` (see `.env.example`): `ELEVENLABS_API_KEY` for the main clone, `FAL_KEY` for the fallback clone-capable model. No keys are needed for a dry run (`--provider dummy`).
- About 2 GB RAM and 1 GB disk free while a video is being made.

## How to Run

    S=${HERMES_SKILL_DIR}/scripts; PY=${HERMES_SKILL_DIR}/../.venv/bin/python
    export WORK=~/tutorial-work
    # 1. voice: clean the voice notes, clone, listen to voice/preview.mp3
    $PY $S/voice_prep.py note1.ogg note2.ogg note3.ogg --out $WORK/voice/sample.mp3
    $PY $S/voice_clone.py $WORK/voice/sample.mp3 --auto --name "Course narrator" --out $WORK/voice/voice.json
    # 2. rig: virtual screen + editor + dev server + browser stage
    bash $S/rig.sh start ~/projects/my-first-app
    # 3. per video: write lessons/04_components.json (see examples/), speak it, record it
    $PY $S/narrate.py lessons/04_components.json --voice $WORK/voice/voice.json --out $WORK/04_components
    $PY $S/record_lesson.py lessons/04_components.json --out $WORK/04_components
    $PY $S/assemble.py $WORK/04_components --out out/04_components.mp4 --title "Components" --kicker "Lesson 4"
    $PY $S/qa_check.py out/04_components.mp4 --frames 6 --sheet out/04_sheet.jpg --project ~/projects/my-first-app
    # 4. when every video is out
    bash $S/rig.sh stop

## Quick Reference

| Script | Does |
|---|---|
| `voice_prep.py NOTES... --out` | Cleans and joins voice notes: rumble/hiss filters, light denoise, long pauses shortened, -18 LUFS, mono MP3. Warns when the sample is too short or clipped. |
| `voice_clone.py SAMPLE --out voice.json` | Instant voice clone. `--provider elevenlabs` (default), `--provider minimax` (fallback through fal.ai), `--auto` tries both. Saves the voice id and speaks a preview line. |
| `narrate.py LESSON --voice --out` | One clip per beat in the cloned voice, cached per line, dead air trimmed, `narration.json` with each clip's length. `--provider dummy` = offline stand-in. `--speed 1.08` for "fast" tutorials. |
| `rig.sh start [PROJECT]` / `stop` / `status` / `shot` | Xvfb `:99` 1920x1080, code-server with tutorial settings, Vite dev server, Chromium in kiosk mode showing `templates/harness.html`, CDP on 9333. All detached, logs in `$WORK/logs`. |
| `record_lesson.py LESSON --out` | Plays the lesson on the stage while ffmpeg records the screen: captions, slides, files created in the explorer, code typed key by key, terminal commands, clicks and typing in the preview, the browser console. Each beat lasts at least as long as its narration. Writes `raw.mkv` + `timeline.json`. `--dry-run` sets the stage only. |
| `assemble.py WORK --out` | Holds frames where a line is longer than its screen time, optional title card, narration placed with `adelay` + `amix`, two-pass loudness to -16 LUFS, H.264/AAC with a bitrate that fits the size limit (default 15 MB). Also the re-voice step. |
| `qa_check.py VIDEO` | Size, codec, resolution, fast start, length, LUFS/true peak, silent stretches, black frames, frames + contact sheet to look at, `--project` runs `npm run build`. Exit 2 on FAIL. |
| `templates/harness.html` | The recording stage: editor left (1190 px), fake browser right (726 px) with URL bar and console drawer, slide overlay, caption box, step label. |
| `templates/code-server-settings.json` | Editor settings for typing on camera (no auto-closing brackets, no auto-indent, no suggestions, big font, quiet UI). |
| `examples/lesson.example.json` | A full lesson: title slide, new component file typed live, import, reuse, a real console warning made on purpose and fixed, practice slide. |
| `references/voice-guide.md` | The message to send for a voice sample, what makes a good sample, clone providers and their limits, writing lines for TTS. |
| `references/recording-rig.md` | Lesson file format (every action), timing rules, layout, how real errors are shown, re-voicing, low-resource box rules. |

## Procedure

1. **Take the request.** Get the source (PDF, notes, an outline or just a topic) and read all of it before planning. Ask only what changes the output, usually one question: one video per section, or one long video? Also note any deadline ("by morning") and the language/accent of the audience. Do not ask about things the source already answers.
2. **Plan from the source, in its order.** One video per section. List for each: the concepts, the exact code examples and file names from the source (use them as written, do not "improve" them), the commands, the mistake to show, the practice task. Keep the teacher's words and examples; trim, do not rewrite the course.
3. **Voice first.** Ask for the sample (text in `references/voice-guide.md`: 2-3 minutes of voice notes, quiet room, phone about a hand away, reading the course out loud in a normal teaching voice). Run `voice_prep.py`, then `voice_clone.py --auto`. Listen to the preview and one real line. If the first provider refuses (account full of custom voices, plan limit), the script falls back to the second clone-capable model; a stock voice is the last resort and the user is told.
4. **Set up the rig and the project.** `rig.sh start PROJECT`, then `rig.sh shot` and look at the screenshot. For a "set up the project" lesson, start without the dev server (`START_VITE=0`) and run `npm create vite@latest`, `npm install`, `npm run dev` on camera in the editor's terminal.
5. **Write the lesson file.** One beat = one narration line + what happens on screen while it is spoken. Short lines (1-3 sentences), plain words, the code read out the way the teacher says it. Put the slide/caption text on screen in short labels ("Step 2: write the component"), not full sentences. Show at least one real error per lesson where the source talks about mistakes: make the mistake on camera, let the real error appear (Vite overlay, console warning), then fix it.
6. **Narrate, then record.** `narrate.py` first: the recorder needs each line's length to pace the beat and spreads the typing across the line. `record_lesson.py` prints, per beat, narration length vs screen time and warns when the screen ran well past the voice.
7. **Assemble and check.** `assemble.py` then `qa_check.py`. Look at the contact sheet and 3+ single frames at full size: code readable, the preview shows what the voice says, captions not covering the code, no toasts or badges in the corners. Fix silent stretches (split the typing or add a line) and re-record that video.
8. **Ship each video as soon as it passes**, with a one-line title ("04 - Components"), in course order. Do not hold the whole series back for the last one. After the last one, a short summary and "tell me the number of any video to fix".
9. **Clean up.** Delete `raw.mkv` and `tmp_*` only once the voice is final (re-voicing needs them), then `rig.sh stop`.

## Pitfalls

- **Editor "helping" while you type.** Auto-closing brackets, auto-indent and suggestions turn typed code into `}}` and doubled indentation. The bundled settings switch them all off; type the indentation as spaces yourself.
- **Silent typing gaps.** A long block typed slowly after a short line = 10 s of clicking keys with no voice. Split big files over several beats with a line each, use `"chunk": "word"` for long boilerplate, or let `"budget"` speed it up. `qa_check.py` lists every silent stretch.
- **Captions ahead of the screen.** A caption that says "Step 3: import it" while the editor still shows the last step reads as a mistake. Put the caption on the beat whose actions do that step, and keep holds (frozen frames) short so the label and picture move together.
- **Re-voicing needs the raw recording.** Old videos made with a stock voice had to be re-voiced in the cloned voice; the cheap way is new narration + `assemble.py` on the same `raw.mkv` and `timeline.json` (holds absorb longer lines). If the raw files were deleted, the only way is to re-time the finished video (no title card on it twice) or record again. Keep raw files until the user has approved the voice.
- **Toasts and badges in the corners.** Notifications ("install recommended extensions"), the Problems badge, the explorer error dots and the account icon show up in frames. The recorder clears notifications before it starts; the settings hide most badges; check the first frame.
- **Clone quality.** The clone copies the room: echo, fan noise and clipping come back in every line. Ask for a better sample rather than denoising harder. Keep the speaker's accent; do not pick an accent-neutralising model setting.
- **Clone expiry and limits.** Some providers drop a custom voice that is unused for days, and accounts have a cap on custom voices. Keep the cleaned sample and re-clone in one command when a voice id stops working.
- **Backgrounded servers hanging the agent.** Never capture the output of a command that leaves a server running (`npm run dev &` inside a captured shell waits forever on the pipe). `rig.sh` starts everything detached with logs in files.
- **Weak box.** One recording or encode at a time, `ffmpeg -threads 2`, every long command under `timeout -k 5 N`, raw recordings as `ultrafast` x264 (a few MB/min, not raw video), temp files removed after each video.
- **WhatsApp size.** 16 MB per video. `assemble.py` sizes the bitrate from the length; screen recordings usually land at 1-2 MB per minute at 1080p, so a 4-minute lesson is far under.
- **Loudness.** One-pass `loudnorm` on speech with pauses lands several LU low; `assemble.py` measures first, then applies.

## Verification

- `python3 ${HERMES_SKILL_DIR}/tests/test_pipeline.py` makes a synthetic recording, speaks a 4-beat lesson with the dummy voice (one line longer than its screen time), assembles it with a title card and checks: the long line got a hold, the next line starts after it, length = recording + title + holds, H.264 1080p, -16 LUFS, fast start, contact sheet. It prints PASS lines and `all passed`. No keys, no display needed.
- Full rig smoke test: `rig.sh start` on a fresh Vite React app, `narrate.py examples/lesson.example.json --provider dummy`, `record_lesson.py`, `assemble.py`, `qa_check.py --project`. On a 4-core / 4 GB box this took about 2 minutes for a 1:30 lesson and produced a 2.3 MB 1080p file with the component typed live, the greeting repeated in the preview and the real lowercase-tag warning in the console.
