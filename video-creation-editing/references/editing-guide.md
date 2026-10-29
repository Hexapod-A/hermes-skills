# Editing guide

Plain rules that make short videos look professional. Break them when the reference does.

## Pacing

- Short-form ads and reels: a new shot every 0.6-1.5 s (about 1 cut per second). Talking heads: cut out pauses and "um"s, punch in (1.1-1.2x crop) every 2-4 s to hide jump cuts.
- Change something every second: a cut, a text change, a zoom, a speed ramp. Static shots longer than 2 s feel slow on a phone.
- Measure the reference with `scene_cuts.py` and match its cuts per second and its shortest/longest shots. Match where the fastest section is (often the first 3 s and the drop).
- Cut on the beat, or a frame or two before it. Cut on action (mid-movement) so cuts feel smooth.

## Structure (15-45 s)

1. Hook, 0-2 s: the most striking picture plus a short line of text that names the problem or promise.
2. Problem or tension, 2-6 s.
3. Proof / demo / product in use: 3-6 fast shots.
4. Result: what changes for the viewer.
5. Call to action, last 2-3 s: one action, readable, logo.

## Shot list template

| # | Time | Length | Picture | Text on screen | Sound |
|---|---|---|---|---|---|
| 1 | 0.0 | 1.0 | Close-up: hands typing, fast | "Still doing this by hand?" | music hit |
| 2 | 1.0 | 0.8 | Screen: inbox with 200 unread | | whoosh |

## Text on screen

- One idea per card, 3-7 words. Two lines max.
- Big: titles 80-110 px, body 54-70 px at 1080 wide. Bold sans, high contrast, box or outline on busy footage.
- Leave each card up long enough to read twice: about 0.3 s per word, at least 1 s.
- Keep the same font, size and position family through the video.

## Footage

- Real beats fake. Use the user's own clips first, then free stock (Pexels, Pixabay, Mixkit, Coverr, Videvo free) at 1080p or 4K. Search for actions ("person typing laptop night", "warehouse worker scanning box"), not ideas.
- Pick shots with motion inside them (people moving, camera moving). Avoid shots with watermarks, other brands' logos, or obvious AI artefacts (melting hands, warped text).
- Generated video is a last resort. When used, keep shots short, avoid faces and text in the generation, and tell the user which shots are generated.
- Match shots: same colour temperature, similar contrast; apply one `grade` across all clips.

## Sound

- Music sets pace: pick tempo first (100-130 BPM for most promos), then cut to it.
- Voice-over clear and close; music under it (ducked); small sound effects (whoosh, click, hit) on cuts and text pops make edits feel finished.
- End on the music's ending or fade over 0.8-1.5 s; never cut mid-note.
- Final mix at -14 LUFS, true peak under -1 dBTP.

## Before sending

- Watch it once at full speed on a phone-sized view, once with sound off (does the text tell the story?).
- `vcheck.py` passes, the contact sheet looks consistent, the first frame is a good thumbnail.
