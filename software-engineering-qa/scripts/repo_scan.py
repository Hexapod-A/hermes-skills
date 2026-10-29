#!/usr/bin/env python3
"""One command to health-check a code repo: detect the stack, then run whatever checks exist
(lint, type check, tests, build, dependency audit, secret scan, malware red flags) and print a table.
Nothing is changed in the repo; missing tools are reported as "skipped", not errors.

Usage:
  python3 repo_scan.py PATH [--build] [--no-tests] [--json report.json] [--timeout 600]

  --build     also run the production build (npm run build / python -m build) - slower
  --no-tests  skip the test suite

Exit code: 0 all ran checks passed, 2 something failed, 1 could not run.
Install the optional scanners for deeper results: gitleaks (secrets in git history), trufflehog,
pip-audit, semgrep (`pip install semgrep`, then `semgrep --config auto`).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def sh(cmd, cwd, timeout):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, shell=isinstance(cmd, str))
        return p.returncode, (p.stdout + "\n" + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except FileNotFoundError as e:
        return 127, str(e)


def tail(text, n=12):
    lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(lines[-n:])


def detect(root):
    st = {"node": os.path.exists(os.path.join(root, "package.json")),
          "python": any(os.path.exists(os.path.join(root, f)) for f in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")),
          "git": os.path.isdir(os.path.join(root, ".git"))}
    pkg = {}
    if st["node"]:
        try:
            pkg = json.load(open(os.path.join(root, "package.json")))
        except ValueError:
            pass
        st["scripts"] = pkg.get("scripts", {})
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        st["framework"] = next((f for f in ("next", "nuxt", "@sveltejs/kit", "astro", "vite", "react-scripts", "express", "@nestjs/core") if f in deps), None)
        st["typescript"] = "typescript" in deps or os.path.exists(os.path.join(root, "tsconfig.json"))
        st["pm"] = ("pnpm" if os.path.exists(os.path.join(root, "pnpm-lock.yaml")) else
                    "yarn" if os.path.exists(os.path.join(root, "yarn.lock")) else
                    "bun" if os.path.exists(os.path.join(root, "bun.lockb")) else "npm")
        st["installed"] = os.path.isdir(os.path.join(root, "node_modules"))
    return st


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--no-tests", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()
    root = os.path.abspath(a.path)
    if not os.path.isdir(root):
        print(f"not a folder: {root}"); sys.exit(1)
    st = detect(root)
    T = a.timeout
    results = []

    def check(name, cmd, ok_codes=(0,), why_skip=None):
        if why_skip:
            results.append({"check": name, "status": "skipped", "detail": why_skip}); return
        code, out = sh(cmd, root, T)
        status = "pass" if code in ok_codes else ("skipped" if code == 127 else "FAIL")
        results.append({"check": name, "status": status, "code": code, "cmd": cmd if isinstance(cmd, str) else " ".join(cmd),
                        "detail": tail(out)})

    # always: malware red flags + secrets in the working tree
    check("red flags + secrets (suspicious_scan)", [sys.executable, os.path.join(HERE, "suspicious_scan.py"), root])
    if shutil.which("gitleaks") and st["git"]:
        check("secrets in git history (gitleaks)", ["gitleaks", "detect", "--source", root, "--no-banner", "--redact", "-v"])
    elif shutil.which("trufflehog") and st["git"]:
        check("secrets in git history (trufflehog)", ["trufflehog", "git", f"file://{root}", "--only-verified", "--fail"])
    else:
        results.append({"check": "secrets in git history", "status": "skipped", "detail": "install gitleaks or trufflehog"})

    if st["node"]:
        scripts = st.get("scripts", {})
        pm = st["pm"]
        run = lambda s: [pm, "run", s] if pm != "npm" else ["npm", "run", "-s", s]  # noqa: E731
        nm = None if st["installed"] else f"node_modules missing: run `{pm} install` (or `npm ci`) first"
        check("dependency audit", ["npm", "audit", "--omit=dev", "--audit-level=high"] if pm == "npm" else [pm, "audit"],
              why_skip=None if os.path.exists(os.path.join(root, "package-lock.json")) or pm != "npm" else "no package-lock.json")
        if "lint" in scripts:
            check("lint", run("lint"), why_skip=nm)
        elif os.path.exists(os.path.join(root, "node_modules", ".bin", "eslint")):
            check("lint (eslint)", ["npx", "--no-install", "eslint", "."], why_skip=nm)
        else:
            results.append({"check": "lint", "status": "skipped", "detail": "no lint script or eslint"})
        if st.get("typescript"):
            if "typecheck" in scripts:
                check("type check", run("typecheck"), why_skip=nm)
            else:
                check("type check (tsc --noEmit)", ["npx", "--no-install", "tsc", "--noEmit", "-p", "."], why_skip=nm)
        if not a.no_tests:
            if "test" in scripts and "no test specified" not in scripts["test"]:
                check("tests", run("test"), why_skip=nm)
            else:
                results.append({"check": "tests", "status": "skipped", "detail": "no test script"})
        if a.build and "build" in scripts:
            check("build", run("build"), why_skip=nm)
    if st["python"]:
        py = os.path.join(root, ".venv", "bin", "python")
        py = py if os.path.exists(py) else sys.executable
        if shutil.which("ruff"):
            check("lint (ruff)", ["ruff", "check", "."])
        else:
            code, _ = sh([py, "-m", "pyflakes", "--version"], root, 30)
            if code == 0:
                check("lint (pyflakes)", [py, "-m", "pyflakes", "."])
            else:
                check("syntax (compileall)", [py, "-m", "compileall", "-q", "-x", r"(\.venv|node_modules|\.git)", "."])
        pyproject = os.path.join(root, "pyproject.toml")
        wants_mypy = os.path.exists(os.path.join(root, "mypy.ini")) or (
            os.path.exists(pyproject) and "[tool.mypy]" in open(pyproject).read())
        if wants_mypy and shutil.which("mypy"):
            check("type check (mypy)", ["mypy", "."])
        if shutil.which("pip-audit") and os.path.exists(os.path.join(root, "requirements.txt")):
            check("dependency audit (pip-audit)", ["pip-audit", "-r", "requirements.txt"])
        else:
            results.append({"check": "python dependency audit", "status": "skipped", "detail": "pip install pip-audit"})
        if not a.no_tests:
            has_tests = any(d in os.listdir(root) for d in ("tests", "test")) or any(f.startswith("test_") for f in os.listdir(root))
            code, _ = sh([py, "-m", "pytest", "--version"], root, 30)
            if has_tests and code == 0:
                check("tests (pytest)", [py, "-m", "pytest", "-q", "-x"], ok_codes=(0, 5))
            elif has_tests:
                results.append({"check": "tests", "status": "skipped", "detail": "pytest not installed"})

    print(f"stack: {json.dumps({k: v for k, v in st.items() if k != 'scripts'})}")
    for r in results:
        print(f"{r['status']:8} {r['check']}")
        if r["status"] == "FAIL":
            for line in r["detail"].splitlines()[-8:]:
                print(f"         | {line[:200]}")
    failed = [r for r in results if r["status"] == "FAIL"]
    print(json.dumps({"passed": sum(r["status"] == "pass" for r in results), "failed": len(failed),
                      "skipped": sum(r["status"] == "skipped" for r in results)}))
    if a.json:
        json.dump({"root": root, "stack": st, "results": results}, open(a.json, "w"), indent=2)
    sys.exit(2 if failed else 0)


if __name__ == "__main__":
    main()
