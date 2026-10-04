#!/usr/bin/env python3
"""Fetch live pages and return clean main text + metadata (title, final URL, published/updated dates).

Usage: fetch.py URL [URL ...] [--max-chars 12000] [--out DIR] [--json]
Prints one block per page. With --out, also saves <slug>.md files for later quoting.
"""
import argparse, datetime as dt, json, os, re, sys
import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}


def dates_from_html(html):
    pats = [r'"datePublished"\s*:\s*"([^"]+)"', r'"dateModified"\s*:\s*"([^"]+)"',
            r'<meta[^>]+(?:property|name)="(?:article:published_time|og:published_time|date|pubdate|publish-date)"[^>]+content="([^"]+)"',
            r'<meta[^>]+(?:property|name)="(?:article:modified_time|og:updated_time|last-modified)"[^>]+content="([^"]+)"',
            r'<time[^>]+datetime="([^"]+)"']
    found = {}
    for key, p in zip(["published", "modified", "published", "modified", "time_tag"], pats):
        m = re.search(p, html, re.I)
        if m and key not in found: found[key] = m.group(1)[:40]
    return found


def fetch(url, max_chars):
    import trafilatura
    out = {"url": url, "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    try:
        r = requests.get(url, headers=UA, timeout=25, allow_redirects=True)
        out.update(status=r.status_code, final_url=r.url, last_modified_header=r.headers.get("Last-Modified"))
        ctype = r.headers.get("Content-Type", "")
        if "pdf" in ctype:
            out.update(error="PDF: download it and read with a PDF tool", text="")
            return out
        html = r.text
    except Exception as e:
        out.update(status=None, error=str(e)[:300], text="")
        return out
    meta = trafilatura.extract_metadata(html)
    text = trafilatura.extract(html, include_links=False, include_tables=True, favor_recall=True) or ""
    if not text:
        from bs4 import BeautifulSoup
        s = BeautifulSoup(html, "lxml")
        for t in s(["script", "style", "nav", "footer", "header", "noscript"]): t.decompose()
        text = re.sub(r"\n{3,}", "\n\n", s.get_text("\n", strip=True))
    d = dates_from_html(html)
    out.update(title=(meta.title if meta and meta.title else None), site=(meta.sitename if meta else None),
               author=(meta.author if meta else None), published=(meta.date if meta and meta.date else d.get("published") or d.get("time_tag")),
               modified=d.get("modified"), chars=len(text), truncated=len(text) > max_chars, text=text[:max_chars])
    if r.status_code >= 400: out["error"] = f"HTTP {r.status_code} (blocked or gone; try another source or the browser tools)"
    elif len(text) < 300: out["warning"] = "Very little text extracted: page may need JavaScript. Use browser tools to read it."
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+"); ap.add_argument("--max-chars", type=int, default=12000)
    ap.add_argument("--out"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    pages = [fetch(u, a.max_chars) for u in a.urls]
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        for p in pages:
            slug = re.sub(r"[^a-z0-9]+", "-", (p.get("final_url") or p["url"]).lower())[-80:].strip("-")
            with open(os.path.join(a.out, slug + ".md"), "w") as f:
                f.write(f"# {p.get('title') or ''}\nURL: {p.get('final_url') or p['url']}\nPublished: {p.get('published')}\nFetched: {p['fetched_at']}\n\n{p.get('text','')}\n")
    if a.json:
        print(json.dumps(pages, indent=2, ensure_ascii=False)); return
    for p in pages:
        print(f"=== {p.get('title') or '(no title)'}\nURL: {p.get('final_url') or p['url']}  status={p.get('status')}\n"
              f"published={p.get('published')} modified={p.get('modified')} fetched={p['fetched_at']}")
        if p.get("error"): print("ERROR:", p["error"])
        if p.get("warning"): print("WARNING:", p["warning"])
        print(p.get("text", ""), "\n")
    sys.exit(0 if any(p.get("text") for p in pages) else 1)


if __name__ == "__main__":
    main()
