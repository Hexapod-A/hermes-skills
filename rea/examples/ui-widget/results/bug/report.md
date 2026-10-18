# Cart widget replica (bug)

**Measured fidelity: 0/16 checks = 0.000%**. Random sample: 0/0; zero-failure one-sided 95% lower bound: 0.000%.

**99.9% claim for the declared random input distribution: NOT SUBSTANTIATED.** Reasons: 16 of 16 cases fail; fix the mismatch before a fidelity claim | no independently generated random cases; hand-picked checks do not support a statistical claim

## What the number means

- Metric: case pass rate over text, boxes (1 px), computed styles, attributes and screenshot (<= 0.1% pixels differ).
- Scope: cart page at 1440x900 and 390x844: first paint, qty stepper (up, down, to 0, cap at 9), coupon good/bad/lower-case, combined flows. It says nothing about inputs outside that set.
- Cases by source: factor 16
- Plan seed: 3 (re-run with the same seed for the same cases).
- Independently generated random cases needed for a 99.9% claim with 0 failures: 2995.
- Fixed, pairwise and boundary cases are failure gates, not confidence-sample size. A predeclared random generator is the measured distribution; a tuned or cherry-picked run cannot certify future production traffic. Do a fresh holdout for a new version.

## Comparison rules (what was NOT compared exactly)

- fields: `["text", "boxes", "styles", "attrs", "screenshot", "page_errors", "title", "element_shots"]`
- tol: `{"boxes.*": 1}`
- images: `["screenshot", "element_shots.*"]`
- why: Boxes may differ by 1 px (sub-pixel rounding between grid and flex layouts). Screenshots (whole viewport and per part) pass when at most 0.1% of pixels differ by more than 16/255 in grey level. Per-part shots are there because a whole-page threshold can hide a small part that changed. Text, styles and attributes are exact.

## By dimension

| Dimension | Passed | Rate |
|---|---|---|
| attrs | 16/16 | 100.00% |
| boxes | 16/16 | 100.00% |
| element_shots | 0/16 | 0.00% |
| page_errors | 16/16 | 100.00% |
| screenshot | 8/16 | 50.00% |
| styles | 0/16 | 0.00% |
| text | 16/16 | 100.00% |
| title | 16/16 | 100.00% |

## Mismatch clusters

1. 8 cases, at element_shots.#buy (value); element_shots.#summary (value); styles.#buy.border-radius (value). Guess: text differs (message wording, format or encoding) | whitespace / trailing newline differs. Smallest: `{"actions": [], "capture": {"attrs": {"#buy": ["disabled"]}, "boxes": ["header", "#item", "#summary", "#buy", "#coupon"], "element_shots": ["#buy", "#summary", `
2. 8 cases, at element_shots.#buy (value); element_shots.#summary (value); screenshot (value); styles.#buy.border-radius (value). Guess: text differs (message wording, format or encoding) | whitespace / trailing newline differs. Smallest: `{"actions": [], "capture": {"attrs": {"#buy": ["disabled"]}, "boxes": ["header", "#item", "#summary", "#buy", "#coupon"], "element_shots": ["#buy", "#summary", `

## Untested edges (not covered by this score)

- hover and focus states
- other viewports and browser zoom
- fonts other than DejaVu Sans (the box's font)
- animations and transitions
- keyboard-only navigation and screen readers
- Safari and Firefox rendering
