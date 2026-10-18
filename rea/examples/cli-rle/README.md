# CLI binary example (offline)

Run `python3 run_demo.py` (requires `cc`). It compiles a small C tool, treats its stdin/stdout/
stderr and exit code as the original, and compares it with a Python replica for encode, decode and
CRC modes. The source is only included so the example runs offline. Do not read it while trying to
infer behaviour from traces.

Verified 2026-10-18 full run:

| Replica | Checks passed | Mismatch caught |
|---|---:|---|
| v1, buffered decode | 2,864/3,029 | 165 cases showed partial output is emitted before error |
| v2, streaming decode | 3,029/3,029 | zero failures in this input distribution |
| v2 with wrong CRC initial value | 2,264/3,029 | 765 cases failed |

The 3,000 seeded random cases in v2 passed; zero-failure one-sided 95% bound is 99.9001%, for the
**defined synthetic stdin/flag mix only**. This does not cover >1 MiB input or other platforms.
The v1 → triage → v2 iteration is the point: a plausible replica was wrong until the diff found it.
