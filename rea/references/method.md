# The REA method

One loop for any target. Each turn of the loop makes the replica closer and the evidence stronger.

    observe -> specify -> hypothesise -> experiment -> rebuild -> differential test -> triage -> (loop)
                                                                                    \-> report (claim gate)

## 1. Observe

Collect raw behaviour before you explain anything. Keep every raw output as a file (response
bodies, HAR files, screenshots, traces, logs). Log each fact with `evidence.py add observed ...
--source ... --artifact FILE`; the sha256 of the artifact is stored, so the claim can be checked later.

Good first probes: the happy path, the same input twice (finds random/time fields), an empty input,
a too-big input, a wrong type, a missing field, an unknown id, a wrong method or flag.

## 2. Specify

Write `templates/spec.md` for the target: interface (inputs, outputs, side effects), states, rules,
errors, and the fidelity metric you will use. Mark every line with its grade:

| Grade | Meaning | Use in the replica |
|---|---|---|
| OBSERVED | You saw it, artifact kept | yes |
| INFERRED | Follows from observed facts by logic (cite them) | yes, but cite |
| HYPOTHESIS | A guess that fits | only after an experiment supports it |

Never write a hypothesis as a fact in the spec or in a report. "The VAT is rounded half-up" is a
hypothesis until a run with tie values shows it.

## 3. Hypothesise and 4. experiment

Turn each unknown into a test you can run. Make the experiment able to fail: pick inputs where the
competing hypotheses give different outputs (for rounding: values that end in exactly .5).
Record the result with `evidence.py test H00n supported|refuted|inconclusive --experiment ... --artifact ...`.

## 5. Rebuild

Build the replica from the spec, not from memory of the original. Put the evidence id next to each
rule in the code (`# E002`, `# H001 supported`), so a refuted hypothesis points at the code to change.

## 6. Differential test

Same cases, both systems, compare outputs. This is the only source of a fidelity number.

- `gen_cases.py` makes the cases: hand-written odd shapes (`fixed_cases`), a factor matrix
  (`pairwise` covers every pair of factor values with few cases), `boundaries` (min, max, just
  outside, empty, null, missing) and seeded `random` cases. The seed makes runs repeatable.
- `run_cases.py` runs them on a target (`http`, `cmd`, `python`, `ui`, or `replay` of captured data).
- `compare.py` compares. Only mask what is random in the original too, mask by format not by
  value, and write why in `rules.why`. Every rule is printed in the report.

## 7. Triage

`triage.py` groups failures by where they differ, shows the smallest failing input and the input
tags that are over-represented. Fix the biggest cluster first, then re-run everything (fixes break
other cases). Its "first guess" is a hypothesis: confirm it with an experiment.

## 8. Report and the claim gate

`report.py` gives the measured pass rate with an exact 95% interval and decides if a target claim
(default 99.9%) is SUBSTANTIATED. All of these must hold:

1. No mismatches at all; a predeclared, independent random sample has a one-sided 95% zero-failure
   lower bound >= target. Fixed/pairwise/boundary cases are failure gates, not confidence sample size.
2. No harness errors (a case that did not run is not a pass).
3. Every planned case source ran, and every declared factor value ran.
4. No open or inconclusive hypotheses in the evidence log (when a log is given).

### How many cases a claim needs

With zero failures, the lower bound is `0.05 ** (1/n)`. So:

| Claim (95% confidence) | Cases needed, 0 failures | With 1 failure |
|---|---|---|
| 99% | 299 | 473 |
| 99.9% | 2995 | 4742 |
| 99.99% | 29956 | 47437 |

16 deterministic UI cases do NOT prove a population rate. A zero-failure random sample of 417
independent cases would give a 99.284% lower bound; the 417-case quick demo mixes hand tests and
randoms, so use the random count from its report instead.

### What a number means

The score is the pass rate **on the tested input distribution**. A confidence claim only covers
fresh, independent draws from a distribution declared before evaluation. Using the same cases to
fix the replica and to certify it is test-set leakage; use a new seed as a holdout when shipping.
The demo's clean result is an illustration on synthetic data, not certification of a real target. It is not a promise about inputs
you did not generate. So the report always prints the scope, the comparison rules, and the
untested edges. Make the distribution honest:

- Mix sources: fixed odd shapes + pairwise + boundaries + random. Random-only plans miss rare branches;
  hand-only plans are small and biased.
- Weight random choices toward real use, but keep invalid inputs in (10-30%).
- If you can capture real traffic (your own app, with permission), replay it as cases: that is the
  best distribution of all.
- Cases must be independent. 3000 copies of one request are one case.
- Report per dimension (status, body, headers / exit, stdout, stderr / text, boxes, styles) so a
  high total does not hide a broken part.

### Allowed wording

- SUBSTANTIATED: "Measured 4117/4117 checks, including 4000 independent seeded random cases;
  zero-failure 95% lower bound 99.925% on the stated synthetic input distribution. Untested: <list>."
- NOT SUBSTANTIATED: "Measured 16/16 UI checks, but none were independent random cases. This
  cannot support 99.9%. At least 2995 zero-failure random cases from a declared distribution
  would be needed for the statistical gate."
- Never: "99.9% accurate" with no scope, no case count, or from a run that had failures removed.

## Stop rules

- Stop when the claim gate passes for the scope the user cares about, or
- when the remaining clusters need access you do not have (say what access would close them), or
- when the user accepts the measured number and the listed gaps.
