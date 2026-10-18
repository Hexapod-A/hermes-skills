#!/usr/bin/env python3
"""Build test cases from a plan: factor matrix (each / pairwise / full), boundary values and
seeded random (property) cases. Same plan + same seed = same cases.

  python gen_cases.py plan.json --out cases.jsonl [--random N] [--seed S]

Plan keys (see templates/plan.json):
  template     the input shape; a string that is exactly "{name}" is replaced by the raw value
               (a value of "__omit__" removes the key); "{name}" inside a longer string is text-filled
  defaults     value per variable when a case does not set it
  factors      {"var": [values...]}  explicit values worth testing
  combine      "each" (one factor at a time), "pairwise" (all value pairs) or "full" (product)
  fields       random generators per variable (int, float, choice, string, bool, const)
  random       number of seeded random cases
  boundaries   true = add min/max/just-outside/empty cases from `fields`
  fixed_cases  [{"name": "...", "vars": {...}}] or [{"name": "...", "input": {...}}] hand-written
               cases (odd shapes, bugs seen in the wild); "input" is used as is, no template
  untested     list of edges this plan does NOT cover; they go into the final report
"""
import argparse
import itertools
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rea_lib import read_json, tag_value, write_jsonl  # noqa: E402

OMIT = "__omit__"


def fill(template, vars_):
    if isinstance(template, dict):
        out = {}
        for k, v in template.items():
            fv = fill(v, vars_)
            if fv is _DROP:
                continue
            out[k] = fv
        return out
    if isinstance(template, list):
        return [x for x in (fill(v, vars_) for v in template) if x is not _DROP]
    if isinstance(template, str):
        if template.startswith("{") and template.endswith("}") and template[1:-1] in vars_:
            v = vars_[template[1:-1]]
            return _DROP if v == OMIT else v
        out = template
        for k, v in vars_.items():
            if "{" + k + "}" in out:
                out = out.replace("{" + k + "}", "" if v == OMIT else str(v))
        return out
    return template


class _Drop:
    def __repr__(self):
        return "<drop>"


_DROP = _Drop()


