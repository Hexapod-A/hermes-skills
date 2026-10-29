#!/usr/bin/env bash
# Clone check at several screen widths in one go: screenshot the REFERENCE URL and your BUILD URL at
# each width (same viewport, same cleaning), score each pair with diff_score.py, make a side-by-side
# sheet per width, then compare computed styles with compare_styles.mjs. Use it when the reference is
# a live website (for an image reference use verify.sh).
#
# Usage: verify_widths.sh REF_URL BUILD_URL OUTDIR [--widths 1440,768,390] [--preset clone|restyle]
#                         [--full] [--clean] [--no-styles]
#   --full   compare full pages (default: first screen only, which is more stable)
# Writes OUTDIR/<width>/{ref,build}-<width>.png, -report.json, -sbs.jpg and OUTDIR/styles/style-diff.md
# Exit: 0 every width passes, 2 at least one below threshold, 1 error.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${PY:-$([ -x "$REPO/.venv/bin/python" ] && echo "$REPO/.venv/bin/python" || echo python3)}"
[ $# -ge 3 ] || { sed -n '2,12p' "$0"; exit 1; }
REF="$1"; BUILD="$2"; OUT="$3"; shift 3
WIDTHS="1440,768,390"; PRESET=clone; VIEW=(--viewport); CLEAN=(); STYLES=1
while [ $# -gt 0 ]; do
  case "$1" in
    --widths) WIDTHS="$2"; shift 2 ;;
    --preset) PRESET="$2"; shift 2 ;;
    --full) VIEW=(); shift ;;
    --clean) CLEAN=(--clean); shift ;;
    --no-styles) STYLES=0; shift ;;
    *) echo "unknown flag $1"; exit 1 ;;
  esac
done
mkdir -p "$OUT"
WORST=0
printf "%-7s %-8s %-8s %-8s %s\n" width ssim layout colour result
for W in ${WIDTHS//,/ }; do
  D="$OUT/$W"; mkdir -p "$D"
  node "$HERE/screenshot.mjs" "$REF" --out "$D" --name ref --widths "$W" "${VIEW[@]}" "${CLEAN[@]}" >/dev/null
  node "$HERE/screenshot.mjs" "$BUILD" --out "$D" --name build --widths "$W" "${VIEW[@]}" "${CLEAN[@]}" >/dev/null
  # full pages can differ in height: crop both to the shorter one so the scores stay comparable
  "$PY" - "$D/ref-$W.png" "$D/build-$W.png" <<'EOF'
import sys
from PIL import Image
a, b = Image.open(sys.argv[1]), Image.open(sys.argv[2])
h = min(a.height, b.height)
if a.height != b.height:
    a.crop((0, 0, a.width, h)).save(sys.argv[1]); b.crop((0, 0, b.width, h)).save(sys.argv[2])
    print(f"note: heights differed ({a.height} vs {b.height}); compared the top {h}px", file=sys.stderr)
EOF
  set +e
  "$PY" "$HERE/diff_score.py" "$D/ref-$W.png" "$D/build-$W.png" --preset "$PRESET" --out "$D/report.json" --heatmap "$D/heat.png" >/dev/null
  CODE=$?
  set -e
  [ "$CODE" -le 2 ] || { echo "diff_score failed at $W"; exit 1; }
  "$PY" "$HERE/side_by_side.py" "$D/ref-$W.png" "$D/build-$W.png" --heatmap "$D/heat.png" --out "$D/sbs.jpg" --labels "Reference,Build,Mismatch" >/dev/null
  "$PY" - "$D/report.json" "$W" "$CODE" <<'EOF'
import json, sys
r = json.load(open(sys.argv[1])); s = r.get("scores", r)
g = lambda k: s.get(k, r.get(k, "?"))
print(f"{sys.argv[2]:<7} {g('ssim'):<8} {g('layout'):<8} {g('colour'):<8} {'PASS' if sys.argv[3] == '0' else 'below threshold'}")
EOF
  [ "$CODE" -eq 0 ] || WORST=2
done
if [ "$STYLES" -eq 1 ]; then
  set +e
  node "$HERE/compare_styles.mjs" "$REF" "$BUILD" --widths "$WIDTHS" --out "$OUT/styles" "${CLEAN[@]}"
  SC=$?
  set -e
  [ "$SC" -le 2 ] || exit 1
  [ "$SC" -eq 0 ] || WORST=2
fi
echo "sheets: $OUT/<width>/sbs.jpg   styles: $OUT/styles/style-diff.md"
exit "$WORST"
