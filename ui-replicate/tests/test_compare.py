#!/usr/bin/env python3
"""Tests for compare_styles.mjs and verify_widths.sh (live-site clone checks). Offline: serves two
local pages, a reference and a build with known differences. Needs Node + Playwright Chromium
(repo Node deps), Pillow, numpy. Run:  python3 ui-replicate/tests/test_compare.py
"""
import json
import os
import socket
import subprocess
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "scripts")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ok = 0

PAGE = """<!doctype html><html lang=en><head><meta name=viewport content="width=device-width,initial-scale=1"><title>t</title>
<style>body{{margin:0;font-family:Arial,sans-serif;background:#fff}} .hero{{padding:{pad}px 24px;background:#111;color:#fff}}
h1{{font-size:{h1}px;font-weight:{w};margin:0 0 16px;letter-spacing:{ls}px}} .cta{{display:inline-block;background:{brand};color:#111;
padding:14px 28px;border-radius:{rad}px;text-decoration:none;font-weight:700}} p{{font-size:18px;line-height:28px;color:#444;max-width:600px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;padding:24px}} .card{{background:#f5f5f5;padding:20px;border-radius:16px}}</style></head>
<body><section class=hero><h1>Automate the boring work</h1><a class=cta href="#">Book a free audit</a></section>
<p style="margin:24px">We build systems that keep running when you are not there.</p>
<div class=grid><div class=card><h3>Fast setup</h3><p>Live in days.</p></div><div class=card><h3>Always on</h3><p>Nights and weekends.</p></div>{extra}</div></body></html>"""


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def check(name, cond, extra=""):
    global ok
    if not cond:
        raise SystemExit(f"FAIL: {name} {extra}")
    ok += 1
    print(f"PASS {name} {extra}")


def run(args):
    env = dict(os.environ, NODE_PATH=os.path.join(REPO, "node_modules"))
    return subprocess.run(args, capture_output=True, text=True, timeout=600, env=env, cwd=REPO)


with tempfile.TemporaryDirectory() as td:
    site = os.path.join(td, "site"); os.makedirs(site)
    open(os.path.join(site, "ref.html"), "w").write(PAGE.format(pad=64, h1=48, w=800, ls=-1, brand="#ff7a00", rad=999,
                                                                extra="<div class=card><h3>Clear reports</h3><p>Every Monday.</p></div>"))
    open(os.path.join(site, "build.html"), "w").write(PAGE.format(pad=48, h1=44, w=700, ls=0, brand="#ff9900", rad=8, extra=""))
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = ThreadingHTTPServer(("127.0.0.1", port), partial(Quiet, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    ref, build = f"http://127.0.0.1:{port}/ref.html", f"http://127.0.0.1:{port}/build.html"
    try:
        r = run(["node", os.path.join(S, "compare_styles.mjs"), ref, ref, "--out", os.path.join(td, "same"), "--widths", "1440"])
        check("compare_styles: a page against itself scores 100%", r.returncode == 0 and "100%" in r.stdout, r.stdout.splitlines()[0] if r.stdout else r.stderr[-300:])
        r = run(["node", os.path.join(S, "compare_styles.mjs"), ref, build, "--out", os.path.join(td, "diff"), "--widths", "1440,390"])
        rep = json.load(open(os.path.join(td, "diff", "style-diff.json")))
        w = rep["widths"]["1440"]
        flat = [(it["text"], d["prop"], d["ref"], d["build"]) for it in w["items"] for d in it["diffs"]]
        has = lambda txt, prop: any(t.startswith(txt) and p == prop for t, p, _, _ in flat)  # noqa: E731
        check("compare_styles: exits 2 on a different build", r.returncode == 2)
        check("compare_styles: heading size 48 vs 44", has("automate the boring", "font-size"))
        check("compare_styles: heading weight 800 vs 700", has("automate the boring", "font-weight"))
        check("compare_styles: letter spacing", has("automate the boring", "letter-spacing"))
        check("compare_styles: button colour #ff7a00 vs #ff9900", any(t.startswith("book a free") and p == "background" and "ff7a00" in a and "ff9900" in b for t, p, a, b in flat))
        check("compare_styles: button radius", has("book a free", "border-radius"))
        check("compare_styles: missing card text reported", "clear reports" in w["missing_in_build"])
        check("compare_styles: writes a markdown report", os.path.getsize(os.path.join(td, "diff", "style-diff.md")) > 300)
        r = run(["bash", os.path.join(S, "verify_widths.sh"), ref, ref, os.path.join(td, "vw_same"), "--widths", "1440,390"])
        check("verify_widths: reference vs itself passes at every width", r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-400:])
        r = run(["bash", os.path.join(S, "verify_widths.sh"), ref, build, os.path.join(td, "vw_diff"), "--widths", "1440,390"])
        check("verify_widths: different build is below threshold", r.returncode == 2, r.stderr[-300:] if r.returncode not in (0, 2) else "")
        check("verify_widths: sheets per width", all(os.path.exists(os.path.join(td, "vw_diff", w_, "sbs.jpg")) for w_ in ("1440", "390")))
    finally:
        srv.shutdown()

print(f"all passed ({ok} checks)")
