#!/usr/bin/env bash
# One pass of the verify loop: screenshot the build at the reference's exact size, score it,
# and make the side-by-side sheet with a mismatch panel.
#
# Usage: verify.sh REF.png URL OUTDIR [--preset restyle|clone] [--name page] [any screenshot.mjs flag]
# Writes OUTDIR/<name>-<width>.png, OUTDIR/<name>-report.json, OUTDIR/<name>-heat.png,
#        OUTDIR/<name>-sbs.jpg, OUTDIR/<name>-blend.png
# Exit code: 0 pass, 2 below threshold, 1 error.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${PY:-$([ -x "$REPO/.venv/bin/python" ] && echo "$REPO/.venv/bin/python" || echo python3)}"

[ $# -ge 3 ] || { sed -n '2,8p' "$0"; exit 1; }
REF="$1"; URL="$2"; OUT="$3"; shift 3
PRESET=restyle; NAME=build; EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --preset) PRESET="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    *) EXTRA+=("$1"); shift ;;
  esac
done
mkdir -p "$OUT"

SHOT_JSON="$(node "$HERE/screenshot.mjs" "$URL" --out "$OUT" --name "$NAME" --size-of "$REF" "${EXTRA[@]}" 2>/dev/null | tail -1)"
SHOT="$(printf '%s' "$SHOT_JSON" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["file"])')"
echo "shot: $SHOT_JSON"

set +e
"$PY" "$HERE/diff_score.py" "$REF" "$SHOT" --preset "$PRESET" \
  --out "$OUT/$NAME-report.json" --heatmap "$OUT/$NAME-heat.png"
CODE=$?
set -e
[ "$CODE" -le 2 ] || exit 1
"$PY" "$HERE/side_by_side.py" "$REF" "$SHOT" --heatmap "$OUT/$NAME-heat.png" \
  --out "$OUT/$NAME-sbs.jpg" --blend "$OUT/$NAME-blend.png" --labels "Reference,Build,Mismatch" >/dev/null
echo "sheet: $OUT/$NAME-sbs.jpg   overlay: $OUT/$NAME-blend.png"
exit "$CODE"
