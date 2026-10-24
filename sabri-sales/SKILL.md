---
name: sabri-sales
description: Sabri Suby-style sales and content copy for 3x Agentic.
version: 1.0.0
author: John (Hexapod-A), 3x Agentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [sales, copywriting, cold-email, cold-dm, content, tiktok, x, linkedin, vsl, landing-page, offer, 3xagentic]
    category: productivity
    related_skills: [outreach-and-proposals, lead-gen, maps-lead-gen, web-research, flyer-studio, video-clipper]
---

# Sabri Sales — Sabri Suby's selling system, done honestly for 3x Agentic

Writes outbound messages, content and offer pages for **3x Agentic** using Sabri Suby's method: research the buyer, lead with pain, make an offer they can't refuse, remove the risk, use real scarcity, and always give one next step. Built from his long YouTube videos (transcripts), his sales letter, his agency site and his posts. Every draft is checked by `scripts/lint_copy.py` against John's rules. Drafts only: John sends and posts.

## When to Use

- "Write a cold email / cold DM / follow-up for {lead or niche}."
- "Give me a TikTok / Reels script", "an X post or thread", "a LinkedIn post".
- "Write the landing page / offer page / VSL script."
- "Prep me for an audit call with {prospect}."
- "Make a week of outreach and content for {niche}."
Not for prices, proposals or SOWs: use `outreach-and-proposals`. Not for finding leads: use `lead-gen` or `maps-lead-gen`.

## Prerequisites

- Python 3.8+ (standard library only) for the lint.
- Read once per session: `references/method.md` (the system), `references/offer-stack.md` (the offer and the three guarantees), `references/voice-rules.md` (John's rules).
- Brand facts: `brands/3x-agentic.json`. The only numbers copy may use live there.

## How to Run

    # lint a draft (exit 0 = no errors)
    python3 ${HERMES_SKILL_DIR}/scripts/lint_copy.py ~/3xagentic/content/drafts/post.md
    # require the CTA
    python3 ${HERMES_SKILL_DIR}/scripts/lint_copy.py --cta draft.md
    # lint only the ```copy blocks in a file
    python3 ${HERMES_SKILL_DIR}/scripts/lint_copy.py --blocks draft.md
    # self-test: every example in this skill passes, bad copy fails
    python3 ${HERMES_SKILL_DIR}/tests/test_lint.py

Save drafts as Markdown, one file per piece or per lead: `~/3xagentic/sales/{outbound|content|conversion}/{date}-{slug}.md`. Put the final copy inside a ```copy block so `--blocks` can check it.

## Quick Reference

Modules (segregated; pick one per request):

| Module | Channel | Template |
|---|---|---|
| Outbound | Cold email | `templates/outbound/cold-email.md` |
| Outbound | Cold DM: LinkedIn, X, Instagram | `templates/outbound/cold-dm.md` |
| Outbound | Follow-ups and break-up | `templates/outbound/follow-ups.md` |
| Content | TikTok / Reels / Shorts scripts | `templates/content/short-video.md` |
| Content | X posts and threads | `templates/content/x-posts.md` |
| Content | LinkedIn posts | `templates/content/linkedin-posts.md` |
| Conversion | Landing / offer page + FAQ | `templates/conversion/landing-page.md` |
| Conversion | VSL, bridge and follow-up videos | `templates/conversion/vsl-script.md` |
| Conversion | Audit call prep + plan email | `templates/conversion/audit-call.md` |

The offer in one breath: **Free automation audit → plan you keep → build → 6 months of care.** Pay half after you see it work. Audit fee credited to the build. Up to 10 audits a week.
Proof (only these): 3+ years · 23+ systems · 450+ hours saved · 12 industries.
CTA (always these words): **Book a free automation audit** · 3xagentic.xyz.
Hooks: `references/hooks.md` (7 types with Sabri's real examples).

## Procedure

1. **Pick the module** from the request. If the request mixes channels, do one module at a time and label each section (OUTBOUND / CONTENT / CONVERSION).
2. **Research the buyer** (method §2). For outbound: open the prospect's site, reviews, job ads or posts with `web_extract` and write down one true detail and the task "nearest to money". For content: name the dream buyer and their pain in their own words. Never guess a detail.
3. **Pick the angle**: the pain, the task, and the hook type from `references/hooks.md`. Write 3 hook options.
4. **Write the draft** from the module template. Pain first, then the fix, then proof (allowed numbers only), then the offer and risk reversal where the format has room, then the CTA. Keep sentences short (voice-rules).
5. **Run the Godfather test** in `references/offer-stack.md` for any piece that states the offer.
6. **Lint**: `python3 ${HERMES_SKILL_DIR}/scripts/lint_copy.py --blocks <file>`. Fix every ERROR. Fix warnings unless there is a reason (say it in the file).
7. **Deliver**: save the file, show John the copy plus the 3 hook options, the true detail you used and where you found it. **Do not send, post or schedule.** John sends.

For "a week of outreach and content": 10-20 researched cold emails or DMs (one per lead, each with a different true detail), the follow-ups for each, 3 short-video scripts, 3 X posts or a thread, 2 LinkedIn posts. Track inputs daily (method §12): sent, replies, audits booked, audits held.

## Pitfalls

- Generic openers ("I came across your business") get ignored. One real detail beats any template line.
- "AI" in the hook scares or bores owners. Talk about the task and the time.
- Borrowing Sabri's numbers or style of money talk reads as fake. Use John's proof only.
- Stretching the guarantees ("we fix anything", "free changes") creates disputes. Fixes and upkeep, not new features.
- Fake urgency kills trust with the exact owners we want. The 10-a-week limit is enough.
- A teardown of a real named business without consent can backfire. Use a labeled mock.
- Pitching in the first DM. Ask a question first.
- Posting in bulk (Sabri's 7-clip dump flopped). Post steadily.

## Verification

- `python3 ${HERMES_SKILL_DIR}/tests/test_lint.py` prints `ALL PASS` (every ```copy example in the templates passes; the bad samples fail).
- Every delivered draft has 0 lint errors, uses the exact CTA wording, writes "3x Agentic" with a space, and has no price.
- Outbound drafts name the true detail and its source in the draft file (not in the message).
