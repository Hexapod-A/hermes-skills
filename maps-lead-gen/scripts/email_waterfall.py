#!/usr/bin/env python3
"""Email waterfall + verification. Stops at the first VALID email and logs which source found it.

Order (default --order site,prospeo,icypeas):
  site      emails published on the business's own site (from enrich_site.py) or in the listing. Free.
  prospeo   PROSPEO_API_KEY  - POST https://api.prospeo.io/enrich-person (needs the owner's name + website domain)
  icypeas   ICYPEAS_API_KEY  - POST https://app.icypeas.com/api/email-search, then polls the result (needs a name + domain)
  (The article runs Prospeo -> Icypeas -> crawl. We put the free crawl first to save credits; change with --order.)

Named beats general: when the owner's name is known and the site only shows a general inbox (info@, office@ ...),
the general inbox is held as a fallback while the paid finders try for the owner's own address. For local service
businesses a general inbox is fine to use (owners read them) - it is flagged email_type=general.

Verification of each candidate, cheapest first:
  1. syntax + MX record (free, dnspython)
  2. MILLIONVERIFIER_API_KEY  -> ok = valid, invalid/disposable = rejected, catch_all/unknown = needs a second check
  3. BOUNCEBAN_API_KEY        -> second check for catch-all domains (deliverable = valid, undeliverable = rejected)
  Without 2, an MX-only pass is email_status=mx_only (not mailbox-verified). Catch-all without 3 = risky.
  Send only email_status=valid from your main inboxes; that is how you stay under 1% bounces.

Usage: email_waterfall.py owners.csv --out emails.csv [--order site,prospeo,icypeas] [--log waterfall_log.csv]
Adds: email, email_type, email_source, email_status, catch_all, email_trace, email_checked_at
"""
import argparse, collections, os, re, sys, time
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import domain_of, email_type, env, log, now_iso, read_csv, write_csv

EMAIL_OK = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_mx_cache = {}


def mx_ok(domain):
    if domain in _mx_cache: return _mx_cache[domain]
    try:
        import dns.resolver
        ok = bool(dns.resolver.resolve(domain, "MX", lifetime=8))
    except Exception:
        ok = False
    _mx_cache[domain] = ok
    return ok


# ------------------------------------------------------------------ verifiers
def millionverifier_request(email, key):
    return {"url": "https://api.millionverifier.com/api/v3/", "params": {"api": key, "email": email, "timeout": 20}}


def parse_millionverifier(j):
    """-> 'valid' | 'invalid' | 'catch_all' | 'unknown'"""
    res = (j.get("result") or "").lower()
    if j.get("error"): return "unknown"
    return {"ok": "valid", "catch_all": "catch_all", "invalid": "invalid", "disposable": "invalid", "unknown": "unknown"}.get(res, "unknown")


def bounceban_request(email, key):
    # waterfall endpoint waits for the result (up to ~80 s); auth header carries the bare key (no Bearer)
    return {"url": "https://api-waterfall.bounceban.com/v1/verify/single", "params": {"email": email, "mode": "deepverify"},
            "headers": {"Authorization": key}}


def parse_bounceban(j):
    res = (j.get("result") or "").lower()
    return {"deliverable": "valid", "undeliverable": "invalid", "risky": "risky"}.get(res, "unknown")


