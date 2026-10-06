#!/usr/bin/env bash
# One niche, one area, one offer: pull -> websites -> crawl -> owners -> emails -> score -> facts -> drafts -> call sheet.
# DRAFTS ONLY: nothing here sends an email, a text or a call.
#
# Usage: pipeline.sh <niche> <city> <state> <out_dir> [extra pull.py args...]
#   pipeline.sh dentist "Austin" TX ~/leads/austin-dentists --zips 78704,78745
#   pipeline.sh dentist "Austin" TX ~/leads/austin-dentists --all-zips --max-zips 30
#   SOURCE=google_places MIN_REVIEWS=20 MAX_REVIEWS=400 pipeline.sh dentist Austin TX ~/leads/atx --zips 78704
# Env knobs: SOURCE (osm|google_places|serper|rapidapi|mapsdata), MIN_REVIEWS, MAX_REVIEWS, SUPPRESS (csv path),
#            OWNER_SAMPLE (default 50: stop after the hand-check sample; set 0 to run the full list), RADIUS_MI (default 2)
set -euo pipefail
NICHE="$1"; CITY="$2"; STATE="$3"; OUT="$4"; shift 4
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-$D/../../.venv/bin/python}"; [ -x "$PY" ] || PY=python3
SOURCE="${SOURCE:-osm}"; OWNER_SAMPLE="${OWNER_SAMPLE:-50}"; RADIUS_MI="${RADIUS_MI:-2}"
mkdir -p "$OUT"
REV=(); [ -n "${MIN_REVIEWS:-}" ] && REV+=(--min-reviews "$MIN_REVIEWS"); [ -n "${MAX_REVIEWS:-}" ] && REV+=(--max-reviews "$MAX_REVIEWS")
SUP=(); [ -n "${SUPPRESS:-}" ] && [ -f "${SUPPRESS}" ] && SUP+=(--suppress "$SUPPRESS")

echo "== 1/9 pull ($SOURCE, zip by zip)"; "$PY" "$D/pull.py" --source "$SOURCE" --niche "$NICHE" --city "$CITY" --state "$STATE" --out "$OUT/market.csv" "$@"
echo "== 2/9 websites";  "$PY" "$D/find_websites.py" "$OUT/market.csv" --out "$OUT/with_sites.csv"
echo "== 3/9 crawl";     "$PY" "$D/enrich_site.py" "$OUT/with_sites.csv" --out "$OUT/enriched.csv" --cache "$OUT/site_cache"
if [ "$OWNER_SAMPLE" != "0" ]; then
  echo "== 4/9 owners (hand-check sample of $OWNER_SAMPLE)"; "$PY" "$D/find_owner.py" "$OUT/enriched.csv" --out "$OUT/owners.csv" --sample "$OWNER_SAMPLE"
  echo "   Open $OUT/owners_handcheck.xlsx, check the names against owner_page, then re-run with OWNER_SAMPLE=0 for the full list."
else
  echo "== 4/9 owners (full list)"; "$PY" "$D/find_owner.py" "$OUT/enriched.csv" --out "$OUT/owners.csv"
fi
echo "== 5/9 email waterfall + verify"; "$PY" "$D/email_waterfall.py" "$OUT/owners.csv" --out "$OUT/emails.csv" --log "$OUT/waterfall_log.csv"
echo "== 6/9 score, dedupe, suppress"; "$PY" "$D/score.py" "$OUT/emails.csv" --out "$OUT/scored.csv" "${REV[@]}" "${SUP[@]}"
echo "== 7/9 local facts";  "$PY" "$D/local_facts.py" "$OUT/scored.csv" --market "$OUT/market.csv" --out "$OUT/facts.csv" --radius-mi "$RADIUS_MI"
echo "== 8/9 email drafts"; "$PY" "$D/draft_emails.py" "$OUT/facts.csv" --out "$OUT/drafts"
echo "== 9/9 call sheet + xlsx"; "$PY" "$D/call_sheet.py" export "$OUT/facts.csv" --out "$OUT/leads" --drafts "$OUT/drafts.csv" --waterfall-log "$OUT/waterfall_log.csv"
echo "Done. Open $OUT/leads.xlsx (Call sheet, Leads, Email drafts, Waterfall log). Nothing was sent."
