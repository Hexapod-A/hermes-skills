# API quote example (offline)

Run: `python3 run_demo.py` (from any cwd). This starts an original shop API and an independently
written replica on loopback ports, creates fixed, pairwise, boundary and 4,000 seeded random
requests, compares exact HTTP status/content-type/Allow/body, and turns on a deliberate VAT
rounding bug. `--random 300` is a fast smoke test, not a 99.9% certification. The original source
is here only so this is runnable offline; when practising, read responses, not original_server.py.

Verified full run, 2026-10-18: clean 4,117/4,117 checks; of those, 4,000 random cases passed,
one-sided 95% lower bound 99.925% **for this synthetic input distribution**. The bug run passed
3,968/4,117; 149 cases exposed the banker's rounding mismatch, clustered at `vat_kobo`,
`total_kobo`, `total_display`. Exact test output lives in `results/` (small JSON + Markdown).
This does not certify real user traffic, concurrency, auth, large bodies or future price changes.
A fresh seed/real traffic sample is needed to validate a production replica.

The two UUID/time fields use strict format masks in `rules.json`; wrong format still fails.
`results/evidence.jsonl` shows what was observed, inferred and hypothesised. Raw probe responses
are in `results/probe_observations.jsonl`; larger case traces are regenerated on each run.
