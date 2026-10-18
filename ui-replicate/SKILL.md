---
name: ui-replicate
description: Rebuild a UI from an image or URL and prove the match.
version: 1.0.0
author: John (Hexapod-A), 3xAgentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [design, ui, frontend, tailwind, nextjs, playwright, dribbble, pixel-match, responsive]
    category: creative
    related_skills: [flyer-studio, web-research]
---

# UI Replicate Skill

Turns a design reference into working front-end code that looks the same: a Dribbble/Behance shot, a screenshot, or a live website. The method is measure first, build tokens and components, then prove the match with a headless-browser screenshot at the reference's exact size, a side-by-side sheet and a diff score. It loops until the score passes and then says plainly what still differs.

Built from the pow-platform job (Oct 2026): two Dribbble shots and two Webflow sites rebuilt in Next.js + Tailwind. See `references/case-pow-platform.md` for what happened and the real scores.

## When to Use

- "Make it look exactly like this" + an image, a Dribbble/Behance link, or a website URL.
- Restyling an app to a reference while keeping your own content (restyle), or copying a page 1:1 (clone).
- Checking how close an existing build is to its design ("is this really the same?").
- Making a desktop-only design work on a 390px phone without losing its look.

Not for: logos, illustrations or AI-generated mockups. Do not ship another designer's artwork, photos or paid fonts in the product; the reference is for study.

## Prerequisites

- Repo Node deps and Chromium (README steps 3): `npm install`, `npx playwright install --with-deps chromium`. To use another Chrome binary, set `CHROME_PATH`.
- Repo venv (README step 4). This skill needs `requests`, `Pillow`, `numpy` (all in `requirements.txt`). No scikit-image: SSIM is computed in numpy.
- A running build to check: `npm run dev`, a preview URL, or production.

## How to Run

    S=${HERMES_SKILL_DIR}/scripts; PY=${HERMES_SKILL_DIR}/../.venv/bin/python
    # 1. get the reference
    $PY $S/fetch_ref.py "https://dribbble.com/shots/23956256-..." --out ~/ui/job/refs --name dash
    $PY $S/prep_ref.py ~/ui/job/refs/dash-1.png --trim --width 1440 --out ~/ui/job/refs/ref_1440.png
    #    or, for a live site:
    node $S/screenshot.mjs https://site.com --out ~/ui/job/refs --name site --widths 1440,390 --clean
    node $S/extract_styles.mjs https://site.com --out ~/ui/job/styles --fonts
    # 2. measure
    $PY $S/palette.py ~/ui/job/refs/ref_1440.png --k 12
    $PY $S/grid_overlay.py ~/ui/job/refs/ref_1440.png --out ~/ui/job/refs/grid.png
    # 3. build (tokens -> components -> pages), then 4. verify, repeat until PASS
    bash $S/verify.sh ~/ui/job/refs/ref_1440.png http://localhost:3000/dashboard ~/ui/job/check --name dashboard

`verify.sh` exits `0` on pass and `2` when below the threshold. It writes `<name>-sbs.jpg` (reference | build | mismatch), `<name>-blend.png` (50/50 overlay) and `<name>-report.json`.

## Quick Reference

| Script | Does |
|---|---|
| `fetch_ref.py URL --out DIR` | Full-res download from Dribbble (strips `?resize=`, reads through r.jina.ai when the page walls bots), Behance (largest module size), og:image of any page, or a direct image. `--video` for motion shots. |
| `prep_ref.py RAW --trim --width 1440` | Cuts the plain backdrop (`--trim`) or a box (`--crop x0,y0,x1,y1`), scales to the viewport width, prints the viewport to render at. |
| `screenshot.mjs URL --out DIR` | PNG per width (`--widths 1440,390`), full page or `--viewport`, `--size-of ref.png` for an exact match, `--clean` hides popups/badges, `--hide "sel"`, `--storage state.json` for logins, `--dpr 2`. Prints horizontal overflow and page errors. |
| `extract_styles.mjs URL --out DIR` | Computed styles of a live page: fonts used, type scale, colours by area, radii, shadows, spacing and base unit, `:root` CSS variables, biggest boxes, images. `--fonts` downloads the used font files. Writes `styles.json` + `styles.md`. |
| `palette.py IMG` | Dominant colours with share. `--at x,y` exact pixel, `--crop` a region, `--compare BUILD` delta-E per colour (ok < 3, close < 8, OFF). |
| `grid_overlay.py IMG --out G` | Labelled px grid to read boxes. `--crop` + `--zoom 2` for small parts. |
| `google_font.py "Family" --out public/fonts --css fonts.css` | Self-hosts a Google font (woff2 + @font-face). |
| `diff_score.py REF BUILD` | `ssim` (detail), `layout` (block positions), `colour` (100 − mean ΔE), `pixels_differ`, worst tiles with px boxes, global offset finder, heatmap. `--preset restyle|clone`. |
| `side_by_side.py REF BUILD --out S` | Labelled sheet, optional heatmap panel and `--blend` overlay. |
| `verify.sh REF URL OUT` | screenshot at the ref's size → diff_score → side_by_side, in one call. |

Score guide (from the pow-platform run, 1440×1013): the accepted dashboard restyle scored ssim 0.75 / layout 0.85 / colour 95.0. A different screen (our peer page) against the dashboard reference scored 0.68 / 0.53 / 86.1. `restyle` passes at 0.72 / 0.84 / 92, `clone` at 0.90 / 0.95 / 97. With your own content in place of the reference's, ssim stays low even when the layout matches (0.75 on that dashboard), so do not chase ssim on a restyle; chase layout and colour.

