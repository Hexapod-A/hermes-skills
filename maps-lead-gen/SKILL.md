---
name: maps-lead-gen
description: Google Maps style local lead lists, zip by zip.
version: 1.0.0
author: John (Hexapod-A), 3xAgentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [sales, leads, google-maps, local-business, cold-email, cold-calling, 3xagentic]
    category: productivity
    related_skills: [lead-gen, outreach-and-proposals, web-research]
required_environment_variables:
  - name: OSM_USER_AGENT
    prompt: "Contact string for OpenStreetMap, e.g. 3xagentic-leads (you@email.com)"
    required_for: "polite free OpenStreetMap pulls (recommended)"
  - name: LLM_BASE_URL
    prompt: "OpenAI-compatible base URL for the owner finder (OpenRouter, Nous Portal, OpenAI, DeepSeek, Ollama)"
    required_for: "optional: LLM owner-name finder (regex-only without it)"
  - name: LLM_API_KEY
    prompt: "API key for LLM_BASE_URL"
    required_for: "optional: LLM owner-name finder"
  - name: LLM_MODEL
    prompt: "Model id, e.g. openai/gpt-4o-mini or deepseek-chat"
    required_for: "optional: LLM owner-name finder"
  - name: MAPSDATA_API_KEY
    prompt: "MapsData API key (Pro/Scale plan)"
    help: "https://mapsdata.ai/api"
    required_for: "optional: paid Maps pull with emails"
  - name: GOOGLE_PLACES_API_KEY
    prompt: "Google Places API (New) key"
    required_for: "optional: paid Maps pull with ratings, review counts, 5 reviews"
  - name: SERPER_API_KEY
    prompt: "Serper key"
    required_for: "optional: paid Maps pull (places + reviews) and website search"
  - name: RAPIDAPI_KEY
    prompt: "RapidAPI key (Local Business Data or another Maps endpoint)"
    required_for: "optional: paid Maps pull"
  - name: PROSPEO_API_KEY
    prompt: "Prospeo API key"
    required_for: "optional: email waterfall step 2"
  - name: ICYPEAS_API_KEY
    prompt: "Icypeas API key"
    required_for: "optional: email waterfall step 3"
  - name: MILLIONVERIFIER_API_KEY
    prompt: "MillionVerifier API key"
    required_for: "optional: mailbox verification"
  - name: BOUNCEBAN_API_KEY
    prompt: "BounceBan API key"
    required_for: "optional: second check for catch-all domains"
  - name: SENDER_ADDRESS
    prompt: "John's physical mailing address for the CAN-SPAM footer"
    required_for: "email drafts footer"
---

# Maps Lead Gen Skill

Builds local-business lead lists the way the Google Maps playbook does it (Christian / @coldemailchris, "Scrape Local Businesses From Google Maps (FULL COURSE)", Oct 2026): one niche, one area, one offer; pull zip code by zip code; filter on review count; find the owner's name on their own site (or "not found", never a guess); email waterfall with verification; one true local fact per lead; 3-sentence emails; a call sheet ranked by intent. Built for 3xAgentic's AI automation offers (missed-call text-back, AI receptionist, speed-to-lead), US/USD clients.

It is separate from the `lead-gen` skill (which scores websites for automation gaps). Use this one for volume local lists with owner names, emails and a call sheet.

**Drafts only. The agent never emails, texts, calls, DMs or submits a form to anyone. John reviews and sends everything himself.**

## When to Use

- "Build me a list of dentists / med spas / roofers / HVAC / law firms in <US city or zips>."
- "Find the owners and emails for this list", "write the cold emails", "give me a call sheet".
- Re-pulling a market before a new campaign (lists go stale in ~3 months).

## Prerequisites

- Repo venv (see README). No paid key is needed: the free path is OpenStreetMap + each business's own website.
- Recommended: `OSM_USER_AGENT` with John's email. `SENDER_ADDRESS` for the CAN-SPAM footer.
- Optional keys (each one only switches its own step on): `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` (or `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`), `MAPSDATA_API_KEY`, `GOOGLE_PLACES_API_KEY`, `SERPER_API_KEY`, `RAPIDAPI_KEY`, `PROSPEO_API_KEY`, `ICYPEAS_API_KEY`, `MILLIONVERIFIER_API_KEY`, `BOUNCEBAN_API_KEY`. Costs: `references/playbook.md`.

