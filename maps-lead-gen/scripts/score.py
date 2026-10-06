#!/usr/bin/env python3
"""Intent scoring + review-count filter + dedupe + suppression. Highest score first.

Signals (each one listed in score_reasons with its evidence; nothing is scored that wasn't observed):
  fresh reviews in the last 90 days (needs review dates: google_places / serper --with-reviews)
  slow-response / missed-call complaints in review text ("never called back", "couldn't get through" ...)
  job postings on their own site (careers page, "now hiring"; front desk / receptionist roles count more)
  automation gaps seen on the site (no chat / AI receptionist, no online booking)
  reachability (phone, valid email, named email, owner name found)

Dedupe key: normalised business name + city + email domain (website domain when there is no email).
Suppression: --suppress suppression.csv (columns any of: email, domain, phone, business_name, city). Matching rows
are removed. Add contacted leads to it with suppress_add.py after every send.

Usage: score.py emails.csv --out scored.csv [--min-reviews 20 --max-reviews 400] [--suppress suppression.csv]
"""
import argparse, datetime as dt, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import domain_of, norm_name, norm_phone, read_csv, to_int, write_csv

SLOW_RE = re.compile(r"(never (?:called|call|got a call|heard) back|no one (?:answered|picks? up|called)|nobody (?:answered|picks? up|called)|"
                     r"(?:couldn'?t|could not|can'?t|cannot) get (?:through|a hold|ahold|anyone)|went (?:straight )?to voicemail|left (?:a |several |multiple )?"
                     r"(?:voicemails?|messages?)|(?:slow|late) to (?:respond|reply|call back|get back)|took (?:days|weeks|forever) to (?:respond|reply|call|get back)|"
                     r"didn'?t (?:return|answer) (?:my )?(?:calls?|emails?|messages?)|unresponsive|hard to (?:reach|get a hold)|on hold for|phone (?:just )?rang)", re.I)
FRONT_DESK_RE = re.compile(r"front desk|receptionist|scheduler|scheduling coordinator|patient coordinator|office manager|csr|customer service", re.I)


def reviews(row):
    try: return json.loads(row.get("reviews_json") or "[]")
    except Exception: return []


def score_row(row, today):
    pts, why = 0, []
    revs = reviews(row)
    fresh = [r for r in revs if r.get("date") and (today - dt.date.fromisoformat(r["date"][:10])).days <= 90]
    if fresh:
        add = 15 if len(fresh) >= 3 else 8
        pts += add; why.append(f"+{add} {len(fresh)} reviews in last 90 days (of {len(revs)} read)")
    slow = [r for r in revs if SLOW_RE.search(r.get("text") or "")]
    if slow:
        q = SLOW_RE.search(slow[0]["text"]).group(0)
        pts += 20; why.append(f'+20 slow-response complaint in reviews: "{q}" ({slow[0].get("date", "")})')
    if str(row.get("hiring_signal")) == "True":
        ev = row.get("hiring_evidence", "")
        add = 15 if FRONT_DESK_RE.search(ev) else 8
        pts += add; why.append(f"+{add} hiring: {ev[:90]}")
    if str(row.get("site_status")) == "200":
        if str(row.get("has_chat_widget")) != "True": pts += 10; why.append("+10 no chat / AI receptionist on site")
        if str(row.get("has_online_booking")) != "True": pts += 10; why.append("+10 no online booking on site")
    if row.get("phone") or row.get("site_phones"): pts += 5; why.append("+5 phone listed")
    st = row.get("email_status")
    if st in ("valid", "mx_only"):
        pts += 5; why.append(f"+5 email ({st})")
        if row.get("email_type") == "named": pts += 5; why.append("+5 named email")
    if row.get("owner_first") not in (None, "", "not found"): pts += 5; why.append("+5 owner name found on site")
    return min(100, pts), why


def dedupe_key(row):
    d = domain_of(row.get("email")) or domain_of(row.get("site_final_url") or row.get("website"))
    return (norm_name(row.get("business_name")), (row.get("city") or "").strip().lower(), d)


def load_suppression(paths):
    s = {"email": set(), "domain": set(), "phone": set(), "namecity": set()}
    for p in paths:
        for r in read_csv(p):
            if r.get("email"): s["email"].add(r["email"].strip().lower())
            if r.get("domain"): s["domain"].add(domain_of(r["domain"]))
            if r.get("phone"): s["phone"].add(norm_phone(r["phone"]))
            if r.get("business_name"): s["namecity"].add((norm_name(r["business_name"]), (r.get("city") or "").strip().lower()))
    return s


def suppressed(row, s):
    if not s: return False
    e = (row.get("email") or "").lower()
    if e and e in s["email"]: return "email"
    d = domain_of(row.get("site_final_url") or row.get("website")) or domain_of(e)
    if d and d in s["domain"]: return "domain"
    p = norm_phone(row.get("phone") or "")
    if p and p in s["phone"]: return "phone"
    nc = (norm_name(row.get("business_name")), (row.get("city") or "").strip().lower())
    if nc in s["namecity"] or (nc[0], "") in s["namecity"]: return "name+city"
    return False


def filled(row):
    return sum(1 for v in row.values() if v not in (None, "", "not found", "none"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--out", required=True)
    ap.add_argument("--min-reviews", type=int); ap.add_argument("--max-reviews", type=int)
    ap.add_argument("--suppress", action="append", default=[]); ap.add_argument("--min-score", type=int, default=0)
    a = ap.parse_args()
    rows = read_csv(a.csv); n0 = len(rows); today = dt.date.today()
    # review-count filter: only applies to rows that HAVE review data
    def keep(r):
        n = to_int(r.get("review_count"))
        if n is None: return True
        return (a.min_reviews is None or n >= a.min_reviews) and (a.max_reviews is None or n <= a.max_reviews)
    rows = [r for r in rows if keep(r)]; n_rev = n0 - len(rows)
    # mis-tagged listings: their own site never mentions the niche
    n_off = sum(1 for r in rows if str(r.get("niche_seen")) == "False")
    rows = [r for r in rows if str(r.get("niche_seen")) != "False"]; n_rev += 0
    best = {}
    for r in rows:
        k = dedupe_key(r)
        if k not in best or filled(r) > filled(best[k]): best[k] = r
    rows = list(best.values()); n_dup = n0 - n_rev - n_off - len(rows)
    sup = load_suppression(a.suppress) if a.suppress else None
    kept, n_sup = [], 0
    for r in rows:
        why = suppressed(r, sup)
        if why: n_sup += 1; continue
        r["intent_score"], reasons = score_row(r, today); r["score_reasons"] = "; ".join(reasons)
        if r["intent_score"] >= a.min_score: kept.append(r)
    kept.sort(key=lambda r: -r["intent_score"])
    write_csv(kept, a.out)
    print(f"{n0} in: {n_rev} dropped by review filter, {n_off} off-niche (site never mentions the niche), {n_dup} duplicates, {n_sup} suppressed (already contacted) -> {len(kept)} scored leads -> {a.out}")


if __name__ == "__main__":
    main()
