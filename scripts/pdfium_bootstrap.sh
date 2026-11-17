#!/bin/bash
# Bootstrap a PDFium checkout and build pdfium_test — the prerequisite the patch dossier demands
# ("no C++ before a clean out/Release build"). Everything lands under ~/pdfium; the repo only records
# the revision that was built.
set -euo pipefail

export PATH="$HOME/depot_tools:$PATH"

if [ ! -d "$HOME/depot_tools" ]; then
  echo "== cloning depot_tools"
  git clone --depth 1 https://chromium.googlesource.com/chromium/tools/depot_tools.git "$HOME/depot_tools"
fi

mkdir -p "$HOME/pdfium"
cd "$HOME/pdfium"

if [ ! -f .gclient ]; then
  echo "== configuring gclient"
  gclient config --unmanaged https://pdfium.googlesource.com/pdfium.git
fi

echo "== bootstrapping depot_tools (downloads its own python)"
gclient --version >/dev/null
echo "== syncing (this is the long part)"
gclient sync --no-history --shallow --nohooks

cd pdfium
echo "== checked out: $(git rev-parse HEAD)"

echo "== generating ninja files"
gn gen out/Release --args='is_debug=false pdf_is_standalone=true pdf_enable_v8=false pdf_enable_xfa=false is_component_build=false use_remoteexec=false treat_warnings_as_errors=false'

echo "== building pdfium_test"
ninja -C out/Release pdfium_test

echo "== done: $(ls -lh out/Release/pdfium_test 2>/dev/null || echo missing)"
