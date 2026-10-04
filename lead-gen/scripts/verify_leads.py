#!/usr/bin/env python3
"""Verify and enrich a lead list by visiting each business's own website. Writes CSV + XLSX.

Usage: verify_leads.py leads.csv --out leads_verified [--workers 6] [--max 200]
Input CSV needs at least: business_name, website (phone/email/address optional).
Every filled field is something observed on the live site (or DNS) at verified_at; the URL it came
from is listed in evidence_urls. Nothing is guessed. Drafts only: this script never contacts anyone.
"""
import argparse, csv, datetime as dt, re, socket, sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?([2-9]\d{2})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})\b")
JUNK_EMAIL = ("example.", "sentry", "wixpress", "domain.com", "email.com", "yourname", "@2x", ".png", ".jpg", ".webp", ".svg", "godaddy", "squarespace")
US_STATES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
CHAT = {"intercom": "intercom", "drift.com": "drift", "tidio": "tidio", "livechatinc": "livechat", "tawk.to": "tawk", "podium": "podium",
        "birdeye": "birdeye", "crisp.chat": "crisp", "zopim": "zendesk", "zendesk": "zendesk", "hs-scripts": "hubspot", "olark": "olark",
        "smith.ai": "smith.ai", "ruby.com": "ruby", "manychat": "manychat", "chatbase": "chatbase", "voiceflow": "voiceflow", "weave": "weave"}
BOOKING = {"calendly": "calendly", "acuityscheduling": "acuity", "squareup.com/appointments": "square", "vagaro": "vagaro", "zocdoc": "zocdoc",
           "nexhealth": "nexhealth", "localmed": "localmed", "housecallpro": "housecall pro", "servicetitan": "servicetitan", "getjobber": "jobber",
           "booksy": "booksy", "mindbody": "mindbody", "fresha": "fresha", "setmore": "setmore", "schedulicity": "schedulicity", "opentable": "opentable",
           "flexbook": "flexbook", "solutionreach": "solutionreach", "lighthouse360": "lighthouse", "modento": "modento", "yelp.com/reservations": "yelp"}


def get(url):
    try:
        r = requests.get(url, headers=UA, timeout=20, allow_redirects=True)
        return r
    except Exception as e:
        return e


def clean_emails(text, domain):
    out = []
    for e in EMAIL_RE.findall(text):
        e = e.strip(".").lower()
        if any(j in e for j in JUNK_EMAIL): continue
        if e not in out: out.append(e)
    # same-domain addresses first, then generic mailboxes
    return sorted(out, key=lambda e: (not e.endswith(domain), not e.split("@")[0] in ("info", "contact", "office", "hello", "frontdesk", "admin")))


def mx_ok(domain):
    try:
        import dns.resolver
        return bool(dns.resolver.resolve(domain, "MX", lifetime=8))
    except Exception:
        return False


