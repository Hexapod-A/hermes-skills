#!/usr/bin/env python3
"""Fill in missing websites (free OSM pulls often lack them).

For each row with no website, search "<name> <city> <state>" and accept a result ONLY if the page itself
proves the match: the business name's distinctive words appear on the page AND (the listed phone OR the
city appears too). Directories (Yelp, Facebook, Zocdoc, ...) are skipped. Unproven rows stay empty.
Search backend: SERPER_API_KEY if set, SEARXNG_URL if set, else DuckDuckGo / Bing HTML (free, polite rate).

Usage: find_websites.py raw.csv --out raw_sites.csv [--max 300]
Adds: website_source (listing | search-verified), website_evidence
"""
import argparse, base64, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, unquote, urlparse
import requests
from bs4 import BeautifulSoup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import UA_BROWSER, domain_of, env, log, norm_name, read_csv, write_csv

DIRECTORIES = ("yelp.", "facebook.", "instagram.", "zocdoc.", "healthgrades.", "yellowpages.", "bbb.org", "mapquest.", "linkedin.",
               "google.", "apple.com", "nextdoor.", "angi.", "homeadvisor.", "thumbtack.", "opencare.", "vitals.com", "webmd.", "tripadvisor.",
               "x.com", "twitter.", "tiktok.", "youtube.", "groupon.", "manta.", "chamberofcommerce.", "birdeye.", "doctor.com", "sharecare.",
               "wikipedia.", "indeed.", "glassdoor.", "porch.", "houzz.", "superpages.", "dexknows.", "foursquare.", "waze.", "bing.", "duckduckgo.")
STOP = {"dental", "dentistry", "family", "cosmetic", "group", "studio", "center", "centre", "clinic", "south", "north", "east", "west",
        "austin", "and", "of", "the", "care", "smile", "smiles", "services", "service", "company", "llc", "inc", "dds", "dmd", "co"}


def _bing_url(h):
    # Bing wraps results as /ck/a?...&u=a1<base64url>; unwrap to the real URL
    u = parse_qs(urlparse(h).query).get("u", [""])[0]
    if u.startswith("a1"):
        s = u[2:]; s += "=" * (-len(s) % 4)
        try: return base64.urlsafe_b64decode(s).decode()
        except Exception: return ""
    return h


def search(q):
    """Serper if SERPER_API_KEY, SearXNG if SEARXNG_URL, else DuckDuckGo HTML, falling back to Bing HTML when DDG rate-limits."""
    key = env("SERPER_API_KEY")
    if key:
        r = requests.post("https://google.serper.dev/search", json={"q": q, "gl": "us", "num": 8}, headers={"X-API-KEY": key}, timeout=30)
        return [x.get("link") for x in r.json().get("organic", [])]
    sx = env("SEARXNG_URL")
    if sx:
        r = requests.get(sx.rstrip("/") + "/search", params={"q": q, "format": "json"}, timeout=30)
        return [x.get("url") for x in r.json().get("results", [])]
    links = []
    for wait in (0, 6, 20):  # DuckDuckGo answers 202 when it wants you to slow down
        time.sleep(wait)
        r = requests.post("https://html.duckduckgo.com/html/", data={"q": q, "kl": "us-en"}, headers=UA_BROWSER, timeout=30)
        if r.status_code == 200:
            for a in BeautifulSoup(r.text, "lxml").select("a.result__a"):
                h = a.get("href", "")
                if "uddg=" in h: h = unquote(parse_qs(urlparse(h).query).get("uddg", [""])[0])
                if h.startswith("http"): links.append(h)
            break
    if not links:  # last resort; Bing's bot results are noisy, the page proof below filters them
        time.sleep(1)
        r = requests.get("https://www.bing.com/search", params={"q": q, "setlang": "en-us", "cc": "us"}, headers=UA_BROWSER, timeout=30)
        for a in BeautifulSoup(r.text, "lxml").select("li.b_algo h2 a"):
            h = _bing_url(a.get("href", ""))
            if h.startswith("http"): links.append(h)
    return links


def proves(url, row):
    try:
        r = requests.get(url, headers=UA_BROWSER, timeout=20)
        if r.status_code >= 400: return None
    except Exception:
        return None
    text = BeautifulSoup(r.text, "lxml").get_text(" ", strip=True).lower()
    words = [w for w in norm_name(row["business_name"]).split() if w not in STOP and len(w) > 2]
    if not words: words = [w for w in norm_name(row["business_name"]).split() if len(w) > 2]
    name_ok = words and all(w in text for w in words[:3])
    digits = re.sub(r"\D", "", row.get("phone") or "")[-10:]
    phone_ok = len(digits) == 10 and digits in re.sub(r"\D", "", r.text)
    city_ok = bool(row.get("city")) and row["city"].lower() in text
    # niche word on the page (dentist -> "dent", roofer -> "roof") so "Lane Dental" never matches a "Lane" college
    stems = [w[:4] for w in re.findall(r"[a-z]+", (row.get("category") or "").lower()) if len(w) > 3]
    niche_ok = not stems or any(s in text for s in stems)
    if phone_ok and name_ok:
        return r.url, f"name words {words[:3]} + listed phone found on page"
    if name_ok and city_ok and niche_ok:
        return r.url, f"name words {words[:3]} + city + niche word found on page (no phone to cross-check)"
    return None


def resolve(row):
    out = dict(row)
    if out.get("website"):
        out.setdefault("website_source", "listing"); out["website_source"] = out.get("website_source") or "listing"; return out
    q = f'{row["business_name"]} {row.get("city", "")} {row.get("state", "")}'.strip()
    try:
        links = search(q)
    except Exception as e:
        out["website_evidence"] = f"search failed: {e}"[:120]; return out
    seen = set()
    for link in links[:6]:
        d = domain_of(link)
        if not d or d in seen or any(x in d for x in DIRECTORIES) or d.endswith((".edu", ".gov")): continue
        seen.add(d)
        hit = proves(f"https://{d}/" if urlparse(link).path in ("", "/") else link, row) or proves(f"https://{d}/", row)
        if hit:
            out["website"] = hit[0]; out["website_source"] = "search-verified"; out["website_evidence"] = hit[1]; return out
    out["website_source"] = ""; out["website_evidence"] = "no result proved the match"
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=1000); ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    rows = read_csv(a.csv)[: a.max]
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(resolve, rows))
    write_csv(res, a.out)
    found = sum(1 for r in res if r.get("website_source") == "search-verified")
    print(f"{len(res)} rows; {sum(1 for r in res if r.get('website'))} with a website ({found} newly found and page-verified) -> {a.out}")


if __name__ == "__main__":
    main()
