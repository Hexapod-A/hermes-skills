#!/usr/bin/env python3
"""Call sheet (highest intent score first) + the final XLSX, and the connect-hour report.

John (or his caller) dials; the agent never calls anyone.
  export:  call_sheet.py export facts.csv --out ~/leads/austin-dentists [--drafts drafts.csv] [--waterfall-log log.csv]
           -> <out>_call_sheet.csv and <out>.xlsx (sheets: Call sheet, Leads, Email drafts, Waterfall log, About)
  hours:   call_sheet.py hours call_log.csv
           -> connects by hour of day (log every dial for 2 weeks, then dial in the hours that answer most)

Call script per row (from the article's method): open with WHY you're calling using a fact from their listing,
ask if that problem is costing them work this month, then offer a specific meeting time.
The call log columns (dialed_at, connected y/n, outcome, notes) are left blank for John to fill.
"""
import argparse, collections, datetime as dt, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_csv, to_int, write_csv, write_xlsx
from draft_emails import CUSTOMER, greeting, pick_offer, short_name

PROBLEM = {"missed_call": "when a {customer} calls and nobody picks up, most just call the next office",
           "speed_to_lead": "web booking requests that wait even an hour usually go cold",
           "ai_receptionist": "calls going to voicemail when the front desk is busy"}
OFFER_SHORT = {"missed_call": "missed-call text-back", "speed_to_lead": "60-second replies to web leads", "ai_receptionist": "an AI receptionist"}
CALL_COLS = ["intent_score", "business_name", "phone", "ask_for", "opener", "question", "close", "local_fact", "fact_evidence", "score_reasons",
             "website", "email", "email_type", "city", "postcode", "dialed_at", "connected (y/n)", "connect_hour", "outcome", "notes"]
LEAD_COLS = ["intent_score", "business_name", "category", "phone", "website", "email", "email_type", "email_source", "email_status", "catch_all",
             "owner_first", "owner_last", "owner_title", "owner_page", "owner_method", "street", "city", "state", "postcode", "rating", "review_count",
             "local_fact", "fact_kind", "fact_evidence", "nearby_competitor", "has_chat_widget", "chat_tool", "has_online_booking", "booking_tool",
             "hiring_signal", "hiring_evidence", "automation_gaps", "score_reasons", "website_source", "maps_url", "source", "zip_queried", "found_at"]


def opener(r):
    hi, name = greeting(dict(r, email=r.get("email") or "x@x"))
    ask = name or "the owner / office manager"
    biz = short_name(r.get("business_name"))
    fact = r.get("local_fact") or ""
    if r.get("fact_kind") == "density": fact = "there are " + fact
    why = f"I was looking at the map around {biz} and noticed {fact}" if fact else f"I help {r.get('category') or 'local'} businesses near {r.get('city') or 'you'}"
    offer = pick_offer(r)
    prob = PROBLEM[offer].format(customer=CUSTOMER.get((r.get("category") or "").lower(), "customer"))
    return {"ask_for": ask,
            "opener": f"Hi, is this {name or 'the owner'}? This is John with 3xAgentic. {why}, and {prob}.",
            "question": "Is that costing you any new business this month?",
            "close": f"If it is, I can show you {OFFER_SHORT[offer]} in 15 minutes. Does Tuesday at 10 or Thursday at 2 your time work?"}


def export(a):
    rows = read_csv(a.csv); rows.sort(key=lambda r: -(to_int(r.get("intent_score")) or 0))
    for r in rows:   # listing phone first, else the first phone on their own site
        if not r.get("phone") and r.get("site_phones"): r["phone"] = r["site_phones"].split(";")[0].strip()
    calls = [dict(r, **opener(r)) for r in rows if r.get("phone")]
    write_csv(calls, a.out + "_call_sheet.csv", CALL_COLS)
    sheets = [("Call sheet", calls, CALL_COLS), ("Leads", rows, [c for c in LEAD_COLS if rows and c in rows[0]])]
    if a.drafts and os.path.exists(a.drafts):
        d = read_csv(a.drafts); sheets.append(("Email drafts", d, ["business_name", "to", "email_type", "send_note", "subject", "body", "offer", "local_fact", "fact_evidence"]))
    if a.waterfall_log and os.path.exists(a.waterfall_log): sheets.append(("Waterfall log", read_csv(a.waterfall_log), None))
    about = [f"Built {dt.date.today().isoformat()} with the maps-lead-gen skill. One niche, one area, one offer.",
             "Every field was observed in a listing or on the business's own site; evidence columns say where. Empty beats guessed.",
             "owner_first = 'not found' means the site did not show a name next to an owner/founder/doctor title. Never fill it by guessing.",
             "email_status: valid = mailbox verified; mx_only = domain takes mail, mailbox not verified; risky = catch-all/unknown. Send valid from your main inbox.",
             "email_type: general = shared inbox (info@, office@). Fine for local service businesses; send those from a separate inbox.",
             "Call sheet: dial top to bottom, fill dialed_at + connected + connect_hour. After 2 weeks run `call_sheet.py hours` to see which hours answer.",
             "DRAFTS ONLY: nothing here was sent or dialed by the agent. CAN-SPAM: real postal address + opt-out in every email; honour opt-outs, add them to the suppression list."]
    write_xlsx(sheets, a.out + ".xlsx", about)
    print(f"{len(calls)} rows on the call sheet, {len(rows)} leads -> {a.out}_call_sheet.csv, {a.out}.xlsx")


def hours(a):
    rows = read_csv(a.csv)
    dials, conns = collections.Counter(), collections.Counter()
    for r in rows:
        h = r.get("connect_hour") or ""
        if not h and r.get("dialed_at"):
            try: h = dt.datetime.fromisoformat(r["dialed_at"]).hour
            except Exception: h = ""
        if h == "": continue
        h = int(str(h).split(":")[0]); dials[h] += 1
        if str(r.get("connected (y/n)") or r.get("connected") or "").lower().startswith("y"): conns[h] += 1
    if not dials: sys.exit("no dial times in the log (fill dialed_at or connect_hour)")
    print("hour  dials  connects  rate")
    for h in sorted(dials):
        print(f"{h:02d}:00 {dials[h]:6d} {conns[h]:9d}  {100 * conns[h] / dials[h]:4.0f}%")
    best = sorted(dials, key=lambda h: -conns[h] / dials[h])[:3]
    print("best hours (their local time): " + ", ".join(f"{h:02d}:00" for h in best))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("csv"); e.add_argument("--out", required=True); e.add_argument("--drafts"); e.add_argument("--waterfall-log")
    h = sub.add_parser("hours"); h.add_argument("csv")
    a = ap.parse_args()
    export(a) if a.cmd == "export" else hours(a)


if __name__ == "__main__":
    main()
