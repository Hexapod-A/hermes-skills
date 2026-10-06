# hermes-skills

Skills for John's self-hosted [Hermes Agent](https://github.com/nousresearch/hermes-agent) (Nous Research), built for 3xAgentic work. Everything runs on public open-source tools; no API keys are required for the core features.

| Skill | What it does |
|---|---|
| **flyer-studio** | On-brand social flyers designed in HTML/CSS (real fonts, colours, logo), rendered to PNG by headless Chromium at 1080×1080, 1080×1350, 1080×1920 and 4K, then auto-checked for overflow, collisions, font fallback and contrast. 6 layouts: announcement, offer/pricing, stat/proof, quote/testimonial, carousel, checklist. Ships the 3xAgentic brand kit. No AI image generation. |
| **web-research** | Search + read live pages, cross-check, answer with numbered sources and dates. |
| **lead-gen** | US small-business prospect lists from OpenStreetMap + each business's own website, verified fields with evidence URLs, CSV + XLSX. Never contacts anyone. |
| **maps-lead-gen** | Google Maps playbook for local lists: one niche/area/offer, zip-by-zip pulls (free OpenStreetMap, optional MapsData / Google Places / Serper / RapidAPI), review-count filter, owner-name finder that says "not found" instead of guessing, email waterfall + verification, intent score, dedupe, suppression list, one true local fact per lead, 3-sentence email drafts, call sheet. Drafts only. |
| **outreach-and-proposals** | Cold email/DM/follow-up drafts for John to send, priced proposals and SOWs as branded PDFs, 3xAgentic pricing guide. |
| **video-clipper** | yt-dlp download, frame-accurate ffmpeg cuts, 9:16 reframe (crop or blur), faster-whisper word-timed captions burned in. |
| **docs-and-pdfs** | Markdown/HTML notes to branded PDF (cover, page numbers) and DOCX, with checks. |
| **profile/USER.md** | John's preferences in Hermes' memory format. |

Sample flyers: `flyer-studio/examples/out/`. Sample proposal: `outreach-and-proposals/examples/proposal-example.pdf`.

## Hermes skill format followed

Read from the Hermes Agent source and docs on 2026-10-04, `nousresearch/hermes-agent` at commit `667b232` (main, 2026-10-04):

- `website/docs/user-guide/features/skills.md`: skills live in `~/.hermes/skills/<category>/<skill>/SKILL.md`; skill folders may hold `scripts/`, `references/`, `templates/`, `assets/`, `examples/`; the skills directory is scanned recursively; `skills.external_dirs` in `config.yaml` adds extra folders.
- `website/docs/developer-guide/creating-skills.md`: SKILL.md YAML frontmatter (`name`, `description`, `version`, `platforms`, `metadata.hermes.*`); `${HERMES_SKILL_DIR}` is substituted with the skill's absolute path so SKILL.md can call bundled scripts; skill env vars only reach `terminal` when declared or listed in `terminal.env_passthrough`.
- `skills/AGENTS.md` (authoring standards): description ≤ 60 characters, one sentence ending with a period; sections in the order When to Use, Prerequisites, How to Run, Quick Reference, Procedure, Pitfalls, Verification; native tools named in backticks (`terminal`, `read_file`, `web_extract`, `vision_analyze` …); helper logic shipped as scripts.
- `website/docs/user-guide/features/memory.md`: `USER.md` lives in `~/.hermes/memories/`, entries separated by `§`, 1,375-character limit.
- Live docs: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills

## Install (Ubuntu / Debian server)

```bash
# 1. system packages
sudo apt update
sudo apt install -y git curl ffmpeg python3 python3-venv python3-pip pandoc poppler-utils
node -v || true   # need Node 18+; if missing or older:
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs

# 2. clone into the Hermes skills folder (private repo: use your SSH key or `gh auth login` first)
git clone git@github.com:Hexapod-A/hermes-skills.git ~/.hermes/skills/hermes-skills
cd ~/.hermes/skills/hermes-skills

# 3. Node deps + headless Chromium (flyer-studio, docs-and-pdfs)
npm install
npx playwright install --with-deps chromium

# 4. Python deps in a repo-local venv (web-research, lead-gen, video-clipper)
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt

# 5. John's profile into Hermes memory (append if USER.md already exists, see profile/README.md)
mkdir -p ~/.hermes/memories
[ -f ~/.hermes/memories/USER.md ] && printf '\n§\n' >> ~/.hermes/memories/USER.md
cat profile/USER.md >> ~/.hermes/memories/USER.md

# 6. optional env vars (search keys etc.): add the block from .env.example to ~/.hermes/.env,
#    then let terminal commands see them in ~/.hermes/config.yaml:
#    terminal:
#      env_passthrough: [SEARXNG_URL, BRAVE_API_KEY, SERPER_API_KEY, TAVILY_API_KEY, OSM_USER_AGENT, HF_TOKEN]

# 7. restart Hermes (new session) and check the skills are listed
hermes skills list | grep -E "flyer-studio|web-research|lead-gen|outreach|video-clipper|docs-and-pdfs"
```

Using a named Hermes profile? Clone into `~/.hermes/profiles/<name>/skills/hermes-skills` instead, and use that profile's `memories/` folder. Prefer keeping the repo elsewhere? Clone to `~/hermes-skills` and add it under `skills.external_dirs` in `config.yaml`.

