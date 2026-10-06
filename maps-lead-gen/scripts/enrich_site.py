#!/usr/bin/env python3
"""Crawl each business's own website: home, About/Team/Doctors, Contact, Careers pages + footer.

Writes the visible text of every page it read to <cache>/<slug>.json (the owner finder reads it), and adds:
  site_status, site_final_url, pages_crawled, site_emails, named_emails, general_emails, site_phones,
  has_chat_widget, chat_tool, has_online_booking, booking_tool, hiring_signal, hiring_evidence,
  copyright_year, automation_gaps, niche_seen, site_cache, crawled_at
Only what is on the page is recorded. Polite: few workers, normal UA, max --pages pages per site.

Usage: enrich_site.py raw.csv --out enriched.csv --cache ./site_cache [--pages 6] [--workers 6]
"""
import argparse, datetime as dt, json, os, re, sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import UA_BROWSER, domain_of, email_type, norm_name, now_iso, read_csv, write_csv

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?([2-9]\d{2})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})\b")
JUNK = ("example.", "sentry", "wixpress", "domain.com", "email.com", "yourname", "yourdomain", "@2x", ".png", ".jpg", ".jpeg", ".webp",
        ".svg", ".gif", "godaddy", "squarespace", "wordpress", "sentry.io", "user@", "name@", "test@", "@test", "jquery")
PAGE_WORDS = {"about": ("about", "our-story", "who-we-are", "our-practice", "practice", "history"),
              "team": ("team", "staff", "doctor", "dentist", "meet", "our-people", "leadership", "providers", "attorneys", "bio"),
              "contact": ("contact", "location", "visit"),
              "careers": ("career", "jobs", "employment", "hiring", "join-our-team", "join-us", "work-with-us")}
CHAT = {"intercom": "intercom", "drift.com": "drift", "tidio": "tidio", "livechatinc": "livechat", "tawk.to": "tawk", "podium": "podium",
        "birdeye": "birdeye", "crisp.chat": "crisp", "zopim": "zendesk", "zdassets": "zendesk", "hs-scripts": "hubspot", "olark": "olark",
        "smith.ai": "smith.ai", "ruby.com": "ruby", "manychat": "manychat", "chatbase": "chatbase", "voiceflow": "voiceflow", "getweave": "weave",
        "leadconnector": "gohighlevel", "msgsndr": "gohighlevel", "nexhealth.com/chat": "nexhealth chat", "gorgias": "gorgias"}
BOOKING = {"calendly": "calendly", "acuityscheduling": "acuity", "squareup.com/appointments": "square", "vagaro": "vagaro", "zocdoc": "zocdoc",
           "nexhealth": "nexhealth", "localmed": "localmed", "housecallpro": "housecall pro", "servicetitan": "servicetitan", "getjobber": "jobber",
           "booksy": "booksy", "mindbody": "mindbody", "fresha": "fresha", "setmore": "setmore", "schedulicity": "schedulicity",
           "opentable": "opentable", "flexbook": "flexbook", "solutionreach": "solutionreach", "lighthouse360": "lighthouse", "modento": "modento",
           "yelp.com/reservations": "yelp", "jane.app": "jane", "janeapp": "jane", "joinblvd": "boulevard", "zenoti": "zenoti",
           "patientpop": "patientpop", "dentalhq": "dentalhq", "sikkasoft": "sikka", "carestack": "carestack", "denticon": "denticon"}
HIRING_RE = re.compile(r"(we(?:'|’)?re hiring|now hiring|join our team|open positions|current openings|job openings|apply (?:now|today)|"
                       r"(?:receptionist|front desk|office manager|dental assistant|hygienist|scheduler|coordinator|technician|csr)\b[^.]{0,60}(?:position|opening|wanted|needed|hiring))", re.I)


def get(url):
    try:
        return requests.get(url, headers=UA_BROWSER, timeout=20, allow_redirects=True)
    except Exception as e:
        return e


def slug(row):
    return re.sub(r"[^a-z0-9]+", "-", f'{norm_name(row.get("business_name"))}-{row.get("postcode") or row.get("city") or ""}'.lower()).strip("-")[:80]


def visible(html):
    soup = BeautifulSoup(html, "lxml")
    footer = " ".join(f.get_text(" ", strip=True) for f in soup.find_all("footer"))
    for t in soup(["script", "style", "noscript", "svg"]): t.decompose()
    return soup.get_text(" ", strip=True), footer


def pick_links(base_url, html, host):
    soup = BeautifulSoup(html, "lxml"); found = {}
    for a in soup.find_all("a", href=True):
        h = a["href"].strip(); t = a.get_text(" ", strip=True).lower()
        if h.startswith(("mailto:", "tel:", "#", "javascript:")): continue
        u = urljoin(base_url, h).split("#")[0]
        if domain_of(u) != host: continue
        path = urlparse(u).path.lower()
        for kind, words in PAGE_WORDS.items():
            if any(w in path or w in t for w in words):
                found.setdefault(kind, [])
                if u not in found[kind]: found[kind].append(u)
    return found


