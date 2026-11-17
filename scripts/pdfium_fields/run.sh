#!/usr/bin/env bash
# Reproduce the Arabic field-shaping measurements end to end.
#
# REQUIRES: the probe binaries built from the UNPUBLISHED PDFium branch
# `arabic-field-shaping@974afb6` (see docs/pdfium-arabic-fields/), and the Najd face at
# `najd/Najd-Regular.ttf` — not shipped: the licence forbids redistributing the font.
#
#   scripts/pdfium_fields/run.sh --out /tmp/fields \
#       [--baseline-probe /path/to/an-unpatched/field_probe]
#
# The probe comes from the PDFium tree the patch lives in:
#   third_party/ninja/ninja -C out/Release field_probe
#
# To produce a baseline probe, stash the patch, rebuild, copy the binary, and
# restore — the recipe is in docs/pdfium-arabic-fields/15-field-shaping.md.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
python=${PYTHON:-"$repo/.venv/bin/python"}
pdfium_out=${PDFIUM_OUT:-"$HOME/pdfium/pdfium/out/Release"}
out=/tmp/fields
baseline_probe=""

while [ $# -gt 0 ]; do
  case "$1" in
    --out) out=$2; shift 2 ;;
    --baseline-probe) baseline_probe=$2; shift 2 ;;
    --pdfium-out) pdfium_out=$2; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$out"
probe="$pdfium_out/field_probe"
test -x "$probe" || { echo "no field_probe at $probe" >&2; exit 2; }

echo "== fixture =="
"$python" "$here/build_field_pdf.py" "$out/fixture.pdf"

echo "== appearance streams (patched) =="
"$python" "$here/measure_ap.py" "$out/after.pdf" --source "$out/fixture.pdf" --probe "$probe"

echo "== extracted text (patched) =="
"$python" "$here/measure_text.py" "$out/after.pdf" --pdfium-out "$pdfium_out" \
    --work "$out/text"

echo "== editor against the appearance stream =="
"$python" "$here/measure_editor.py" "$out/fixture.pdf" --source "$out/after.pdf" \
    --pdfium-out "$pdfium_out" --work "$out/editor"

if [ -n "$baseline_probe" ]; then
  test -x "$baseline_probe" || { echo "no baseline probe at $baseline_probe" >&2; exit 2; }
  echo "== appearance streams (baseline) =="
  "$python" "$here/measure_ap.py" "$out/before.pdf" --source "$out/fixture.pdf" \
      --probe "$baseline_probe" --expect baseline
  echo "== controls against the baseline =="
  "$python" "$here/measure_ap.py" "$out/after.pdf" --baseline "$out/before.pdf" | tail -3
  echo "== rendered appearance: ar =="
  "$python" "$here/render_ap.py" "$out/before.pdf" "$out/after.pdf" "$out/ap" \
      --normalize-subtype
  echo "== rendered appearance: mixed =="
  "$python" "$here/render_ap.py" "$out/before.pdf" "$out/after.pdf" "$out/mx" \
      --field mixed --normalize-subtype
  echo "== rendered appearance: ltr_mixed (not right-aligned) =="
  "$python" "$here/render_ap.py" "$out/before.pdf" "$out/after.pdf" "$out/ltr" \
      --field ltr_mixed --normalize-subtype --no-margin-check
  echo "== rendered appearance: center (Q=1) =="
  "$python" "$here/render_ap.py" "$out/before.pdf" "$out/after.pdf" "$out/ct" \
      --field center --normalize-subtype --no-margin-check --center-check
else
  echo "position checks need a baseline probe: pass --baseline-probe" >&2
  exit 2
fi

echo "== done: $out =="
