# Case: pow-platform (Oct 2026)

John's school platform (Next.js App Router + TypeScript + Tailwind) was built to match two Dribbble shots, with the homepage taken from two Webflow sites. Live: https://pow-platform.vercel.app (demo data).

## References

| Screen | Reference | How it was prepared |
|---|---|---|
| Dashboard | dribbble.com/shots/23956256 | original PNG 3228×2638 (transparent areas on white). The backdrop is not flat, so `--trim` does not find the frame; crop by hand (197,181,3037,2178), scaled to 1440×1013 |
| Peer page | dribbble.com/shots/27776892 | original PNG 6532×4452 on a plain backdrop; cropped to the app frame, scaled to 1440×989. `prep_ref.py --trim` finds the same box (384,248,6144,4208) |
| Homepage | uni-learn.webflow.io, graide-new.webflow.io | full-page screenshots at 1440 |

## What worked

- Getting the original upload, not the 752px preview: strip the `?resize=` query from the `cdn.dribbble.com/userupload/...` URL. The page itself is behind a bot wall; the r.jina.ai reader returned the media URLs.
- Scaling the reference to the target viewport (1440 wide) and screenshotting the build at exactly that size, so the two images line up pixel for pixel.
- Colours sampled from the reference into the Tailwind config, with a comment naming the source file.
- Two fonts: the dashboard shot reads as Outfit, the peer shot as Manrope; each screen got its own.
- Real people photos (stock, background removed) instead of the 3D cartoon avatars in the peer shot, because John dislikes cartoon placeholders. This was said to John up front.

## What went wrong

- `next/font/google` failed during the Vercel build (font fetch). Fix: woff2 files in `public/fonts` + `@font-face` in `globals.css`. Same look.
- Vercel refused Next 15.5.4 (`VULNERABLE_NEXTJS_VERSION`). Fix: 15.5.28 / React 19.1.10.
- Git-triggered deploys of commits authored by a name not on the Vercel team came back BLOCKED.
- The first report to John said the dashboard matched "closely"; when he asked, the honest list of gaps was: event cards built differently, lock buttons black instead of white, no music notes on the purple card, different top-bar icons. That list should have come with the first report. This skill's step 6 makes it standard.

## Scores (diff_score.py, Oct 18 2026, live production vs prepared refs)

| Pair | ssim | layout | colour | pixels differ | restyle preset |
|---|---|---|---|---|---|
| dashboard build vs dashboard ref (1440×1013) | 0.7525 | 0.8489 | 95.0 | 12.9% | PASS |
| peer build vs peer ref (1440×989) | 0.6737 | 0.6801 | 88.4 | 24.9% | FAIL |
| peer build vs dashboard ref (control) | 0.6817 | 0.5347 | 86.1 | 35.6% | FAIL |
| dashboard build vs peer ref (control) | 0.6478 | 0.5207 | 83.7 | 35.9% | FAIL |

The `restyle` thresholds were set from the dashboard pair and the two controls. The dashboard worst tiles were the bottom row (event cards, lock buttons) and the right column: the same gaps found by eye. The peer page fails: the reference keeps a white outer margin and a black rounded frame that the build does not have, its 3D avatars were swapped for photos, and its content differs. The worst tile is the middle of the page (ΔE 30), where the large 3D figure in an orange top was swapped for a smaller photo. Treat that as open work, not a pass.
