---
name: web-research
description: Live web research with dated, cited sources.
version: 1.0.0
author: John (Hexapod-A), 3xAgentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [research, search, citations, web]
    category: research
    related_skills: [lead-gen, outreach-and-proposals]
---

# Web Research Skill

Answers questions from the live web: search, open the actual pages, read them, cross-check, and reply with numbered citations that carry each source's date. Snippets are leads, not evidence. It does not guess from memory when the answer can change.

## When to Use

- Anything current: prices, tools, laws, people, companies, news, "what's the best X right now".
- Fact-checking a claim before it goes into a flyer, proposal or post.
- Background on a prospect or market before outreach.

## Prerequisites

- Native tools first: `web_search`, `web_extract`, and the browser tools (`browser_navigate`, `browser_snapshot`) for JavaScript-heavy pages.
- Fallback scripts need the repo venv (see README). Optional search keys in `~/.hermes/.env`: `SEARXNG_URL`, `BRAVE_API_KEY`, `SERPER_API_KEY` or `TAVILY_API_KEY`. With none set, `search.py` uses DuckDuckGo's HTML endpoint, which rate-limits datacenter IPs.

## How to Run

    # search (JSON: title, url, snippet, date, backend)
    ${HERMES_SKILL_DIR}/../.venv/bin/python ${HERMES_SKILL_DIR}/scripts/search.py "ai receptionist pricing for dental clinics" -n 8 --recent year

    # read live pages (clean text + title, final URL, published/modified date, fetch time)
    ${HERMES_SKILL_DIR}/../.venv/bin/python ${HERMES_SKILL_DIR}/scripts/fetch.py https://example.com/a https://example.com/b --max-chars 8000 --out ~/research/<topic>

## Quick Reference

| Need | Use |
|---|---|
| Search | `web_search`, else `scripts/search.py` |
| Read a page | `web_extract`, else `scripts/fetch.py` |
| JS app / login wall / infinite scroll | `browser_navigate` + `browser_snapshot` |
| Very recent | `--recent week` and the source's own site, not aggregators |
| Save notes for a long job | `fetch.py --out DIR`, then `read_file` |

## Procedure

1. **Frame it.** Restate the question in one line and note what would change the answer (date range, country: default US/USD for 3xAgentic work).
2. **Search wide, then narrow.** 2–4 queries with different wording. Prefer primary sources: official sites, docs, filings, pricing pages, the company's own announcements, government data.
3. **Open the pages.** Read at least 3 independent sources for anything that matters. Never cite a page you did not open. If a page is blocked, use another source or the browser tools; say what you could not read.
4. **Date everything.** Record each source's published or updated date (from `fetch.py` or the page) and today's date. Flag anything older than 12 months for fast-moving topics.
5. **Cross-check.** If sources disagree, say so and say which you trust and why (primary > secondary, newer > older, specific > vague).
6. **Answer.** Lead with the answer in 1–3 short sentences, then the supporting points, then sources:

       [1] Title, Site, published 2026-08-12, https://… (read 2026-10-04)

7. **Keep claims honest.** No invented numbers. If you could not verify something, write "unverified" next to it or leave it out.

## Pitfalls

- Search snippets and AI overviews are cached copies, sometimes months old. Prices and features change; read the live page.
- SEO listicles copy each other. Three listicles saying the same thing is one source.
- `fetch.py` returns little text on JavaScript apps; switch to the browser tools.
- Respect paywalls and robots rules; summarize, don't paste long passages.

## Verification

- `${HERMES_SKILL_DIR}/../.venv/bin/python ${HERMES_SKILL_DIR}/scripts/fetch.py https://hermes-agent.nousresearch.com/docs/ --max-chars 300` prints a title, status=200 and text.
- Every final answer has numbered sources with URLs and dates.
