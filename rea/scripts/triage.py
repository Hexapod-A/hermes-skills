#!/usr/bin/env python3
"""Group mismatches into clusters so you fix causes, not cases.

  python triage.py compare.json --out triage.md [--json triage.json]

Each failing case gets a signature: the set of (generic path, diff kind). Cases with the same
signature are one cluster. For each cluster it prints: size, share of all failures, the input tags
that are over-represented (lift vs all cases), the smallest failing input, one example of
original vs replica, and a first guess at the cause (a guess, not a fact: confirm with an experiment).
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rea_lib import generic_path, read_json, write_json  # noqa: E402


def guess(diff):
    p, k = diff["path"], diff["kind"]
    o, r = diff.get("original"), diff.get("replica")
    if k == "missing_in_replica":
        return f"replica never sets {generic_path(p)} (schema or branch missing)"
    if k == "extra_in_replica":
        return f"replica adds {generic_path(p)} the original does not have"
    if k == "type":
        return f"type differs at {generic_path(p)}: {type(o).__name__} vs {type(r).__name__} (serialisation)"
    if p in ("status", "exit") or p.endswith(".status"):
        return f"different outcome class ({o} vs {r}): validation, routing or error-handling rule"
    if diff.get("note") and "timeline:" in diff["note"]:
        return diff["note"].split("timeline:")[1].strip()
    if diff.get("note") and "pixels differ" in diff["note"]:
        return "image pixels differ; inspect this element at the matched viewport (" + diff["note"] + ")"
    if isinstance(o, int) and isinstance(r, int) and not isinstance(o, bool) and abs(o - r) == 1:
        return "off by one unit: rounding mode (half-up vs half-even), floor vs round, or order of operations"
    if isinstance(o, (int, float)) and isinstance(r, (int, float)):
        d = abs(o - r)
        rel = d / max(abs(o), abs(r), 1e-12)
        if d <= 0.011 or rel < 1e-6:
            return f"small numeric drift (delta {d:g}): rounding mode, order of operations or float precision"
        return f"numeric rule differs (delta {d:g})"
    if isinstance(o, str) and isinstance(r, str):
        if o.strip() == r.strip():
            return "whitespace / trailing newline differs"
        if o.lower() == r.lower():
            return "letter case differs"
        return "text differs (message wording, format or encoding)"
    if diff.get("note"):
        return diff["note"]
    return "value differs"


def size_of(x):
    return len(json.dumps(x, sort_keys=True, default=str))


def triage(data, top=12):
    res = data["results"]
    fails = [r for r in res if r["status"] == "fail"]
    errors = [r for r in res if r["status"] == "harness_error"]
    base = collections.Counter()
    for r in res:
        for k, v in (r.get("tags") or {}).items():
            base[(k, json.dumps(v))] += 1
    clusters = collections.defaultdict(list)
    for r in fails:
        sig = tuple(sorted({(generic_path(d["path"]), d["kind"]) for d in r["diffs"]}))
        clusters[sig].append(r)
    out = []
    for sig, rows in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
        tagc = collections.Counter()
        for r in rows:
            for k, v in (r.get("tags") or {}).items():
                tagc[(k, json.dumps(v))] += 1
        lifts = []
        for key, c in tagc.items():
            share_in = c / len(rows)
            share_all = base[key] / len(res)
            if share_in >= 0.5 and share_all < 0.999:
                lifts.append({"tag": f"{key[0]}={key[1]}", "in_cluster": round(share_in, 3),
                              "in_all": round(share_all, 3), "lift": round(share_in / share_all, 2)})
        lifts.sort(key=lambda x: (-x["lift"], -x["in_cluster"]))
        smallest = min(rows, key=lambda r: size_of(r.get("input")))
        out.append({
            "signature": [f"{p} ({k})" for p, k in sig],
            "count": len(rows),
            "share_of_failures": round(len(rows) / len(fails), 4),
            "case_ids": [r["id"] for r in rows[:20]],
            "tag_lift": lifts[:5],
            "smallest_input": smallest.get("input"),
            "smallest_id": smallest["id"],
            "example_diffs": smallest["diffs"][:5],
            "guess": sorted({guess(d) for d in smallest["diffs"]})[:3],
        })
    return {"failures": len(fails), "harness_errors": len(errors), "clusters": out[:top],
            "clusters_total": len(out),
            "harness_error_examples": [{"id": e["id"], **e.get("detail", {})} for e in errors[:5]]}


def to_md(t):
    L = [f"# Mismatch triage", "", f"Failures: {t['failures']} in {t['clusters_total']} clusters. "
         f"Harness errors: {t['harness_errors']}.", ""]
    if not t["failures"] and not t["harness_errors"]:
        L.append("No mismatches. Nothing to triage.")
    for i, c in enumerate(t["clusters"], 1):
        L += [f"## Cluster {i}: {c['count']} cases ({100 * c['share_of_failures']:.1f}% of failures)", "",
              "Differs at: " + "; ".join(c["signature"]), "",
              "First guess (hypothesis, test it): " + " | ".join(c["guess"]), ""]
        if c["tag_lift"]:
            L.append("Over-represented inputs: " + ", ".join(
                f"`{x['tag']}` ({100 * x['in_cluster']:.0f}% here vs {100 * x['in_all']:.0f}% overall)" for x in c["tag_lift"]))
            L.append("")
        L += [f"Smallest failing case `{c['smallest_id']}`:", "", "    input: " + json.dumps(c["smallest_input"], ensure_ascii=False)]
        for d in c["example_diffs"]:
            L.append(f"    {d['path']}: original={json.dumps(d.get('original'), ensure_ascii=False)} "
                     f"replica={json.dumps(d.get('replica'), ensure_ascii=False)}" + (f"  ({d['note']})" if d.get("note") else ""))
        L += ["", "Cases: " + ", ".join(c["case_ids"]) + (" ..." if c["count"] > 20 else ""), ""]
    if t["harness_errors"]:
        L += ["## Harness errors (fix the test rig first; these are not behaviour)", ""]
        for e in t["harness_error_examples"]:
            L.append(f"- {e['id']}: original={e.get('original')} replica={e.get('replica')}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("compare")
    ap.add_argument("--out", required=True, help="markdown output")
    ap.add_argument("--json", help="json output")
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()
    t = triage(read_json(a.compare), a.top)
    with open(a.out, "w") as f:
        f.write(to_md(t))
    if a.json:
        write_json(a.json, t)
    print(f"{t['failures']} failures in {t['clusters_total']} clusters, {t['harness_errors']} harness errors -> {a.out}")
    for i, c in enumerate(t["clusters"][:5], 1):
        print(f"  {i}. {c['count']:>5}  {'; '.join(c['signature'])[:110]}")


if __name__ == "__main__":
    main()
