#!/usr/bin/env python3
"""End-to-end REA demo on a compiled binary (offline): input/output traces of `kcode` vs a Python replica.

  python run_demo.py               # ~3,000 cases per target, about 1-2 min on 4 cores
  python run_demo.py --random 200  # quick run (tests)

Needs a C compiler (cc/gcc). Builds kcode into a temp folder and runs both plans on:
  original  the C binary
  v1        the first rebuild (REA_BUG=v1), kept to show what triage found
  clean     the fixed rebuild (v2)
  bug       v2 with a deliberate mismatch (REA_BUG=crc_init)
then compare + triage + report for each replica against the binary.
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
    ap.add_argument("--random", type=int)
    ap.add_argument("--results", default=os.path.join(HERE, "results"))
    a = ap.parse_args()
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        print("SKIP: no C compiler")
        return None
    work = tempfile.mkdtemp(prefix="rea-cli-")
    try:
        binary = os.path.join(work, "kcode")
        subprocess.run([cc, "-O2", "-o", binary, os.path.join(HERE, "kcode.c")], check=True)
        targets = {
            "original": {"kind": "cmd", "name": "kcode (C binary)", "command": [binary], "timeout": 10},
            "v1": {"kind": "cmd", "name": "replica v1 (first rebuild)", "command": [PY, os.path.join(HERE, "kcode_replica.py")],
                   "env": {"REA_BUG": "v1"}, "timeout": 10},
            "clean": {"kind": "cmd", "name": "replica v2", "command": [PY, os.path.join(HERE, "kcode_replica.py")], "timeout": 10},
            "bug": {"kind": "cmd", "name": "replica REA_BUG=crc_init", "command": [PY, os.path.join(HERE, "kcode_replica.py")],
                    "env": {"REA_BUG": "crc_init"}, "timeout": 10},
        }
        cases = os.path.join(work, "cases.jsonl")
        gen = [os.path.join(S, "gen_cases.py"), os.path.join(HERE, "plan_bytes.json"), os.path.join(HERE, "plan_decode.json"), "--out", cases]
        if a.random is not None:
            gen += ["--random", a.random]
        print(sh(*gen))
        obs = {}
        for name, t in targets.items():
            tp = os.path.join(work, f"t_{name}.json")
            with open(tp, "w") as f:
                json.dump(t, f)
            obs[name] = os.path.join(work, f"obs_{name}.jsonl")
            print(sh(os.path.join(S, "run_cases.py"), "--target", tp, "--cases", cases, "--out", obs[name]))
        out = {}
        for label in ("v1", "clean", "bug"):
            d = os.path.join(a.results, label)
            os.makedirs(d, exist_ok=True)
            cmp_ = os.path.join(work, f"compare_{label}.json")
            print(sh(os.path.join(S, "compare.py"), obs["original"], obs[label], "--rules", os.path.join(HERE, "rules.json"),
                     "--cases", cases, "--out", cmp_, ok=(0, 2)))
            print(sh(os.path.join(S, "triage.py"), cmp_, "--out", os.path.join(d, "triage.md"), "--json", os.path.join(d, "triage.json")))
            print(sh(os.path.join(S, "report.py"), "--compare", cmp_, "--meta", os.path.join(work, "cases.meta.json"),
                     "--triage", os.path.join(d, "triage.json"), "--title", f"kcode replica ({label})",
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