## How to Run

    PY=${HERMES_SKILL_DIR}/../.venv/bin/python
    # whole pipeline, free path, 2 zips (stops owner finding at a 50-row hand-check sample)
    bash ${HERMES_SKILL_DIR}/scripts/pipeline.sh dentist "Austin" TX ~/leads/atx-dentists --zips 78704,78745
    # every zip in the city, paid source with reviews, review filter + suppression list
    SOURCE=google_places MIN_REVIEWS=20 MAX_REVIEWS=400 SUPPRESS=~/leads/suppression.csv \
      bash ${HERMES_SKILL_DIR}/scripts/pipeline.sh dentist "Austin" TX ~/leads/atx-dentists --all-zips
    # after the hand-check: full owner run
    OWNER_SAMPLE=0 bash ${HERMES_SKILL_DIR}/scripts/pipeline.sh dentist "Austin" TX ~/leads/atx-dentists --zips 78704,78745

Each step is also its own script (all take `--help`): `pull.py`, `find_websites.py`, `enrich_site.py`, `find_owner.py`, `email_waterfall.py`, `score.py`, `local_facts.py`, `draft_emails.py`, `call_sheet.py`, `suppress_add.py`.

## Quick Reference

| Step | Script | Free | Optional paid |
|---|---|---|---|
| Pull, zip by zip | `pull.py --zips` / `--all-zips` | OpenStreetMap (`--source osm`) | `mapsdata`, `google_places`, `serper`, `rapidapi` |
| Review filter | `pull.py` / `score.py --min-reviews --max-reviews` | only when the source has review counts | |
| Missing websites | `find_websites.py` | DuckDuckGo/Bing + page proof | `SERPER_API_KEY` |
| Site crawl | `enrich_site.py` | About/Team/Contact/Careers + footer | |
| Owner name | `find_owner.py --sample 50` | regex + guard | any LLM + guard |
| Email | `email_waterfall.py` | site emails + MX | Prospeo -> Icypeas; MillionVerifier + BounceBan |
| Intent, dedupe, suppression | `score.py --suppress` | | |
| Local fact | `local_facts.py --market` | from your own pull | review data makes it stronger |
| Emails | `draft_emails.py` | 3 sentences: fact, offer, question | |
| Call sheet + XLSX | `call_sheet.py export` / `hours` | | |

Output: `<out>/leads.xlsx` with sheets Call sheet, Leads, Email drafts, Waterfall log, About.

## Procedure

1. **Pick the market with John (one niche, one area, one offer).** Niches where one new customer is worth a lot: dentists, orthodontists, med spas, chiropractors, roofers, HVAC, law firms, home services. Aim for a few thousand businesses across the area, not a few hundred (a few hundred runs out fast). Offer: one of missed-call text-back, AI receptionist or speed-to-lead. Don't mix niches in one campaign.
2. **Pull zip by zip.** Searching a whole city shows a fraction; each zip returns its own batch. `--all-zips` lists every zip for the city (free zippopotam.us). OSM coverage is thin on websites and has no reviews; for real volume suggest a paid source (MapsData free tier: 500 leads with emails a month is enough to test a niche). MapsData works on cities/states, not zips: it covers the area itself.
3. **Review filter** (when the source has review counts): set a minimum to drop tiny shops and a maximum to drop chains with their own buying process. Start around 20-400 for dental/med spa and adjust.
4. **Websites, then crawl.** `find_websites.py` only accepts a site the page itself proves (name words + phone, or name + city + niche word). `enrich_site.py` reads home, About, Team, Contact, Careers and the footer, and drops listings whose site never mentions the niche.
5. **Owner names: hand-check 50 before the full run.** `find_owner.py --sample 50` writes `owners_handcheck.xlsx`. Open each `owner_page`, mark correct y/n. More than 1-2 wrong in 50: tighten the prompt (`references/owner-prompt.md`) or change model before the full run. The rule never changes: a name only counts when the site shows it next to owner/founder/principal/president/doctor; otherwise "not found". The guard re-reads the page and throws away any LLM name that isn't there next to a title.
6. **Email waterfall.** Site emails first (free), then Prospeo, then Icypeas when keys exist; first valid email wins and `email_source` logs who found it (`waterfall_log.csv`: after a few campaigns it tells John which tools pay off in his niche). Verify: MX always; MillionVerifier if keyed; BounceBan second check for catch-all domains. Target bounce rate under 1%: send only `email_status=valid` from main inboxes; `mx_only`/`risky` from a separate inbox or not at all. Keep info@/office@ for local service businesses (owners read them), flagged `email_type=general`.
7. **Score, dedupe, suppress.** `score.py` adds points for fresh reviews (last 90 days), slow-response complaints in reviews, job posts on their site, no chat/booking, reachability; dedupes on name + city + email domain; drops anything in John's suppression list (already contacted).
8. **One true local fact per lead** (`local_facts.py --market <full pull>`): a nearby competitor with more reviews, their own rating only if 4.0+, or how many same-niche businesses sit within 2 miles (a lower bound from the pull). No fact, no email.
9. **Drafts.** `draft_emails.py`: 3 sentences (local fact, one offer, one question with a free useful offer like a competitor ranking comparison or review audit). Never "saw your Google listing". Show John 3 drafts in chat before he uses the rest; he edits and sends. Follow-ups: `references/email-templates.md`.
10. **Call sheet.** `call_sheet.py export`: highest score first, opener built from a listing fact, "is that costing you work this month?", then a specific meeting time. John logs dialed_at/connected for 2 weeks, then `call_sheet.py hours call_log.csv` shows the hours that answer.
11. **Deliver** `leads.xlsx` + a 3-line summary: how many pulled, how many with owner names, emails (named/general, valid/mx_only/risky), top 5 by score. Remind John: after he sends, `suppress_add.py sent.csv --list ~/leads/suppression.csv`.

