---
name: lead-gen
description: Verified US small-business lead lists, CSV and XLSX.
version: 1.0.0
author: John (Hexapod-A), 3xAgentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [sales, leads, prospecting, csv, xlsx, 3xagentic]
    category: productivity
    related_skills: [web-research, outreach-and-proposals]
---

# Lead Gen Skill

Builds prospect lists for 3xAgentic: US small businesses that pay in USD and visibly need AI automation (missed calls, no online booking, no instant replies). Every field in the output is observed on the business's own website or a public directory, with the evidence URL and a timestamp. It **never contacts anyone**; John sends all outreach himself.

## When to Use

- "Find me 50 dental clinics / med spas / HVAC companies / realtors in <US city> that need automation."
- Enriching or re-checking an existing lead CSV.
- Picking the best 10 prospects for a campaign.

## Prerequisites

- Repo venv (see README). No API keys needed: candidates come from OpenStreetMap (`osm_search.py`) and from `web_search` / the web-research skill.
- Optional: set `OSM_USER_AGENT="3xagentic-leads (your@email)"` in `~/.hermes/.env` (OpenStreetMap asks for a contact in the user agent).

## How to Run

    PY=${HERMES_SKILL_DIR}/../.venv/bin/python
    # 1. candidates from OpenStreetMap
    $PY ${HERMES_SKILL_DIR}/scripts/osm_search.py --city "Boise, Idaho" --category dentist --require-website --limit 60 --out ~/leads/boise-dentists-raw.csv
    # 2. verify on each business's own site -> CSV + XLSX, best fits first
    $PY ${HERMES_SKILL_DIR}/scripts/verify_leads.py ~/leads/boise-dentists-raw.csv --out ~/leads/boise-dentists --min-score 60

## Quick Reference

Categories: `dentist, med-spa, chiropractor, physio, clinic, veterinary, hvac, plumber, electrician, roofer, home-services, real-estate, law-firm, accountant, insurance, auto-repair, salon, gym, restaurant`, or any raw OSM tag with `--tag craft=hvac`.

Output columns (added by `verify_leads.py`): `website_status, website_final_url, https, emails_found, email_mx_ok, phones_found, us_signal, has_chat_widget, chat_tool, has_online_booking, booking_tool, contact_page, copyright_year, automation_gaps, fit_score, evidence_urls, verified_at, notes`. Template: `templates/leads_template.csv`.

## Procedure

1. **Scope.** Niche, US city/state, count. Default to niches where speed-to-lead matters: dental, med spa, chiropractic, home services, real estate, law.
2. **Candidates.** Run `osm_search.py`. If OpenStreetMap is thin for the city, add businesses found with `web_search` (e.g. "dentist Boise ID") into the same CSV columns, recording the page you found them on in `source`.
3. **Verify.** Run `verify_leads.py`. It visits each site and its contact page, extracts public business emails/phones, checks the email domain has MX records, and spots chat widgets and booking tools.
4. **Review the top rows** by reading the CSV with `read_file`. Spot-check 3 sites yourself with `web_extract`. Drop chains, franchises and anything outside the US.
5. **Deliver** the `.xlsx` path plus a 3-line summary: how many, how many with email, top 5 with their main gap. Offer outreach drafts (outreach-and-proposals skill). Do not send anything.

## Rules

- **Drafts only. Never email, DM, call, text or submit a form to a lead.** Not even "just one test". John reviews and sends.
- Only business contact details published by the business itself. No personal emails, no scraped social profiles of employees, no bought lists.
- No invented fields: an empty cell beats a guessed one. `fit_score` is a priority hint, not a fact about the business.
- USD/US market only for 3xAgentic leads. Skip businesses in other countries.
- Be polite to websites: default 6 workers, normal browser user agent, no hammering.

## Pitfalls

- OpenStreetMap coverage varies by city; small towns may return few results.
- Sites built as JavaScript apps can hide emails/booking widgets from a plain fetch; `has_online_booking=False` means "not seen", so verify top leads by hand.
- Overpass returns HTTP 429/504 when busy; the script retries, then tells you to wait.
- Many dental/medical sites only offer forms, not emails. That's normal; the phone is the channel John will use.

## Verification

- `$PY ${HERMES_SKILL_DIR}/scripts/osm_search.py --city "Boise, Idaho" --category dentist --require-website --limit 5` prints a CSV with 5 rows.
- The XLSX opens with a `Leads` sheet (filters, frozen header) and an `About` sheet explaining the fields.
