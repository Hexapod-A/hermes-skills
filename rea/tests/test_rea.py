"""Offline unit and integration checks. Run: python3 -m unittest discover -s rea/tests -v.
UI and media examples are separate because they require Playwright/ffmpeg, but both were run on box.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
S = BASE / "scripts"
sys.path.insert(0, str(S))
import rea_lib as lib
import gen_cases
import compare
import triage


class MathsTest(unittest.TestCase):
    def test_bounds(self):
        self.assertAlmostEqual(lib.lower_bound(2995, 2995), 0.05 ** (1 / 2995), places=10)
        self.assertLess(lib.lower_bound(2994, 2994), .999)
        self.assertGreaterEqual(lib.lower_bound(2995, 2995), .999)
        self.assertEqual(lib.required_cases(.999), 2995)
        self.assertEqual(lib.required_cases(.999, failures=1), 4742)
        self.assertEqual(lib.lower_bound(0, 10), 0)
        self.assertEqual(lib.upper_bound(10, 10), 1)
        self.assertLess(lib.lower_bound(9, 10), .9)

    def test_zero_deterministic_not_a_claim(self):
        with tempfile.TemporaryDirectory() as d:
            cmp_ = Path(d, "compare.json")
            lib.write_json(str(cmp_), {"summary": {"cases_compared": 4000, "passed": 4000,
                          "harness_errors": 0, "pass_rate": 1.0, "dimensions": {}},
                          "rules": {}, "results": [{"status": "pass", "tags": {"source": "fixed"}}] * 4000})
            report = Path(d, "report.md"); rj = Path(d, "report.json")
            p = subprocess.run([sys.executable, str(S / "report.py"), "--compare", str(cmp_),
                                "--out", str(report), "--json", str(rj)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 3)
            self.assertEqual(lib.read_json(str(rj))["verdict"], "NOT SUBSTANTIATED")
            self.assertIn("no independently generated random cases", report.read_text())


class MatrixTest(unittest.TestCase):
    def test_pairwise(self):
        f = {"a": [1, 2, 3], "b": ["x", "y"], "c": [True, False]}
        rows = gen_cases.pairwise(f)
        for a in f["a"]:
            for b in f["b"]:
                self.assertTrue(any(r["a"] == a and r["b"] == b for r in rows))
        for a in f["a"]:
            for c in f["c"]:
                self.assertTrue(any(r["a"] == a and r["c"] == c for r in rows))
        for b in f["b"]:
            for c in f["c"]:
                self.assertTrue(any(r["b"] == b and r["c"] == c for r in rows))

    def test_seed_and_omit_and_boundary(self):
        plan = {"template": {"a": "{a}", "b": "{b}"}, "defaults": {"a": 1, "b": "__omit__"},
                "fields": {"a": {"type": "int", "min": 1, "max": 3},
                           "b": {"type": "string", "min_len": 0, "max_len": 2, "omit_prob": .5}},
                "boundaries": True, "random": 5, "seed": 42}
        cases, meta = gen_cases.build(plan)
        again, _ = gen_cases.build(plan)
        self.assertEqual(cases, again)
        self.assertIn("boundary", meta["counts"])
        self.assertTrue(any("b" not in c["input"] for c in cases))
        self.assertTrue(any(c["input"]["a"] == 0 for c in cases))


class CompareTest(unittest.TestCase):
    def test_rules_and_mismatch(self):
        o = {"id": "x", "output": {"status": 200, "body": {"amount": 10, "id": "a0a0", "list": [3, 2]}}}
        r = {"id": "x", "output": {"status": 200, "body": {"amount": 10.01, "id": "b0b0", "list": [2, 3]}}}
        rules = {"tol": {"body.amount": .02}, "mask": [{"path": "body.id", "regex": "^[a-f0-9]{4}$", "replace": "<id>"}],
                 "unordered": ["body.list"]}
        self.assertEqual(compare.compare_case(o, r, rules)["status"], "pass")
        rules["tol"]["body.amount"] = .001
        diffs = compare.compare_case(o, r, rules)["diffs"]
        self.assertEqual([x["path"] for x in diffs], ["body.amount"])
        r["output"]["body"]["id"] = "broken"
        self.assertEqual(len(compare.compare_case(o, r, rules)["diffs"]), 2)

    def test_missing_and_harness_errors(self):
        o = {"id": "x", "output": {"status": 200, "body": {"a": 1}}}
        r = {"id": "x", "output": {"status": 200, "body": {}}}
        d = compare.compare_case(o, r, {})
        self.assertTrue(any(x["kind"] == "missing_in_replica" and x["path"] == "body.a" for x in d["diffs"]))
        self.assertEqual(compare.compare_case(o, {"id": "x", "error": "timeout"}, {})["status"], "harness_error")

    def test_triage(self):
        data = {"results": [
            {"id": "1", "status": "fail", "input": {"qty": 1}, "tags": {"source": "random"},
             "diffs": [{"path": "body.items[0].price", "kind": "value", "original": 50, "replica": 49}]},
            {"id": "2", "status": "fail", "input": {"qty": 2}, "tags": {"source": "random"},
             "diffs": [{"path": "body.items[1].price", "kind": "value", "original": 60, "replica": 59}]},
        ]}
        tr = triage.triage(data)
        self.assertEqual(tr["clusters_total"], 1)
        self.assertEqual(tr["clusters"][0]["count"], 2)
        self.assertIn("rounding", tr["clusters"][0]["guess"][0])


class DemoTest(unittest.TestCase):
    def test_api_quick(self):
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run([sys.executable, str(BASE / "examples/api-quote/run_demo.py"),
                                "--random", "250", "--results", d], capture_output=True, text=True, timeout=120)
            self.assertEqual(p.returncode, 0, p.stderr[-1000:])
            result = lib.read_json(os.path.join(d, "summary.json"))
            self.assertEqual(result["clean"]["passed"], result["clean"]["compared"])
            self.assertTrue(result["bug_caught"])
            self.assertEqual(result["clean"]["verdict"], "NOT SUBSTANTIATED")


if __name__ == "__main__":
    unittest.main()
