#!/usr/bin/env python3
"""Run every case against one target and record what it did (one JSON line per case).
Run it twice, once for the original and once for your replica, then compare.py.

  python run_cases.py --target original.json --cases cases.jsonl --out obs_original.jsonl [--workers 8]

Target kinds (see templates/target-*.json):
  http    {"kind":"http","base_url":"http://127.0.0.1:8001","headers_keep":["content-type"],"timeout":10}
          case input: {"method":"POST","path":"/v1/x","query":{},"headers":{},"json":{...}} or "body": "text"
          records status, kept headers, body (parsed JSON when it is JSON). Redirects are NOT followed.
  cmd     {"kind":"cmd","command":["./prog","--flag"],"timeout":10,"env":{}}
          case input: {"args":[...],"stdin":"text","stdin_hex":"00ff","files":{"in.txt":"..."}}
          runs in a fresh temp dir; records exit code, stdout, stderr and sha256 of files the program wrote.
  python  {"kind":"python","callable":"module:function","path":"dir/with/module"}
          case input: {"args":[...],"kwargs":{}}; records the return value or the exception type+message.
  ui      {"kind":"ui","base_url":"http://localhost:3000/ or file:///dir/"}
          case input: {"path":"page.html","viewport":[1440,900],"actions":[...],"capture":{...}}
          runs scripts/ui_probe.mjs (Playwright). Records text, boxes, styles, screenshot path.
  replay  {"kind":"replay","file":"captured.jsonl"}  observations captured earlier (HAR export,
          device logs, a video probe) keyed by case id. Use when you cannot call the original again.

Errors of the harness itself (refused connection, timeout) are written as {"error": "..."} so they
are never mistaken for behaviour.
"""
import argparse
import base64
import concurrent.futures as cf
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rea_lib import read_json, read_jsonl, sha256_bytes, write_jsonl  # noqa: E402


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def run_http(target, inp):
    method = inp.get("method", "GET").upper()
    url = target["base_url"].rstrip("/") + "/" + inp.get("path", "").lstrip("/")
    if inp.get("query"):
        url += "?" + urllib.parse.urlencode(inp["query"], doseq=True)
    headers = dict(target.get("headers", {}))
    headers.update(inp.get("headers", {}))
    data = None
    if "json" in inp:
        data = json.dumps(inp["json"]).encode()
        headers.setdefault("Content-Type", "application/json")
    elif "body" in inp:
        data = inp["body"].encode() if isinstance(inp["body"], str) else inp["body"]
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        resp = _OPENER.open(req, timeout=target.get("timeout", 10))
        status, hdrs, raw = resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as e:
        status, hdrs, raw = e.code, e.headers, e.read()
    keep = [h.lower() for h in target.get("headers_keep", ["content-type"])]
    out = {"status": status, "headers": {k.lower(): v for k, v in hdrs.items() if k.lower() in keep}}
    ctype = (hdrs.get("Content-Type") or "").lower()
    text = raw.decode("utf-8", "replace")
    if "json" in ctype:
        try:
            out["body"] = json.loads(text) if text else None
        except ValueError:
            out["body"] = text
            out["body_not_json"] = True
    else:
        out["body"] = text
    return out


