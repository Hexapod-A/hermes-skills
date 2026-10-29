#!/usr/bin/env python3
"""Scan a code folder for leaked secrets and malware red flags. Standard library only.

Usage:
  python3 suspicious_scan.py PATH [--json report.json] [--max-mb 2] [--include-node-modules]

Looks for:
  secrets      cloud keys, API tokens, private keys, passwords in code, committed .env files
  install      npm lifecycle scripts (preinstall/install/postinstall/prepare) that download or run code
  obfuscation  eval(atob(...)), eval of base64/hex, new Function on long strings, huge encoded blobs
  exfil        Discord/Telegram webhooks, paste sites, raw IP URLs, reading ~/.ssh or browser/wallet files
  auto-run     .vscode/tasks.json "runOn": "folderOpen", git hooks, workflow pull_request_target with checkout
  disguised    files named like fonts/images that contain script code
Prints findings by severity. Exit code 2 when any HIGH finding exists, else 0.
It is a first pass: a clean result does not prove code is safe; read anything that runs on install.

A file whose first lines contain the marker "suspicious-scan: rules-file" (scanner rule files, test
fixtures) is not pattern-scanned, but it is always listed as LOW so nobody can hide code that way.
"""
# suspicious-scan: rules-file
import argparse
import json
import os
import re
import subprocess
import sys

SKIP_DIRS = {".git", "node_modules", ".next", "dist", "build", ".venv", "venv", "__pycache__", ".turbo", ".cache",
             "coverage", ".pytest_cache", ".mypy_cache", "out", "target", "vendor"}
TEXT_EXT = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".py", ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
            ".json", ".yml", ".yaml", ".toml", ".env", ".ini", ".cfg", ".conf", ".rb", ".php", ".go", ".rs",
            ".java", ".kt", ".swift", ".html", ".vue", ".svelte", ".sql", ".md", ".txt", ".xml", ".properties", ""}
