# kcode replica (clean)

**Measured fidelity: 3029/3029 checks = 100.000%**. Random sample: 3000/3000; one-sided 95% lower bound: 99.900%.

**99.9% claim for the declared random input distribution: SUBSTANTIATED.**

## What the number means

- Metric: case pass rate: a case passes only if every compared field is equal after the stated rules.
- Scope: kcode -e and -c on stdin of 0-700 bytes (random bytes and long runs); kcode -d on text input (valid and broken encodings), bad usage. It says nothing about inputs outside that set.
- Cases by source: boundary 5, factor 16, fixed 8, random 3000
- Plan seed: 7 (re-run with the same seed for the same cases).
- Independently generated random cases needed for a 99.9% claim with 0 failures: 2995.
- Fixed, pairwise and boundary cases are failure gates, not confidence-sample size. A predeclared random generator is the measured distribution; a tuned or cherry-picked run cannot certify future production traffic. Do a fresh holdout for a new version.

## Comparison rules (what was NOT compared exactly)

- fields: `["exit", "stdout", "stderr", "stdout_b64", "stderr_b64", "files_out", "timeout"]`
- why: Everything the process shows is compared exactly: exit code, stdout bytes, stderr text, files written.

## By dimension

| Dimension | Passed | Rate |
|---|---|---|
| exit | 3029/3029 | 100.00% |
| stderr | 3029/3029 | 100.00% |
| stdout | 2852/2852 | 100.00% |
| stdout_b64 | 177/177 | 100.00% |

## Untested edges (not covered by this score)

- inputs over 1 MiB (the original reads at most 1 MiB; behaviour past it not probed)
- stdin closed early / pipes that fail
- locale or terminal settings
- decode outputs over 1 MiB
