#!/usr/bin/env python3
"""Self-host a Google font: download its woff2 files and write the @font-face CSS.

Why: next/font/google and <link> tags fetch fonts at build or load time. That fetch failed on
Vercel's build for pow-platform (Oct 2026). Files in the repo never fail and render the same.

Usage:
  google_font.py "Outfit" --out public/fonts --css src/app/fonts.css [--weights 100..900] [--subsets latin,latin-ext]
  google_font.py "Plus Jakarta Sans" --weights 400,500,700 --italic --out public/fonts --css fonts.css

--url-prefix sets the path the CSS uses (default /fonts). All Google Fonts are under the SIL OFL or
Apache licence, so self-hosting is allowed; keep the licence note in the CSS header.
"""
import argparse
import os
import re
import sys

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")  # a modern UA gets woff2 + unicode-range


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("family")
    ap.add_argument("--out", required=True, help="folder for the woff2 files")
    ap.add_argument("--css", required=True, help="CSS file to write")
    ap.add_argument("--weights", default="100..900", help="variable range like 100..900, or a list 400,500,700")
    ap.add_argument("--italic", action="store_true")
    ap.add_argument("--subsets", default="latin,latin-ext")
    ap.add_argument("--url-prefix", default="/fonts")
    a = ap.parse_args()

    fam = a.family.replace(" ", "+")
    w = a.weights
    if a.italic:
        spec = "ital,wght@" + ";".join(f"{i},{x}" for i in (0, 1) for x in (w.split(",") if "," in w else [w]))
    else:
        spec = "wght@" + (";".join(w.split(",")) if "," in w else w)
    url = f"https://fonts.googleapis.com/css2?family={fam}:{spec}&display=swap"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    if r.status_code != 200:
        sys.exit(f"Google Fonts answered {r.status_code} for {url}\n{r.text[:300]}")
    want = set(s.strip() for s in a.subsets.split(","))
    os.makedirs(a.out, exist_ok=True)
    blocks = re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*{[^}]*})", r.text)
    css_out = [f"/* {a.family}: self-hosted from Google Fonts (SIL Open Font License / Apache 2.0). */"]
    saved = 0
    for subset, block in blocks:
        if subset not in want:
            continue
        src = re.search(r"url\((https://[^)]+\.woff2)\)", block).group(1)
        weight = re.search(r"font-weight:\s*([^;]+);", block).group(1).strip().replace(" ", "-")
        style = re.search(r"font-style:\s*([^;]+);", block).group(1).strip()
        name = f"{a.family.replace(' ', '')}-{style}-{weight}-{subset}.woff2"
        path = os.path.join(a.out, name)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(requests.get(src, headers={"User-Agent": UA}, timeout=60).content)
            saved += 1
        css_out.append(block.replace(src, f"{a.url_prefix.rstrip('/')}/{name}"))
    if len(css_out) == 1:
        sys.exit(f"no blocks for subsets {sorted(want)}; available: {sorted(set(s for s, _ in blocks))}")
    os.makedirs(os.path.dirname(os.path.abspath(a.css)), exist_ok=True)
    with open(a.css, "w") as f:
        f.write("\n".join(css_out) + "\n")
    print(f"{len(css_out) - 1} @font-face blocks -> {a.css}; {saved} new files in {a.out}")
    print(f"use: font-family: '{a.family}', system-ui, sans-serif;")


if __name__ == "__main__":
    main()
