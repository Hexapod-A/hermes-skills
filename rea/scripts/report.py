#!/usr/bin/env python3
"""Final REA report with an honest claim gate.

  python report.py --compare compare.json [--meta cases.meta.json] [--evidence ev.jsonl]
                   [--target 0.999] [--min-per-source 1] --title "Quote API replica" --out report.md

The claim gate. A fidelity claim of T (default 99.9%) is SUBSTANTIATED only when all hold:
  1. a zero-failure sample of independent random cases has a one-sided lower bound (default
     95% confidence) >= T (needs >= 2995 random cases for 99.9%); all non-random cases pass too
  2. no harness errors (a case that did not run is not a pass)
  3. every case source in the plan (fixed, pairwise, boundary, random...) ran at least
     --min-per-source cases, and every declared factor value appears in a run case
  4. (if --evidence) no hypothesis the replica depends on is still open or refuted
Otherwise the report says NOT SUBSTANTIATED and why, and gives the number that WAS measured.
The score always describes the tested input set only; untested edges are listed by name.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rea_lib import lower_bound, pct, read_json, required_cases, upper_bound, write_json  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--compare", required=True)
    ap.add_argument("--meta")
    ap.add_argument("--evidence")
    ap.add_argument("--triage", help="triage.json to summarise")
    ap.add_argument("--target", type=float, default=0.999)
    ap.add_argument("--confidence", type=float, default=0.95)
    ap.add_argument("--min-per-source", type=int, default=1)
    ap.add_argument("--title", default="REA report")
    ap.add_argument("--metric", default="case pass rate: a case passes only if every compared field is equal after the stated rules")
    ap.add_argument("--untested", action="append", default=[], help="extra untested edge (repeatable)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()

    cmp_ = read_json(a.compare)
    s = cmp_["summary"]
    meta = read_json(a.meta) if a.meta else {}
    n, k, errs = s["cases_compared"], s["passed"], s["harness_errors"]
    lb = lower_bound(k, n, a.confidence)   # descriptive only; includes hand-picked cases
    ub = upper_bound(k, n, a.confidence)
    need = required_cases(a.target, a.confidence, 0)
    random_rows = [r for r in cmp_["results"] if (r.get("tags") or {}).get("source") == "random"]
    rn = len(random_rows)
    rk = sum(r["status"] == "pass" for r in random_rows)
    # Exact one-sided no-failure bound for independent random draws from a declared distribution.
    # The 0-failure bound is also conservative for independent stratified draws with a fixed mix.
    # Deliberate boundary/pairwise cases must all pass but cannot inflate the confidence sample.
    rlb = lower_bound(rk, rn, a.confidence) if rn else 0.0
    reasons = []
    if k < n:
        reasons.append(f"{n-k} of {n} cases fail; fix the mismatch before a fidelity claim")
    if rn == 0:
        reasons.append("no independently generated random cases; hand-picked checks do not support a statistical claim")
    elif rk < rn:
        reasons.append(f"{rn-rk} of {rn} random cases fail; the zero-failure claim gate is not met")
    elif rlb < a.target:
        reasons.append(f"only {rn} zero-failure random cases: need >= {need} for a {pct(a.target, 1)} lower bound at {int(a.confidence * 100)}% confidence")
    if errs:
        reasons.append(f"{errs} cases did not run (harness errors)")
    # coverage
    ran_sources = collections.Counter((r.get("tags") or {}).get("source", "?") for r in cmp_["results"] if r["status"] != "harness_error")
    cov_issues = []
    for src, planned in (meta.get("counts") or {}).items():
        if ran_sources.get(src, 0) < min(a.min_per_source, planned):
            cov_issues.append(f"source '{src}': {ran_sources.get(src, 0)} ran of {planned} planned")
    seen_vals = collections.defaultdict(set)
    for r in cmp_["results"]:
        if r["status"] == "harness_error":
            continue
        for t, v in (r.get("tags") or {}).items():
            if t.startswith("var."):
                seen_vals[t[4:]].add(json.dumps(v))
    for f, vals in (meta.get("factors") or {}).items():
        miss = [v for v in vals if v not in seen_vals.get(f, set())]
        if miss:
            cov_issues.append(f"factor '{f}' values never ran: {', '.join(miss[:5])}")
    if cov_issues:
        reasons.append("coverage gaps: " + "; ".join(cov_issues))
    ev_summary = None
    if a.evidence and not os.path.exists(a.evidence):
        reasons.append(f"evidence log not found: {a.evidence}")
    if a.evidence and os.path.exists(a.evidence):
        import evidence as ev
        cur = ev.state(ev.load(a.evidence))
        ev_summary = collections.Counter(e["kind"] for e in cur.values())
        open_h = [e["id"] for e in cur.values() if e["kind"] == "hypothesis" and e["status"] in ("open", "inconclusive")]
        ref_h = [e["id"] for e in cur.values() if e["kind"] == "hypothesis" and e["status"] == "refuted"]
        ev_summary = {"counts": dict(ev_summary), "open_hypotheses": open_h, "refuted_hypotheses": ref_h}
        if open_h:
            reasons.append(f"untested hypotheses still in the model: {', '.join(open_h)}")
    verdict = "SUBSTANTIATED" if not reasons else "NOT SUBSTANTIATED"
    untested = list(meta.get("untested", [])) + a.untested
    tri = read_json(a.triage) if a.triage else None

    L = [f"# {a.title}", "",
         f"**Measured fidelity: {k}/{n} checks = {pct(s['pass_rate'])}**. "
         f"Random sample: {rk}/{rn}; one-sided {int(a.confidence * 100)}% lower bound: {pct(rlb)}.", "",
         f"**{pct(a.target, 1)} claim for the declared random input distribution: {verdict}.**" + ("" if not reasons else " Reasons: " + " | ".join(reasons)), "",
         "## What the number means", "",
         f"- Metric: {a.metric}.",
         f"- Scope: {meta.get('scope') or 'the cases in this run only'}. It says nothing about inputs outside that set.",
         f"- Cases by source: " + ", ".join(f"{src} {c}" for src, c in sorted(ran_sources.items())),
         f"- Plan seed: {meta.get('seed', 'n/a')} (re-run with the same seed for the same cases).",
         f"- Independently generated random cases needed for a {pct(a.target, 1)} claim with 0 failures: {need}.",
         "- Fixed, pairwise and boundary cases are failure gates, not confidence-sample size. "
         "A predeclared random generator is the measured distribution; a tuned or cherry-picked run "
         "cannot certify future production traffic. Do a fresh holdout for a new version.", ""]
    rules = cmp_.get("rules") or {}
    if rules:
        L += ["## Comparison rules (what was NOT compared exactly)", ""]
        for key in ("fields", "ignore", "mask", "float_tol", "tol", "unordered", "case_insensitive", "images"):
            if rules.get(key):
                L.append(f"- {key}: `{json.dumps(rules[key], ensure_ascii=False)}`")
        if rules.get("why"):
            L.append(f"- why: {rules['why']}")
        L.append("")
    if s.get("dimensions"):
        L += ["## By dimension", "", "| Dimension | Passed | Rate |", "|---|---|---|"]
        for d, v in s["dimensions"].items():
            L.append(f"| {d} | {v['passed']}/{v['total']} | {pct(v['pass_rate'], 2)} |")
        L.append("")
    if tri and tri.get("clusters"):
        L += ["## Mismatch clusters", ""]
        for i, c in enumerate(tri["clusters"][:8], 1):
            L.append(f"{i}. {c['count']} cases, at {'; '.join(c['signature'])}. Guess: {' | '.join(c['guess'])}. Smallest: `{json.dumps(c['smallest_input'], ensure_ascii=False)[:160]}`")
        L.append("")
    if ev_summary:
        L += ["## Evidence", "", f"- Entries: {json.dumps(ev_summary['counts'])}",
              f"- Open hypotheses: {', '.join(ev_summary['open_hypotheses']) or 'none'}",
              f"- Refuted hypotheses: {', '.join(ev_summary['refuted_hypotheses']) or 'none'}", ""]
    L += ["## Untested edges (not covered by this score)", ""]
    L += [f"- {u}" for u in untested] or ["- none declared. That is unlikely; list what you did not test."]
    L.append("")
    with open(a.out, "w") as f:
        f.write("\n".join(L))
    out = {"title": a.title, "passed": k, "compared": n, "harness_errors": errs, "pass_rate": s["pass_rate"],
           "lower_bound": rlb, "all_cases_descriptive_lower_bound": lb, "random_passed": rk, "random_compared": rn, "confidence": a.confidence, "target": a.target,
           "verdict": verdict, "reasons": reasons, "untested": untested, "cases_needed_zero_fail": need,
           "sources": dict(ran_sources), "evidence": ev_summary}
    if a.json:
        write_json(a.json, out)
    print(f"{a.title}: {k}/{n} = {pct(s['pass_rate'])}, random {rk}/{rn}, {int(a.confidence * 100)}% random lower bound {pct(rlb)}; "
          f"{pct(a.target, 1)} claim {verdict}" + ("" if not reasons else f" ({reasons[0]})") + f" -> {a.out}")
    return 0 if verdict == "SUBSTANTIATED" else 3


if __name__ == "__main__":
    sys.exit(main())
