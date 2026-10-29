---
name: frontend-build
description: Build fast, responsive, polished web frontends.
version: 1.0.0
author: John (Hexapod-A)
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [frontend, nextjs, react, tailwind, html, css, responsive, design-tokens, performance, accessibility, core-web-vitals]
    category: engineering
    related_skills: [software-engineering-qa, ui-replicate, persistent-problem-solving]
---

# Frontend Build Skill

Builds production front ends that look finished on every screen: Next.js + Tailwind for apps and sites with data, or plain HTML/CSS/JS for simple pages. The method: tokens first, mobile first, real content, components with all their states, then prove it with the QA checks (no errors at 320-1440 px) and a speed check (LCP, CLS, JS size) before calling it done.

To copy an existing design exactly, start with `ui-replicate` (it measures the design and scores the match); this skill is how the code itself is built.

## When to Use

- "Build me a landing page / website / dashboard / web app front end."
- Turning a design, a sketch or a description into real pages.
- Making an existing site responsive, faster, or more polished.
- Picking a stack for a front end and setting it up right.

## Prerequisites

- Node 20+ and npm. For new apps: `npx create-next-app@latest app --ts --tailwind --eslint --app --src-dir --import-alias "@/*"`.
- Repo Node deps + Chromium for checks (README step 3).
- The `software-engineering-qa` skill (its `ui_check.mjs` is the final QA gate).

## How to Run

    S=${HERMES_SKILL_DIR}/scripts; T=${HERMES_SKILL_DIR}/templates
    # plain HTML start: copy the starter + base.css, edit tokens and content
    mkdir -p ~/site && cp $T/base.css $T/starter.html ~/site/ && mv ~/site/starter.html ~/site/index.html
    # Next.js start: create-next-app (above), then put the tokens from base.css :root into app/globals.css
    # run it, then the two gates:
    node ${HERMES_SKILL_DIR}/../software-engineering-qa/scripts/ui_check.mjs http://localhost:3000/ --out ~/qa/ui --links
    node $S/web_vitals.mjs http://localhost:3000/ --runs 3 --out ~/qa/vitals.json      # phone profile
    node $S/web_vitals.mjs http://localhost:3000/ --desktop

## Quick Reference

| File | Use |
|---|---|
| `templates/base.css` | Tokens (colour, fluid type scale, 4 px spacing, radius, shadow, container), modern reset, focus ring, reduced motion, layout helpers (`.container`, `.stack`, `.cluster`, auto-fit `.grid`), button/card basics. |
| `templates/starter.html` | Responsive page skeleton (sticky header, hero, feature grid, stats, form, footer) that passes the QA checks at all 5 widths with 0 warnings. |
| `scripts/web_vitals.mjs URL` | LCP, CLS (with the shifting elements), FCP, TBT, bytes by type, oversized images, unsized images, lazy-loading mistakes, render-blocking files, font count. Phone profile by default (4x slower CPU, fast 4G). Exit 2 when over budget. |
| `references/checklist.md` | The finish checklist: layout, type, spacing, images, states, accessibility, SEO, performance. |
| `references/nextjs-tailwind.md` | Project structure, Tailwind token setup, `next/image` and `next/font` patterns, server vs client components. |

Budgets (phone profile): LCP under 2.5 s, CLS under 0.1, TBT under 300 ms, JS under 350 KB compressed on first load.

## Procedure

1. **Pin the brief.** Pages, sections, the main action, brand (logo, colours, fonts), real content (copy, photos, prices). Missing copy: write plain, specific copy; never lorem ipsum in a delivered page.
2. **Pick the stack.** Static marketing page with no data: plain HTML/CSS (fastest, nothing to break). Anything with data, auth, many pages, or a CMS: Next.js (App Router) + TypeScript + Tailwind. Keep dependencies few.
3. **Tokens first.** Colours (with text/background pairs that pass 4.5:1 contrast), font families, a type scale (fluid `clamp()` sizes), a spacing scale (4 px base), radius, shadow, container width. In Tailwind put them in the theme; in CSS, `:root` variables (`base.css`). Use only tokens in components; no random `13px` or `#3a3a3a`.
4. **Layout, mobile first.** Build at 375 px first, then add `min-width` breakpoints (640, 768, 1024, 1280). Use flex/grid with `gap`, `minmax(min(100%, 260px), 1fr)` grids, `max-width` containers and `ch`-limited text. No fixed widths on content; no `100vw` (it includes the scrollbar).
5. **Components with every state.** Header/nav (with a mobile menu), buttons (hover, focus, disabled, loading), forms (labels, errors, success), cards, empty states, loading skeletons, error messages. Tap targets at least 44 px. Visible focus ring.
6. **Images and fonts.** Right size and format (WebP/AVIF), `width`/`height` or `aspect-ratio` on every image, `loading="lazy"` below the fold, `priority`/eager on the hero image only. In Next.js use `next/image` with a correct `sizes`. Self-host fonts (woff2, 2-3 weights, `font-display: swap`), use `next/font/local` when build-time downloads are a risk.
7. **Motion, lightly.** 150-300 ms ease-out transitions on hover/open; animate `transform` and `opacity` only; respect `prefers-reduced-motion`.
8. **QA gate.** Run `ui_check.mjs` at 320/375/414/768/1440: 0 errors, and read the warnings. Look at every screenshot with `vision_analyze`: alignment, spacing rhythm, text wrapping, orphans, image crops. Fix and repeat.
9. **Speed gate.** `web_vitals.mjs` on the phone profile; fix anything over budget (see Pitfalls). Optional: `npx lighthouse URL --preset=perf` for the official score.
10. **Ship.** Production build passes, deploy, run both gates again on the live URL, then report the URL, the screenshots and the numbers.

## Pitfalls

- **Sideways scroll on phones.** Usual causes: a fixed `width`, long words/URLs (`overflow-wrap: anywhere`), `100vw`, negative margins, big images without `max-width: 100%`, wide tables (wrap them in `overflow-x: auto`). `ui_check.mjs` names the element.
- **Layout shift.** Images and embeds without size, fonts swapping with very different metrics (use `size-adjust` or a close fallback), banners injected at the top after load. `web_vitals.mjs` names the shifting elements.
- **Slow LCP.** Huge hero image (resize, WebP, `fetchpriority="high"`), lazy-loaded hero, render-blocking CSS/JS, client-side rendering of the main content.
- **Too much JS.** Whole UI libraries for one component, client components that could be server components, heavy animation libraries. Check with `next build` output sizes.
- **Hydration errors.** `Date.now()`, `Math.random()`, `window` or locale formatting during render. Compute in `useEffect` or pass from the server.
- **Low contrast.** Light grey text on white, white text on orange/yellow. Check every text/background pair.
- **Inconsistent spacing.** Values not from the scale make a page look amateur. Use the tokens.
- **Desktop-first CSS.** Leads to piles of overrides. Write the phone layout first.
- **Fonts fetched at build time.** Can fail on the build machine; self-host.

## Verification

- `python3 ${HERMES_SKILL_DIR}/tests/test_frontend.py` checks the starter has 0 QA errors and 0 contrast/label/tap warnings at all 5 widths and is inside the speed budget, and that a deliberately bad page is caught (layout shift, main-thread blocking, oversized unsized image, render-blocking script). It prints 8 PASS lines and `all passed`.
- A real build is done when `ui_check.mjs` exits 0, `web_vitals.mjs` exits 0 on the phone profile, and the screenshots at 375 and 1440 look right to the eye.
