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
from verapdf_json import failing_rules_detail  # noqa: E402  (one reader for both screens)

NS = spec_loader.load()  # noqa: E402

def rules(path, flavour):
    """The gate's own reader — one place turns veraPDF's JSON into a failing set (B5, P3 review)."""
    return failing_rules_detail(path, flavour)


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
