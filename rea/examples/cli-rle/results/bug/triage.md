# Mismatch triage

Failures: 765 in 1 clusters. Harness errors: 0.

## Cluster 1: 765 cases (100.0% of failures)

Differs at: stdout (value)

First guess (hypothesis, test it): text differs (message wording, format or encoding)

Over-represented inputs: `var.mode="-c"` (100% here vs 25% overall), `source="random"` (99% here vs 99% overall)

Smallest failing case `b00009`:

    input: {"args": ["-c"], "stdin_hex": ""}
    stdout: original="FFFF\n" replica="0000\n"

Cases: b00009, b00010, b00011, b00012, b00013, b00014, b00015, b00016, b00017, b00018, b00021, b00024, b00027, b00028, b00033, b00036, b00037, b00038, b00039, b00040 ...

