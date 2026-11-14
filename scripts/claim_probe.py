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

def rules(path, flavour):
    r = subprocess.run(["verapdf", "--flavour", flavour, "--format", "json", path],
                       capture_output=True, text=True, timeout=900)
    data = json.loads(r.stdout or "{}")
    out = []
    def walk(o):
        if isinstance(o, dict):
            if "ruleSummaries" in o:
                for x in o["ruleSummaries"]:
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

# What remains when the file DOES declare conformance. Measured on 47b479a; a rule that stays,
# appears or disappears outside this table fails the gate — the identification claim is now guarded.
EXPECTED = {
    "3b": set(),                                   # strict widths: 0 rules (measured)
    "ua1": {"7.1-3", "7.4.2-1"},
}
CLAIMS = {"3b": {"pdfaid:part": "3", "pdfaid:conformance": "B"},
          "ua1": {"pdfuaid:part": "1"}}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"
    if "--check" in sys.argv:
        bad = 0
        for flavour, keys in CLAIMS.items():
            got = {rid for rid, _ in probe(src, flavour, keys)}
            want = EXPECTED[flavour]
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
