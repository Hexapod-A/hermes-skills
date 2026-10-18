---
name: web-unblock
description: Read public pages when normal web access is blocked.
version: 1.0.0
author: John (Hexapod-A), 3xAgentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [web, research, browser, scraping, captcha, cloudflare, archives, media]
    category: research
    related_skills: [web-research, ui-replicate, maps-lead-gen]
---

# Web Unblock Skill

Use this for **any site and any task** when a page you need to read is blocked or blank. This is a general fetch fallback, not a design-only tool. It reads public pages and gets their images or media; it does not log in without a saved session, post, or fill forms. Other skills should call this as their fetch fallback: `web-research` when `web_extract` fails, `ui-replicate` for blocked design references, `maps-lead-gen` for a prospect's blocked public page, and any task with a URL. Stop at the first route with the actual page content, not a challenge screen.

## When to Use

- A normal `web_extract` / `browser_navigate` / HTTP read hits a captcha, Cloudflare "Just a moment", 403/429, a login wall, or an empty JavaScript shell.
- You need the text, HTML, images, video metadata or media of a public URL on **any** site: news, shops, social posts, documentation, portfolios, forums, blogs.
- A URL was removed and you need an archived copy, clearly marked as old.

Not for breaking into private accounts. Respect robots rules, site terms and rate limits. No mass hammering; use one bounded fetch per URL and say when a site cannot be read.

## Prerequisites

- Repo venv (README step 4): `requests`; `Pillow` validates downloaded images. Both are already in `requirements.txt`. The detector itself uses only the Python standard library.
- Browser route: repo Node deps plus Chromium (README step 3). `npm install && npx playwright install chromium`. Set `CHROME_PATH` if Chrome is elsewhere. Browser is optional: the free HTTP, reader, site-source and archive routes work without it.
- Media route: `yt-dlp` (in `requirements.txt`). Media downloads can be large; `--max-filesize 30M` bounds a single file, and no playlist is fetched.
- The free routes need no key. Optional paid route: set `PROXY_URL` (residential proxy) and/or `CAPSOLVER_API_KEY` or `TWOCAPTCHA_API_KEY` in your private `~/.hermes/.env`; list the names in `terminal.env_passthrough` in `~/.hermes/config.yaml`. **Those services charge per byte or solve.** Leaving all keys unset never calls them. Do not paste keys into chats or the repo. `JINA_API_KEY` is optional if anonymous reader access is limited.

## How to Run

    S=${HERMES_SKILL_DIR}/scripts; PY=${HERMES_SKILL_DIR}/../.venv/bin/python
    $PY $S/unblock_fetch.py 'https://site.example/article' --want text --out ~/research/article
    $PY $S/unblock_fetch.py 'https://dribbble.com/shots/23956256' --want images --out ~/research/shot
    $PY $S/unblock_fetch.py 'https://site.example/video' --want media --out ~/research/video
    $PY $S/unblock_fetch.py 'https://site.example/app' --want html --out ~/research/app

The CLI prints each attempted route on stderr, then one JSON line with `ok`, winning `route`, `files` and `result`. `result.json` records the original URL, source URL, time and every route attempted. Exit `0` means real content saved, `2` means nothing passed the checks, `1` means a code error. `--limit 8` caps image count, `--wait 25` bounds browser challenge wait, `--no-browser` / `--no-cache` skip routes if you know they are not useful. `--storage /path/to/state.json` uses a Playwright session **you own** for a login wall. `--save-state` writes a cookie file into the output folder with mode 0600: keep it private, never commit it. Never ask someone to send a password.

## Quick Reference

| Need | Command / route |
|---|---|
| Check a saved response | `$PY $S/blockcheck.py page.html --status 403 --url https://site.example` (0 real, 2 blocked) |
| Read text | `unblock_fetch.py URL --want text --out DIR` → `page.txt` and `result.json` |
| Keep HTML | `--want html` → `page.html` (reader may return HTML with `X-Return-Format: html`) |
| Grab real images | `--want images` → verified image files + `images/sources.json`; Dribbble CDN `?resize=` is removed |
| Fetch video/audio | `--want media` → yt-dlp download or direct media found on page, max 30 MB per yt-dlp file |
| Browser alone | `node $S/browser_fetch.mjs URL --out DIR --wait 30` → `browser.html`, `browser.txt`, screenshot and `browser.json` |
| Login you already own | `--storage /private/state.json`; no password or cookies printed |
| Need optional paid routes | Set `PROXY_URL` and/or solver key in your private env, rerun. Do not buy a service without approval. |

## Procedure

