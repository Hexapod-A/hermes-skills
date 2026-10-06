#!/usr/bin/env python3
"""3-sentence cold email DRAFTS for 3xAgentic: one local fact, one offer, one question (+ a free useful offer).
DRAFTS ONLY. This script never sends anything; John reviews and sends from his own inbox.

  Sentence 1  the lead's local_fact (from local_facts.py; skipped lead if it has none - no fact, no email)
  Sentence 2  one 3xAgentic offer, picked from what was observed:
                slow-response complaints or a front-desk job post -> AI receptionist
                online booking / web form but no chat             -> speed-to-lead (reply to every web lead in 60s)
                otherwise                                         -> missed-call text-back
  Sentence 3  a question with a free, useful offer (competitor ranking comparison or review audit)

Greeting: the owner's name only when it was found on their site AND the email is the owner's or a general inbox.
A named mailbox that isn't the owner's gets "Hi there". Never a guessed name.
Every draft ends with a CAN-SPAM footer: your physical postal address + a plain opt-out line. Fill SENDER_ADDRESS.

Usage: draft_emails.py facts.csv --out drafts [--sender "John" --company 3xAgentic --address "..."] [--top 50]
Writes drafts.csv (one row per lead: to, subject, body, offer, fact_kind) and drafts.md (easy to read/review).
"""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import read_csv, to_int, write_csv

PLURAL = {"dentist": "dental offices", "orthodontist": "orthodontists", "med-spa": "med spas", "chiropractor": "chiropractors",
          "hvac": "HVAC companies", "plumber": "plumbers", "roofer": "roofers", "electrician": "electricians", "law-firm": "law firms",
          "real-estate": "agents", "veterinary": "vet clinics", "salon": "salons", "gym": "gyms", "landscaper": "landscapers"}
CUSTOMER = {"dentist": "patient", "orthodontist": "patient", "med-spa": "client", "chiropractor": "patient", "veterinary": "pet owner",
            "law-firm": "client", "real-estate": "buyer", "salon": "client", "gym": "member"}
OFFERS = {
    "ai_receptionist": "We set up an AI receptionist for {plural} that answers every call 24/7, books the appointment and handles the usual questions, so nothing goes to voicemail.",
    "speed_to_lead": "We set up instant replies for {plural}, so every web form or booking request gets a personal text back within 60 seconds while the {customer} is still deciding.",
    "missed_call": "We set up missed-call text-back for {plural}, so every call you can't pick up gets a friendly text within seconds and the {customer} books with you instead of calling the next office.",
}
CREDENTIALS = re.compile(r"\b(dr\.?|doctor|dds|dmd|md|do|dc|dvm|od)\b", re.I)


def pick_offer(r):
    reasons = (r.get("score_reasons") or "").lower()
    if "slow-response" in reasons or re.search(r"front desk|receptionist|scheduler|coordinator", r.get("hiring_evidence") or "", re.I):
        return "ai_receptionist"
    if str(r.get("has_online_booking")) == "True" and str(r.get("has_chat_widget")) != "True":
        return "speed_to_lead"
    return "missed_call"


def greeting(r):
    first = r.get("owner_first") or ""; last = r.get("owner_last") or ""
    if first in ("", "not found") or not r.get("email"): return "Hi there,", ""
    owner_match = any(x and x.lower() in r["email"].split("@")[0].lower() for x in (first.split()[0], last))
    if r.get("email_type") == "named" and not owner_match: return "Hi there,", ""
    if last and (CREDENTIALS.search(r.get("owner_title") or "") or re.search(r"Dr\.?\s+" + re.escape(first.split()[0]) + r"\s+(?:[A-Z]\.\s+)?" + re.escape(last), r.get("owner_quote") or "")):
        return f"Hi Dr. {last},", f"Dr. {last}"
    return f"Hi {first.split()[0]},", first.split()[0]


def short_name(name):
    """'ATX Family Dental - South Austin' -> 'ATX Family Dental' (reads like a person wrote it)."""
    n = re.split(r"\s+[-–|]\s+", name or "")[0]
    return re.sub(r",?\s+(LLC|PLLC|Inc\.?|P\.?C\.?)$", "", n).strip() or name


