---
name: flyer-studio
description: Branded social flyers laid out in HTML/CSS, not AI art.
version: 1.0.0
author: John (Hexapod-A), 3xAgentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [design, flyers, social-media, branding, html, playwright]
    category: creative
    related_skills: [docs-and-pdfs, outreach-and-proposals]
---

# Flyer Studio Skill

Designs on-brand social flyers (feed, portrait, story, 4K) as real layouts: HTML/CSS templates with the brand's own fonts, colours and logo, rendered to PNG by headless Chromium, then machine-checked for overflow, collisions and contrast. It does **not** generate images with AI models; that is the whole point.

## When to Use

- "Make a flyer / post / carousel / story for 3xAgentic (or another brand in `brands/`)".
- Announcements, offers and pricing, stats/proof, testimonials, checklists, multi-slide carousels.
- Resizing an existing flyer to another format (same spec, different `--sizes`).

Not for: photo editing, illustrations, or anything that needs generated imagery. If a brief truly needs a photo, ask the user for one and place it in the layout.

## Prerequisites

- Node 18+ and the repo's Node deps: run `npm install` once in the repo root, then `npx playwright install --with-deps chromium`.
- A brand kit in `${HERMES_SKILL_DIR}/brands/<brand>/` (see `references/brand-kit.md`). `3xagentic` ships ready.

## How to Run

1. Write a spec JSON (copy one from `${HERMES_SKILL_DIR}/examples/` with `read_file`, then edit with `write_file`). Work in a scratch dir, e.g. `~/flyers/<job>/spec.json`.
2. Render with `terminal`:

       node ${HERMES_SKILL_DIR}/scripts/render.mjs ~/flyers/<job>/spec.json --out ~/flyers/<job> --sizes square,portrait,story --sheet

3. Read the printed summary (or `<name>-report.json`). Exit code `0` = every check passed, `2` = blocking errors.

## Quick Reference

| Layout | Use for | Key content fields |
|---|---|---|
| `announcement` | launches, hooks, one big message | `headline`, `body`, `eyebrow`, `tag`, `cta`, `align: center\|left` |
| `offer` | a price or a tier table | `headline`, `price`, `price_from`, `price_note`, `bullets[]` or `tiers[{name,price,note,featured}]` |
| `stat` | proof with a number | `stat`, `stat_label`, `body`, **`source` (required)** |
| `quote` | testimonials | `quote`, **`name` (required)**, `role`, `avatar` (image path) |
| `carousel` | multi-slide posts | `slides[]`, each like an announcement plus `num`, `bullets[]` |
| `checklist` | "what we handle" lists | `headline`, `items[]` (3–5) |

Sizes: `square` 1080×1080, `portrait` 1080×1350, `story` 1080×1920, `square-4k` 4320×4320, `portrait-4k` 4320×5400, `story-4k` 2160×3840.

Copy markup: `*word*` turns a word accent-coloured; `\n` forces a line break (use it to balance 2-line headlines). Options per spec or per slide: `decor: corner | edge | stairs | none`, `cta_style: pill | url`, `max_lines`, and a `css` string for one-off tweaks.

## Procedure

1. **Brief.** Get the goal, audience, the one message, and the CTA. Pull facts only from the user or a cited source. Never invent stats, client names, quotes or results; leave a visible `REPLACE` note instead and tell the user.
2. **Copy first.** Headline ≤ 8 words in Title Case, body ≤ 25 words, one idea per flyer. Follow `voice` in the brand's `brand.json` (for 3xAgentic: AI automation only, never blockchain or crypto wording).
3. **Pick a layout** from the table. Vary between centered (`align: center`, corner blocks) and left-aligned (`align: left`, edge blocks) across a series.
4. **Render** all requested sizes with `--sheet`.
5. **Self-check loop (mandatory).** Fix every `ERROR` in the report, then re-render:
   - `overflow-x`, `content-too-tall`, `too-many-lines`, `shrunk-to-min` → shorten copy first; then drop an optional field (eyebrow, a bullet); only then use a taller size.
   - `text-overlap`, `decor-overlap` → shorten copy, change `decor`, or switch `align`.
   - `low-contrast` → never put text on the accent or on decor; use `fg` on `bg`.
   - `font-not-loaded`, `image-missing` → fix the path in `brand.json` / spec.
   - `claim-without-source`, `quote-without-attribution` → get the real source/person from the user. Do not make one up.
   - Treat `widow` and `shrunk-to-min` warnings as fix-worthy for headlines.
6. **Look at it.** If your model has vision, open the PNG (or the `-sheet.png`) with `vision_analyze` and check: logo crisp and not touching anything, headline reads in 2 seconds, nothing cramped against edges, spacing even, accent used once or twice, decor not covering words, matches the examples' look. If you have no vision, rely on the report and say so.
7. **Deliver** the PNG paths (one per line; the gateway sends them as images). Add `[[as_document]]` on the last line for 4K files so chat apps do not recompress them.

## Never use AI image generation for the layout

Do not call `image_generate` (or any diffusion/image model) to make the flyer, its text, its background or its logo. Generated layouts misspell words, drift off-brand and read as "AI slop". Every pixel comes from HTML/CSS: brand fonts, brand colours, the real logo file and code-drawn shapes. If the user explicitly asks for an AI image *inside* a flyer, place it as a photo in the layout and tell them it is generated.

## Pitfalls

- **Logo placeholder.** `brands/3xagentic/logo.svg` is a placeholder until John's SVG is dropped in; the renderer then falls back to `logo-interim.png` (cropped from his own sample, slightly soft at 4K) and warns `placeholder-logo`.
- **"3x" turning into "3×".** Plus Jakarta Sans swaps `x` between digits for a multiplication sign via contextual alternates; `base.css` turns `calt` off. Keep it off in custom CSS.
- **Fallback fonts** look almost right at a glance. Trust the `font-not-loaded` check, not your eyes.
- **Story safe zones.** Platform UI covers ~200px top and ~250px bottom; the story preset pads for it.
- **Text on images.** If you add a photo, put text on a solid panel, then let the contrast check confirm.
- New layouts: copy a template in `templates/`, keep `data-text` on text and `data-fit data-max-lines data-min` on anything that can grow, so the checks and auto-fit keep working.

## Verification

- `node ${HERMES_SKILL_DIR}/scripts/render.mjs ${HERMES_SKILL_DIR}/examples/announcement.json --out /tmp/flyer-test` exits `0` and writes 4 PNGs (the 4K one is 4320×4320).
- `node ${HERMES_SKILL_DIR}/scripts/selftest.mjs` proves the checker catches a deliberately broken flyer.
- References: `references/brand-kit.md` (adding a brand), `references/design-rules.md` (the 3xAgentic look and layout rules).