## First week (runbook)

Day 1: pick one niche + one area + one offer with John. Pull about 500 businesses (free MapsData tier or OSM zips).
Day 2: crawl the sites; run the owner finder on 50, John hand-checks; fix, then the full run.
Day 3: email waterfall + verification; check the waterfall log and the valid/mx_only/risky split.
Day 4: local facts, drafts; John reviews 3 drafts, edits the template once, approves the batch.
Day 5: John sends a small batch (say 50-100) from a warmed inbox and starts calling the top of the call sheet, logging connect hours.
Then: keep what gets replies; expand to new areas before new niches; re-pull every campaign.

## Rules

- **Drafts only. Never email, text, call, DM or submit a form to a lead.** Not one test send. John sends.
- **Never invent facts.** No guessed names, no made-up numbers, no "I loved your work on X" unless the data says so. Empty beats guessed. Ratings below 4.0 are never mentioned.
- CAN-SPAM (US): John's real postal address and a working opt-out in every email (the drafts carry both; set `SENDER_ADDRESS`), honest subject lines, honour opt-outs within 10 business days and add them to the suppression list. GDPR/CASL where they apply; check with a lawyer for his own case.
- Business contact data only (published by the business or its listing). No bought personal lists.
- US/USD market for 3xAgentic. 3xAgentic is AI-only: never blockchain, crypto or Web3 wording.
- Be polite to sites and free services: few workers, real contact in `OSM_USER_AGENT`.

## Pitfalls

- OpenStreetMap: free but thin (often no website, never reviews). `find_websites.py` recovers some sites; DuckDuckGo rate-limits, so it can take minutes. A paid source fixes both.
- Overpass is shared; the pull rotates public mirrors and reports zips that failed so you can re-run just those (`--zips`).
- Many dental/medical sites only show a form and info@; that is normal. The phone is the main channel.
- Paid adapters are built from each vendor's public docs (read 2026-10-06) and unit-tested with mocked responses; the first live run should be small (`--max-zips 1`, MapsData `--dry-run`).
- JavaScript-only sites can hide emails/booking widgets from a plain fetch: "not seen" is not "absent".

## Verification

- `python3 ${HERMES_SKILL_DIR}/tests/test_adapters.py` -> `OK` (24 offline tests: paid request/parse with mocks, owner guard, waterfall order, scoring, dedupe, suppression, facts, drafts).
- `$PY ${HERMES_SKILL_DIR}/scripts/pull.py --niche dentist --zips 78704 --out /tmp/p.csv` prints "N unique businesses pulled".
- The XLSX opens with Call sheet, Leads, Email drafts, Waterfall log and About sheets; every found owner has an `owner_page`.