def fact_sentence(r):
    k, biz = r.get("fact_kind"), short_name(r.get("business_name"))
    if k == "density":
        m = re.match(r"at least (\d+) other (.+) within ([\d.]+) miles of you", r["local_fact"])
        if m: return f"I counted at least {m[1]} other {m[2]} within {m[3]} miles of {biz} on the map."
    if k == "competitor_reviews":
        return f"Noticed {r['nearby_competitor']}, about {r['competitor_distance_mi']} mi from you, is sitting on {r['competitor_reviews']} Google reviews."
    if k == "own_rating":
        m = re.match(r"your ([\d.]+) stars from (\d+)", r["local_fact"])
        if m: return f"{biz} has a {m[1]}-star rating from {m[2]} Google reviews, which is a lot of happy {CUSTOMER.get((r.get('category') or '').lower(), 'customer')}s."
    if k == "nearest":
        return f"Noticed {r['local_fact'].replace(' from you', ' from ' + biz, 1)}."
    return ""


def question(r):
    k, biz = r.get("fact_kind"), short_name(r.get("business_name"))
    if k in ("density", "competitor_reviews", "nearest"):
        who = r.get("nearby_competitor") if k == "competitor_reviews" else "the offices around you"
        return f"Want me to send over a free 1-page comparison of how {biz} ranks on Google Maps against {who}?"
    return f"Want a free audit of your Google reviews that shows which ones mention calls, wait times or follow-up?"


def subject(r):
    k = r.get("fact_kind")
    if k == "density":
        m = re.match(r"at least (\d+) other (.+) within ([\d.]+) miles", r["local_fact"])
        if m: return f"{m[1]}+ {m[2]} within {m[3]} miles"
    if k == "competitor_reviews": return f"{short_name(r['nearby_competitor'])} vs {short_name(r['business_name'])}"
    if k == "own_rating": return "your google reviews"
    return f"quick question about {short_name(r['business_name'])}"


def draft(r, sender, company, address):
    fs = fact_sentence(r)
    if not fs or not r.get("email"): return None
    cat = (r.get("category") or "").lower()
    offer = pick_offer(r)
    hi, name = greeting(r)
    o = OFFERS[offer].format(plural=PLURAL.get(cat, "businesses like yours"), customer=CUSTOMER.get(cat, "customer"))
    body = (f"{hi}\n\n{fs} {o} {question(r)}\n\n{sender}\n{company}\n\n--\n{address}\n"
            f"Not the right person, or not interested? Reply \"no\" and I won't email again.")
    return {"business_name": r.get("business_name"), "to": r["email"], "email_type": r.get("email_type"), "email_status": r.get("email_status"),
            "greeting_name": name or "(none)", "subject": subject(r), "body": body, "offer": offer, "fact_kind": r.get("fact_kind"),
            "local_fact": r.get("local_fact"), "fact_evidence": r.get("fact_evidence"), "intent_score": r.get("intent_score"),
            "send_note": "send from main inbox" if r.get("email_status") == "valid" else
                         "verify first (MX-only) or send from a separate inbox" if r.get("email_status") == "mx_only" else
                         "risky/catch-all: separate inbox or skip"}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--out", required=True, help="path without extension")
    ap.add_argument("--sender", default=os.environ.get("SENDER_NAME", "John")); ap.add_argument("--company", default=os.environ.get("SENDER_COMPANY", "3xAgentic"))
    ap.add_argument("--address", default=os.environ.get("SENDER_ADDRESS", "[YOUR PHYSICAL MAILING ADDRESS - required by CAN-SPAM]"))
    ap.add_argument("--top", type=int, default=0)
    a = ap.parse_args()
    rows = read_csv(a.csv)
    rows.sort(key=lambda r: -(to_int(r.get("intent_score")) or 0))
    drafts = [d for d in (draft(r, a.sender, a.company, a.address) for r in rows) if d]
    if a.top: drafts = drafts[: a.top]
    write_csv(drafts, a.out + ".csv")
    with open(a.out + ".md", "w", encoding="utf-8") as f:
        f.write(f"# Email drafts ({len(drafts)}) - DRAFTS ONLY, John reviews and sends\n\n")
        for d in drafts:
            f.write(f"## {d['business_name']}  (score {d['intent_score']}, {d['offer']})\nTo: {d['to']} ({d['email_type']}, {d['email_status']}; {d['send_note']})\n"
                    f"Subject: {d['subject']}\nFact source: {d['fact_evidence']}\n\n{d['body']}\n\n---\n\n")
    skipped = len(rows) - len(drafts)
    print(f"{len(drafts)} drafts ({skipped} leads skipped: no email or no true local fact) -> {a.out}.csv, {a.out}.md")


if __name__ == "__main__":
    main()
