#!/usr/bin/env python3
"""Zip-code-by-zip-code business pull for ONE niche in ONE area.

Free default: OpenStreetMap (Overpass), no key. Paid sources run only when their key env var is set:
  --source mapsdata       MAPSDATA_API_KEY   (Google Maps listings + emails from each site; city/state jobs, not zips)
  --source google_places  GOOGLE_PLACES_API_KEY (Places API "searchText", returns rating, review count, 5 reviews)
  --source serper         SERPER_API_KEY     (google.serper.dev/places; --with-reviews adds /reviews per listing)
  --source rapidapi       RAPIDAPI_KEY       (+ RAPIDAPI_MAPS_HOST, default local-business-data.p.rapidapi.com)

Examples:
  pull.py --niche dentist --city "Austin" --state TX --zips 78704,78745 --out raw.csv
  pull.py --niche dentist --city "Austin" --state TX --all-zips --max-zips 40 --out raw.csv
  pull.py --source google_places --niche "dentist" --zips 78704 --out raw.csv
  pull.py --source mapsdata --niche Dentist --city Austin --state TX --limit 2000 --out raw.csv   (submits a job, polls, downloads)

Output columns: business_name, category, phone, website, email, street, city, state, postcode, country, lat, lon,
rating, review_count, reviews_json, maps_url, source, source_id, zip_queried, found_at.
rating/review_count/reviews_json are only filled when the source gives them (OSM never does).
"""
import argparse, hashlib, json, os, re, sys, time
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import UA_OSM, US_STATES, env, log, norm_phone, now_iso, write_csv, to_int, to_float

# Public Overpass instances, tried in turn when one is busy. OVERPASS_URL (your own or a preferred mirror) goes first.
OVERPASS_MIRRORS = [u for u in [os.environ.get("OVERPASS_URL"), "https://overpass-api.de/api/interpreter",
                                "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"] if u]


class SourceBusy(Exception):
    pass
FIELDS = ["business_name", "category", "phone", "website", "email", "street", "city", "state", "postcode", "country", "lat", "lon",
          "rating", "review_count", "reviews_json", "maps_url", "source", "source_id", "zip_queried", "found_at"]

# OSM tags per niche (free path). Anything else: --osm-tag key=value
OSM_TAGS = {
    "dentist": ["amenity=dentist", "healthcare=dentist"], "orthodontist": ["healthcare:speciality=orthodontics"],
    "med-spa": ["shop=beauty", "healthcare=cosmetic"], "chiropractor": ["healthcare=chiropractor"],
    "physio": ["healthcare=physiotherapist"], "clinic": ["amenity=clinic", "amenity=doctors"], "veterinary": ["amenity=veterinary"],
    "hvac": ["craft=hvac"], "plumber": ["craft=plumber"], "electrician": ["craft=electrician"], "roofer": ["craft=roofer"],
    "landscaper": ["craft=gardener", "shop=garden_centre"], "home-services": ["craft=hvac", "craft=plumber", "craft=electrician", "craft=roofer"],
    "real-estate": ["office=estate_agent"], "law-firm": ["office=lawyer"], "accountant": ["office=accountant", "office=tax_advisor"],
    "insurance": ["office=insurance"], "auto-repair": ["shop=car_repair"], "salon": ["shop=hairdresser", "shop=beauty"],
    "gym": ["leisure=fitness_centre"], "restaurant": ["amenity=restaurant"],
}
ADDR_RE = re.compile(r"^(?P<street>.*?),\s*(?P<city>[^,]+),\s*(?P<state>[A-Z]{2})\s*(?P<zip>\d{5})?(?:-\d{4})?(?:,\s*(?:USA|United States))?\s*$")


def split_address(addr):
    m = ADDR_RE.match((addr or "").strip())
    if not m: return {"street": addr or "", "city": "", "state": "", "postcode": ""}
    return {"street": m["street"], "city": m["city"].strip(), "state": m["state"], "postcode": m["zip"] or ""}


def row(**kw):
    r = {k: "" for k in FIELDS}; r.update({k: v for k, v in kw.items() if v is not None}); r["found_at"] = r["found_at"] or now_iso()
    r["phone"] = norm_phone(r["phone"]); r["country"] = r["country"] or "US"
    return r


