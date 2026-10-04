---
name: outreach-and-proposals
description: Outreach drafts, proposals and SOWs for 3xAgentic.
version: 1.0.0
author: John (Hexapod-A), 3xAgentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [sales, email, proposals, sow, pricing, 3xagentic]
    category: productivity
    related_skills: [lead-gen, docs-and-pdfs, web-research]
---

# Outreach and Proposals Skill

Writes cold emails, DMs and follow-ups as **drafts for John to send**, and turns a discovery call or notes into a priced proposal and a Statement of Work as branded PDFs. Uses 3xAgentic's pricing ranges. It never sends, posts or submits anything on its own.

## When to Use

- "Draft outreach for these leads" (usually the XLSX from lead-gen).
- "Write a follow-up to <name>", "reply to this prospect".
- "Make a proposal / SOW for <client>", "what should I charge for X?"

## Prerequisites

- docs-and-pdfs skill in the same repo (used to render PDFs).
- References: `references/pricing.md`, `references/outreach-playbook.md`. Templates: `templates/cold-email.md`, `templates/proposal.md`, `templates/sow.md`.

## How to Run

    # proposal or SOW -> PDF (fill the template into a new file first)
    node ${HERMES_SKILL_DIR}/../docs-and-pdfs/scripts/build.mjs ~/3xagentic/clients/acme/proposal.md --out ~/3xagentic/clients/acme/proposal.pdf --preview

Drafts are saved as Markdown, one file per lead: `~/3xagentic/outreach/drafts/<business-slug>.md` (email + 3 follow-ups + DM version).

## Quick Reference

| Tier | Build | Monthly |
|---|---|---|
| Pilot | $500–750 | none |
| Starter | $1,000–2,000 | $250–400 |
| Growth | $2,500–4,000 | $500–800 |
| Pro | $5,000–10,000 | scoped |

Cold email: specific observed gap → cost in plain words → what we do + Pilot → 15-minute ask. Under 120 words. CAN-SPAM footer and opt-out line.

## Procedure

**Outreach drafts**
1. For each lead, read its row (website, `automation_gaps`, evidence URLs). Open the site with `web_extract` if you need one specific, true detail.
2. Write the email from `templates/cold-email.md` following `references/outreach-playbook.md`. Every claim about the business must be something you saw on their site. No invented stats, results, clients or familiarity.
3. Add follow-ups (day 3, 7, 14) and a 2-sentence DM version.
4. Save with `write_file` and show John the first 2–3 drafts in chat. **Do not send.** If John says "send it", tell him the draft is ready for him to send from his own inbox; only send yourself if he explicitly asks you to, for that specific message, and he has connected an email tool.

**Proposals and SOWs**
1. Collect: client name, their problem in their words, current process, tools they use, the workflows, timeline. Ask John for anything missing; leave `{{placeholder}}` rather than guess.
2. Recommend a tier and price from `references/pricing.md` with one line of reasoning. Present it to John as a recommendation.
3. Copy `templates/proposal.md` (and `templates/sow.md` once they agree) into the client folder, fill it, build the PDF, fix any unfilled placeholders the build reports, and view page 1 with `vision_analyze` if available.
4. Deliver the PDF path(s) to John. He sends them.

## Rules

- **Never contact third parties without John's OK**: no emails, DMs, form submissions, calls or texts to leads or clients from this agent.
- USD pricing; US clients. 3xAgentic is AI-only: no blockchain, crypto or Web3 language anywhere.
- No fabricated claims: no made-up ROI, case studies, testimonials, logos or "trusted by".
- Casual, short, human tone. No hype words.

## Pitfalls

- Generic openers ("I came across your business") get ignored; use one real observation.
- Proposals that list features instead of outcomes don't close; tie every workflow to a result the client said they want.
- Don't promise timelines that depend on the client's access/approvals without saying so.

## Verification

- `node ${HERMES_SKILL_DIR}/../docs-and-pdfs/scripts/build.mjs ${HERMES_SKILL_DIR}/examples/proposal-example.md --out /tmp/proposal.pdf` prints `"errors": []` and `"pages": 2`.
- Every draft file contains no sent-status claims and ends with the opt-out line.
