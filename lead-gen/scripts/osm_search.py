#!/usr/bin/env python3
"""Find local businesses in a US city from OpenStreetMap (free, public, no key).

Usage:
  osm_search.py --city "Boise, Idaho" --category dentist [--limit 50] [--out leads.csv]
  osm_search.py --city "Austin, Texas" --tag craft=hvac --tag craft=plumber
Categories: see CATEGORIES below. Results are a starting list; run verify_leads.py next.
Be polite: Nominatim allows ~1 request/second; Overpass is shared infrastructure.
"""
import argparse, csv, datetime as dt, json, os, sys, time
import requests

UA = {"User-Agent": os.environ.get("OSM_USER_AGENT", "hermes-lead-gen/1.0 (contact: set OSM_USER_AGENT)")}
OVERPASS = os.environ.get("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
CATEGORIES = {
    "dentist": ["amenity=dentist", "healthcare=dentist"],
    "med-spa": ["shop=beauty", "healthcare=cosmetic", "amenity=clinic][healthcare:speciality=cosmetic"],
    "chiropractor": ["healthcare=chiropractor"],
    "physio": ["healthcare=physiotherapist"],
    "clinic": ["amenity=clinic", "amenity=doctors"],
    "veterinary": ["amenity=veterinary"],
    "hvac": ["craft=hvac"],
    "plumber": ["craft=plumber"],
    "electrician": ["craft=electrician"],
    "roofer": ["craft=roofer"],
    "home-services": ["craft=hvac", "craft=plumber", "craft=electrician", "craft=roofer", "craft=carpenter", "craft=painter"],
    "real-estate": ["office=estate_agent"],
    "law-firm": ["office=lawyer"],
    "accountant": ["office=accountant", "office=tax_advisor"],
    "insurance": ["office=insurance"],
    "auto-repair": ["shop=car_repair"],
    "salon": ["shop=hairdresser", "shop=beauty"],
    "gym": ["leisure=fitness_centre"],
    "restaurant": ["amenity=restaurant"],
}


def area_id(city):
    r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": city, "format": "json", "limit": 5, "countrycodes": "us"}, headers=UA, timeout=30)
    r.raise_for_status()
    for x in r.json():
        if x.get("osm_type") == "relation":
            return 3600000000 + int(x["osm_id"]), x.get("display_name")
    raise SystemExit(f"Could not find a US city boundary for {city!r}. Try 'City, State'.")


def overpass(aid, tags):
    parts = []
    for t in tags:
        filt = "".join(f'["{k}"="{v}"]' for k, v in (p.split("=", 1) for p in t.split("][")))
        parts.append(f"nwr{filt}(area.a);")
    q = f"[out:json][timeout:90];area(id:{aid})->.a;({''.join(parts)});out center tags;"
    for attempt in range(3):
        r = requests.post(OVERPASS, data={"data": q}, headers=UA, timeout=120)
        if r.status_code in (429, 504): time.sleep(10 * (attempt + 1)); continue
        r.raise_for_status(); return r.json().get("elements", [])
    raise SystemExit("Overpass is busy (429/504). Wait a minute or set OVERPASS_URL to another instance.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True); ap.add_argument("--category", choices=sorted(CATEGORIES))
    ap.add_argument("--tag", action="append", default=[], help="raw OSM tag like craft=hvac (repeatable)")
    ap.add_argument("--limit", type=int, default=100); ap.add_argument("--require-website", action="store_true")
    ap.add_argument("--out", default="-")
    a = ap.parse_args()
    tags = (CATEGORIES.get(a.category, []) if a.category else []) + a.tag
    if not tags: ap.error("give --category or --tag")
    aid, name = area_id(a.city); time.sleep(1)
    els = overpass(aid, tags)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    rows, seen = [], set()
    for e in els:
        t = e.get("tags", {})
        nm = t.get("name")
        if not nm: continue
        site = t.get("website") or t.get("contact:website") or t.get("url") or ""
        if a.require_website and not site: continue
        key = (nm.lower(), t.get("addr:street", ""))
        if key in seen: continue
        seen.add(key)
        rows.append({
            "business_name": nm, "category": a.category or ";".join(a.tag),
            "website": site, "phone": t.get("phone") or t.get("contact:phone") or "",
            "email": t.get("email") or t.get("contact:email") or "",
            "street": " ".join(x for x in [t.get("addr:housenumber", ""), t.get("addr:street", "")] if x),
            "city": t.get("addr:city", ""), "state": t.get("addr:state", ""), "postcode": t.get("addr:postcode", ""), "country": "US",
            "osm_url": f"https://www.openstreetmap.org/{e['type']}/{e['id']}", "source": f"OpenStreetMap via Overpass ({name})", "found_at": now,
        })
        if len(rows) >= a.limit: break
    fields = list(rows[0].keys()) if rows else ["business_name"]
    f = sys.stdout if a.out == "-" else open(a.out, "w", newline="")
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    if f is not sys.stdout: f.close(); print(f"{len(rows)} businesses -> {a.out} (area: {name})", file=sys.stderr)


if __name__ == "__main__":
    main()
