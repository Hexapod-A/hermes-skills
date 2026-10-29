#!/usr/bin/env python3
"""Tests for frontend-build: the starter template must pass the browser QA checks at every width and
stay inside the speed budget; a deliberately bad page must be caught. Offline (local server).
Needs Node + Playwright Chromium (repo Node deps) and Pillow. Run:
    python3 frontend-build/tests/test_frontend.py
"""
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(SKILL, ".."))
UI_CHECK = os.path.join(REPO, "software-engineering-qa", "scripts", "ui_check.mjs")
VITALS = os.path.join(SKILL, "scripts", "web_vitals.mjs")
ok = 0


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def check(name, cond, extra=""):
    global ok
    if not cond:
        raise SystemExit(f"FAIL: {name} {extra}")
    ok += 1
    print(f"PASS {name} {extra}")


def node(args):
    env = dict(os.environ, NODE_PATH=os.path.join(REPO, "node_modules"))
    return subprocess.run(["node"] + args, capture_output=True, text=True, timeout=600, env=env, cwd=REPO)


with tempfile.TemporaryDirectory() as td:
    site = os.path.join(td, "site")
    os.makedirs(site)
    for f in ("base.css", "starter.html"):
        shutil.copy(os.path.join(SKILL, "templates", f), site)
    # a bad page: huge unsized image injected late (layout shift), heavy JS on load, render-blocking script
    Image.new("RGB", (3000, 2000), (200, 120, 40)).save(os.path.join(site, "big.png"))
    with open(os.path.join(site, "slow.js"), "w") as fh:
        fh.write("var t=Date.now();while(Date.now()-t<700){}\n")
    with open(os.path.join(site, "bad.html"), "w") as fh:
        fh.write("""<!doctype html><html lang=en><head><meta name=viewport content="width=device-width">
<title>bad</title><script src="slow.js"></script></head><body style="margin:0;font-family:sans-serif">
<h1>Bad page</h1><div id=slot></div><p style="font-size:20px">Some text that will be pushed down when the image loads late.</p>
<div style="height:700px;background:#eee">a big block of content below the image slot</div>
<script>setTimeout(function(){var i=new Image();i.src='big.png';i.alt='big';i.style.width='100%';document.getElementById('slot').appendChild(i);
var t=Date.now();while(Date.now()-t<400){}},600)</script></body></html>""")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = ThreadingHTTPServer(("127.0.0.1", port), partial(Quiet, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        r = node([UI_CHECK, f"{base}/starter.html", "--out", os.path.join(td, "ui")])
        rep = json.load(open(os.path.join(td, "ui", "report.json")))
        per = {w: (len(v["errors"]), v["warnings"]) for w, v in rep["pages"][0]["widths"].items()}
        check("starter: 0 errors at 320/375/414/768/1440", r.returncode == 0 and all(e == 0 for e, _ in per.values()),
              r.stdout[-600:] if r.returncode else "")
        warns = [w for _, ws in per.values() for w in ws]
        check("starter: no contrast / label / tap-target warnings",
              not any(k in w for w in warns for k in ("low contrast", "without label", "no name", "small tap")), str(warns[:5]))
        r = node([VITALS, f"{base}/starter.html", "--out", os.path.join(td, "v.json")])
        v = json.load(open(os.path.join(td, "v.json")))
        check("starter: within speed budget on the phone profile", r.returncode == 0,
              f"LCP {v['lcp_ms']} ms, CLS {v['cls']}, TBT {v['tbt_ms']} ms")
        r = node([VITALS, f"{base}/bad.html", "--out", os.path.join(td, "b.json")])
        b = json.load(open(os.path.join(td, "b.json")))
        joined = " | ".join(b["over_budget"] + b["warnings"])
        check("bad page fails the budget", r.returncode == 2, f"CLS {b['cls']}, TBT {b['tbt_ms']} ms")
        check("bad page: layout shift caught", b["cls"] > 0.1)
        check("bad page: main-thread blocking caught", b["tbt_ms"] > 300)
        check("bad page: oversized + unsized image flagged", "too big" in joined and "without width/height" in joined)
        check("bad page: render-blocking script flagged", "render-blocking" in joined)
    finally:
        srv.shutdown()

print(f"all passed ({ok} checks)")