def gen_value(spec, rng):
    if rng.random() < spec.get("omit_prob", 0):
        return OMIT
    if rng.random() < spec.get("null_prob", 0):
        return None
    t = spec["type"]
    if t == "int":
        return rng.randint(spec["min"], spec["max"])
    if t == "float":
        v = rng.uniform(spec["min"], spec["max"])
        return round(v, spec["decimals"]) if "decimals" in spec else v
    if t == "choice":
        return rng.choices(spec["values"], weights=spec.get("weights"))[0]
    if t == "bool":
        return rng.random() < 0.5
    if t == "const":
        return spec["value"]
    if t == "string":
        alphabet = spec.get("alphabet", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_")
        n = rng.randint(spec.get("min_len", 0), spec.get("max_len", 12))
        return "".join(rng.choice(alphabet) for _ in range(n))
    if t == "bytes_hex":
        n = rng.randint(spec.get("min_len", 0), spec.get("max_len", 32))
        if spec.get("runs"):  # bytes in runs (aaaabbbbbbc...), good for codecs and parsers
            out = bytearray()
            pool = spec.get("byte_pool", list(range(256)))
            while len(out) < n:
                out += bytes([rng.choice(pool)]) * rng.randint(1, spec.get("max_run", 300))
            return bytes(out[:n]).hex()
        return bytes(rng.randrange(256) for _ in range(n)).hex()
    raise SystemExit(f"unknown field type: {t}")


def boundary_values(name, spec):
    t = spec["type"]
    out = []
    if t == "int":
        lo, hi = spec["min"], spec["max"]
        out = [lo, lo + 1, hi - 1, hi]
        if spec.get("outside", True):
            out += [lo - 1, hi + 1]
        if lo < 0 < hi:
            out.append(0)
    elif t == "float":
        lo, hi = spec["min"], spec["max"]
        out = [lo, hi, (lo + hi) / 2]
        if spec.get("outside", True):
            out += [lo - 0.001, hi + 0.001]
    elif t == "choice":
        out = list(spec["values"])
        if spec.get("outside", True):
            out.append(spec.get("invalid", "__not_a_choice__"))
    elif t == "string":
        alphabet = spec.get("alphabet", "a")
        out = ["", alphabet[0] * spec.get("max_len", 12)]
        if spec.get("outside", True):
            out += [alphabet[0] * (spec.get("max_len", 12) + 1), " ", "\u00e9\u4e2d\U0001F600"]
    elif t == "bool":
        out = [True, False]
    elif t == "bytes_hex":
        out = ["", "00", "ff" * spec.get("max_len", 32)]
    if spec.get("omit_prob", 0) > 0 or spec.get("boundary_omit"):
        out.append(OMIT)
    if spec.get("null_prob", 0) > 0:
        out.append(None)
    seen, uniq = set(), []
    for v in out:
        key = json.dumps(v, sort_keys=True)
        if key not in seen:
            seen.add(key)
            uniq.append(v)
    return uniq


def pairwise(factors):
    """Greedy all-pairs: every value pair of every two factors appears in at least one row."""
    names = list(factors)
    if len(names) < 2:
        return [{names[0]: v} for v in factors[names[0]]] if names else []
    need = set()
    for (i, a), (j, b) in itertools.combinations(enumerate(names), 2):
        for va in range(len(factors[a])):
            for vb in range(len(factors[b])):
                need.add((i, va, j, vb))
    rows = []
    while need:
        best, best_cov = None, -1
        # seed each candidate row with one uncovered pair, then fill greedily
        for seed in list(need)[:50]:
            row = [None] * len(names)
            row[seed[0]], row[seed[2]] = seed[1], seed[3]
            for k in range(len(names)):
                if row[k] is not None:
                    continue
                scores = []
                for v in range(len(factors[names[k]])):
                    s = 0
                    for m in range(len(names)):
                        if m == k or row[m] is None:
                            continue
                        key = (min(k, m), v if k < m else row[m], max(k, m), row[m] if k < m else v)
                        s += key in need
                    scores.append(s)
                row[k] = max(range(len(scores)), key=lambda x: scores[x])
            cov = sum(1 for (i, va, j, vb) in need if row[i] == va and row[j] == vb)
            if cov > best_cov:
                best, best_cov = row, cov
        need = {(i, va, j, vb) for (i, va, j, vb) in need if not (best[i] == va and best[j] == vb)}
        rows.append({names[k]: factors[names[k]][best[k]] for k in range(len(names))})
    return rows


def build(plan, seed=None, n_random=None, prefix="c"):
    seed = plan.get("seed", 1) if seed is None else seed
    n_random = plan.get("random", 0) if n_random is None else n_random
    rng = random.Random(seed)
    defaults = plan.get("defaults", {})
    template = plan["template"]
    fields = plan.get("fields", {})
    factors = plan.get("factors", {})
    cases = []

    def add(source, vars_, extra_tags=None, raw_input=None):
        v = dict(defaults)
        v.update(vars_)
        tags = {"source": source}
        for k, val in vars_.items():
            tags[f"var.{k}"] = tag_value(val)
        if extra_tags:
            tags.update(extra_tags)
        inp = raw_input if raw_input is not None else fill(template, v)
        cases.append({"id": f"{prefix}{len(cases) + 1:05d}", "input": inp, "tags": tags, "vars": v})

    for fc in plan.get("fixed_cases", []):
        add("fixed", fc.get("vars", {}), {"name": fc.get("name", "")}, fc.get("input"))
    mode = plan.get("combine", "pairwise")
    if factors:
        if mode == "each":
            for k, vals in factors.items():
                for val in vals:
                    add("factor", {k: val})
        elif mode == "full":
            names = list(factors)
            for combo in itertools.product(*(factors[n] for n in names)):
                add("factor", dict(zip(names, combo)))
        else:
            for row in pairwise(factors):
                add("pairwise", row)
    if plan.get("boundaries"):
        for name, spec in fields.items():
            for val in boundary_values(name, spec):
                add("boundary", {name: val}, {"boundary": name})
    for _ in range(n_random):
        add("random", {name: gen_value(spec, rng) for name, spec in fields.items()})
    meta = {
        "plan_name": plan.get("name", ""),
        "seed": seed,
        "counts": {},
        "factors": {k: [json.dumps(tag_value(v)) for v in vals] for k, vals in factors.items()},
        "untested": plan.get("untested", []),
        "scope": plan.get("scope", ""),
    }
    for c in cases:
        meta["counts"][c["tags"]["source"]] = meta["counts"].get(c["tags"]["source"], 0) + 1
    meta["total"] = len(cases)
    return cases, meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", nargs="+", help="one or more plan files (one per endpoint/mode is fine)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--random", type=int, help="override plan.random")
    ap.add_argument("--seed", type=int, help="override plan.seed")
    a = ap.parse_args()
    cases, meta = [], None
    for i, path in enumerate(a.plan):
        plan = read_json(path)
        prefix = "c" if len(a.plan) == 1 else (plan.get("id_prefix") or f"p{i + 1}_")
        c, m = build(plan, a.seed, a.random, prefix)
        cases += c
        if meta is None:
            meta = m
        else:
            for k, v in m["counts"].items():
                meta["counts"][k] = meta["counts"].get(k, 0) + v
            for k, v in m["factors"].items():
                meta["factors"].setdefault(k, [])
                meta["factors"][k] += [x for x in v if x not in meta["factors"][k]]
            meta["untested"] += [u for u in m["untested"] if u not in meta["untested"]]
            meta["scope"] = "; ".join(x for x in (meta["scope"], m["scope"]) if x)
            meta["plan_name"] += "+" + m["plan_name"]
    meta["total"] = len(cases)
    write_jsonl(a.out, cases)
    meta_path = os.path.splitext(a.out)[0] + ".meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"{len(cases)} cases -> {a.out}  ({', '.join(f'{k} {v}' for k, v in meta['counts'].items())}); meta -> {meta_path}")


if __name__ == "__main__":
    main()
