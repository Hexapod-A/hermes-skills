# Mismatch triage

Failures: 16 in 2 clusters. Harness errors: 0.

## Cluster 1: 8 cases (50.0% of failures)

Differs at: element_shots.#buy (value); element_shots.#summary (value); styles.#buy.border-radius (value)

First guess (hypothesis, test it): text differs (message wording, format or encoding) | whitespace / trailing newline differs

Over-represented inputs: `var.viewport="[1440, 900]"` (100% here vs 50% overall)

Smallest failing case `c00001`:

    input: {"actions": [], "capture": {"attrs": {"#buy": ["disabled"]}, "boxes": ["header", "#item", "#summary", "#buy", "#coupon"], "element_shots": ["#buy", "#summary", "#item"], "screenshot": true, "styles": {"#buy": ["background-color", "border-radius", "color", "font-size"], "#msg": ["color"], "#summary": ["box-shadow", "border-radius"]}, "text": ["h1", "#qty", "#sub", "#disc", "#vat", "#total", "#msg"]}, "path": "index.html", "viewport": [1440, 900]}
    element_shots.#buy: original="c00001___buy.png" replica="c00001___buy.png"  (3.459% pixels differ)
    element_shots.#summary: original="c00001___summary.png" replica="c00001___summary.png"  (0.411% pixels differ)
    styles.#buy.border-radius: original="24px" replica="8px"

Cases: c00001, c00002, c00003, c00004, c00005, c00006, c00007, c00008

## Cluster 2: 8 cases (50.0% of failures)

Differs at: element_shots.#buy (value); element_shots.#summary (value); screenshot (value); styles.#buy.border-radius (value)

First guess (hypothesis, test it): text differs (message wording, format or encoding) | whitespace / trailing newline differs

Over-represented inputs: `var.viewport="[390, 844]"` (100% here vs 50% overall)

Smallest failing case `c00009`:

    input: {"actions": [], "capture": {"attrs": {"#buy": ["disabled"]}, "boxes": ["header", "#item", "#summary", "#buy", "#coupon"], "element_shots": ["#buy", "#summary", "#item"], "screenshot": true, "styles": {"#buy": ["background-color", "border-radius", "color", "font-size"], "#msg": ["color"], "#summary": ["box-shadow", "border-radius"]}, "text": ["h1", "#qty", "#sub", "#disc", "#vat", "#total", "#msg"]}, "path": "index.html", "viewport": [390, 844]}
    element_shots.#buy: original="c00009___buy.png" replica="c00009___buy.png"  (3.481% pixels differ)
    element_shots.#summary: original="c00009___summary.png" replica="c00009___summary.png"  (0.413% pixels differ)
    screenshot: original="c00009.png" replica="c00009.png"  (0.157% pixels differ)
    styles.#buy.border-radius: original="24px" replica="8px"

Cases: c00009, c00010, c00011, c00012, c00013, c00014, c00015, c00016

