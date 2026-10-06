#!/usr/bin/env python3
"""Append leads you have contacted to your suppression list so they never get pulled into a new campaign.
John runs this after he sends (the agent never sends).

Usage: suppress_add.py sent_leads.csv --list ~/leads/suppression.csv [--note "austin dentists wk1"]
"""
import argparse, datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import domain_of, read_csv, write_csv

COLS = ["email", "domain", "phone", "business_name", "city", "added_at", "note"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--list", required=True); ap.add_argument("--note", default="")
    a = ap.parse_args()
    old = read_csv(a.list) if os.path.exists(a.list) else []
    seen = {(r.get("email", ""), r.get("domain", ""), r.get("phone", ""), r.get("business_name", "")) for r in old}
    now = dt.datetime.now(dt.timezone.utc).date().isoformat(); added = 0
    for r in read_csv(a.csv):
        em = (r.get("email") or r.get("to") or "").strip().lower()   # works on leads CSVs and on drafts.csv
        row = {"email": em, "domain": domain_of(r.get("site_final_url") or r.get("website") or em),
               "phone": r.get("phone", ""), "business_name": r.get("business_name", ""), "city": r.get("city", ""), "added_at": now, "note": a.note}
        k = (row["email"], row["domain"], row["phone"], row["business_name"])
        if k in seen: continue
        seen.add(k); old.append(row); added += 1
    write_csv(old, a.list, COLS)
    print(f"added {added}, suppression list now {len(old)} rows -> {a.list}")


if __name__ == "__main__":
    main()
