#!/usr/bin/env python3
"""End-to-end REA demo on a local quote API (offline, safe).

  python run_demo.py              # full run: ~4,250 cases, about 30-60 s
  python run_demo.py --random 300 # quick run (used by tests); too few cases for a 99.9% claim

It does the whole loop with the skill's scripts:
  1. observe the original with a few probes and log evidence (observed / hypothesis)
  2. generate cases from plan.json (pairwise matrix + boundaries + fixed odd shapes + seeded random)
  3. run every case on the original and on the replica, compare, triage, report
  4. start the replica again with a deliberate bug (REA_BUG=vat_round) and show it is caught
Writes small results (report, triage, summary, evidence) to results/ and the bulky observation
files to a temp folder that is deleted at the end (use --keep to keep it).
"""
import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "..", "scripts")
PY = sys.executable


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def start(script, port, env=None):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.Popen([PY, os.path.join(HERE, script), "--port", str(port)], env=e,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/health", timeout=1).read()
            return p
        except Exception:
            time.sleep(0.05)
    p.kill()
    raise SystemExit(f"{script} did not start")


def sh(*args, ok=(0,)):
    p = subprocess.run([PY, *[str(a) for a in args]], capture_output=True, text=True)
    if p.returncode not in ok:
        raise SystemExit(f"failed ({p.returncode}): {' '.join(map(str, args))}\n{p.stdout}\n{p.stderr}")
    return p.stdout.strip()


def target(path, name, port):
    with open(path, "w") as f:
        json.dump({"kind": "http", "name": name, "base_url": f"http://127.0.0.1:{port}",
                   "headers_keep": ["content-type", "allow"], "timeout": 10}, f)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--random", type=int, help="random cases (default: plan.json value)")
    ap.add_argument("--results", default=os.path.join(HERE, "results"))
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    work = tempfile.mkdtemp(prefix="rea-api-")
    res = a.results
    os.makedirs(res, exist_ok=True)
    ev = os.path.join(res, "evidence.jsonl")
    if os.path.exists(ev):
        os.remove(ev)
    procs = []
    try:
        po, pr, pb = free_port(), free_port(), free_port()
        procs.append(start("original_server.py", po))
        t_orig = target(os.path.join(work, "t_orig.json"), "original", po)

        # 1. observe: a few probes, logged as evidence with the raw output kept
        probe_plan = os.path.join(work, "probe_plan.json")
        with open(probe_plan, "w") as f:
            json.dump({"template": {}, "fixed_cases": [
                {"name": "skus", "input": {"method": "GET", "path": "/v1/skus"}},
                {"name": "simple quote", "input": {"method": "POST", "path": "/v1/quote", "json": {"sku": "PN-002", "qty": 3}}},
                {"name": "same quote again", "input": {"method": "POST", "path": "/v1/quote", "json": {"sku": "PN-002", "qty": 3}}},
                {"name": "coupon lower+spaces", "input": {"method": "POST", "path": "/v1/quote", "json": {"sku": "BK-101", "qty": 2, "coupon": " save10 "}}},
                {"name": "qty 0", "input": {"method": "POST", "path": "/v1/quote", "json": {"sku": "BK-101", "qty": 0}}},
                {"name": "vat tie", "input": {"method": "POST", "path": "/v1/quote", "json": {"sku": "BK-205", "qty": 1, "coupon": "SAVE10"}}},
            ]}, f)
        probe_cases = os.path.join(work, "probe_cases.jsonl")
        sh(os.path.join(S, "gen_cases.py"), probe_plan, "--out", probe_cases)
        probe_obs = os.path.join(res, "probe_observations.jsonl")
        sh(os.path.join(S, "run_cases.py"), "--target", t_orig, "--cases", probe_cases, "--out", probe_obs, "--workers", "1")
        E = os.path.join(S, "evidence.py")
        sh(E, "--log", ev, "add", "observed", "GET /v1/skus lists 5 SKUs with integer prices in kobo", "--source", "probe c00001", "--artifact", probe_obs)
        sh(E, "--log", ev, "add", "observed", "two identical quote requests return different quote_id (uuid4) and created_at; all money fields equal", "--source", "probes c00002,c00003", "--artifact", probe_obs)
        sh(E, "--log", ev, "add", "observed", "qty 0 -> 422 {error:{code:out_of_range,field:qty,min:1}}", "--source", "probe c00005", "--artifact", probe_obs)
        sh(E, "--log", ev, "add", "hypothesis", "coupon is trimmed and upper-cased; SAVE10 = 10% of subtotal", "--from", "E001")
        sh(E, "--log", ev, "add", "hypothesis", "VAT = 7.5% of (subtotal - discount + express fee), rounded half-up to the kobo", "--from", "E001")
        sh(E, "--log", ev, "add", "hypothesis", "VAT uses banker's rounding (round half to even)", "--from", "E001")
        sh(E, "--log", ev, "add", "inferred", "quote_id and created_at must be compared by format only", "--from", "E002")

        # 2. cases
        cases = os.path.join(work, "cases.jsonl")
        gen = [os.path.join(S, "gen_cases.py"), os.path.join(HERE, "plan.json"), "--out", cases]
        if a.random is not None:
            gen += ["--random", a.random]
        print(sh(*gen))
        meta = os.path.join(work, "cases.meta.json")

        # 3. run original once; replica clean; replica with bug
        obs_o = os.path.join(work, "obs_original.jsonl")
        print(sh(os.path.join(S, "run_cases.py"), "--target", t_orig, "--cases", cases, "--out", obs_o))
        procs.append(start("replica_server.py", pr))
        procs.append(start("replica_server.py", pb, {"REA_BUG": "vat_round"}))
        summary = {}
        for label, port in (("clean", pr), ("bug", pb)):
            d = os.path.join(res, label)
            os.makedirs(d, exist_ok=True)
            t = target(os.path.join(work, f"t_{label}.json"), f"replica-{label}", port)
            obs = os.path.join(work, f"obs_{label}.jsonl")
            print(sh(os.path.join(S, "run_cases.py"), "--target", t, "--cases", cases, "--out", obs))
            cmp_ = os.path.join(work, f"compare_{label}.json")
            print(sh(os.path.join(S, "compare.py"), obs_o, obs, "--rules", os.path.join(HERE, "rules.json"),
                     "--cases", cases, "--out", cmp_, ok=(0, 2)))
            print(sh(os.path.join(S, "triage.py"), cmp_, "--out", os.path.join(d, "triage.md"),
                     "--json", os.path.join(d, "triage.json")))
            cs = os.path.join(d, "compare_summary.json")
            with open(cs, "w") as f:
                json.dump(json.load(open(cmp_))["summary"], f, indent=2)
            if label == "clean":
                h_res = "supported" if json.load(open(cmp_))["summary"]["failed"] == 0 else "refuted"
                sh(E, "--log", ev, "test", "H001", h_res, "--experiment", f"differential run, {label} replica, all coupon cases", "--artifact", cs)
                sh(E, "--log", ev, "test", "H002", h_res, "--experiment", f"differential run, {label} replica, all priced cases", "--artifact", cs)
            else:
                caught = json.load(open(cmp_))["summary"]["failed"] > 0
                sh(E, "--log", ev, "test", "H003", "refuted" if caught else "inconclusive",
                   "--experiment", "replica with banker's VAT rounding vs original", "--artifact", cs)
            print(sh(os.path.join(S, "report.py"), "--compare", cmp_, "--meta", meta, "--triage", os.path.join(d, "triage.json"),
                     "--evidence", ev, "--title", f"Quote API replica ({label})", "--out", os.path.join(d, "report.md"),
                     "--json", os.path.join(d, "report.json"), ok=(0, 3)))
            summary[label] = json.load(open(os.path.join(d, "report.json")))
        # The evidence log changed after the clean report (H003 was tested in the bug run): re-run the
        # clean report so it reads the final log.
        print(sh(os.path.join(S, "report.py"), "--compare", os.path.join(work, "compare_clean.json"), "--meta", meta,
                 "--triage", os.path.join(res, "clean", "triage.json"), "--evidence", ev,
                 "--title", "Quote API replica (clean)", "--out", os.path.join(res, "clean", "report.md"),
                 "--json", os.path.join(res, "clean", "report.json"), ok=(0, 3)))
        summary["clean"] = json.load(open(os.path.join(res, "clean", "report.json")))
        out = {k: {x: v[x] for x in ("passed", "compared", "pass_rate", "lower_bound", "verdict", "reasons")} for k, v in summary.items()}
        out["bug_caught"] = summary["bug"]["passed"] < summary["bug"]["compared"]
        with open(os.path.join(res, "summary.json"), "w") as f:
            json.dump(out, f, indent=2)
        print(json.dumps(out, indent=2))
        return out
    finally:
        for p in procs:
            p.kill()
        if a.keep:
            print("kept work dir:", work)
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
