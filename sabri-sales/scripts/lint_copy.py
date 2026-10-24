#!/usr/bin/env python3
"""lint_copy.py - check 3x Agentic sales copy against John's rules.

Usage:
  python3 lint_copy.py DRAFT.md [MORE.md ...]          # lint whole files (drafts)
  python3 lint_copy.py --blocks TEMPLATE.md            # lint only ```copy fenced blocks
  echo "text" | python3 lint_copy.py -                 # lint stdin
Options: --brand PATH (default: ../brands/3x-agentic.json)  --json  --cta (require the CTA)

Exit code 0 = no errors (warnings allowed), 1 = errors found, 2 = bad input.
Standard library only.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BRAND = os.path.join(HERE, "..", "brands", "3x-agentic.json")
SPELLED = r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|hundred|thousand|million|billion|dozen)\b"
PRICE = r"(\$\s?\d|\bUSD\s?\d|\d\s?(k|K)\b|\bper\s+month\b|/mo\b|\bdollars?\b|\bpric(e|ing)\s+(is|starts|from)\b)"


def load_brand(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def blocks(text):
    return [m.group(1) for m in re.finditer(r"```copy[^\n]*\n(.*?)```", text, re.S)]


def strip_placeholders(text):
    return re.sub(r"\{[^{}\n]{1,60}\}", "X", text)


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n", text)
    return [p.strip() for p in parts if p.strip()]


def lint(text, brand, require_cta=False):
    errors, warnings = [], []
    body = strip_placeholders(text)
    low = body.lower()

    for w in brand["banned_phrases"]:
        if re.search(r"(?<![\w-])" + re.escape(w.lower()) + r"(?![\w-])", low):
            errors.append(f"banned word/phrase: '{w}'")
    for w in brand["fake_urgency"]:
        if w.lower() in low:
            errors.append(f"fake urgency: '{w}' (use the real limit: 10 audits a week)")
    for w in brand["wordmark_wrong"]:
        if re.search(r"(?<![\w.])" + re.escape(w) + r"(?![\w.])", body) and w != brand["name"]:
            errors.append(f"wordmark: write '{brand['name']}', not '{w}'")
    if re.search(PRICE, body, re.I):
        errors.append("price or money amount found: this skill never states prices")

    scan = body
    for s in brand["strip_before_number_scan"]:
        scan = re.sub(re.escape(s), " ", scan, flags=re.I)
    for pat in brand["allowed_number_patterns"]:
        scan = re.sub(pat, " ", scan, flags=re.I)
    for m in re.finditer(r"\d[\d,.]*\s*\+?%?", scan):
        ctx = scan[max(0, m.start() - 25): m.end() + 25].replace("\n", " ")
        errors.append(f"number not on the allowed list: '{m.group(0).strip()}' in '...{ctx.strip()}...'")
    for m in re.finditer(SPELLED, scan, re.I):
        warnings.append(f"spelled-out number '{m.group(0)}': is it a real, allowed fact?")

    for w, fix in brand["warn_words"].items():
        if re.search(r"\b" + re.escape(w) + r"\b", low):
            warnings.append(f"plain English: '{w}' -> {fix}")
    limit = brand.get("max_words_per_sentence", 20)
    for s in sentences(body):
        n = len(re.findall(r"[A-Za-z0-9'%+/-]+", s))
        if n > limit:
            warnings.append(f"long sentence ({n} words > {limit}): '{s[:70]}...'")
    if body.count("!") > 1:
        warnings.append(f"{body.count('!')} exclamation marks: keep it calm")
    if require_cta and brand["cta"].lower() not in low:
        errors.append(f"missing CTA: '{brand['cta']}'")
    return errors, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--brand", default=DEFAULT_BRAND)
    ap.add_argument("--blocks", action="store_true", help="lint only ```copy fenced blocks")
    ap.add_argument("--cta", action="store_true", help="error if the CTA is missing")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    brand = load_brand(a.brand)
    results, total_err = [], 0
    for p in a.paths:
        text = sys.stdin.read() if p == "-" else open(p, encoding="utf-8").read()
        units = [(f"{p}#copy{i+1}", b) for i, b in enumerate(blocks(text))] if a.blocks else [(p, text)]
        if a.blocks and not units:
            print(f"{p}: no ```copy blocks found", file=sys.stderr)
            return 2
        for name, t in units:
            e, w = lint(t, brand, a.cta)
            total_err += len(e)
            results.append({"unit": name, "errors": e, "warnings": w})
    if a.json:
        print(json.dumps({"ok": total_err == 0, "results": results}, indent=2))
    else:
        for r in results:
            status = "PASS" if not r["errors"] else "FAIL"
            print(f"{status} {r['unit']} ({len(r['errors'])} errors, {len(r['warnings'])} warnings)")
            for e in r["errors"]:
                print(f"  ERROR {e}")
            for w in r["warnings"]:
                print(f"  warn  {w}")
    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