## Procedure

1. **Ingest.**
   - Image link: `fetch_ref.py`. Keep the original. Find the app frame inside the shot (Dribbble shots often sit on a backdrop or inside a device frame) and make a viewport-sized reference with `prep_ref.py` (`--trim` first; `--crop` if the trim keeps a frame). Write the printed viewport into the spec. Every later screenshot uses it.
   - Live URL: `screenshot.mjs --widths 1440,390 --clean` (full page) and `extract_styles.mjs --fonts`. The site's own numbers beat any measurement from pixels.
   - Screenshot from the user: use it as is; ask for the device width only if it is not obvious (a 1179px-wide phone shot is 393 CSS px at 3x).
2. **Analyse before coding.** Copy `templates/spec-template.md` to the job folder and fill it in: viewport, layout grid with measured px boxes (`grid_overlay.py`, zoom into small parts), palette with hex values (`palette.py`, `--at` on every card, pill and text colour), type scale (sizes, weights, line heights, letter spacing), radius and shadow tokens, icon set, and a list of every component on screen. Name the font (see `references/fonts.md`; pick the closest free font when unknown and write down why). Look at the reference with `vision_analyze` at full size and in zoomed crops; small details (notches, tilted cards, pill shapes, icon weight) are what make it "the same".
3. **Build tokens first.** Colours, fonts, radii, shadows and spacing go into `templates/tokens.css` / `templates/tailwind.tokens.ts` (or the project's own config) before any component. Self-host fonts with `google_font.py`. Then build components from the list, then pages. Use real content from the job (real course names, prices in the right currency, real names), never lorem ipsum. Use real photos for people (licensed stock or randomuser.me in demos), not cartoon or silhouette placeholders, unless the user asks for the reference's illustration style.
4. **Verify loop.** Run `verify.sh` with the reference and the page URL. Read the numbers, then look at the sheet and the heatmap with `vision_analyze`. Fix in this order: global offset note (outer margins, header height, wrong crop) → worst tiles (layout and size) → colours flagged OFF by `palette.py --compare` → type (size, weight, line height) → radius/shadow/icon details. Re-run after each round. Stop when it passes and the sheet looks the same to the eye; a passing score with an obvious visual miss is not done.
5. **Responsive.** Follow `references/responsive.md`: same tokens, same components, reflow the grid, keep the signature details. Check 390px with `screenshot.mjs --widths 390` and look for `horizontal_overflow: true`.
6. **Report honestly.** Give the user the side-by-side sheet, the scores, and a short list of what still differs and why (content swapped on purpose, photos instead of 3D avatars, an icon not in the free set). Never call it "exact" or "100%" unless `--preset clone` passes.

## Pitfalls

- **Fonts fetched at build time break deploys.** `next/font/google` failed on Vercel's build for pow-platform. Self-host with `google_font.py` and an `@font-face` in the global CSS.
- **Vercel blocks vulnerable framework versions.** Next 15.5.4 was refused (`VULNERABLE_NEXTJS_VERSION`). Start on the latest patch release and check advisories before deploy.
- **Vercel blocks git deploys from unknown commit authors.** Commits authored by a name that is not on the Vercel team come back BLOCKED; commit as the account owner or deploy through the API.
- **Dribbble walls bots.** A plain fetch gets HTTP 202 with an empty body. `fetch_ref.py` falls back to the r.jina.ai reader. Thumbnails of other shots on the page are skipped on purpose.
- **Wrong crop = wrong score.** If the reference keeps backdrop or a device frame, every box is offset and layout drops. The pow-platform peer reference kept a white outer margin and a black rounded frame that the build does not have (layout 0.68). When the whole build is shifted, `diff_score.py` prints a "build content sits about dx/dy" note; re-crop or fix margins first.
- **Popups ruin live-site captures.** Webflow templates show promo modals and badges. Use `--clean` or `--hide`.
- **Placeholder people look cheap.** Cartoon avatars and grey silhouettes read as unfinished. Real photos; cut out the background only when the reference uses cut-outs.
- **Two fonts in two references.** If two reference screens use different fonts, match each screen and say so, or ask which one wins.
- **Mock data drifts.** Demo data that changes on clicks makes screenshots differ between runs. Freeze the seed or log in as a fixed demo user before verifying.
- **Do not copy assets.** Recreate icons from a free set (Iconsax, Lucide, Phosphor) and draw shapes in CSS/SVG. Paid fonts found by `extract_styles.mjs --fonts` are for identification only.

## Verification

- `python3 ${HERMES_SKILL_DIR}/tests/test_scripts.py` prints 11 PASS lines and `all passed` (offline, synthetic images).
- `node ${HERMES_SKILL_DIR}/scripts/screenshot.mjs https://example.com --out /tmp/uir --widths 1440,390` writes two PNGs and prints `"horizontal_overflow":false`.
- Full loop on a real page: see the example in `examples/pow-dashboard/README.md`.
- Files: `templates/spec-template.md` (the analysis spec), `templates/tokens.css` and `templates/tailwind.tokens.ts` (token starters), `references/fonts.md` (font matching), `references/responsive.md` (desktop to 390px), `references/case-pow-platform.md` (the real job and its scores).