DISGUISE_EXT = {".woff", ".woff2", ".ttf", ".otf", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp"}

SECRETS = [
    ("HIGH", "AWS access key", r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("HIGH", "private key", r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    ("HIGH", "GitHub token", r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    ("HIGH", "OpenAI/Anthropic-style key", r"\bsk-(proj-|ant-)?[A-Za-z0-9_\-]{32,}\b"),
    ("HIGH", "Stripe live key", r"\b(sk|rk)_live_[A-Za-z0-9]{20,}\b"),
    ("MED", "Paystack/Flutterwave secret", r"\b(sk_live_|FLWSECK-)[A-Za-z0-9\-]{20,}\b"),
    ("HIGH", "Slack token", r"\bxox[abpors]-[A-Za-z0-9-]{10,}\b"),
    ("MED", "Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("MED", "Supabase service role JWT", r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]*c2VydmljZV9yb2xl[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+"),
    ("MED", "database URL with password", r"\b(postgres(ql)?|mysql|mongodb(\+srv)?|redis)://[^:\s/]+:[^@\s]{4,}@"),
    ("MED", "hard-coded password", r"(?i)\b(password|passwd|secret|api_?key|auth_?token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
    ("MED", "private key in a mnemonic/seed var", r"(?i)\b(mnemonic|seed_?phrase|private_?key)\b\s*[:=]\s*['\"][^'\"]{20,}['\"]"),
]
CODE = [
    ("HIGH", "eval of decoded data", r"eval\s*\(\s*(atob|Buffer\.from|unescape|decodeURIComponent|base64|bytes\.fromhex|codecs\.decode)"),
    ("HIGH", "python exec of decoded data", r"exec\s*\(\s*(base64\.b64decode|zlib\.decompress|marshal\.loads|bytes\.fromhex|codecs\.decode)"),
    ("HIGH", "download piped to a shell", r"(curl|wget)[^\n|;]{0,200}\|\s*(sudo\s+)?(ba|z)?sh\b|iwr[^\n]{0,200}\|\s*iex|Invoke-Expression"),
    ("MED", "new Function / vm on dynamic string", r"new\s+Function\s*\(\s*[a-zA-Z_$][\w$]*\s*\)|vm\.runIn(New|This)Context\s*\("),
    ("MED", "child_process with network tool", r"(exec|execSync|spawn)\s*\([^)]{0,120}(curl|wget|powershell|nc\s|bash\s+-c)"),
    ("HIGH", "Discord/Telegram webhook (data exfil)", r"discord(app)?\.com/api/webhooks/|api\.telegram\.org/bot[0-9]+:"),
    ("MED", "paste/file-drop site", r"(pastebin\.com/raw|transfer\.sh|paste\.ee|hastebin|0x0\.st|ngrok\.io|requestbin)"),
    ("LOW", "URL with a raw IP address", r"https?://(?!127\.0\.0\.1|0\.0\.0\.0|localhost)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"),
    ("HIGH", "reads SSH keys, browser or wallet data", r"\.ssh/id_|Login Data|Local State['\"]|Cookies['\"]|/Local Extension Settings/|keychain-db|wallet\.dat|Exodus|MetaMask|nkbihfbeogaeaoehlefnkodbefgpgknn"),
    ("MED", "long hex-escaped string", r"(\\x[0-9a-fA-F]{2}){40,}"),
    ("MED", "String.fromCharCode chain", r"String\.fromCharCode\((\s*\d+\s*,){30,}"),
    ("LOW", "obfuscator variable names", r"\b_0x[0-9a-f]{4,6}\b"),
]
BLOB = re.compile(r"['\"`]([A-Za-z0-9+/]{400,}={0,2})['\"`]")
LIFECYCLE = ("preinstall", "install", "postinstall", "prepare", "prepublish", "preprepare", "postprepare")
RISKY_SCRIPT = re.compile(r"curl|wget|node\s+-e|bash\s+-c|sh\s+-c|powershell|base64|\|\s*sh|http[s]?://|eval|nohup|&\s*$")


def tracked_files(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return set(out.stdout.splitlines())
    except Exception:
        pass
    return None


def walk(root, include_nm=False):
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if include_nm and x == "node_modules" or x not in SKIP_DIRS]
        for f in files:
            yield os.path.join(d, f)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def scan(root, max_mb=2.0, include_nm=False):
    findings = []
    add = lambda sev, kind, path, line, detail: findings.append(  # noqa: E731
        {"severity": sev, "kind": kind, "file": os.path.relpath(path, root), "line": line, "detail": detail[:160]})
    tracked = tracked_files(root)
    for path in walk(root, include_nm):
        rel = os.path.relpath(path, root)
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size > max_mb * 1048576:
            continue
        if name.startswith(".env") and not name.endswith((".example", ".sample", ".template")):
            if tracked is None or rel in tracked:
                add("HIGH" if tracked is not None else "MED", "secrets", path, 0,
                    "env file is committed to git" if tracked is not None else "env file present (check it is in .gitignore)")
        try:
            raw = open(path, "rb").read()
        except OSError:
            continue
        if ext in DISGUISE_EXT:
            head = raw[:4000]
            if ext != ".svg" and re.search(rb"(require\(|import\s|function\s*\(|eval\(|child_process|#!/bin/)", head) and b"\x00" not in head[:200]:
                add("HIGH", "disguised", path, 0, f"{ext} file contains script code")
            if ext == ".svg" and re.search(rb"<script|onload\s*=|javascript:", raw, re.I):
                add("MED", "disguised", path, 0, "SVG contains script or event handler")
            continue
        if ext not in TEXT_EXT and not name.startswith(".") and name not in ("Dockerfile", "Makefile"):
            continue
        if b"\x00" in raw[:1000]:
            continue
        text = raw.decode("utf-8", "ignore")
        if "suspicious-scan: rules-file" in text[:3000]:
            add("LOW", "opted-out", path, 0, "marked as a rules/fixture file; not pattern-scanned - read it if unsure")
            continue
        is_example = any(k in rel.lower() for k in ("example", "sample", "test", "fixture", "mock", ".md"))
        for sev, kind, pat in SECRETS:
            for m in re.finditer(pat, text):
                val = m.group(0)
                if re.search(r"(?i)(xxx|your[_-]|changeme|example|placeholder|\$\{|process\.env|os\.environ|<.*>)", val):
                    continue
                add("LOW" if is_example else sev, "secrets", path, line_of(text, m.start()), f"{kind}: {val[:12]}...")
        is_doc = ext in (".md", ".txt")  # docs describe patterns; they do not run
        for sev, kind, pat in CODE:
            for m in re.finditer(pat, text):
                add("LOW" if is_doc else sev, "code", path, line_of(text, m.start()), f"{kind}{' (in docs)' if is_doc else ''}: {m.group(0)[:80]}")
        for m in BLOB.finditer(text):
            if ext in (".js", ".mjs", ".cjs", ".ts", ".py", ".sh", ".ps1") and "data:image" not in text[max(0, m.start() - 40):m.start()]:
                add("MED", "obfuscation", path, line_of(text, m.start()), f"{len(m.group(1))}-char encoded blob")
        if name == "package.json":
            try:
                pkg = json.loads(text)
            except ValueError:
                pkg = {}
            for k, v in (pkg.get("scripts") or {}).items():
                if k in LIFECYCLE:
                    sev = "HIGH" if RISKY_SCRIPT.search(str(v)) else "LOW"
                    add(sev, "install", path, 0, f'"{k}": "{v}"')
            for sect in ("dependencies", "devDependencies", "optionalDependencies"):
                for dep, ver in (pkg.get(sect) or {}).items():
                    sv = str(ver)
                    if re.match(r"^(git|git\+|https?:|github:|file:)", sv) or re.match(r"^[\w-]+/[\w.-]+(#.*)?$", sv):
                        add("MED", "install", path, 0, f"{dep} comes from {sv} (not the registry)")
                    elif sv in ("*", "latest", ""):
                        add("LOW", "install", path, 0, f"{dep} pinned to '{sv}'")
        if rel.replace("\\", "/").endswith(".vscode/tasks.json") and re.search(r'"runOn"\s*:\s*"folderOpen"', text):
            add("HIGH", "auto-run", path, 0, 'VS Code task runs automatically when the folder is opened ("runOn": "folderOpen")')
        if "/.github/workflows/" in "/" + rel.replace("\\", "/"):
            if "pull_request_target" in text and re.search(r"ref:\s*\$\{\{\s*github\.event\.pull_request\.head", text):
                add("HIGH", "auto-run", path, 0, "pull_request_target checks out untrusted PR code with secrets available")
            if re.search(r"echo\s+\$\{\{\s*secrets\.", text):
                add("MED", "auto-run", path, 0, "workflow echoes a secret")
    hooks = os.path.join(root, ".husky")
    if os.path.isdir(hooks):
        for f in os.listdir(hooks):
            p = os.path.join(hooks, f)
            if os.path.isfile(p) and RISKY_SCRIPT.search(open(p, errors="ignore").read()):
                add("MED", "auto-run", p, 0, "git hook downloads or runs remote code")
    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: (order[f["severity"]], f["file"], f["line"]))
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--json")
    ap.add_argument("--max-mb", type=float, default=2.0)
    ap.add_argument("--include-node-modules", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.path)
    f = scan(root, a.max_mb, a.include_node_modules)
    counts = {s: sum(1 for x in f if x["severity"] == s) for s in ("HIGH", "MED", "LOW")}
    for x in f:
        loc = f"{x['file']}:{x['line']}" if x["line"] else x["file"]
        print(f"{x['severity']:4}  {x['kind']:11}  {loc}  {x['detail']}")
    print(json.dumps({"root": root, "counts": counts}))
    if a.json:
        json.dump({"root": root, "counts": counts, "findings": f}, open(a.json, "w"), indent=2)
    sys.exit(2 if counts["HIGH"] else 0)


if __name__ == "__main__":
    main()
