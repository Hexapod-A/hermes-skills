# Mismatch triage

Failures: 165 in 2 clusters. Harness errors: 0.

## Cluster 1: 122 cases (73.9% of failures)

Differs at: stdout (extra_in_replica); stdout_b64 (missing_in_replica)

First guess (hypothesis, test it): replica adds stdout the original does not have | replica never sets stdout_b64 (schema or branch missing)

Over-represented inputs: `source="random"` (100% here vs 99% overall)

Smallest failing case `d00284`:

    input: {"args": ["-d"], "stdin": "38Ea xa7"}
    stdout: original=null replica=""
    stdout_b64: original="6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6urq6uo=" replica=null

Cases: d00025, d00031, d00044, d00051, d00052, d00063, d00082, d00102, d00115, d00126, d00149, d00161, d00194, d00204, d00215, d00226, d00258, d00263, d00264, d00268 ...

## Cluster 2: 43 cases (26.1% of failures)

Differs at: stdout (value)

First guess (hypothesis, test it): text differs (message wording, format or encoding)

Over-represented inputs: `source="random"` (100% here vs 99% overall)

Smallest failing case `d00654`:

    input: {"args": ["-d"], "stdin": "bF69E4 0"}
    stdout: original="iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii" replica=""

Cases: d00049, d00127, d00166, d00199, d00255, d00266, d00288, d00341, d00349, d00379, d00386, d00422, d00451, d00476, d00481, d00491, d00537, d00566, d00587, d00613 ...