1. **Try the normal read first.** `unblock_fetch.py` walks the ladder automatically: plain `requests` fetch with browser headers; one retry with another UA. `blockcheck.py` rejects 403/429/404/410, Cloudflare, DataDome, PerimeterX, AWS WAF, Amazon captchas, a login-only page, and an empty JS shell. A page mentioning "captcha" in a real article is not a block.
2. **Public reader.** It requests `https://r.jina.ai/` + the full URL. `X-Return-Format: markdown` is the default and includes image links; `X-With-Images-Summary: true` adds an image list. For `--want html`, it asks for `X-Return-Format: html`. These headers were tested against Dribbble on 2026-10-18. `Accept: application/json` also gives structured `data.images`; the CLI uses markdown or HTML. Anonymous access may be temporarily blocked per domain; the CLI moves on. An optional `JINA_API_KEY` can lift anonymous rate limits.
3. **Site-owned data.** Try the page with a link-preview UA; parse `og:image`, `twitter:image`, JSON-LD and `__NEXT_DATA__`, plus linked oEmbed, RSS and sitemap. Then try known public paths: Reddit `.json`, X syndication/oEmbed, Instagram oEmbed, YouTube/Vimeo oEmbed, and `?format=json`. Feeds and sitemaps are leads, **not** the requested article; never call a generic homepage or 404 JSON-LD a successful read. Public JSON/API data may be fresher than a cached snippet. For Reddit when the live page is blocked, Wayback or the public Arctic Shift historical post archive can supply old content, marked as archived.
4. **Archived copy.** Wayback availability API gives a snapshot URL, and `/web/TIMESTAMPid_/URL` returns the raw page without its toolbar. Archive.today's `/newest/URL` lookup is also tried, but it can show a captcha. Google Cache is **gone** (retired in 2024); a `webcache.googleusercontent.com/search?q=cache:` URL now serves generic Google Search, not a cached page. Do not present that as a copy. An archive is old: name its snapshot date, not a live price or current claim.
5. **Real browser.** If the above failed, `browser_fetch.mjs` opens Chromium with a normal viewport, locale, full-browser UA, small anti-automation patches, waits for a challenge to clear, scrolls to load lazy images, saves rendered text, HTML, image URLs and a screenshot. It can click a Cloudflare checkbox or hold a PerimeterX button once; those actions may still fail. Some providers remain blocked from data-centre IPs.
6. **Optional paid tier.** Only if env vars are present, rerun the browser through `PROXY_URL`, or use CapSolver/2Captcha for supported reCAPTCHA, hCaptcha and Turnstile **widgets**. These cost money; keys are never in command arguments or output. Cloudflare managed interstitials may require a valid browser clearance cookie and are **not** always solved by injecting a widget token. Do not promise a bypass.
7. **Media.** For video/audio/social links, try `yt-dlp --dump-single-json` for title, caption, thumbnail and format metadata. With `--want media`, `yt-dlp` downloads at most one item with `--max-filesize 30M`. Some logged-in social posts still need a session you own.
8. **Verify the result.** Open `result.json`, inspect `page.txt` or an image, and check the source is the requested page rather than a login prompt, search page, empty footer or unrelated redirect. If the result is partial, say so. Use the public source URL in citations.

## Pitfalls

- A 200 response is not proof of content. Dribbble returned HTTP 202 with AWS WAF markup; Reddit returned 403 or a 200 page saying its bot UA was identified. Both must fail the check. A long real article *about* captchas should pass.
- The reader can serve cached content, be stale, or show its own abuse-limit error. The archive is older still. Check dates before citing current facts.
- Dribbble image lists also contain related shots; the downloader favours `/userupload/` originals and drops `?resize=`, but inspect the saved images before using them.
- Media and image links may be signed or expire. `result.json` includes the source URL and time for that reason. Keep output folders private if their links contain tokens.
- A headless browser on a data-centre IP does not always beat a bot wall. A login-required page is not public content; use an account session with permission, or ask the user for a copy.
- `--want html` does not silently accept reader Markdown as HTML. Some sites need the browser or an archive for raw markup.

## Verification

Offline: `$PY ${HERMES_SKILL_DIR}/tests/test_blockcheck.py` → 18 tests pass (blockers, login, empty JS, real content and metadata extraction).

Live checks from this box on 2026-10-18 (each is an actual run of `unblock_fetch.py` unless noted; the route is what `result.json` recorded):

| Target / kind | Direct result | Winning route | Checked result |
|---|---|---|---|
| Dribbble shot `23956256` (design image) | HTTP 202 AWS WAF | `r.jina.ai reader` | Original CDN PNG downloaded without `?resize=` (451 KB). |
| Stack Overflow question `231767` (Cloudflare, docs/Q&A) | HTTP 403 "Just a moment" | `browser` | Rendered ~89K chars, saved screenshot. Tested with `--no-cache` so browser path was exercised. |
| Reddit r/Python post `1hjcng4` (forum) | HTTP 403 network block; reader 403 | `Wayback raw snapshot` | Archived March 2025 post and comments; **historical, not live**. |
| Apple iPhone 3G page (removed) | HTTP 404 | `Wayback raw snapshot` | 2010 raw archived page with the actual iPhone 3G features; page is gone today. |
| NASA Instagram post `DSklZFtkpa2` (social) | First fetch empty | `plain fetch retry` | Post text and image description returned. |
| @jack X post `20` (social) | Login wall | `r.jina.ai reader` | Post text, dated 2006; X oEmbed/syndication JSON also answered independently. |
| NYT homepage (news) | HTTP 403 DataDome | `site preview metadata` | Page HTML + headlines, not the captcha. The browser also rendered it independently. |
| Zillow property page `84074482_zpid` (property/e-commerce) | HTTP 403 PerimeterX | `r.jina.ai reader` | Property text; browser also rendered it independently. |
| Amazon product `B0BSHF7WHW` (shopping) | HTTP 200 | `plain fetch` | Product page text, so no fallback needed. |

Limitations observed: anonymous Jina returned temporary 403s for Reddit, Stack Overflow, Medium and NYT; archive.today returned 429/captcha here; the free browser did not clear Medium's Cloudflare challenge in 25 seconds. No residential proxy or paid captcha solver was used or tested. No saved login was available. The Google cache endpoint showed Google Search rather than a cache. Do not say every block can be bypassed.
