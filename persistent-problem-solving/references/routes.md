# Routes around common blockers

Try these before telling anyone a task cannot be done. Read the error first; the error usually names the next route.

## A web page will not load or blocks bots

1. Plain HTTP with a normal browser user agent and `Accept-Language`.
2. The site's own data: `/api/...` calls seen in the browser's network tab, `?format=json`, `/feed`, `/rss`, `sitemap.xml`, `og:` tags, `__NEXT_DATA__` / `application/ld+json` in the HTML.
3. A reader or text proxy (for public pages), Google cache-style mirrors, the mobile site (`m.`), AMP pages.
4. A real headless browser (Playwright), wait for network idle, scroll to load lazy parts. Save the session (cookies) if the user logs in once.
5. Archive copies (Wayback Machine `https://web.archive.org/web/2024*/URL`, archive.today). Mark them as old.
6. The same information elsewhere: the publisher's press page, LinkedIn, a directory, a public registry, a PDF version.
See the `web-unblock` skill for a script that runs this ladder.

## Media (video, audio, images)

- `yt-dlp URL` handles most sites (YouTube, Instagram, TikTok, X, Facebook, Vimeo, many news sites). Add `--cookies-from-browser chrome` or `--cookies cookies.txt` for login-only posts. `yt-dlp -F URL` lists formats.
- Direct media URLs sit in page JSON (`video_url`, `playback_url`, `.m3u8`). `ffmpeg -i "https://.../index.m3u8" -c copy out.mp4` saves HLS streams.
- Images: take the largest size from `srcset`, strip resize parameters (`?w=400`).
- Audio you need as text: transcribe with faster-whisper.

## A tool or package is missing

- Check: `command -v tool`, `python3 -c "import x"`, `node -e "require('x')"`.
- Install: `pip install x` (in a venv), `npm install x`, `sudo apt-get install -y x`, `brew install x`, a release binary from GitHub, or `docker run`.
- No root? Use `pip install --user`, a static binary in `~/bin`, or a different tool that does the same job.

## Code does not build or tests fail

- Read the first error, not the last. Reproduce with the smallest command.
- Check versions (`node -v`, lockfile, `python -V`), clean install (`rm -rf node_modules && npm ci`), clear caches (`.next`, `__pycache__`).
- Search the exact error text in the project's issues.
- Bisect: last known good commit vs now (`git bisect`).
- See `software-engineering-qa`.

## A file is in the wrong format

- Video/audio: ffmpeg. Documents: `pandoc`, `libreoffice --headless --convert-to pdf`. Images: Pillow, ImageMagick, `rsvg-convert` for SVG. PDF text: `pdftotext`; scans: OCR with `tesseract`. Spreadsheets: pandas / openpyxl.

## An API refuses

- 401/403: wrong key, missing scope, or wrong account. Check which account the token belongs to.
- 404: wrong id or path; list the parent resource to find the right id.
- 422/400: read the error body; it names the bad field.
- 429: wait the `Retry-After` time, batch requests, cache results.
- 5xx / timeout: retry once with backoff; if it keeps failing, try another endpoint or a later time and tell the user.
- Body or size limits: send smaller parts, paginate, or use the upload/multipart endpoint.

## You cannot find information

- Change the words: synonyms, the local language, the official name, the product code.
- Go to the source: official site, filings, docs, the company's social pages.
- Use site search: `site:example.com term`, `filetype:pdf`.
- Still nothing: say exactly what you searched and where, and offer to call or email the source (draft for approval).

## It needs the user

Only for: passwords and 2FA codes, payment approval, choices only they can make, physical actions, sending things in their name. Make that step as small as possible: prepare everything, give one clear action ("tap this link and log in; I'll do the rest").