# ---------------------------------------------------------------- zip codes (free: api.zippopotam.us)
def zips_for_city(city, state):
    st = state.strip().upper()
    r = requests.get(f"https://api.zippopotam.us/us/{st.lower()}/{city.strip().lower().replace(' ', '%20')}", timeout=30)
    if r.status_code != 200: raise SystemExit(f"No zip list for {city}, {st} (zippopotam answered {r.status_code}). Pass --zips yourself.")
    return [{"zip": p["post code"], "lat": float(p["latitude"]), "lon": float(p["longitude"]), "city": p["place name"], "state": st}
            for p in r.json().get("places", [])]


def zip_info(z):
    r = requests.get(f"https://api.zippopotam.us/us/{z}", timeout=30)
    if r.status_code != 200: raise SystemExit(f"Unknown US zip {z}")
    j = r.json(); p = j["places"][0]
    return {"zip": z, "lat": float(p["latitude"]), "lon": float(p["longitude"]), "city": p["place name"], "state": p["state abbreviation"]}


# ---------------------------------------------------------------- sources
def pull_osm(niche, z, radius_m, extra_tags):
    tags = OSM_TAGS.get(niche.lower(), []) + extra_tags
    if not tags: raise SystemExit(f"No OSM tags for niche {niche!r}. Use one of {sorted(OSM_TAGS)} or add --osm-tag key=value")
    parts = "".join(f'nwr["{k}"="{v}"](around:{radius_m},{z["lat"]},{z["lon"]});' for k, v in (t.split("=", 1) for t in tags))
    q = f"[out:json][timeout:90];({parts});out center tags;"
    r = None
    for attempt in range(6):
        url = OVERPASS_MIRRORS[attempt % len(OVERPASS_MIRRORS)]
        try:
            r = requests.post(url, data={"data": q}, headers=UA_OSM, timeout=120)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"): break
            log(f"overpass {url} answered {r.status_code}")
        except requests.RequestException as e:
            log(f"overpass {url} error {str(e)[:80]}")
        r = None; time.sleep(5 * (attempt + 1))
    if r is None:
        raise SourceBusy(f"Overpass busy for zip {z['zip']}")
    out = []
    for e in r.json().get("elements", []):
        t = e.get("tags", {}); nm = t.get("name")
        if not nm: continue
        lat = e.get("lat") or (e.get("center") or {}).get("lat"); lon = e.get("lon") or (e.get("center") or {}).get("lon")
        out.append(row(business_name=nm, category=niche, phone=t.get("phone") or t.get("contact:phone") or "",
                       website=t.get("website") or t.get("contact:website") or t.get("url") or "",
                       email=t.get("email") or t.get("contact:email") or "",
                       street=" ".join(x for x in [t.get("addr:housenumber", ""), t.get("addr:street", "")] if x),
                       city=t.get("addr:city", "") or z["city"], state=t.get("addr:state", "") or z["state"], postcode=t.get("addr:postcode", ""),
                       lat=lat, lon=lon, maps_url=f"https://www.openstreetmap.org/{e['type']}/{e['id']}", source="osm",
                       source_id=f"osm:{e['type']}/{e['id']}", zip_queried=z["zip"]))
    return out


GOOGLE_FIELDS = ",".join("places." + f for f in ["id", "displayName", "formattedAddress", "nationalPhoneNumber", "websiteUri", "rating",
                                                 "userRatingCount", "primaryTypeDisplayName", "location", "googleMapsUri", "reviews",
                                                 "businessStatus"]) + ",nextPageToken"


def google_places_request(query, page_token=None, key="KEY"):
    body = {"textQuery": query, "pageSize": 20, "regionCode": "US"}
    if page_token: body["pageToken"] = page_token
    return {"url": "https://places.googleapis.com/v1/places:searchText", "json": body,
            "headers": {"X-Goog-Api-Key": key, "X-Goog-FieldMask": GOOGLE_FIELDS, "Content-Type": "application/json"}}