def run_cmd(target, inp):
    work = tempfile.mkdtemp(prefix="rea-cmd-")
    try:
        for name, content in inp.get("files", {}).items():
            p = os.path.join(work, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write(content)
        before = {n: _hash(os.path.join(work, n)) for n in _walk(work)}
        if "stdin_hex" in inp:
            stdin = bytes.fromhex(inp["stdin_hex"])
        else:
            stdin = (inp.get("stdin") or "").encode()
        env = dict(os.environ)
        env.update(target.get("env", {}))
        cmd = [os.path.expanduser(c) for c in target["command"]] + [str(x) for x in inp.get("args", [])]
        try:
            p = subprocess.run(cmd, input=stdin, capture_output=True, cwd=work, env=env,
                               timeout=target.get("timeout", 10))
        except subprocess.TimeoutExpired:
            return {"timeout": True}
        out = {"exit": p.returncode}
        for name, raw in (("stdout", p.stdout), ("stderr", p.stderr)):
            try:
                out[name] = raw.decode("utf-8")
            except UnicodeDecodeError:
                out[name + "_b64"] = base64.b64encode(raw).decode()
        after = {n: _hash(os.path.join(work, n)) for n in _walk(work)}
        written = {n: h for n, h in after.items() if before.get(n) != h}
        if written or target.get("record_files"):
            out["files_out"] = written
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _walk(root):
    for d, _, fs in os.walk(root):
        for f in fs:
            yield os.path.relpath(os.path.join(d, f), root)


def _hash(p):
    with open(p, "rb") as f:
        return sha256_bytes(f.read())


_PY_CACHE = {}


def run_python(target, inp):
    key = (target.get("path"), target["callable"])
    if key not in _PY_CACHE:
        if target.get("path"):
            sys.path.insert(0, os.path.abspath(target["path"]))
        mod, fn = target["callable"].split(":")
        _PY_CACHE[key] = getattr(importlib.import_module(mod), fn)
    fn = _PY_CACHE[key]
    try:
        val = fn(*inp.get("args", []), **inp.get("kwargs", {}))
        try:
            json.dumps(val)
        except TypeError:
            val = repr(val)
        return {"return": val}
    except Exception as e:  # behaviour, not harness error
        return {"raises": f"{type(e).__name__}: {e}"}


def run_one(target, case):
    t0 = time.time()
    try:
        kind = target["kind"]
        if kind == "http":
            out = run_http(target, case["input"])
        elif kind == "cmd":
            out = run_cmd(target, case["input"])
        elif kind == "python":
            out = run_python(target, case["input"])
        else:
            raise ValueError(f"unknown target kind {kind}")
        rec = {"id": case["id"], "output": out}
    except Exception as e:
        rec = {"id": case["id"], "error": f"{type(e).__name__}: {e}"}
        if os.environ.get("REA_DEBUG"):
            rec["trace"] = traceback.format_exc()
    rec["ms"] = round((time.time() - t0) * 1000, 1)
    return rec


def run_ui(target, cases, out_path, shots_dir):
    probe = os.path.join(HERE, "ui_probe.mjs")
    tmp_cases = out_path + ".cases.tmp.jsonl"
    write_jsonl(tmp_cases, cases)
    cfg = dict(target)
    cfg["shots_dir"] = shots_dir
    cfg_path = out_path + ".target.tmp.json"
    with open(cfg_path, "w") as f:
        json.dump(cfg, f)
    try:
        p = subprocess.run(["node", probe, cfg_path, tmp_cases, out_path], capture_output=True, text=True,
                           timeout=target.get("timeout_total", 600))
        if p.returncode != 0:
            raise SystemExit(f"ui_probe failed ({p.returncode}): {p.stderr[-2000:]}")
        return read_jsonl(out_path)
    finally:
        for f in (tmp_cases, cfg_path):
            if os.path.exists(f):
                os.remove(f)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True, help="target JSON file")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--shots", help="screenshot folder for ui targets (default: next to --out)")
    a = ap.parse_args()
    target = read_json(a.target)
    base = os.path.dirname(os.path.abspath(a.target))
    for k in ("path", "file"):
        if k in target and not os.path.isabs(target[k]):
            target[k] = os.path.join(base, target[k])
    if target.get("kind") == "ui" and not target["base_url"].startswith(("http://", "https://", "file://")):
        target["base_url"] = "file://" + os.path.join(base, target["base_url"]).rstrip("/") + "/"
    if target.get("kind") == "cmd":
        target["command"] = [os.path.join(base, c) if c.startswith("./") else c for c in target["command"]]
    cases = read_jsonl(a.cases)
    t0 = time.time()
    if target["kind"] == "ui":
        shots = a.shots or os.path.splitext(a.out)[0] + "_shots"
        recs = run_ui(target, cases, a.out, shots)
    elif target["kind"] == "replay":
        have = {r["id"]: r for r in read_jsonl(target["file"])}
        recs = [have.get(c["id"], {"id": c["id"], "error": "no captured observation"}) for c in cases]
        write_jsonl(a.out, recs)
    else:
        workers = 1 if target["kind"] == "python" else a.workers
        with cf.ThreadPoolExecutor(workers) as ex:
            recs = list(ex.map(lambda c: run_one(target, c), cases))
        write_jsonl(a.out, recs)
    errs = sum(1 for r in recs if "error" in r)
    print(f"{len(recs)} cases run on {target.get('name', target['kind'])} in {time.time() - t0:.1f}s, "
          f"harness errors: {errs} -> {a.out}")
    if errs:
        first = next(r for r in recs if "error" in r)
        print(f"first harness error: {first['id']}: {first['error']}")


if __name__ == "__main__":
    main()
