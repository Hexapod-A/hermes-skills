#!/usr/bin/env python3
"""Differential test: compare the original's observations with the replica's, case by case.

  python compare.py obs_original.jsonl obs_replica.jsonl --rules rules.json --cases cases.jsonl --out compare.json

A case passes only when every compared value is equal after the rules below. Nothing is skipped
silently: ignored paths and masks are listed in compare.json so the report can show them.

Rules (all optional, see templates/rules.json):
  fields         only compare these top-level keys (e.g. ["status","body"]); default all
  ignore         glob paths never compared (e.g. "headers.date", "body.request_id"). Only for
                 values that are random or time-based in the ORIGINAL too; say why in "why".
  mask           [{"path":"body.*","regex":"\\d{4}-\\d\\d-\\d\\dT[^\"]+","replace":"<time>"}]
  float_tol      absolute tolerance for numbers (default 0 = exact)
  tol            {"glob": tolerance} per path (e.g. {"boxes.*": 1} for 1 px)
  unordered      glob paths of arrays whose order does not matter
  case_insensitive  glob paths compared without case
  images         glob paths whose values are image files: pass when the share of differing
                 pixels <= image_max_diff (default 0.001) with channel threshold image_tol (16)
  why            free text kept in the output (why each ignore/mask is honest)
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rea_lib import flatten, lower_bound, path_match, read_json, read_jsonl, write_json  # noqa: E402


def _canon_unordered(obj, rules, prefix=""):
    pats = rules.get("unordered", [])
    if isinstance(obj, dict):
        return {k: _canon_unordered(v, rules, f"{prefix}.{k}" if prefix else k) for k, v in obj.items()}
    if isinstance(obj, list):
        items = [_canon_unordered(v, rules, f"{prefix}[{i}]") for i, v in enumerate(obj)]
        if pats and path_match(prefix, pats):
            items = sorted(items, key=lambda x: json.dumps(x, sort_keys=True))
        return items
    return obj


def _prep(output, rules):
    if output is None:
        return {}
    fields = rules.get("fields")
    if fields:
        output = {k: v for k, v in output.items() if k in fields}
    output = _canon_unordered(output, rules)
    flat = flatten(output)
    out = {}
    for p, v in flat.items():
        if path_match(p, rules.get("ignore", [])):
            continue
        if isinstance(v, str):
            for m in rules.get("mask", []):
                if path_match(p, [m.get("path", "*")]):
                    v = re.sub(m["regex"], m.get("replace", "<masked>"), v)
            if path_match(p, rules.get("case_insensitive", [])):
                v = v.lower()
        out[p] = v
    return out


def _tol_for(path, rules):
    for pat, t in rules.get("tol", {}).items():
        if path_match(path, [pat]):
            return t
    return rules.get("float_tol", 0)


def _image_diff(a, b, rules):
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return None, "Pillow not installed"
    if not (a and b and os.path.exists(a) and os.path.exists(b)):
        return None, "image file missing"
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if ia.size != ib.size:
        return 1.0, f"size {ia.size} vs {ib.size}"
    d = ImageChops.difference(ia, ib).convert("L")
    thr = rules.get("image_tol", 16)
    hist = d.histogram()
    bad = sum(hist[thr + 1:])
    return bad / (ia.size[0] * ia.size[1]), ""


def _equal(path, a, b, rules):
    if path_match(path, rules.get("images", [])):
        share, note = _image_diff(a, b, rules)
        if share is None:
            return False, f"image compare failed: {note}"
        ok = share <= rules.get("image_max_diff", 0.001)
        return ok, f"{share * 100:.3f}% pixels differ" + (f" ({note})" if note else "")
    
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b, ""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        tol = _tol_for(path, rules)
        if tol:
            return abs(a - b) <= tol, ""
        if type(a) is not type(b) and not rules.get("int_float_equal", False):
            return False, "int vs float"
        return a == b, ""
    return a == b, ""


def compare_case(o, r, rules):
    if "error" in o or "error" in r:
        return {"status": "harness_error",
                "detail": {"original": o.get("error"), "replica": r.get("error")}}
    po, pr = _prep(o.get("output"), rules), _prep(r.get("output"), rules)
    diffs = []
    for p in sorted(set(po) | set(pr)):
        if p not in pr:
            diffs.append({"path": p, "kind": "missing_in_replica", "original": po[p]})
        elif p not in po:
            diffs.append({"path": p, "kind": "extra_in_replica", "replica": pr[p]})
        else:
            ok, note = _equal(p, po[p], pr[p], rules)
            if not ok:
                kind = "type" if type(po[p]) is not type(pr[p]) else "value"
                d = {"path": p, "kind": kind, "original": po[p], "replica": pr[p]}
                if path_match(p, rules.get("images", [])):   # keep file names, not machine paths
                    d["original"], d["replica"] = os.path.basename(str(po[p])), os.path.basename(str(pr[p]))
                if note:
                    d["note"] = note
                diffs.append(d)
    return {"status": "pass" if not diffs else "fail", "diffs": diffs}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("original")
    ap.add_argument("replica")
    ap.add_argument("--rules")
    ap.add_argument("--cases", help="cases.jsonl, to keep inputs and tags next to each result")
    ap.add_argument("--out", required=True)
    ap.add_argument("--confidence", type=float, default=0.95)
    a = ap.parse_args()
    rules = read_json(a.rules) if a.rules else {}
    orig = {x["id"]: x for x in read_jsonl(a.original)}
    repl = {x["id"]: x for x in read_jsonl(a.replica)}
    cases = {c["id"]: c for c in read_jsonl(a.cases)} if a.cases else {}
    ids = list(cases) if cases else list(orig)
    results, dims = [], {}
    for cid in ids:
        o = orig.get(cid, {"id": cid, "error": "no observation from original"})
        r = repl.get(cid, {"id": cid, "error": "no observation from replica"})
        res = compare_case(o, r, rules)
        res["id"] = cid
        if cid in cases:
            res["input"] = cases[cid]["input"]
            res["tags"] = cases[cid].get("tags", {})
        results.append(res)
        if res["status"] != "harness_error":
            top = {d["path"].split(".")[0].split("[")[0] for d in res["diffs"]}
            keys = set(k for k in (o.get("output") or {})) | set(k for k in (r.get("output") or {}))
            if rules.get("fields"):
                keys &= set(rules["fields"])
            for k in keys:
                dd = dims.setdefault(k, [0, 0])
                dd[1] += 1
                dd[0] += k not in top
    n = sum(1 for x in results if x["status"] != "harness_error")
    k = sum(1 for x in results if x["status"] == "pass")
    errs = len(results) - n
    summary = {
        "cases_total": len(results),
        "cases_compared": n,
        "passed": k,
        "failed": n - k,
        "harness_errors": errs,
        "pass_rate": k / n if n else 0.0,
        "confidence": a.confidence,
        "lower_bound": lower_bound(k, n, a.confidence),
        "dimensions": {d: {"passed": v[0], "total": v[1], "pass_rate": v[0] / v[1] if v[1] else 0.0}
                       for d, v in sorted(dims.items())},
    }
    write_json(a.out, {"summary": summary, "rules": rules, "results": results})
    print(f"compared {n} cases: {k} pass, {n - k} fail, {errs} harness errors | "
          f"pass rate {100 * summary['pass_rate']:.3f}% | {int(a.confidence * 100)}% lower bound "
          f"{100 * summary['lower_bound']:.3f}% -> {a.out}")
    for d, v in summary["dimensions"].items():
        print(f"  {d:<14} {v['passed']}/{v['total']}")
    return 0 if n - k == 0 and errs == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
