---
name: software-engineering-qa
description: Scan, review, run and browser-test code.
version: 1.0.0
author: John (Hexapod-A)
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [code-review, security, secrets, malware, lint, tests, playwright, responsive, accessibility, vercel, qa]
    category: engineering
    related_skills: [frontend-build, ui-replicate, persistent-problem-solving, rea]
---

# Software Engineering QA Skill

Checks code and the app it makes, the way a careful senior engineer would: read the repo fast, scan it for leaked secrets, malware and weak dependencies, run lint/types/tests/build, change the smallest thing that fixes the problem, then open the real app in a browser at phone, tablet and desktop widths and prove the interface works. Nothing ships until the checks pass and you have looked at the screenshots.

## When to Use

- "Review this repo / PR", "is this code safe?", "check my GitHub for malware".
- Fixing a bug or adding a feature in a codebase you did not write.
- Before any deploy or hand-off: "test it", "make sure it works on mobile".
- A page looks broken, scrolls sideways on phones, throws console errors, or has dead links/images.
- Setting up or debugging a Vercel (or similar) deploy.

## Prerequisites

- Python 3.9+ (standard library only for the scanners).
- Repo Node deps and Chromium for browser checks (README step 3): `npm install && npx playwright install --with-deps chromium`. Run `ui_check.mjs` from the repo root, or set `NODE_PATH=<repo>/node_modules`.
- Optional deeper scanners: `gitleaks` or `trufflehog` (secrets in git history), `pip-audit`, `semgrep`, `axe-core` (`npm i -D axe-core`, then `ui_check.mjs --axe`).

## How to Run

    S=${HERMES_SKILL_DIR}/scripts
    # 1. code health + security in one go (lint, types, tests, audit, secrets, red flags)
    python3 $S/repo_scan.py ~/code/app --json ~/qa/scan.json          # add --build before a deploy
    python3 $S/suspicious_scan.py ~/code/app                           # red flags only, any folder
    # 2. run the app, then test the interface in a real browser
    (cd ~/code/app && npm run build && npm start &)                    # or the preview/production URL
    node $S/ui_check.mjs http://localhost:3000/ http://localhost:3000/pricing --out ~/qa/ui --links
    # look at ~/qa/ui/*-375.jpg and *-1440.jpg, fix, run again until 0 errors

## Quick Reference

| Script | Does |
|---|---|
| `repo_scan.py PATH` | Detects the stack (Node/Python, framework, package manager), runs what exists: red-flag scan, gitleaks/trufflehog, `npm audit --omit=dev`, lint, `tsc --noEmit`, tests, ruff/pyflakes, mypy, pip-audit, pytest, `--build`. Table of pass/FAIL/skipped. Exit 2 on any FAIL. |
| `suspicious_scan.py PATH` | Secrets (cloud keys, tokens, private keys, DB URLs, committed `.env`), install-time scripts that download/run code, `eval(atob(...))` and other obfuscation, exfil endpoints (Discord/Telegram webhooks, paste sites), code that reads SSH keys/browser/wallet data, VS Code `folderOpen` auto-run tasks, risky GitHub workflows, script code hidden in font/image files. Exit 2 on HIGH. |
| `ui_check.mjs URL...` | Real Chromium at 320/375/414/768/1440: console errors, JS crashes, failed requests, HTTP 4xx/5xx, sideways scroll **with the element causing it**, broken images, missing alt, unnamed buttons/links, unlabeled inputs, tap targets under 32 px, text under 12 px, low-contrast text, title/lang/h1/viewport meta, dead links (`--links`), axe-core (`--axe`), full-page screenshot per width. Exit 2 on errors. `--storage state.json` for logged-in pages. |
| `references/code-review.md` | Reading an unfamiliar repo in 15 minutes; review checklist; minimal-diff rules. |
| `references/deploy-checks.md` | Vercel build and env var checklist, common deploy failures and fixes. |

## Procedure

