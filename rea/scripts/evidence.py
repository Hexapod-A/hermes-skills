#!/usr/bin/env python3
"""Evidence log: every claim about the target is OBSERVED, INFERRED or a HYPOTHESIS, with its source.
A hypothesis becomes usable only after an experiment supports it. One JSON line per entry.

  python evidence.py --log ev.jsonl add observed   "POST /v1/quote returns 400 for qty=0" --source "curl run 14:02" --artifact obs/0001.json
  python evidence.py --log ev.jsonl add hypothesis "discount is applied before rounding" --from E001,E004
  python evidence.py --log ev.jsonl test H003 supported --experiment "500 random coupon cases, 0 diffs" --artifact compare.json
  python evidence.py --log ev.jsonl add inferred   "prices are stored in kobo (integers)" --from E002,E005
  python evidence.py --log ev.jsonl list [--kind hypothesis]
  python evidence.py --log ev.jsonl check [--strict]

Rules the check enforces:
  - observed needs a --source (what you ran or looked at); an --artifact is strongly advised (its sha256 is stored)
  - inferred needs --from (the entries it is drawn from)
  - a hypothesis with no experiment is "open"; --strict fails while any are open or refuted ones are still marked used
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rea_lib import sha256_file  # noqa: E402

PREFIX = {"observed": "E", "inferred": "I", "hypothesis": "H"}


def load(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(x) for x in f if x.strip()]


def save_line(path, row):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def state(rows):
    """Fold the log (entries + experiment results) into the current state per id."""
    cur = {}
    for r in rows:
        if r.get("type") == "entry":
            cur[r["id"]] = dict(r, experiments=[])
        elif r.get("type") == "experiment" and r["target"] in cur:
            cur[r["target"]]["experiments"].append(r)
    for e in cur.values():
        if e["kind"] == "hypothesis":
            res = [x["result"] for x in e["experiments"]]
            e["status"] = res[-1] if res else "open"
    return cur


def portable(path, log):
    """Store artifact paths relative to the log's folder when they live under it."""
    root = os.path.dirname(os.path.abspath(log))
    ap_ = os.path.abspath(path)
    return os.path.relpath(ap_, root) if ap_.startswith(root + os.sep) else path


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("add")
    a1.add_argument("kind", choices=list(PREFIX))
    a1.add_argument("claim")
    a1.add_argument("--source", default="")
    a1.add_argument("--artifact", default="")
    a1.add_argument("--from", dest="from_", default="")
    a2 = sub.add_parser("test")
    a2.add_argument("id")
    a2.add_argument("result", choices=["supported", "refuted", "inconclusive"])
    a2.add_argument("--experiment", required=True)
    a2.add_argument("--artifact", default="")
    a3 = sub.add_parser("list")
    a3.add_argument("--kind", choices=list(PREFIX))
    a4 = sub.add_parser("check")
    a4.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    rows = load(a.log)
    cur = state(rows)

    if a.cmd == "add":
        if a.kind == "observed" and not a.source:
            sys.exit("observed needs --source: what did you run or look at?")
        if a.kind == "inferred" and not a.from_:
            sys.exit("inferred needs --from: which entries is it drawn from?")
        n = 1 + sum(1 for e in cur.values() if e["kind"] == a.kind)
        eid = f"{PREFIX[a.kind]}{n:03d}"
        row = {"type": "entry", "id": eid, "kind": a.kind, "claim": a.claim, "source": a.source,
               "from": [x.strip() for x in a.from_.split(",") if x.strip()], "at": now()}
        if a.artifact:
            row["artifact"] = portable(a.artifact, a.log)
            row["artifact_sha256"] = sha256_file(a.artifact) if os.path.exists(a.artifact) else "MISSING"
        missing = [x for x in row["from"] if x not in cur]
        if missing:
            sys.exit(f"unknown ids in --from: {missing}")
        save_line(a.log, row)
        print(eid)
    elif a.cmd == "test":
        if a.id not in cur:
            sys.exit(f"no entry {a.id}")
        if cur[a.id]["kind"] != "hypothesis":
            sys.exit(f"{a.id} is {cur[a.id]['kind']}, only hypotheses are tested")
        row = {"type": "experiment", "target": a.id, "result": a.result, "experiment": a.experiment, "at": now()}
        if a.artifact:
            row["artifact"] = portable(a.artifact, a.log)
            row["artifact_sha256"] = sha256_file(a.artifact) if os.path.exists(a.artifact) else "MISSING"
        save_line(a.log, row)
        print(f"{a.id} -> {a.result}")
    elif a.cmd == "list":
        for e in cur.values():
            if a.kind and e["kind"] != a.kind:
                continue
            st = f" [{e['status']}]" if e["kind"] == "hypothesis" else ""
            print(f"{e['id']:<5} {e['kind']:<10}{st} {e['claim']}")
    else:
        issues, counts = [], {"observed": 0, "inferred": 0, "hypothesis": 0}
        hyp = {"open": 0, "supported": 0, "refuted": 0, "inconclusive": 0}
        for e in cur.values():
            counts[e["kind"]] += 1
            if e["kind"] == "observed" and not e.get("artifact"):
                issues.append(f"{e['id']}: observed without an artifact (keep the raw output)")
            if e.get("artifact_sha256") == "MISSING":
                issues.append(f"{e['id']}: artifact file was missing when logged")
            if e["kind"] == "hypothesis":
                hyp[e["status"]] += 1
                if e["status"] == "open":
                    issues.append(f"{e['id']}: hypothesis not tested yet: {e['claim']}")
            for src in e.get("from", []):
                if cur.get(src, {}).get("status") == "refuted":
                    issues.append(f"{e['id']}: built on refuted hypothesis {src}")
        print(json.dumps({"counts": counts, "hypotheses": hyp, "issues": issues}, indent=2))
        if a.strict and (hyp["open"] or any("refuted" in i for i in issues)):
            sys.exit(2)


if __name__ == "__main__":
    main()
