# Media clip example (offline)

Run `python3 run_demo.py` (needs ffmpeg + ffprobe with libx264/aac). It generates a 4-second
pattern and beep, re-encodes it as a clean replica and makes a second cut starting 0.2s late.
The technical comparison checks container facts, 16 low-res sampled frames, 16 audio RMS windows,
SSIM/PSNR and best timeline offset.

Verified 2026-10-18: clean 38/38 checks, SSIM 0.971188. Late cut 14/38 checks, SSIM 0.775037;
shift detector estimated 0.25s late at its default 4fps resolution. No independent random cases
were run, so **99.9% is NOT substantiated**. The metric does not prove colour/detail fidelity,
subtitle timing, voice timbre or creative meaning. Increase `--fps` and add a human rubric when
those matter.