Update later: `cd ~/.hermes/skills/hermes-skills && git pull && npm install && .venv/bin/pip install -r requirements.txt`.

## One-line test per skill

Run from `~/.hermes/skills/hermes-skills`:

```bash
node flyer-studio/scripts/selftest.mjs                                    # flyer-studio: 4 PASS lines
node flyer-studio/scripts/render.mjs flyer-studio/examples/announcement.json --out /tmp/flyers   # 4 PNGs, all "ok"
.venv/bin/python web-research/scripts/fetch.py https://hermes-agent.nousresearch.com/docs/ --max-chars 300   # web-research
.venv/bin/python lead-gen/scripts/osm_search.py --city "Boise, Idaho" --category dentist --require-website --limit 5   # lead-gen
.venv/bin/python maps-lead-gen/tests/test_adapters.py && .venv/bin/python maps-lead-gen/scripts/pull.py --niche dentist --zips 78704 --out /tmp/maps.csv   # maps-lead-gen: OK + "N unique businesses pulled"
node docs-and-pdfs/scripts/build.mjs outreach-and-proposals/examples/proposal-example.md --out /tmp/proposal.pdf   # outreach-and-proposals
.venv/bin/python video-clipper/scripts/clip.py make --url "https://www.youtube.com/watch?v=jNQXAC9IVRw" --end 15 --captions --model tiny --out /tmp/short.mp4   # video-clipper
node docs-and-pdfs/scripts/build.mjs docs-and-pdfs/examples/notes-example.md --out /tmp/notes.pdf   # docs-and-pdfs
```

Then in Hermes: `/flyer-studio make a square + story flyer for 3xAgentic: "Your Front Desk Never Sleeps"`.

## The 3xAgentic logo

`flyer-studio/brands/3xagentic/logo.svg` is a **placeholder**. Save John's real SVG over it (same filename, the version that reads on black). Until then the renderer uses `logo-interim.png` (cropped from his own sample post; a little soft at 4K) and prints a `placeholder-logo` warning.

## maps-lead-gen (Google Maps playbook)

A second, separate lead skill built from Christian's (@coldemailchris) "Scrape Local Businesses From Google Maps" course (Oct 2026). `lead-gen` is untouched; use `maps-lead-gen` for volume local lists with owner names, emails, drafts and a call sheet.

Full run, free path (2 zips; stops the owner finder at a 50-row hand-check sheet):

```bash
bash maps-lead-gen/scripts/pipeline.sh dentist "Austin" TX ~/leads/atx-dentists --zips 78704,78745
# check ~/leads/atx-dentists/owners_handcheck.xlsx, then:
OWNER_SAMPLE=0 bash maps-lead-gen/scripts/pipeline.sh dentist "Austin" TX ~/leads/atx-dentists --zips 78704,78745
```

Output: `leads.xlsx` (Call sheet, Leads, Email drafts, Waterfall log, About). Nothing is ever sent.

Every paid service is optional and switches on only when its key is in `~/.hermes/.env`:

| Env var | Step it switches on | Tested here |
|---|---|---|
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (or `OPENROUTER_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`) | LLM owner finder (regex + guard without it) | live, via an OpenAI-compatible endpoint |
| `MAPSDATA_API_KEY` | `pull.py --source mapsdata` (Pro/Scale plan for API) | mocked only |
| `GOOGLE_PLACES_API_KEY` | `pull.py --source google_places` (ratings, review counts, 5 reviews) | mocked only |
| `SERPER_API_KEY` | `pull.py --source serper`, also website search | mocked only |
| `RAPIDAPI_KEY` (+ `RAPIDAPI_MAPS_HOST`) | `pull.py --source rapidapi` | mocked only |
| `PROSPEO_API_KEY`, `ICYPEAS_API_KEY` | email waterfall steps 2 and 3 | mocked only |
| `MILLIONVERIFIER_API_KEY` | mailbox verification | live against MillionVerifier's test keys + mocked |
| `BOUNCEBAN_API_KEY` | second check for catch-all domains | mocked only |
| `SENDER_ADDRESS`, `SENDER_NAME`, `SENDER_COMPANY` | CAN-SPAM footer and signature in drafts | yes |

Add the ones you use to `terminal.env_passthrough` too (the skill also declares them in its SKILL.md, which Hermes passes through when the skill loads). Costs quoted in the article are in `maps-lead-gen/references/playbook.md`. No new Python packages: the existing `requirements.txt` covers it.

## Rules baked into the skills

- Drafts only: the agent never emails, DMs, calls, texts or submits forms to leads or clients without John's OK.
- No fabricated claims: stat flyers require a source, testimonial flyers require a real name, proposals leave `{{placeholders}}` instead of guessing.
- 3xAgentic is AI-only: never blockchain, crypto or Web3 wording.
- No secrets in this repo. Keys come from environment variables (`.env.example`).

## Licences

Code: MIT (`LICENSE`). Fonts: DM Sans and Plus Jakarta Sans, SIL Open Font License 1.1 (licence files next to the fonts). Tools used: Playwright/Chromium, ffmpeg, yt-dlp, faster-whisper, trafilatura, pandoc, OpenStreetMap data (© OpenStreetMap contributors, ODbL).