def parse_google_places(j, niche, zq):
    out = []
    for p in j.get("places", []):
        if p.get("businessStatus") and p["businessStatus"] != "OPERATIONAL": continue
        a = split_address(p.get("formattedAddress", ""))
        revs = [{"date": (rv.get("publishTime") or "")[:10], "rating": rv.get("rating"),
                 "text": ((rv.get("text") or {}).get("text") or "")[:400]} for rv in p.get("reviews", [])]
        loc = p.get("location") or {}
        out.append(row(business_name=(p.get("displayName") or {}).get("text", ""), category=(p.get("primaryTypeDisplayName") or {}).get("text", niche),
                       phone=p.get("nationalPhoneNumber", ""), website=p.get("websiteUri", ""), lat=loc.get("latitude"), lon=loc.get("longitude"),
                       rating=p.get("rating", ""), review_count=p.get("userRatingCount", ""), reviews_json=json.dumps(revs) if revs else "",
                       maps_url=p.get("googleMapsUri", ""), source="google_places", source_id=p.get("id", ""), zip_queried=zq, **a))
    return out, j.get("nextPageToken")


def pull_google_places(niche, z, max_pages=3):
    key = env("GOOGLE_PLACES_API_KEY")
    out, tok = [], None
    for _ in range(max_pages):
        req = google_places_request(f"{niche} in {z['zip']}", tok, key)
        r = requests.post(req["url"], json=req["json"], headers=req["headers"], timeout=30); r.raise_for_status()
        rows, tok = parse_google_places(r.json(), niche, z["zip"]); out += rows
        if not tok: break
        time.sleep(2)
    return out


def serper_places_request(niche, zipcode, page=1, key="KEY"):
    return {"url": "https://google.serper.dev/places", "json": {"q": f"{niche} {zipcode}", "gl": "us", "hl": "en", "page": page},
            "headers": {"X-API-KEY": key, "Content-Type": "application/json"}}


def parse_serper_places(j, niche, zq):
    out = []
    for p in j.get("places", []):
        a = split_address(p.get("address", ""))
        cid = str(p.get("cid") or "")
        out.append(row(business_name=p.get("title", ""), category=p.get("category") or niche, phone=p.get("phoneNumber", ""),
                       website=p.get("website", ""), lat=p.get("latitude"), lon=p.get("longitude"), rating=p.get("rating", ""),
                       review_count=p.get("ratingCount", ""), maps_url=f"https://maps.google.com/?cid={cid}" if cid else "",
                       source="serper", source_id=cid, zip_queried=zq, **a))
    return out


def parse_serper_reviews(j):
    return [{"date": (rv.get("isoDate") or "")[:10], "rating": rv.get("rating"), "text": (rv.get("snippet") or "")[:400]}
            for rv in j.get("reviews", [])]


def pull_serper(niche, z, pages=2, with_reviews=False):
    key = env("SERPER_API_KEY"); out = []
    for page in range(1, pages + 1):
        req = serper_places_request(niche, z["zip"], page, key)
        r = requests.post(req["url"], json=req["json"], headers=req["headers"], timeout=30); r.raise_for_status()
        rows = parse_serper_places(r.json(), niche, z["zip"]); out += rows
        if len(rows) < 10: break
    if with_reviews:
        for rw in out:
            if not rw["source_id"]: continue
            r = requests.post("https://google.serper.dev/reviews", json={"cid": rw["source_id"], "sortBy": "newest", "gl": "us"},
                              headers={"X-API-KEY": key, "Content-Type": "application/json"}, timeout=30)
            if r.ok: rw["reviews_json"] = json.dumps(parse_serper_reviews(r.json())[:10])
    return out


def rapidapi_request(niche, zipcode, key="KEY", host=None, limit=100):
    host = host or os.environ.get("RAPIDAPI_MAPS_HOST", "local-business-data.p.rapidapi.com")
    return {"url": f"https://{host}/search", "params": {"query": f"{niche} in {zipcode}", "limit": limit, "region": "us", "language": "en"},
            "headers": {"X-RapidAPI-Key": key, "X-RapidAPI-Host": host}}


def parse_rapidapi(j, niche, zq):
    out = []
    for p in j.get("data", []) or []:
        a = split_address(p.get("full_address") or p.get("address") or "")
        if p.get("zipcode"): a["postcode"] = a["postcode"] or str(p["zipcode"])
        out.append(row(business_name=p.get("name", ""), category=p.get("type") or niche, phone=p.get("phone_number", ""),
                       website=p.get("website") or "", lat=p.get("latitude"), lon=p.get("longitude"), rating=p.get("rating", ""),
                       review_count=p.get("review_count", ""), maps_url=p.get("place_link", ""), source="rapidapi",
                       source_id=p.get("business_id", ""), zip_queried=zq, **a))
    return out


