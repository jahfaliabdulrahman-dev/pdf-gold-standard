#!/usr/bin/env python3
"""Claim probe: would the file conform if it DECLARED conformance?

Copies the file, injects the identification keys into XMP, runs veraPDF on the copy and prints the
failing rules that remain. The published file declares nothing; the probe answers "is the content
conformant, apart from the claim itself?" without ever shipping a false identifier.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

import pikepdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import spec_loader  # noqa: E402

NS = spec_loader.load()  # noqa: E402

def rules(path, flavour):
    r = subprocess.run(["verapdf", "--flavour", flavour, "--format", "json", path],
                       capture_output=True, text=True, timeout=900)
    # `r.stdout or "{}"` turned a crash into «zero violations», so a broken tool passed the claim probe.
    if r.returncode not in (0, 1):
        raise SystemExit(f"verapdf {flavour}: exit {r.returncode} — the tool failed: {r.stderr[-300:]}")
    if not r.stdout.strip():
        raise SystemExit(f"verapdf {flavour}: empty JSON output (exit {r.returncode}): {r.stderr[-300:]}")
    data = json.loads(r.stdout)
    out = []
    def walk(o):
        if isinstance(o, dict):
            if "ruleSummaries" in o:
                for x in o["ruleSummaries"]:
                    if x.get("ruleStatus", "FAILED") != "FAILED":
                        continue
                    out.append((f'{x.get("clause")}-{x.get("testNumber")}', x.get("description", "")[:90]))
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(data)
    return sorted(set(out))

def probe(pdf_path, flavour, keys):
    with pikepdf.open(pdf_path) as pdf:
        with pdf.open_metadata() as m:
            for k, v in keys.items(): m[k] = v
        fd, tmp = tempfile.mkstemp(suffix=".pdf"); os.close(fd)
        pdf.save(tmp)
    try:
        got = rules(tmp, flavour)
    finally:
        os.unlink(tmp)
    print(f"--- {flavour} with {keys}: {len(got)} failing")
    for rid, desc in got:
        print(f"    {rid} | {desc}")
    return got

# What remains when the file DOES declare conformance is a property of the document, measured on that
# build — never a shared default. Each spec carries its own CLAIM_EXPECTED; a spec without one is an
# error, not a reason to judge it against another document's table.
CLAIMS = {"3b": {"pdfaid:part": "3", "pdfaid:conformance": "B"},
          "ua1": {"pdfuaid:part": "1"}}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"
    if "--check" in sys.argv:
        bad = 0
        table = getattr(NS, "CLAIM_EXPECTED", None)
        if not table:
            raise SystemExit(f"{NS.__name__} declares no CLAIM_EXPECTED — the table is per document")
        for flavour, keys in CLAIMS.items():
            got = {rid for rid, _ in probe(src, flavour, keys)}
            want = table[flavour]
            new, dead = got - want, want - got
            ok = not new and not dead
            print(("PASS " if ok else "FAIL ") + f"claim-{flavour} - {len(got)} remaining"
                  + (f" · NEW {sorted(new)}" if new else "") + (f" · DEAD {sorted(dead)}" if dead else ""))
            bad += 0 if ok else 1
        if bad:
            raise SystemExit(1)
        print("CLAIM PROBE HELD — what remains under a claim is exactly what is documented")
    else:
        for flavour, keys in CLAIMS.items():
            probe(src, flavour, keys)
