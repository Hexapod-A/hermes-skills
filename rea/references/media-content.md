# Video, audio and content

A content replica is not measured like an API. Pick the metric before you build it.

## Observe

For video, write a timeline: shot starts/ends, framing, motion, onscreen text, colour, transitions,
subtitle timing. `ffprobe` gives container/stream facts; extract frames with `ffmpeg -vf fps=4`.
For audio, record dialogue transcript and timestamps, loudness over time, silence, peak and codec;
`ffmpeg` can extract mono PCM. A transcript cannot tell you timbre. Save the source when licensed.

For a written article or ad, keep a structure map (hook, claims, proof, CTA) and explicitly state
which parts are facts vs your interpretation. A human editorial review is still needed: a high
pixel score cannot prove meaning, legal claims or tone match.

## Specify and test

- Technical: `media_compare.py original.mp4 replica.mp4 --out compare.json` checks duration,
  frame size/rate, sampled grayscale frames, per-window audio RMS, best timeline offset, SSIM and
  PSNR. Frame and audio checks become cases for `report.py`. Use `--fps 25` for a 40 ms timeline
  resolution rather than the default 250 ms; do not call these checks a complete media score.
- Creative: ask reviewers to score shot order, hook, pacing, voice, mood and meaning on a written
  rubric. Keep their blind ratings and disagreements. Do not average a human rating with PSNR and
  label the result '99.9%'. Report each dimension in its own units.
- Copyright and likeness: use assets you can use; say when a replica uses placeholders.

The `media-clip` demo produces 4-second offline clips. Clean re-encode passes 38/38 technical
checks (SSIM 0.971188); a cut starting 0.2 s late fails 24/38 and the coarse timeline finder
reports about 0.25 s. It cannot tell you whether the scene has the same story or timbre.
