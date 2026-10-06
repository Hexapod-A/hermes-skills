#!/usr/bin/env python3
"""One TRUE local fact per lead, built only from data you pulled (never invented, never "saw your Google listing").

Fact types, best first (the first one the data supports wins):
  competitor_reviews  a nearby same-niche business with MORE Google reviews (needs review counts):
                      "Smile Dental, about 0.8 mi from you, has 412 Google reviews"
  own_rating          their own rating, ONLY if 4.0 stars or higher: "your 4.8 stars from 236 Google reviews"
  density             how many same-niche businesses sit within --radius-mi of them (counted from your pull)
                      "at least 17 other dental offices within 2 miles of you"  (a lower bound: only what your pull found)
  nearest             the nearest same-niche business by name and street

Usage: local_facts.py scored.csv --market raw.csv --out facts.csv [--radius-mi 2] [--niche-word "dental office"]
--market is the FULL pull for the area (every business found, not just the ones with emails).
Adds: local_fact, fact_kind, fact_evidence, nearby_competitor, competitor_distance_mi, competitor_reviews
"""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import norm_name, read_csv, to_float, to_int, write_csv

NICHE_WORDS = {"dentist": "dental offices", "orthodontist": "orthodontists", "med-spa": "med spas", "chiropractor": "chiropractors",
               "hvac": "HVAC companies", "plumber": "plumbers", "roofer": "roofers", "electrician": "electricians", "law-firm": "law firms",
               "real-estate": "real estate offices", "veterinary": "vet clinics", "salon": "salons", "gym": "gyms", "landscaper": "landscapers"}


def miles(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(h))


def facts_for(row, market, radius, niche_word):
    out = dict(row)
    out.update(local_fact="", fact_kind="", fact_evidence="", nearby_competitor="", competitor_distance_mi="", competitor_reviews="")
    me = (to_float(row.get("lat")), to_float(row.get("lon")))
    my_name = norm_name(row.get("business_name")); my_rev = to_int(row.get("review_count")); my_rating = to_float(row.get("rating"))
    near = []
    if None not in me:
        for m in market:
            loc = (to_float(m.get("lat")), to_float(m.get("lon")))
            if None in loc or norm_name(m.get("business_name")) == my_name: continue
            d = miles(me, loc)
            if d <= radius: near.append((d, m))
        near.sort(key=lambda x: x[0])
    # 1. competitor with more reviews
    if my_rev is not None:
        bigger = [(d, m) for d, m in near if (to_int(m.get("review_count")) or 0) > my_rev]
        if bigger:
            d, m = max(bigger, key=lambda x: to_int(x[1].get("review_count")))
            out.update(local_fact=f'{m["business_name"]}, about {d:.1f} mi from you, has {to_int(m["review_count"])} Google reviews',
                       fact_kind="competitor_reviews", nearby_competitor=m["business_name"], competitor_distance_mi=round(d, 1),
                       competitor_reviews=to_int(m["review_count"]),
                       fact_evidence=f'{m.get("source")} listing {m.get("maps_url") or m.get("source_id")}; yours: {my_rev} reviews')
            return out
    # 2. own rating, only 4.0+
    if my_rating is not None and my_rating >= 4.0 and my_rev:
        out.update(local_fact=f"your {my_rating:.1f} stars from {my_rev} Google reviews", fact_kind="own_rating",
                   fact_evidence=f'{row.get("source")} listing {row.get("maps_url") or row.get("source_id")}')
        return out
    # 3. density
    if len(near) >= 3:
        d0, m0 = near[0]
        out.update(local_fact=f"at least {len(near)} other {niche_word} within {radius:g} miles of you", fact_kind="density",
                   nearby_competitor=m0["business_name"], competitor_distance_mi=round(d0, 1),
                   fact_evidence=f"counted in our {row.get('source') or 'map'} pull of this area; nearest: {m0['business_name']} ({d0:.1f} mi)")
        return out
    # 4. nearest
    if near:
        d0, m0 = near[0]
        street = m0.get("street") or ""
        out.update(local_fact=f'{m0["business_name"]} is about {d0:.1f} mi from you' + (f" on {street}" if street else ""), fact_kind="nearest",
                   nearby_competitor=m0["business_name"], competitor_distance_mi=round(d0, 1),
                   fact_evidence=f'{m0.get("source")} listing {m0.get("maps_url") or m0.get("source_id")}')
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--market", action="append", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--radius-mi", type=float, default=2.0); ap.add_argument("--niche-word")
    a = ap.parse_args()
    rows = read_csv(a.csv); market = [m for p in a.market for m in read_csv(p)]
    seen, mk = set(), []
    for m in market:
        k = m.get("source_id") or (m.get("business_name"), m.get("street"))
        if k not in seen: seen.add(k); mk.append(m)
    niche = (rows[0].get("category") if rows else "") or ""
    word = a.niche_word or NICHE_WORDS.get(niche.lower(), f"{niche} businesses")
    res = [facts_for(r, mk, a.radius_mi, word) for r in rows]
    write_csv(res, a.out)
    from collections import Counter
    c = Counter(r["fact_kind"] or "none" for r in res)
    print(f"{len(res)} leads, market of {len(mk)} businesses: " + ", ".join(f"{k}={v}" for k, v in c.most_common()) + f" -> {a.out}")


if __name__ == "__main__":
    main()