def crawl(row, cache_dir, max_pages):
    out = dict(row)
    for k in ["site_status", "site_final_url", "pages_crawled", "site_emails", "named_emails", "general_emails", "site_phones", "has_chat_widget",
              "chat_tool", "has_online_booking", "booking_tool", "hiring_signal", "hiring_evidence", "copyright_year", "automation_gaps", "site_cache", "niche_seen"]:
        out[k] = ""
    out["crawled_at"] = now_iso()
    site = (row.get("website") or "").strip()
    if not site:
        out["site_status"] = "no website"; return out
    if not site.startswith("http"): site = "https://" + site
    r = get(site)
    if isinstance(r, Exception) and site.startswith("https://"): r = get("http://" + site[8:])
    if isinstance(r, Exception):
        out["site_status"] = "unreachable"; return out
    out["site_status"] = r.status_code; out["site_final_url"] = r.url
    if r.status_code >= 400: return out
    host = domain_of(r.url)
    pages = {r.url: r.text}; kinds = {r.url: "home"}
    links = pick_links(r.url, r.text, host)
    queue = []
    for kind in ("team", "about", "contact", "careers"):
        for u in links.get(kind, [])[:2]: queue.append((kind, u))
    for kind, u in queue:
        if len(pages) >= max_pages: break
        if u in pages: continue
        p = get(u)
        if not isinstance(p, Exception) and p.status_code < 400 and "html" in p.headers.get("content-type", "html"):
            pages[p.url] = p.text; kinds[p.url] = kind
    texts, html_all = {}, "\n".join(pages.values())
    footer_text = ""
    for u, h in pages.items():
        t, f = visible(h); texts[u] = {"kind": kinds[u], "text": t[:20000]}
        if f and not footer_text: footer_text = f
    if footer_text: texts["footer"] = {"kind": "footer", "text": footer_text[:3000]}
    low = html_all.lower()
    mailtos = [m.split("?")[0] for m in re.findall(r'mailto:([^"\'>\s]+)', html_all, re.I)]
    all_text = " ".join(v["text"] for v in texts.values())
    emails = []
    for e in EMAIL_RE.findall(" ".join(mailtos) + " " + all_text):
        e = e.strip(".").lower()
        if any(j in e for j in JUNK) or e in emails: continue
        emails.append(e)
    emails.sort(key=lambda e: (not e.endswith(host), e))
    out["site_emails"] = "; ".join(emails[:6])
    out["named_emails"] = "; ".join(e for e in emails if email_type(e, row.get("business_name", "")) == "named")
    out["general_emails"] = "; ".join(e for e in emails if email_type(e, row.get("business_name", "")) == "general")
    phones = []
    for m in PHONE_RE.finditer(" ".join(re.findall(r'tel:([+\d().\-\s]+)', html_all, re.I)) + " " + all_text):
        p = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
        if p not in phones: phones.append(p)
    out["site_phones"] = "; ".join(phones[:3])
    chat = next((v for k, v in CHAT.items() if k in low), "")
    book = next((v for k, v in BOOKING.items() if k in low), "")
    if not book and re.search(r"book (an )?(appointment|online|now)|schedule (online|now|an appointment)|request (an )?appointment", all_text, re.I) \
            and re.search(r"<form|<iframe", low):
        book = "on-site form"
    out.update(has_chat_widget=bool(chat), chat_tool=chat, has_online_booking=bool(book), booking_tool=book)
    hire = []
    if any(k == "careers" for k in kinds.values()): hire.append("careers page: " + next(u for u, k in kinds.items() if k == "careers"))
    m = HIRING_RE.search(all_text)
    if m: hire.append(f'"{m.group(0)[:80]}"')
    out["hiring_signal"] = bool(hire); out["hiring_evidence"] = " | ".join(hire)
    years = [int(y) for y in re.findall(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(20\d{2})", html_all, re.I)]
    out["copyright_year"] = max(years) if years else ""
    gaps = []
    if not chat: gaps.append("no chat/AI receptionist seen")
    if not book: gaps.append("no online booking seen")
    if not emails: gaps.append("no public email")
    if years and max(years) < dt.date.today().year - 2: gaps.append(f"site footer says {max(years)}")
    out["automation_gaps"] = "; ".join(gaps)
    # niche sanity: does their own site mention the niche at all? (catches mis-tagged map listings)
    stems = [w[:4] for w in re.findall(r"[a-z]+", (row.get("category") or "").lower()) if len(w) > 3]
    out["niche_seen"] = (not stems) or any(s in all_text.lower() for s in stems)
    out["pages_crawled"] = " ".join(pages)
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, slug(row) + ".json")
    json.dump({"business_name": row.get("business_name"), "website": r.url, "crawled_at": out["crawled_at"], "pages": texts}, open(path, "w"))
    out["site_cache"] = path
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--out", required=True)
    ap.add_argument("--cache", default="site_cache"); ap.add_argument("--pages", type=int, default=6)
    ap.add_argument("--workers", type=int, default=6); ap.add_argument("--max", type=int, default=5000)
    a = ap.parse_args()
    rows = read_csv(a.csv)[: a.max]
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(lambda r: crawl(r, a.cache, a.pages), rows))
    write_csv(res, a.out)
    live = sum(1 for r in res if str(r["site_status"]) == "200")
    print(f"{len(res)} rows, {live} sites crawled, {sum(1 for r in res if r['site_emails'])} with an email on site, "
          f"{sum(1 for r in res if r['hiring_signal'] in (True, 'True'))} hiring -> {a.out}")


if __name__ == "__main__":
    main()