def verify(row):
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    out = dict(row)
    out.update({k: "" for k in ["website_status", "website_final_url", "https", "emails_found", "email_mx_ok", "phones_found", "us_signal",
                                "has_chat_widget", "chat_tool", "has_online_booking", "booking_tool", "contact_page", "copyright_year",
                                "automation_gaps", "fit_score", "evidence_urls", "verified_at", "notes"]})
    out["verified_at"] = now
    site = (row.get("website") or "").strip()
    if not site:
        out["notes"] = "no website listed"; out["fit_score"] = 0; return out
    if not site.startswith("http"): site = "https://" + site
    r = get(site)
    if isinstance(r, Exception) and site.startswith("https://"):
        r = get("http://" + site[8:])
    if isinstance(r, Exception):
        out.update(website_status="unreachable", notes=str(r)[:120], fit_score=0); return out
    out["website_status"] = r.status_code
    out["website_final_url"] = r.url
    out["https"] = r.url.startswith("https://")
    if r.status_code >= 400:
        out.update(notes=f"HTTP {r.status_code}", fit_score=0); return out
    host = urlparse(r.url).netloc.lower().removeprefix("www.")
    pages = [(r.url, r.text)]
    soup = BeautifulSoup(r.text, "lxml")
    contact = None
    for a in soup.find_all("a", href=True):
        h = a["href"].lower(); t = a.get_text(" ", strip=True).lower()
        if any(k in h or k in t for k in ("contact", "appointment", "request-appointment", "book", "schedule")) and not h.startswith(("mailto:", "tel:")):
            contact = urljoin(r.url, a["href"]); break
    if contact and urlparse(contact).netloc.lower().removeprefix("www.") == host:
        c = get(contact)
        if not isinstance(c, Exception) and c.status_code < 400:
            pages.append((c.url, c.text)); out["contact_page"] = c.url
    html_all = "\n".join(p[1] for p in pages)
    low = html_all.lower()
    mailtos = [m.split("?")[0] for m in re.findall(r'mailto:([^"\'>\s]+)', html_all, re.I)]
    text_all = " ".join(BeautifulSoup(p[1], "lxml").get_text(" ", strip=True) for p in pages)
    emails = clean_emails(" ".join(mailtos) + " " + text_all, host)
    out["emails_found"] = "; ".join(emails[:3])
    if emails: out["email_mx_ok"] = mx_ok(emails[0].split("@")[1])
    tels = re.findall(r'tel:([+\d().\-\s]+)', html_all, re.I)
    phones = []
    for m in PHONE_RE.finditer(" ".join(tels) + " " + text_all):
        p = f"({m.group(1)}) {m.group(2)}-{m.group(3)}"
        if p not in phones: phones.append(p)
    out["phones_found"] = "; ".join(phones[:2])
    us = []
    if phones: us.append("US-format phone")
    if re.search(r"\b(" + "|".join(US_STATES) + r")\s+\d{5}(?:-\d{4})?\b", text_all): us.append("US state + ZIP")
    if "$" in text_all: us.append("USD prices")
    out["us_signal"] = "; ".join(us)
    chat = next((v for k, v in CHAT.items() if k in low), "")
    book = next((v for k, v in BOOKING.items() if k in low), "")
    if not book and re.search(r"book (an )?(appointment|online|now)|schedule (online|now|an appointment)", text_all, re.I) and re.search(r"<form|iframe", low):
        book = "on-site form"
    out.update(has_chat_widget=bool(chat), chat_tool=chat, has_online_booking=bool(book), booking_tool=book)
    years = [int(y) for y in re.findall(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(20\d{2})", html_all, re.I)]
    out["copyright_year"] = max(years) if years else ""
    gaps = []
    if not chat: gaps.append("no chat/AI receptionist seen")
    if not book: gaps.append("no online booking seen")
    if not out["https"]: gaps.append("no https")
    if not emails: gaps.append("no public email")
    this_year = dt.date.today().year
    if years and max(years) < this_year - 2: gaps.append(f"site footer says {max(years)}")
    out["automation_gaps"] = "; ".join(gaps)
    score = 40 + (20 if not chat else 0) + (15 if not book else 0) + (10 if phones else 0) + (5 if emails else 0) + (10 if us else 0)
    out["fit_score"] = max(0, min(100, score))
    out["evidence_urls"] = " ".join(dict.fromkeys(p[0] for p in pages))
    return out


def write_xlsx(rows, path, verified_on):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = "Leads"
    cols = list(rows[0].keys())
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="000000"); c.alignment = Alignment(vertical="center")
    for r in rows: ws.append([("" if r.get(c) is None else r.get(c)) for c in cols])
    for i, c in enumerate(cols, 1):
        width = min(60, max(10, *(len(str(r.get(c, ""))) for r in rows[:200]), len(c)) + 2)
        ws.column_dimensions[get_column_letter(i)].width = width
        if c in ("website", "website_final_url", "contact_page", "osm_url"):
            for cell in ws[get_column_letter(i)][1:]:
                if str(cell.value).startswith("http"): cell.hyperlink = cell.value; cell.font = Font(color="0563C1", underline="single")
    ws.freeze_panes = "B2"; ws.auto_filter.ref = ws.dimensions
    info = wb.create_sheet("About")
    for line in [["How to read this sheet"], [f"Verified on {verified_on} (UTC) by visiting each business's own website."],
                 ["A field is filled only when it was observed on the page(s) listed in evidence_urls, or in DNS (email_mx_ok)."],
                 ["fit_score is a rough priority (no chat widget, no online booking, US signals, reachable by phone/email). It is not a promise of interest."],
                 ["Outreach: drafts only. John reviews and sends every message himself."]]:
        info.append(line)
    info.column_dimensions["A"].width = 120
    wb.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv"); ap.add_argument("--out", required=True, help="output path without extension")
    ap.add_argument("--workers", type=int, default=6); ap.add_argument("--max", type=int, default=500)
    ap.add_argument("--min-score", type=int, default=0)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.csv, newline="", encoding="utf-8")))[: a.max]
    if not rows: sys.exit("no rows")
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(verify, rows))
    res = [r for r in res if int(r.get("fit_score") or 0) >= a.min_score]
    res.sort(key=lambda r: -int(r.get("fit_score") or 0))
    with open(a.out + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(res[0].keys())); w.writeheader(); w.writerows(res)
    write_xlsx(res, a.out + ".xlsx", res[0]["verified_at"])
    ok = sum(1 for r in res if str(r.get("website_status")) == "200")
    print(f"{len(res)} leads ({ok} live sites) -> {a.out}.csv, {a.out}.xlsx")


if __name__ == "__main__":
    main()
