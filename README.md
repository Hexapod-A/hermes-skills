# hermes-skills

Skills for John's self-hosted [Hermes Agent](https://github.com/nousresearch/hermes-agent) (Nous Research), built for 3xAgentic work. Everything runs on public open-source tools; no API keys are required for the core features.

| Skill | What it does |
|---|---|
| **flyer-studio** | On-brand social flyers designed in HTML/CSS (real fonts, colours, logo), rendered to PNG by headless Chromium at 1080×1080, 1080×1350, 1080×1920 and 4K, then auto-checked for overflow, collisions, font fallback and contrast. 6 layouts: announcement, offer/pricing, stat/proof, quote/testimonial, carousel, checklist. Ships the 3xAgentic brand kit. No AI image generation. |
| **web-research** | Search + read live pages, cross-check, answer with numbered sources and dates. |
| **lead-gen** | US small-business prospect lists from OpenStreetMap + each business's own website, verified fields with evidence URLs, CSV + XLSX. Never contacts anyone. |
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
node docs-and-pdfs/scripts/build.mjs outreach-and-proposals/examples/proposal-example.md --out /tmp/proposal.pdf   # outreach-and-proposals
.venv/bin/python video-clipper/scripts/clip.py make --url "https://www.youtube.com/watch?v=jNQXAC9IVRw" --end 15 --captions --model tiny --out /tmp/short.mp4   # video-clipper
node docs-and-pdfs/scripts/build.mjs docs-and-pdfs/examples/notes-example.md --out /tmp/notes.pdf   # docs-and-pdfs
```

Then in Hermes: `/flyer-studio make a square + story flyer for 3xAgentic: "Your Front Desk Never Sleeps"`.

## The 3xAgentic logo

`flyer-studio/brands/3xagentic/logo.svg` is a **placeholder**. Save John's real SVG over it (same filename, the version that reads on black). Until then the renderer uses `logo-interim.png` (cropped from his own sample post; a little soft at 4K) and prints a `placeholder-logo` warning.

## Rules baked into the skills

- Drafts only: the agent never emails, DMs, calls, texts or submits forms to leads or clients without John's OK.
- No fabricated claims: stat flyers require a source, testimonial flyers require a real name, proposals leave `{{placeholders}}` instead of guessing.
- 3xAgentic is AI-only: never blockchain, crypto or Web3 wording.
- No secrets in this repo. Keys come from environment variables (`.env.example`).

## Licences

Code: MIT (`LICENSE`). Fonts: DM Sans and Plus Jakarta Sans, SIL Open Font License 1.1 (licence files next to the fonts). Tools used: Playwright/Chromium, ffmpeg, yt-dlp, faster-whisper, trafilatura, pandoc, OpenStreetMap data (© OpenStreetMap contributors, ODbL).
