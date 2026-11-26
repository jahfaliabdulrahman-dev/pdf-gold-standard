#!/usr/bin/env python3
"""The control for `poppler-bidi-decorations`: pdftotext decorates lines of a file this pipeline did not write.

The file is a **committed fixture** (`poppler-bidi-fixture.pdf`, 23 KB, one Arabic line, no direction controls in
the source) written once by PyMuPDF 2.1 with the Amiri face and stored with its sha256 below. It is committed
rather than generated on the spot because PyMuPDF is an OPTIONAL extra (it is AGPLv3-or-commercial, and the
shipped checker must run without it) — a control that needed it could not refresh on a clean install, and a
limitation that cannot be re-run is a claim, not a measurement. Committing the input does not weaken the claim:
the file is still one this pipeline did not write, and the sha256 is what makes the re-run the same file.

pdftotext wraps each line in U+202A…U+202C; PDFium, reading the same file, returns none. The measured `per_line`
is what the limit is allowed to excuse, and it is the SAME key the predicate reads (`detail.per_line`) — an
earlier version wrote `pdftotext_per_line` there, and the limit silently excused nothing (review S1).

Measured 2026-11-26 against poppler 26.11.0: pdftotext 4 controls over 1 line ⇒ per_line 4 · PDFium 0.

Prints one JSON object: {"reproduces": bool, "detail": {...}}
"""
import hashlib
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)

import pypdfium2

from conformance.checks import metrics
from conformance.readers import poppler as poppler_reader

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poppler-bidi-fixture.pdf")
FIXTURE_SHA256 = "c231376694b13f14878e03b6ce0235ec30053e88581d92d0edae6ea1f01f67c5"
PRODUCED_BY = "PyMuPDF 2.1 · insert_text · Amiri · committed as the fixture"


def write_fixture() -> int:
    """Re-create the input — the only reason PyMuPDF is still nameable here, and only on demand.

    Run it deliberately: a new font version or a new PyMuPDF changes the bytes, so the constant below must be
    updated in the same commit, and the measurement re-read. The hash is the identity of the input; this function
    is its provenance.
    """
    import pymupdf                                   # optional extra, imported only for this branch
    from conformance.adapters import fonts
    line = "سطر عربي واحد بلا محارف اتجاه في المصدر."
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 120), line, fontname="Amiri", fontfile=fonts.path("amiri"), fontsize=14)
    doc.subset_fonts(verbose=False)
    doc.save(FIXTURE, garbage=4, deflate=True)
    doc.close()
    digest = hashlib.sha256(open(FIXTURE, "rb").read()).hexdigest()
    print(json.dumps({"written": FIXTURE, "sha256": digest, "bytes": os.path.getsize(FIXTURE),
                      "producer": f"PyMuPDF {pymupdf.__version__}", "note":
                      "update FIXTURE_SHA256 and re-measure per_line in the same commit"}, ensure_ascii=False))
    return 0


def main() -> int:
    if "--write-fixture" in sys.argv[1:]:
        return write_fixture()
    if not os.path.isfile(FIXTURE):
        print(json.dumps({"reproduces": False, "detail": {"error": f"fixture missing: {FIXTURE}"}}))
        return 0
    digest = hashlib.sha256(open(FIXTURE, "rb").read()).hexdigest()
    if digest != FIXTURE_SHA256:
        # A different input measures a different claim: refuse instead of recording a number for a file nobody
        # can name. Re-generating the fixture is a deliberate act that updates this constant.
        print(json.dumps({"reproduces": False, "detail": {"error": "fixture sha256 changed",
                                                          "expected": FIXTURE_SHA256, "got": digest}}))
        return 0
    binary = poppler_reader.binary()          # the pinned build, exactly as the reader resolves it
    r = subprocess.run([binary, "-q", "-enc", "UTF-8", FIXTURE, "-"],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(json.dumps({"reproduces": False, "detail": {"error": f"{binary} exited {r.returncode}",
                                                          "stderr": (r.stderr or "").strip()[:200]}}))
        return 0
    out = r.stdout
    ref_doc = pypdfium2.PdfDocument(FIXTURE)
    try:
        textpage = ref_doc[0].get_textpage()
        try:
            ref = textpage.get_text_range()
        finally:
            textpage.close()
    finally:
        ref_doc.close()
    lines = max(1, len([ln for ln in out.splitlines() if ln.strip()]))
    per_line = metrics.bidi_count(out) // lines
    detail = {"producer": PRODUCED_BY, "fixture_sha256": digest, "binary": binary, "per_line": per_line,
              "pdftotext_total": metrics.bidi_count(out), "pdfium_total": metrics.bidi_count(ref),
              "lines": lines, "text": out}
    reproduces = per_line >= 1 and metrics.bidi_count(ref) == 0
    print(json.dumps({"reproduces": reproduces, "detail": detail}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