1. **Map the repo (10-15 min).** README, `package.json`/`pyproject.toml` scripts, folder tree (`git ls-files | head -200`), entry points (routes, `app/`, `pages/`, `main.py`), config (`.env.example`, `next.config.*`), recent history (`git log --oneline -20`). Write 5 lines: what it does, stack, how to run, how to test, where the change goes. See `references/code-review.md`.
2. **Scan before running anything.** `suspicious_scan.py` first on unknown code: do not `npm install` a repo with a HIGH install-script finding until you have read that script. Then `repo_scan.py` for lint/types/tests/audit. Note what was already failing before your change (baseline).
3. **Reproduce.** For a bug, make it happen (a failing test, a curl, a browser step) before fixing. For a feature, write down how you will prove it works.
4. **Change the minimum.** Follow the code's existing style and patterns. Small diff, one concern per commit. No drive-by reformatting, no new dependency when a few lines do. Never commit secrets: use env vars and update `.env.example`.
5. **Check the code.** Re-run `repo_scan.py --build`. New failures are yours to fix; old ones you report.
6. **Run the app and test the interface.** Start it (dev for speed, production build before a deploy), run `ui_check.mjs` on every page you touched plus the home page. Then look at the screenshots with `vision_analyze`: layout, spacing, text wrapping, images, empty states. Click through the main flow with a short Playwright script (fill the form, submit, see the success state). Fix and repeat until 0 errors and the screenshots look right.
7. **Deploy and check the live URL.** Follow `references/deploy-checks.md`; run `ui_check.mjs` again on the deployed URL (production can differ: env vars, image domains, caching).
8. **Report.** What changed (files, commit), what you tested and the results (numbers: tests passed, 0 console errors at 5 widths), what is still open, and anything the user must set (env vars, keys).

## Writing a flow test (Playwright)

    // flow.mjs  - node flow.mjs http://localhost:3000
    import { chromium } from 'playwright';
    const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 375, height: 812 } });
    const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => m.type() === 'error' && errs.push(m.text()));
    await p.goto(process.argv[2] + '/contact');
    await p.getByLabel('Email').fill('test@example.com');
    await p.getByRole('button', { name: /send/i }).click();
    await p.getByText(/thanks/i).waitFor({ timeout: 10000 });
    await p.screenshot({ path: 'contact-done.png', fullPage: true });
    console.log(errs.length ? errs : 'flow ok'); await b.close(); process.exit(errs.length ? 2 : 0);

Prefer `getByRole` / `getByLabel` / `getByText` over CSS selectors: they survive restyles and also test accessibility.

## Pitfalls

- **Installing before scanning.** Malicious repos run code on `npm install` (postinstall) or when a folder opens in VS Code. Scan first; use `npm ci --ignore-scripts` when unsure.
- **"Works on my machine".** Test the production build and the deployed URL, not just `npm run dev`.
- **Only checking desktop.** Most users are on phones. 320 and 375 catch most overflow bugs: long words/URLs, fixed widths, `100vw` with a scrollbar, wide tables, big images without `max-width:100%`.
- **Ignoring console errors.** Hydration errors, 404 scripts and failed API calls show up here first.
- **Lockfile drift.** Commit the lockfile; use `npm ci` in CI and deploys.
- **Secrets in git history.** Deleting a key from code does not remove it from history. Rotate the key, then clean history if needed.
- **Big diffs.** They hide bugs and are hard to review. Split them.
- **Trusting a passing score blindly.** The checker finds common problems, not all of them. Always look at the screenshots.

## Verification

- `python3 ${HERMES_SKILL_DIR}/tests/test_qa.py` builds a fake malicious repo, a clean repo and a broken local web page, and checks every scanner finds what it should. It prints 24 PASS lines and `all passed`.
- `python3 ${HERMES_SKILL_DIR}/scripts/suspicious_scan.py ${HERMES_SKILL_DIR}/..` on this repo prints `"HIGH": 0`.
