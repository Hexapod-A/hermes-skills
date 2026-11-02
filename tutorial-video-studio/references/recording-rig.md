# Recording rig and lesson format

## Screen layout (1920x1080)

    +------------------------------+-------------------+
    | code-server (VS Code)        | fake browser      |
    | explorer | editor            | URL bar           |
    |          |                   | live preview      |
    |----------+-------------------| (dev server)      |
    | terminal (opens on demand)   | console drawer    |
    +------------------------------+-------------------+
    caption box: bottom of the browser pane; slides: full screen

The browser pane is an iframe of the real dev server, so hot reload, the Vite error overlay and real clicks all work. The console drawer is filled from the preview's real console messages (Vite's own chatter filtered out).

## Lesson file

    {
      "slug": "05_props", "title": "Props", "kicker": "Lesson 5",
      "project": "~/projects/my-first-app", "preview": "http://localhost:5173",
      "setup": {"files": {"src/App.jsx": "..."}, "delete": ["src/Old.jsx"], "open": ["src/App.jsx"]},
      "beats": [ {"say": "...", "cap": "...", "slide": "<h1>..</h1>", "do": [ ...actions... ], "pad": 0.35} ]
    }

`setup` puts the project in the state the lesson starts from (written before recording). Beat keys: `say` (narration line), `cap` (caption, `null` clears it, `"full": true` centres it), `step` (small label), `slide` (full-screen HTML; the next beat hides it unless it has its own), `pad` (pause after the line).

Actions in `do`, run in order:

| Action | Effect |
|---|---|
| `{"new_file": "src/Welcome.jsx"}` | Explorer: click the folder, New File, type the name |
| `{"open": "src/App.jsx"}` | Quick Open (Ctrl+P) and type the name |
| `{"type": "code...", "budget": 6, "chunk": "char"}` | Type into the editor key by key; without `budget` the beat's narration is spread over the typing; `"chunk": "word"` for long boilerplate |
| `{"goto": 6, "col": "end"}` | Go to line (Ctrl+G), cursor at end or `start` |
| `{"select_lines": [7, 9]}` | Select whole lines (then `type` replaces them, or `key: Delete`) |
| `{"clear": true}` / `{"select_all": true}` | Empty the file / select all |
| `{"save": true}` | Ctrl+S (hot reload follows) |
| `{"term": "npm install", "wait_for": {"file": "node_modules/.package-lock.json"}}` | Focus terminal, type the command, Enter, then wait for a file / `{"url": ...}` / seconds |
| `{"term_new": true}` | A second terminal (e.g. `npm install axios` while the dev server runs) |
| `{"term_keys": ["ArrowDown", "Enter"]}` | Answer an interactive prompt (create-vite asks questions) |
| `{"preview": "http://localhost:5173"}` / `{"reload": true}` | Show or reload the browser pane |
| `{"click": "button", "times": 3}` | Click in the preview |
| `{"fill": "input", "text": "Ada"}` | Type into a form field in the preview |
| `{"console": "show"}` / `"hide"` / `"clear"` | Console drawer |
| `{"palette": "View: Toggle Terminal"}` | Any VS Code command by name |
| `{"key": "Control+z"}` / `{"wait": 1.5}` / `{"mouse": [x, y]}` | Single key, pause, move the pointer |

## Timing rules

- Narration is generated first; each beat lasts at least as long as its line plus `pad`, so the voice never runs into the next step.
- Typing speed: per-key jitter, longer pauses at line ends and after `; { } ( )`, an occasional pause on a new line, fast indentation. Clamped to 28-140 ms per key so it never looks like a paste or a crawl.
- If the screen work is much longer than the line, the recorder warns: write a second line for that part, or split the action into two beats.
- Holds in `assemble.py` freeze the last frame of a beat when the line is longer than its screen time (common after re-voicing). Keep them under ~2 s; longer holds look stuck.

## Showing real errors on purpose

Make the mistake in a beat, save, let the real result show (Vite's red overlay for a syntax error such as two root tags, a console warning for a lowercase component, "X is not defined" for a missing import, a function call firing on render for `onClick={sayHi()}`), name it in the line, fix it in the next beat. Real errors teach better than slides of errors, and they prove the code is live.

## Re-voicing old videos

1. `narrate.py` with the new `voice.json` into the same work folder (new clips, new lengths).
2. `assemble.py WORK --raw WORK/raw.mkv` again: same picture, new voice, holds where lines grew.
3. Without the raw file, pass the old finished video as `--raw` with a timeline of its beat starts (and no second title card).

## Low-resource box rules

- One recording or encode at a time; the recorder itself is `ultrafast` x264 at 25 fps.
- `ffmpeg -threads 2`, every long command under `timeout -k 5 N` (SIGKILL if SIGTERM is ignored).
- Servers start detached with output to log files; never capture the output of something that keeps running.
- Delete `raw.mkv`, `tmp_assemble/` and frame grabs once a video is approved; `rig.sh stop` at the end (Chromium + code-server hold about 1 GB).
- Check `df -h` before a series: each video needs a few hundred MB of working space while it is made (the raw recording is the big part).
