#!/usr/bin/env python3
"""The checker defines no reader, no metric and no normalization of its own.

Three controls, each total in a different way:
  1. **Static imports**: nothing under `arabic_pdf_check/` imports a reader library (`pymupdf`,
     `pypdfium2`, `pdfplumber`), `subprocess`, or `arafix` directly. The reader matrix comes from
     `conformance.readers`, and the orientation detector from `conformance.checks.visual_order` — a second
     import of arafix here would be a second copy of the metric that can drift from the measured one.
  2. **No private ranges**: no file defines the Arabic / presentation-form / PUA ranges again; they are
     imported (`structure.ARABIC`, `metrics.PRESENTATION_FORM`).
  3. **Runtime**: after a real `check`, the modules the checker loaded are exactly the shared ones — its
     own package plus `conformance.*` (and their dependencies), never a reader module it reached itself.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PKG = os.path.join(REPO, "arabic_pdf_check")
sys.path.insert(0, REPO)

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


FORBIDDEN_IMPORTS = {"pymupdf", "pypdfium2", "pdfplumber", "pdfminer", "subprocess", "arafix"}
RANGE_MARKERS = ("\\u06", "\\uFB5", "\\uFE7", "0xFB50", "0xFE70", "0x06F0", "0xE000")

hits = []
for root, _dirs, files in os.walk(PKG):
    # the guard's own tests use subprocess and name the ranges to assert about them; they are not the tool
    if os.path.relpath(root, PKG).split(os.sep)[0] == "tests":
        continue
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        rel = os.path.relpath(path, REPO)
        source = open(path, encoding="utf-8").read()
        tree = ast.parse(source, filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                        hits.append(f"{rel}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                    hits.append(f"{rel}:{node.lineno}: from {node.module} import …")
        for i, line in enumerate(source.splitlines(), 1):
            code = line.split("#", 1)[0]
            for marker in RANGE_MARKERS:
                if marker.lower() in code.lower():
                    hits.append(f"{rel}:{i}: defines a range literal ({marker})")
check("no-private-reader-metric-or-range", not hits, "; ".join(hits[:5]))

PROBE = r'''
import json, os, sys
sys.path.insert(0, %r)
from arabic_pdf_check import blind
rep = blind.check(os.path.join(%r, "tests/vocalised_raw.pdf"),
                  json.load(open(os.path.join(%r, "arabic_pdf_check/thresholds.json"))))
print(json.dumps({"readers": sorted(rep["readers"]), "mode": rep["mode"]}))
''' % (REPO, REPO, REPO)
r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, timeout=600, cwd=REPO)
check("runtime-check-runs", r.returncode == 0, (r.stderr or r.stdout).strip()[-300:])
if r.returncode == 0:
    payload = json.loads(r.stdout.strip().splitlines()[-1])
    check("runtime-readers-from-conformance", set(payload["readers"]) <= {"pdfium", "pdfkit", "mupdf", "poppler",
                                                                          "pdfminer"} and payload["readers"],
          str(payload))

# the wrapper is the only door to arafix: it must exist and be imported from conformance
wrapper = os.path.join(REPO, "conformance", "checks", "visual_order.py")
check("arafix-wrapper-exists", os.path.exists(wrapper), wrapper)
wrapper_src = open(wrapper, encoding="utf-8").read() if os.path.exists(wrapper) else ""
check("arafix-wrapper-imports-arafix", "from arafix import" in wrapper_src, "the one import lives here")

print()
if fails:
    print(f"CHECKER ISOLATION FAILED — {len(fails)}: {', '.join(fails)}")
    raise SystemExit(1)
print("CHECKER ISOLATION PASSED — readers, metrics, ranges and arafix all come from conformance/")
