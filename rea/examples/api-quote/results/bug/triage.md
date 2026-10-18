# Mismatch triage

Failures: 149 in 1 clusters. Harness errors: 0.

## Cluster 1: 149 cases (100.0% of failures)

Differs at: body.total_display (value); body.total_kobo (value); body.vat_kobo (value)

First guess (hypothesis, test it): off by one unit: rounding mode (half-up vs half-even), floor vs round, or order of operations | text differs (message wording, format or encoding)

Over-represented inputs: `var.sku="BK-101"` (59% here vs 16% overall), `source="random"` (99% here vs 97% overall)

Smallest failing case `c00068`:

    input: {"json": {"qty": 2, "sku": "BK-205"}, "method": "POST", "path": "/v1/quote"}
    body.total_display: original="₦4,298.93" replica="₦4,298.92"
    body.total_kobo: original=429893 replica=429892
    body.vat_kobo: original=29993 replica=29992

Cases: c00068, c00235, c00238, c00331, c00335, c00351, c00373, c00389, c00390, c00448, c00484, c00503, c00516, c00546, c00597, c00611, c00615, c00619, c00683, c00702 ...

