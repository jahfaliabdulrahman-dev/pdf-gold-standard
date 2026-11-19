#!/usr/bin/env python3
"""C-isolation guard: a conformance run never loads a calibrated document spec.

Two controls:
  1. **Static**: no file under `conformance/` imports a document spec (`nav_spec`, `report_spec`,
     `najd_spec`, `report_print_spec`, `gate_policy`) or `spec_loader` — the module that would load one.
     A grep, because it is total. (A mention in a comment is not an import; the regex requires `import`.)
  2. **Runtime**: a real build of one case, in a fresh process, and then `sys.modules` is inspected — the
     static check cannot see an import made *inside* a function (`postprocess.feature_pdfua` does exactly
     that when no case spec is passed), so the runtime half is the one that would have caught the leak.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
# The spec modules themselves, not `spec_loader`: `postprocess` imports the loader inside two functions even
# when it is given a case spec, and an imported module that is never asked to `load()` a document spec cannot
# leak a constant. What must be absent is the loaded spec — that is the runtime control below.
FORBIDDEN = ("nav_spec", "report_spec", "najd_spec", "report_print_spec", "gate_policy")
fails = []


def check(name, ok, detail):
    print(("PASS " if ok else "FAIL ") + name + " - " + detail)
    if not ok:
        fails.append(name)


# --- 1 · static -------------------------------------------------------------
hits = []
for root, _dirs, files in os.walk(os.path.join(REPO, "conformance")):
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        text = open(path, encoding="utf-8").read()
        for name in FORBIDDEN + ("spec_loader",):
            for m in re.finditer(rf"^\s*(?:from|import)\s+.*\b{name}\b", text, re.M):
                hits.append(f"{os.path.relpath(path, REPO)}: {m.group(0).strip()}")
check("no-static-spec-import", not hits, "; ".join(hits[:4]) or f"no import of {', '.join(FORBIDDEN)}")

# --- 2 · runtime ------------------------------------------------------------
PROBE = r'''
import os, sys, json
sys.path.insert(0, %r)
os.chdir(%r)
from conformance.adapters import chrome
from conformance.corpus import cases
case = cases.load(os.path.join(%r, "conformance/corpus/cases/head-h1-h3.json"))
chrome.render_case(case, os.path.join(tempfile.mkdtemp(prefix="isolation-"), "probe.pdf"), "chrome")
bad = [m for m in %r if m in sys.modules]
print(json.dumps({"loaded": bad, "modules": len(sys.modules)}))
''' % (REPO, REPO, REPO, FORBIDDEN)
r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True, text=True, timeout=300,
                   env={**os.environ, "CHROME_PATH": os.environ.get("CHROME_PATH", "")})
if r.returncode != 0:
    check("no-runtime-spec-load", False, f"the probe build failed: {(r.stderr or r.stdout).strip()[-300:]}")
else:
    loaded = json.loads(r.stdout.strip().splitlines()[-1])["loaded"]
    check("no-runtime-spec-load", not loaded, f"spec modules loaded by a full case build: {loaded or 'none'}")

print(f"\nFORBIDDEN: {len(FORBIDDEN)} module names")
if fails:
    print(f"TEST FAILED — {fails}")
    raise SystemExit(1)
print("ISOLATION GUARD PASSED")