def verify(email, trace):
    """-> (status, catch_all) with status in valid | mx_only | risky | invalid"""
    if not EMAIL_OK.match(email or ""):
        trace.append(f"{email}: bad syntax"); return "invalid", ""
    d = email.split("@")[1]
    if not mx_ok(d):
        trace.append(f"{email}: no MX"); return "invalid", ""
    mv = env("MILLIONVERIFIER_API_KEY")
    if not mv:
        trace.append(f"{email}: MX ok"); return "mx_only", ""
    try:
        req = millionverifier_request(email, mv)
        v = parse_millionverifier(requests.get(req["url"], params=req["params"], timeout=40).json())
    except Exception as e:
        trace.append(f"{email}: millionverifier error {str(e)[:60]}"); return "mx_only", ""
    trace.append(f"{email}: millionverifier {v}")
    if v in ("valid", "invalid"): return v, False
    catch_all = v == "catch_all"
    bb = env("BOUNCEBAN_API_KEY")
    if not bb:
        return "risky", catch_all
    try:
        req = bounceban_request(email, bb)
        v2 = parse_bounceban(requests.get(req["url"], params=req["params"], headers=req["headers"], timeout=100).json())
    except Exception as e:
        trace.append(f"{email}: bounceban error {str(e)[:60]}"); return "risky", catch_all
    trace.append(f"{email}: bounceban {v2}")
    return ("valid" if v2 == "valid" else "invalid" if v2 == "invalid" else "risky"), catch_all


# ------------------------------------------------------------------ finders
def prospeo_request(first, last, domain, company, key):
    return {"url": "https://api.prospeo.io/enrich-person", "headers": {"X-KEY": key, "Content-Type": "application/json"},
            "json": {"only_verified_email": True, "data": {"first_name": first, "last_name": last, "company_website": domain, "company_name": company}}}


def parse_prospeo(j):
    if j.get("error"): return None
    em = ((j.get("person") or {}).get("email") or {})
    if em.get("revealed") is False or "*" in (em.get("email") or ""): return None
    return em.get("email") or None


def find_prospeo(row, first, last, domain):
    key = env("PROSPEO_API_KEY")
    req = prospeo_request(first, last, domain, row.get("business_name", ""), key)
    r = requests.post(req["url"], json=req["json"], headers=req["headers"], timeout=60)
    if r.status_code == 429: time.sleep(5); r = requests.post(req["url"], json=req["json"], headers=req["headers"], timeout=60)
    return parse_prospeo(r.json()) if r.ok else None


def icypeas_request(first, last, domain, key):
    return {"url": "https://app.icypeas.com/api/email-search", "headers": {"Authorization": key, "Content-Type": "application/json"},
            "json": {"firstname": first or "", "lastname": last or "", "domainOrCompany": domain}}


def parse_icypeas_read(j):
    """-> ('pending', None) | ('done', email or None)"""
    items = j.get("items") or []
    if not items: return "pending", None
    it = items[0]; st = (it.get("status") or "").upper()
    if st in ("NONE", "SCHEDULED", "IN_PROGRESS"): return "pending", None
    emails = ((it.get("results") or {}).get("emails") or [])
    good = [e for e in emails if (e.get("certainty") or "") in ("ultra_sure", "very_sure", "sure", "probable")]
    return "done", (good[0]["email"] if good else None)


def find_icypeas(row, first, last, domain):
    key = env("ICYPEAS_API_KEY")
    req = icypeas_request(first, last, domain, key)
    r = requests.post(req["url"], json=req["json"], headers=req["headers"], timeout=60).json()
    sid = ((r.get("item") or {}).get("_id"))
    if not r.get("success") or not sid: return None
    for wait in (3, 4, 6, 8, 10, 15):
        time.sleep(wait)
        j = requests.post("https://app.icypeas.com/api/bulk-single-searchs/read", json={"id": sid}, headers=req["headers"], timeout=60).json()
        st, email = parse_icypeas_read(j)
        if st == "done": return email
    return None


FINDERS = {"prospeo": ("PROSPEO_API_KEY", find_prospeo), "icypeas": ("ICYPEAS_API_KEY", find_icypeas)}


def split_list(s):
    return [x.strip().lower() for x in (s or "").split(";") if x.strip()]


def site_candidates(row, first, last):
    named = split_list(row.get("named_emails")); general = split_list(row.get("general_emails"))
    listing = (row.get("email") or "").strip().lower()
    if listing and listing not in named + general:
        (general if email_type(listing, row.get("business_name", "")) == "general" else named).append(listing)
    fl = [x.lower() for x in (first, last) if x and x != "not found"]
    owner_named = [e for e in named if fl and any(x in e.split("@")[0] for x in fl)]
    rest_named = [e for e in named if e not in owner_named]
    return owner_named, rest_named, general


