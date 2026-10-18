"""Shared helpers for the REA scripts: JSONL files, path flattening, hashing and the
fidelity maths (exact Clopper-Pearson bounds). Standard library only."""
import fnmatch
import hashlib
import json
import math
import os
import re

MISSING = object()


# ---------- files ----------
def read_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as e:
                raise SystemExit(f"{path}:{n}: bad JSON line: {e}")
    return rows


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def tag_value(v):
    """Short, stable label for a variable value (long strings become <str:len:hash>)."""
    if isinstance(v, str) and len(v) > 24:
        return f"<str:{len(v)}:{sha256_bytes(v.encode())[:8]}>"
    if isinstance(v, (list, dict)):
        s = json.dumps(v, sort_keys=True)
        return s if len(s) <= 24 else f"<{type(v).__name__}:{len(s)}:{sha256_bytes(s.encode())[:8]}>"
    return v


# ---------- paths ----------
def flatten(obj, prefix=""):
    """{'a': {'b': [1, 2]}} -> {'a.b[0]': 1, 'a.b[1]': 2}. Empty dict/list keep a marker."""
    out = {}
    if isinstance(obj, dict):
        if not obj and prefix:
            out[prefix] = {}
        for k in obj:
            out.update(flatten(obj[k], f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        if not obj and prefix:
            out[prefix] = []
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix or "$"] = obj
    return out


_IDX = re.compile(r"\[\d+\]")


def generic_path(path):
    """body.items[3].price -> body.items[*].price (used to group mismatches)."""
    return _IDX.sub("[*]", path)


def path_match(path, patterns):
    """True if path (or its generic form, or any parent) matches one of the glob patterns."""
    if not patterns:
        return False
    cands = {path, generic_path(path)}
    parts = re.split(r"(?=[.\[])", path)
    acc = ""
    for p in parts:
        acc += p
        cands.add(acc)
        cands.add(generic_path(acc))
    return any(fnmatch.fnmatchcase(c, pat) for c in cands for pat in patterns)


def get_path(obj, dotted):
    cur = obj
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", dotted):
        if part.startswith("["):
            i = int(part[1:-1])
            if not isinstance(cur, list) or i >= len(cur):
                return MISSING
            cur = cur[i]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return MISSING
            cur = cur[part]
    return cur


# ---------- fidelity maths ----------
def _log_binom_pmf(n, k, p):
    if p <= 0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1:
        return 0.0 if k == n else -math.inf
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log1p(-p))


def _upper_tail(n, k, p):
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    logs = [_log_binom_pmf(n, j, p) for j in range(k, n + 1)]
    m = max(logs)
    if m == -math.inf:
        return 0.0
    return min(1.0, math.exp(m) * sum(math.exp(x - m) for x in logs))


def _lower_tail(n, k, p):
    """P(X <= k)."""
    if k >= n:
        return 1.0
    logs = [_log_binom_pmf(n, j, p) for j in range(0, k + 1)]
    m = max(logs)
    if m == -math.inf:
        return 0.0
    return min(1.0, math.exp(m) * sum(math.exp(x - m) for x in logs))


def lower_bound(k, n, confidence=0.95):
    """One-sided exact (Clopper-Pearson) lower bound on the true pass rate, given k passes in n.
    With k == n this is (1 - confidence) ** (1 / n)."""
    if n <= 0:
        return 0.0
    if k <= 0:
        return 0.0
    alpha = 1 - confidence
    if k == n:
        return alpha ** (1.0 / n)
    lo, hi = 0.0, k / n
    for _ in range(80):
        mid = (lo + hi) / 2
        if _upper_tail(n, k, mid) < alpha:
            lo = mid
        else:
            hi = mid
    return lo


def upper_bound(k, n, confidence=0.95):
    """One-sided exact upper bound on the true pass rate."""
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0
    alpha = 1 - confidence
    lo, hi = k / n, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _lower_tail(n, k, mid) < alpha:
            hi = mid
        else:
            lo = mid
    return hi


def required_cases(target=0.999, confidence=0.95, failures=0):
    """Smallest n such that n - failures passes out of n gives a lower bound >= target."""
    if not 0 < target < 1:
        raise ValueError("target must be between 0 and 1")
    if failures == 0:
        return math.ceil(math.log(1 - confidence) / math.log(target))
    n = failures + 1
    step = max(1, required_cases(target, confidence, 0) // 4)
    while lower_bound(n - failures, n, confidence) < target:   # coarse then fine
        n += step
    while n - step > failures and lower_bound(n - step - failures, n - step, confidence) >= target:
        n -= step
    while n > failures + 1 and lower_bound(n - 1 - failures, n - 1, confidence) >= target:
        n -= 1
    return n


def pct(x, digits=3):
    return f"{100 * x:.{digits}f}%"
