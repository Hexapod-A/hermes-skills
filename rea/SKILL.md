---
name: rea
description: Rebuild observable systems and prove the match.
version: 1.0.0
author: John (Hexapod-A), 3xAgentic
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [reverse-engineering, api, web, mobile, binary, firmware, video, differential-testing]
    category: engineering
    related_skills: [ui-replicate, web-unblock, web-research]
---

# REA — Reverse Engineer Anything

A standalone method and test kit for rebuilding an observable result: a website, API, mobile app,
binary, video, or public product workflow. It does not just describe how the target *might* work.
It keeps evidence, runs the same cases on original and replica, groups mismatches, fixes them,
and measures the match. "99.9%" is a measured target for a named scope, never a blanket promise.

## When to Use

- "Rebuild this system so the outputs behave the same" — from a URL, app, binary, file or demo.
- "Find the hidden rules behind these responses" — exact API errors, pricing maths, edge cases.
- "How close is our replica?" — evidence, differential score, remaining gaps.
- "Reverse engineer this product/process" — public customer journey, not private internals.

For only the look of a screenshot, use `ui-replicate`. For reading a blocked public page, use
`web-unblock`. REA owns the broader behaviour and the proof loop; neither other skill is required.
Do not use it to break into private systems. See `references/safety.md`.

## Prerequisites

- Core API/CLI tools: Python 3.10+ standard library; no key or service needed.
- UI probes: Node 18+, Playwright and Chromium. Use the repo's `npm install` and
  `npx playwright install chromium` from the root README. Set `CHROME_PATH` for an existing Chrome.
  Pixel compare needs Pillow (repo `requirements.txt`).
- Media checks: `ffmpeg` and `ffprobe` on PATH. CLI binary demo: a C compiler (`cc`).
- Work folder: copy the templates there. Keep raw observations out of a public repo if they contain
  private data. Never commit secrets, HAR credentials or a person's data.

## How to Run

Run the offline API demo. It makes an original and a replica locally, compares them, and then
turns on a deliberate rounding bug to prove the detector catches it:

    SKILL=/path/to/hermes-skills/rea
    python3 "$SKILL/examples/api-quote/run_demo.py" --results /tmp/rea-quote
    cat /tmp/rea-quote/summary.json
    cat /tmp/rea-quote/bug/triage.md

On the verified 2026-10-18 full run: clean 4,117/4,117 checks; 4,000 seeded random cases with a
zero-failure 95% lower bound of 99.925% for this **synthetic quote-input distribution only**.
Buggy replica: 3,968/4,117 checks; 149 mismatches in VAT and total fields. Fresh production use
needs a new holdout seed and tests drawn from the actual traffic distribution. This example does
not prove 99.9% on websites, mobile apps or anything outside the local quote API.

Quick smoke test (less work; cannot substantiate 99.9%):

    python3 "$SKILL/examples/api-quote/run_demo.py" --random 300 --results /tmp/rea-quick
    python3 -m unittest discover -s "$SKILL/tests" -v

Other offline examples: `examples/cli-rle/run_demo.py` (compiled C binary, v1 → triage → v2),
`examples/ui-widget/run_demo.py` (two viewports, clicks, DOM/styles/screenshots),
`examples/media-clip/run_demo.py` (frame timeline + audio loudness). Their README files explain
scope and limits.

## Quick Reference

| Script | Job |
|---|---|
| `scripts/evidence.py` | Append and check an evidence log; link claims to raw artifacts and experiments. |
| `scripts/gen_cases.py` | Fixed odd cases, factor matrix (each/pairwise/full), boundaries and seeded random cases. |
| `scripts/run_cases.py` | Run original or replica targets (`http`, `cmd`, `python`, `ui`, `replay`) to observation JSONL. |
| `scripts/ui_probe.mjs` | Browser actions + DOM text/boxes/styles/attributes and full/per-element screenshots. |
| `scripts/compare.py` | Exact path-level diff with explicit masks/tolerances, dimensions and image comparisons. |
| `scripts/triage.py` | Group failures, show representative inputs and likely causes (as hypotheses). |
| `scripts/media_compare.py` | Duration, frame timeline, audio RMS windows, SSIM/PSNR and best time shift. |
| `scripts/report.py` | Coverage and 99.9% claim gate; measured score plus what is untested. |