def run_row(row, order):
    out = dict(row); trace = []
    out.update(email="", email_type="", email_source="", email_status="none", catch_all="", email_trace="", email_checked_at=now_iso())
    first = (row.get("owner_first") or "").split()[0] if row.get("owner_first") not in (None, "", "not found") else ""
    last = row.get("owner_last") or ""
    domain = domain_of(row.get("site_final_url") or row.get("website"))
    fallback = None

    def accept(email, source, status, ca):
        out.update(email=email, email_type=email_type(email, row.get("business_name", "")), email_source=source, email_status=status,
                   catch_all="" if ca == "" else bool(ca))

    for src in order:
        if src == "site":
            owner_named, rest_named, general = site_candidates(row, first, last)
            for e in owner_named + rest_named:
                st, ca = verify(e, trace)
                if st in ("valid", "mx_only"):
                    accept(e, "site", st, ca); out["email_trace"] = " | ".join(trace); return out
                if st == "risky" and not fallback: fallback = (e, "site", st, ca)
            for e in general:
                st, ca = verify(e, trace)
                if st in ("valid", "mx_only", "risky"):
                    if first and last and any(env(FINDERS[s][0]) for s in order if s in FINDERS):
                        if not fallback or fallback[2] == "risky" and st != "risky": fallback = (e, "site", st, ca)
                        trace.append(f"{e}: general inbox held as fallback, trying finders for the owner")
                        break
                    accept(e, "site", st, ca); out["email_trace"] = " | ".join(trace); return out
        elif src in FINDERS:
            key_name, fn = FINDERS[src]
            if not env(key_name): continue
            if not (first and last and domain): trace.append(f"{src}: skipped (needs owner name + domain)"); continue
            try:
                e = fn(row, first, last, domain)
            except Exception as ex:
                trace.append(f"{src}: error {str(ex)[:60]}"); continue
            if not e: trace.append(f"{src}: nothing found"); continue
            st, ca = verify(e.lower(), trace)
            if st in ("valid", "mx_only"):
                accept(e.lower(), src, st, ca); out["email_trace"] = " | ".join(trace); return out
            if st == "risky" and not fallback: fallback = (e.lower(), src, st, ca)
    if fallback: accept(*fallback)
    out["email_trace"] = " | ".join(trace)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--out", required=True)
    ap.add_argument("--order", default="site,prospeo,icypeas"); ap.add_argument("--log", help="per-source summary CSV")
    a = ap.parse_args()
    order = [x.strip() for x in a.order.split(",") if x.strip()]
    active = [s for s in order if s == "site" or env(FINDERS.get(s, ("",))[0] or "")]
    log(f"waterfall: {' -> '.join(active)}; verifier: MX" + (" + MillionVerifier" if env("MILLIONVERIFIER_API_KEY") else "")
        + (" + BounceBan (catch-all)" if env("BOUNCEBAN_API_KEY") else ""))
    rows = read_csv(a.csv)
    res = [run_row(r, order) for r in rows]
    write_csv(res, a.out)
    by = collections.Counter((r["email_source"] or "none", r["email_status"]) for r in res)
    summ = [{"source": s, "status": st, "count": n} for (s, st), n in sorted(by.items())]
    if a.log: write_csv(summ, a.log, ["source", "status", "count"])
    got = [r for r in res if r["email"]]
    print(f"{len(res)} rows: email for {len(got)} ({sum(1 for r in got if r['email_type'] == 'named')} named, "
          f"{sum(1 for r in got if r['email_type'] == 'general')} general). By source/status: "
          + ", ".join(f"{s}/{st}={n}" for (s, st), n in sorted(by.items())) + f" -> {a.out}")


if __name__ == "__main__":
    main()