def pull_rapidapi(niche, z):
    req = rapidapi_request(niche, z["zip"], env("RAPIDAPI_KEY"))
    r = requests.get(req["url"], params=req["params"], headers=req["headers"], timeout=60); r.raise_for_status()
    return parse_rapidapi(r.json(), niche, z["zip"])


# MapsData works on cities/states, not zips: it does its own area coverage. Docs: https://mapsdata.ai/api
MAPSDATA = "https://mapsdata.ai/api/v1"


def mapsdata_job_body(category, cities=None, states=None, limit=500, min_reviews=0, max_reviews=None, dry_run=False):
    body = {"query": category, "country": "us", "total_limit": int(limit), "min_reviews": int(min_reviews or 0), "dry_run": bool(dry_run)}
    if cities: body["cities"] = [{"city": c, "state": US_STATES.get(s.upper(), s)} for c, s in cities]
    elif states: body["states"] = [US_STATES.get(s.upper(), s) for s in states]
    if max_reviews is not None: body["max_reviews"] = int(max_reviews)
    return body


def mapsdata_map_row(rec):
    low = {k.strip().lower().replace(" ", "_"): (v or "") for k, v in rec.items()}
    g = lambda *ks: next((low[k] for k in ks if low.get(k)), "")
    a = split_address(g("address", "full_address"))
    return row(business_name=g("name", "business_name", "title"), category=g("category", "type"), phone=g("phone", "phone_number"),
               website=g("website", "site", "url"), email=g("email", "emails").split(",")[0].strip(), rating=g("rating", "stars"),
               review_count=g("reviews", "review_count", "reviews_count", "rating_count"), maps_url=g("google_maps_url", "maps_url", "place_url"),
               lat=g("latitude", "lat"), lon=g("longitude", "lng", "lon"), source="mapsdata", source_id=g("place_id", "cid", "id"),
               street=a["street"], city=g("city") or a["city"], state=g("state") or a["state"], postcode=g("zip", "postal_code", "postcode") or a["postcode"])


def pull_mapsdata(a):
    import csv, io
    key = env("MAPSDATA_API_KEY"); h = {"Authorization": f"Bearer {key}"}
    job_id = a.mapsdata_job
    if not job_id:
        v = requests.get(f"{MAPSDATA}/categories/validate", params={"name": a.niche}, headers=h, timeout=30).json()
        if not v.get("valid"): raise SystemExit(f"MapsData does not know category {a.niche!r}. Suggestions: {v.get('suggestions')}")
        cities = [(a.city, a.state)] if a.city else None
        body = mapsdata_job_body(v["canonical"], cities, [a.state] if (a.state and not a.city) else None, a.limit, a.min_reviews or 0,
                                 a.max_reviews, a.dry_run)
        r = requests.post(f"{MAPSDATA}/jobs", json=body, headers={**h, "Idempotency-Key": "hermes-" + hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()[:24]}, timeout=60)
        if r.status_code >= 400: raise SystemExit(f"MapsData refused the job: {r.text[:500]}")
        j = r.json()
        if a.dry_run: print(json.dumps(j, indent=2)); return []
        job_id = j["id"]; log(f"MapsData job {job_id} queued. Re-run with --mapsdata-job {job_id} to resume if this stops.")
    for _ in range(int(a.poll_minutes * 2)):
        j = requests.get(f"{MAPSDATA}/jobs/{job_id}", headers=h, timeout=30).json()
        log(f"MapsData {job_id}: {j.get('status')} {j.get('progress')}% leads={j.get('lead_count')} emails={j.get('email_count')}")
        if j.get("status") in ("completed", "failed", "cancelled"): break
        time.sleep(30)
    if j.get("status") != "completed": raise SystemExit(f"MapsData job {job_id} is {j.get('status')}; resume later with --mapsdata-job {job_id}")
    link = requests.get(f"{MAPSDATA}/jobs/{job_id}/download", params={"format": "csv", "scope": "all"}, headers=h, timeout=30)
    if link.status_code >= 400:  # the "all rows" file is not always produced; the with-email file always is
        link = requests.get(f"{MAPSDATA}/jobs/{job_id}/download", params={"format": "csv", "scope": "emails"}, headers=h, timeout=30)
    link = link.json()
    text = requests.get(link["url"], timeout=120).text
    return [mapsdata_map_row(rec) for rec in csv.DictReader(io.StringIO(text))]


