# Media replica (bug)

**Measured fidelity: 14/38 checks = 36.842%**. Random sample: 0/0; one-sided 95% lower bound: 0.000%.

**99.9% claim for the declared random input distribution: NOT SUBSTANTIATED.** Reasons: 24 of 38 cases fail; fix the mismatch before a fidelity claim | no independently generated random cases; hand-picked checks do not support a statistical claim

## What the number means

- Metric: check pass rate: container facts, frames every 0.25 s (32x18 grey, mean diff <= 6), audio RMS every 0.25 s (<= 1.5 dB).
- Scope: the cases in this run only. It says nothing about inputs outside that set.
- Cases by source: audio 16, frame 16, meta 6
- Plan seed: n/a (re-run with the same seed for the same cases).
- Independently generated random cases needed for a 99.9% claim with 0 failures: 2995.
- Fixed, pairwise and boundary cases are failure gates, not confidence-sample size. A predeclared random generator is the measured distribution; a tuned or cherry-picked run cannot certify future production traffic. Do a fresh holdout for a new version.

## Comparison rules (what was NOT compared exactly)

- why: frames at 4 fps, 32x18 grey, tol 6; audio RMS per 0.25s, tol 1.5 dB; duration tol 0.040s

## By dimension

| Dimension | Passed | Rate |
|---|---|---|
| audio | 8/16 | 50.00% |
| frame | 0/16 | 0.00% |
| meta | 6/6 | 100.00% |

## Mismatch clusters

1. 16 cases, at frame_mad (value). Guess: replica content runs 0.25 s ahead of the original (its cut starts late); resolution 0.25 s, raise --fps for finer. Smallest: `{"t": 0.0}`
2. 8 cases, at rms_db (value). Guess: replica content runs 0.25 s ahead of the original (its cut starts late); resolution 0.25 s, raise --fps for finer. Smallest: `{"t": 0.0}`

## Untested edges (not covered by this score)

- colour accuracy (frames are compared in grey)
- fine detail below 32x18 (see ssim/psnr info)
- audio pitch and timbre (only loudness per window is compared)
- subtitles, chapters, metadata tags