Use the same steps on a new job:

    S=/path/to/hermes-skills/rea/scripts
    python3 "$S/gen_cases.py" plan.json --out cases.jsonl --seed 1810
    python3 "$S/run_cases.py" --target original.json --cases cases.jsonl --out original.jsonl
    python3 "$S/run_cases.py" --target replica.json --cases cases.jsonl --out replica.jsonl
    python3 "$S/compare.py" original.jsonl replica.jsonl --cases cases.jsonl --rules rules.json --out compare.json
    python3 "$S/triage.py" compare.json --out triage.md --json triage.json
    python3 "$S/report.py" --compare compare.json --meta cases.meta.json --triage triage.json --evidence evidence.jsonl --out report.md

`compare.py` returns 2 on mismatches; `report.py` returns 3 when 99.9% is not substantiated.
These are informative states, not crashes. Fix and rerun. `gen_cases.py` takes more than one plan
for different endpoints/modes. `run_cases.py` can compare captured `replay` observations when the
original is offline. A harness error never counts as a match.

## Procedure

1. **Observe.** Run the original. Save raw responses, screenshots or traces. Log each claim with
   `scripts/evidence.py add observed ... --source ... --artifact ...`.
2. **Specify.** Fill `templates/spec.md`: inputs, outputs, side effects, states, errors, what
   metric counts as a pass and what you cannot see. Mark OBSERVED / INFERRED / HYPOTHESIS.
3. **Hypothesise.** State possible rules. Design experiments whose outputs separate them. Test
   edge values (missing, empty, wrong type, min/max, tie-rounding, repeated calls). Do not pass a
   guess as a fact. `evidence.py test H001 supported|refuted --experiment ... --artifact ...`.
4. **Rebuild.** Implement the smallest model that fits what was observed. Link code rules to
   evidence ids. Keep the original and replica in separate processes/accounts.
5. **Differential test.** Generate a fixed+pairwise+boundary+seeded-random matrix; run the same
   cases on both targets; compare exact outputs after explicit, documented masks.
6. **Triage and repeat.** `triage.py` groups errors by path and finds a small failing input.
   Its proposed cause is a new hypothesis. Fix the cause, rerun the full matrix, then use a fresh
   random holdout for final claims.
7. **Report.** `report.py` states the observed pass rate, scope, random-sample confidence bound,
   coverage, comparison rules and untested edges. It refuses 99.9% when the tests cannot back it.

Full guide: `references/method.md`. Domain guides below keep each medium's metric separate.

## Domain Guides

| Target | Read | What to measure |
|---|---|---|
| Website/UI | `references/websites-ui.md` | screenshots, DOM, interaction, matched viewports |
| API | `references/apis.md` | status, headers, body/schema, errors, maths, randomized cases |
| Mobile app | `references/mobile-apps.md` | screen states, taps, network, OS/device versions |
| Binary/firmware | `references/binaries-firmware.md` | input/output bytes, exit, files, traces, hardware limits |
| Video/content | `references/media-content.md` | timeline, frames, audio and human editorial rubric |
| Public product/process | `references/products-processes.md` | dated prices, journey outcomes, public evidence |

## Fidelity Rule

A case passes only if **every chosen dimension** matches after declared rules. Never merge SSIM,
API statuses and human ratings into one 'god score'. A statistical 99.9% claim needs at least 2,995
independent zero-failure random cases at 95% one-sided confidence, plus no failures in fixed,
pairwise or boundary cases and no untested hypothesis the replica relies on. The random generator
must define the scope and be set before evaluation. If the target changes, the claim expires.
Even a passing number covers only that input distribution and the dimensions named in the report.

## Pitfalls

- An API can return correct values but wrong status, header, type, error shape or validation order.
- A pixel match at one viewport can hide a broken click flow or a mobile layout.
- A whole-page image score can hide one wrong button; check per-element shots and computed styles.
- A CLI can emit partial output before an error. Buffering until success changes observable output.
- Two video files can have matching duration yet a shifted cut or silent audio.
- Black-box observations cannot prove the source algorithm. Rebuild *behaviour*, label guesses,
  and use the experiment that would distinguish competing rules.

## Verification

Run `python3 -m unittest discover -s rea/tests -v` from the repo root. Then run the four offline
examples. Each writes a `results/summary.json` with the exact passed/compared count and verdict.
If any demo cannot run because a system dependency is missing, say so; do not claim it passed.
Re-run on a fresh random seed for a new replica version and keep the report with its scope.