SOURCES = {"osm": None, "google_places": "GOOGLE_PLACES_API_KEY", "serper": "SERPER_API_KEY", "rapidapi": "RAPIDAPI_KEY", "mapsdata": "MAPSDATA_API_KEY"}


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        k = r["source_id"] or (r["business_name"].lower(), r["street"].lower())
        if k in seen: continue
        seen.add(k); out.append(r)
    return out


def review_filter(rows, mn, mx, drop_unknown=False):
    kept = []
    for r in rows:
        n = to_int(r.get("review_count"))
        if n is None:
            if not drop_unknown: kept.append(r)
            continue
        if mn is not None and n < mn: continue
        if mx is not None and n > mx: continue
        kept.append(r)
    return kept


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--niche", required=True, help="one niche, e.g. dentist / roofer / med-spa (MapsData: a Google Maps category)")
    ap.add_argument("--source", default="osm", choices=sorted(SOURCES))
    ap.add_argument("--city"); ap.add_argument("--state", help="2-letter state, e.g. TX")
    ap.add_argument("--zips", help="comma-separated zip codes"); ap.add_argument("--all-zips", action="store_true", help="every zip of --city/--state")
    ap.add_argument("--max-zips", type=int, default=0); ap.add_argument("--radius-m", type=int, default=2500, help="OSM search radius around each zip centre")
    ap.add_argument("--osm-tag", action="append", default=[]); ap.add_argument("--require-website", action="store_true")
    ap.add_argument("--min-reviews", type=int); ap.add_argument("--max-reviews", type=int)
    ap.add_argument("--drop-unknown-reviews", action="store_true", help="drop rows with no review data when filtering")
    ap.add_argument("--with-reviews", action="store_true", help="serper: fetch newest reviews per listing (extra cost)")
    ap.add_argument("--limit", type=int, default=500, help="mapsdata total_limit")
    ap.add_argument("--mapsdata-job"); ap.add_argument("--poll-minutes", type=float, default=30); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    need = SOURCES[a.source]
    if need and not env(need): raise SystemExit(f"--source {a.source} needs {need} in the environment (~/.hermes/.env). Free path: --source osm")

    if a.source == "mapsdata":
        rows = pull_mapsdata(a)
    else:
        if a.zips: zips = [zip_info(z.strip()) for z in a.zips.split(",") if z.strip()]
        elif a.all_zips and a.city and a.state: zips = zips_for_city(a.city, a.state)
        else: raise SystemExit("Give --zips 78704,78745 or --all-zips with --city and --state")
        if a.max_zips: zips = zips[: a.max_zips]
        log(f"{len(zips)} zip codes: {', '.join(z['zip'] for z in zips)}")
        rows, failed = [], []
        for i, z in enumerate(zips, 1):
            fn = {"osm": lambda: pull_osm(a.niche, z, a.radius_m, a.osm_tag), "google_places": lambda: pull_google_places(a.niche, z),
                  "serper": lambda: pull_serper(a.niche, z, with_reviews=a.with_reviews), "rapidapi": lambda: pull_rapidapi(a.niche, z)}[a.source]
            try:
                got = fn()
            except (SourceBusy, requests.RequestException) as e:
                failed.append(z["zip"]); log(f"[{i}/{len(zips)}] {z['zip']} FAILED ({str(e)[:80]}), continuing"); continue
            new = len(dedupe(rows + got)) - len(dedupe(rows)); rows += got
            log(f"[{i}/{len(zips)}] {z['zip']} {z['city']}: {len(got)} found, {new} new")
            time.sleep(1.5 if a.source == "osm" else 0.3)
    rows = dedupe(rows)
    total = len(rows)
    if a.require_website: rows = [r for r in rows if r["website"]]
    if a.min_reviews is not None or a.max_reviews is not None:
        rows = review_filter(rows, a.min_reviews, a.max_reviews, a.drop_unknown_reviews)
    write_csv(rows, a.out, FIELDS)
    with_rev = sum(1 for r in rows if r["review_count"] != "")
    print(f"{total} unique businesses pulled, {len(rows)} kept ({with_rev} with review counts) -> {a.out}")
    if a.source != "mapsdata" and failed:
        print(f"{len(failed)} zip(s) failed, re-run them later and merge: --zips {','.join(failed)}")


if __name__ == "__main__":
    main()
