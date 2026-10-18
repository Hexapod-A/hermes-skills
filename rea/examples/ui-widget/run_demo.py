#!/usr/bin/env python3
"""End-to-end REA demo on a web page: original cart widget vs a rebuilt replica, at 1440 and 390 px,
with clicks and typing, comparing text, boxes, computed styles, attributes and screenshots.

  python run_demo.py

Needs Node + Playwright + Chromium (README steps 3). 16 cases per target. With so few cases the
report must refuse a 99.9% claim even at 100% match; that is the point of the gate.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "..", "scripts")
PY = sys.executable


def sh(*args, ok=(0,)):
    p = subprocess.run([PY, *map(str, args)], capture_output=True, text=True)
    if p.returncode not in ok:
        raise SystemExit(f"failed ({p.returncode}): {args}\n{p.stdout}\n{p.stderr}")
    return p.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(HERE, "results"))
    a = ap.parse_args()
    if not shutil.which("node"):
        print("SKIP: node not found")
        return None
    work = tempfile.mkdtemp(prefix="rea-ui-")
    try:
        cases = os.path.join(work, "cases.jsonl")
        print(sh(os.path.join(S, "gen_cases.py"), os.path.join(HERE, "plan.json"), "--out", cases))
        bug_t = json.load(open(os.path.join(HERE, "target-replica.json")))
        bug_t.update({"name": "replica ?bug=1", "query": "bug=1", "base_url": os.path.join(HERE, "replica") + "/"})
        bug_path = os.path.join(work, "target-bug.json")
        json.dump(bug_t, open(bug_path, "w"))
        targets = {"original": os.path.join(HERE, "target-original.json"),
                   "clean": os.path.join(HERE, "target-replica.json"), "bug": bug_path}
        obs = {}
        for name, tp in targets.items():
            obs[name] = os.path.join(work, f"obs_{name}.jsonl")
            print(sh(os.path.join(S, "run_cases.py"), "--target", tp, "--cases", cases, "--out", obs[name],
                     "--shots", os.path.join(work, f"shots_{name}")))
        out = {}
        for label in ("clean", "bug"):
            d = os.path.join(a.results, label)
            os.makedirs(d, exist_ok=True)
            cmp_ = os.path.join(work, f"compare_{label}.json")
            print(sh(os.path.join(S, "compare.py"), obs["original"], obs[label], "--rules", os.path.join(HERE, "rules.json"),
                     "--cases", cases, "--out", cmp_, ok=(0, 2)))
            print(sh(os.path.join(S, "triage.py"), cmp_, "--out", os.path.join(d, "triage.md"), "--json", os.path.join(d, "triage.json")))
            print(sh(os.path.join(S, "report.py"), "--compare", cmp_, "--meta", os.path.join(work, "cases.meta.json"),
                     "--triage", os.path.join(d, "triage.json"), "--title", f"Cart widget replica ({label})",
                     "--metric", "case pass rate over text, boxes (1 px), computed styles, attributes and screenshot (<= 0.1% pixels differ)",
                     "--out", os.path.join(d, "report.md"), "--json", os.path.join(d, "report.json"), ok=(0, 3)))
            r = json.load(open(os.path.join(d, "report.json")))
            out[label] = {x: r[x] for x in ("passed", "compared", "pass_rate", "lower_bound", "verdict", "reasons")}
        out["bug_caught"] = out["bug"]["passed"] < out["bug"]["compared"]
        with open(os.path.join(a.results, "summary.json"), "w") as f:
            json.dump(out, f, indent=2)
        print(json.dumps(out, indent=2))
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
