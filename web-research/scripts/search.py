#!/usr/bin/env python3
"""Web search with whatever backend is configured; prints JSON results.

Backends (first configured wins, or pick with --backend):
  searxng  SEARXNG_URL=https://your-searx.example   (self-hosted, free)
  brave    BRAVE_API_KEY
  serper   SERPER_API_KEY
  tavily   TAVILY_API_KEY
  ddg      no key (DuckDuckGo HTML endpoint; fine for light use)

Usage: search.py "query" [-n 8] [--backend brave] [--recent week|month|year]
"""
import argparse, json, os, sys, time, datetime as dt
from urllib.parse import urlparse, parse_qs, unquote
import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
T = 20


def searxng(q, n, recent):
    p = {"q": q, "format": "json"}
    if recent: p["time_range"] = {"week": "week", "month": "month", "year": "year"}[recent]
    r = requests.get(os.environ["SEARXNG_URL"].rstrip("/") + "/search", params=p, headers=UA, timeout=T); r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("content"), "date": x.get("publishedDate")} for x in r.json().get("results", [])[:n]]


def brave(q, n, recent):
    p = {"q": q, "count": n}
    if recent: p["freshness"] = {"week": "pw", "month": "pm", "year": "py"}[recent]
    r = requests.get("https://api.search.brave.com/res/v1/web/search", params=p, timeout=T,
                     headers={"Accept": "application/json", "X-Subscription-Token": os.environ["BRAVE_API_KEY"]}); r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("description"), "date": x.get("page_age") or x.get("age")} for x in r.json().get("web", {}).get("results", [])[:n]]


def serper(q, n, recent):
    body = {"q": q, "num": n}
    if recent: body["tbs"] = {"week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}[recent]
    r = requests.post("https://google.serper.dev/search", json=body, timeout=T, headers={"X-API-KEY": os.environ["SERPER_API_KEY"]}); r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("link"), "snippet": x.get("snippet"), "date": x.get("date")} for x in r.json().get("organic", [])[:n]]


def tavily(q, n, recent):
    body = {"query": q, "max_results": n}
    if recent: body["days"] = {"week": 7, "month": 31, "year": 365}[recent]
    r = requests.post("https://api.tavily.com/search", json=body, timeout=T, headers={"Authorization": "Bearer " + os.environ["TAVILY_API_KEY"]}); r.raise_for_status()
    return [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("content"), "date": x.get("published_date")} for x in r.json().get("results", [])[:n]]


def ddg(q, n, recent):
    from bs4 import BeautifulSoup
    p = {"q": q}
    if recent: p["df"] = {"week": "w", "month": "m", "year": "y"}[recent]
    r = requests.post("https://html.duckduckgo.com/html/", data=p, headers=UA, timeout=T); r.raise_for_status()
    s = BeautifulSoup(r.text, "html.parser"); out = []
    for res in s.select(".result"):
        a = res.select_one("a.result__a")
        if not a: continue
        href = a.get("href", "")
        if "uddg=" in href: href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
        if "duckduckgo.com/y.js" in href: continue  # ads
        sn = res.select_one(".result__snippet")
        out.append({"title": a.get_text(" ", strip=True), "url": href, "snippet": sn.get_text(" ", strip=True) if sn else "", "date": None})
        if len(out) >= n: break
    if not out:  # DDG sometimes serves an empty/anomaly page to scripts; try the lite endpoint once
        time.sleep(1.5)
        r = requests.get("https://lite.duckduckgo.com/lite/", params=p, headers=UA, timeout=T)
        s = BeautifulSoup(r.text, "html.parser")
        for a in s.select("a.result-link"):
            href = a.get("href", "")
            if "uddg=" in href: href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
            if "duckduckgo.com/y.js" in href: continue
            out.append({"title": a.get_text(" ", strip=True), "url": href, "snippet": "", "date": None})
            if len(out) >= n: break
    if not out:
        raise RuntimeError("DuckDuckGo returned no results (likely rate-limited). Configure SEARXNG_URL or BRAVE_API_KEY.")
    return out


BACKENDS = {"searxng": ("SEARXNG_URL", searxng), "brave": ("BRAVE_API_KEY", brave), "serper": ("SERPER_API_KEY", serper), "tavily": ("TAVILY_API_KEY", tavily), "ddg": (None, ddg)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query"); ap.add_argument("-n", type=int, default=8)
    ap.add_argument("--backend", choices=list(BACKENDS)); ap.add_argument("--recent", choices=["week", "month", "year"])
    a = ap.parse_args()
    order = [a.backend] if a.backend else [k for k, (env, _) in BACKENDS.items() if env is None or os.environ.get(env)]
    errors = {}
    for name in order:
        try:
            res = BACKENDS[name][1](a.query, a.n, a.recent)
            print(json.dumps({"query": a.query, "backend": name, "searched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                              "note": "Snippets are index copies; open the page before citing it.", "results": res}, indent=2, ensure_ascii=False))
            return
        except Exception as e:  # try the next backend
            errors[name] = str(e)[:300]
    print(json.dumps({"query": a.query, "error": "all backends failed", "details": errors}, indent=2)); sys.exit(1)


if __name__ == "__main__":
    main()
