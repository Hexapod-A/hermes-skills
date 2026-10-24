#!/usr/bin/env python3
"""Self-test for sabri-sales: every ```copy example passes the lint; known-bad copy fails."""
import glob, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
LINT = os.path.join(SKILL, "scripts", "lint_copy.py")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import lint_copy  # noqa: E402

brand = lint_copy.load_brand(lint_copy.DEFAULT_BRAND)
fails = 0

# 1. every filled example in the templates and examples passes
files = sorted(glob.glob(os.path.join(SKILL, "templates", "*", "*.md")) + glob.glob(os.path.join(SKILL, "examples", "*.md")))
n_blocks = 0
for f in files:
    blocks = lint_copy.blocks(open(f, encoding="utf-8").read())
    if not blocks and "templates" in f:
        print(f"FAIL no copy examples in {os.path.relpath(f, SKILL)}"); fails += 1
    for i, b in enumerate(blocks):
        n_blocks += 1
        e, _ = lint_copy.lint(b, brand)
        if e:
            fails += 1
            print(f"FAIL {os.path.relpath(f, SKILL)} example {i+1}: {e}")
print(f"checked {n_blocks} examples in {len(files)} files")

# 2. bad copy must fail, each for the expected reason
bad = {
    "Stop the grind and earn passive income.": "banned",
    "3xAgentic builds automations.": "wordmark",
    "Builds start at $1,500.": "price",
    "We cut admin time by 80% for clients.": "number not on the allowed list",
    "Act now, this offer ends soon.": "fake urgency",
    "We also build on blockchain.": "banned",
    "Try a free build, or get your money back.": "banned",
}
for text, reason in bad.items():
    e, _ = lint_copy.lint(text, brand)
    if not any(reason in x for x in e):
        fails += 1
        print(f"FAIL bad sample passed or wrong reason: {text!r} -> {e}")

# 3. good copy passes, CTA check works
good = "We have built 23+ systems and saved clients 450+ hours in 12 industries over 3+ years. We do up to 10 audits a week. Book a free automation audit."
e, _ = lint_copy.lint(good, brand, require_cta=True)
if e:
    fails += 1; print(f"FAIL good sample: {e}")
e, _ = lint_copy.lint("Great tips today.", brand, require_cta=True)
if not any("missing CTA" in x for x in e):
    fails += 1; print("FAIL CTA check did not fire")

# 4. CLI exit codes
r = subprocess.run([sys.executable, LINT, "-"], input="Stop the grind.", capture_output=True, text=True)
if r.returncode != 1:
    fails += 1; print(f"FAIL CLI exit code on bad copy: {r.returncode}")

print("ALL PASS" if fails == 0 else f"{fails} FAILURES")
sys.exit(1 if fails else 0)
