#!/bin/bash
# Build PDFium with HarfBuzz enabled — the dossier's phase 0.5: prove the shaping engine is actually in the
# binary before writing a line of C++ that calls it.
set -euo pipefail
export PATH="$HOME/depot_tools:$PATH"

cd "$HOME/pdfium/pdfium"

echo "== generating out/HB"
gn gen out/HB --args='is_debug=false pdf_is_standalone=true pdf_enable_v8=false pdf_enable_xfa=false is_component_build=false use_remoteexec=false skia_use_harfbuzz=true'

echo "== args as written"
grep -E "skia_use_harfbuzz|pdf_is_standalone" out/HB/args.gn || true

echo "== building pdfium_test"
ninja -C out/HB pdfium_test

echo "== harfbuzz objects in the build tree"
find out/HB/obj -path '*harfbuzz*' -name '*.o' | head -5
find out/HB/obj -path '*harfbuzz*' -name '*.o' | wc -l

echo "== hb_shape in the binary"
nm out/HB/pdfium_test 2>/dev/null | grep -c "hb_shape" || echo 0
nm out/HB/pdfium_test 2>/dev/null | grep "hb_version_string" | head -2 || true
