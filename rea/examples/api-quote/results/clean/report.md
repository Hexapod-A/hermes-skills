# Quote API replica (clean)

**Measured fidelity: 4117/4117 checks = 100.000%**. Random sample: 4000/4000; one-sided 95% lower bound: 99.925%.

**99.9% claim for the declared random input distribution: SUBSTANTIATED.**

## What the number means

- Metric: case pass rate: a case passes only if every compared field is equal after the stated rules.
- Scope: POST /v1/quote with JSON bodies (valid, invalid, wrong types), GET /v1/skus, /v1/health, wrong method, unknown path; single requests, no auth, no concurrency. It says nothing about inputs outside that set.
- Cases by source: boundary 33, fixed 21, pairwise 63, random 4000
- Plan seed: 20261018 (re-run with the same seed for the same cases).
- Independently generated random cases needed for a 99.9% claim with 0 failures: 2995.
- Fixed, pairwise and boundary cases are failure gates, not confidence-sample size. A predeclared random generator is the measured distribution; a tuned or cherry-picked run cannot certify future production traffic. Do a fresh holdout for a new version.

## Comparison rules (what was NOT compared exactly)

- fields: `["status", "headers", "body"]`
- mask: `[{"path": "body.quote_id", "regex": "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", "replace": "<uuid4>"}, {"path": "body.created_at", "regex": "^\\d{4}-\\d\\d-\\d\\dT\\d\\d:\\d\\d:\\d\\d(\\.\\d{6})?\\+00:00$", "replace": "<utc-iso>"}]`
- why: quote_id is a fresh UUID4 and created_at is the server clock on every call in the ORIGINAL too (two identical requests gave different values). They are masked by FORMAT, so a replica with a wrong id or time format still fails.

## By dimension

| Dimension | Passed | Rate |
|---|---|---|
| body | 4117/4117 | 100.00% |
| headers | 4117/4117 | 100.00% |
| status | 4117/4117 | 100.00% |

## Evidence

- Entries: {"observed": 3, "hypothesis": 3, "inferred": 1}
- Open hypotheses: none
- Refuted hypotheses: H003

## Untested edges (not covered by this score)

- concurrency and rate limits
- authentication (the API has none in this test)
- request bodies over 1 MB
- HTTP methods other than GET and POST
- latency and timeouts
- non-UTF-8 bodies
- behaviour after catalog or price changes
