#!/usr/bin/env python3
"""The control for `poppler-bidi-decorations`: pdftotext decorates lines of a file this pipeline did not write.

The file is written by **PyMuPDF** (`insert_text` with the Amiri face) — a producer that is not our pipeline and
not the engine under test. One Arabic line, no direction controls in the source. pdftotext wraps it in
U+202A…U+202C; PDFium, reading the same file, returns none. The measured `per_line` is what the limit is allowed
to excuse, and it is the SAME key the predicate reads (`detail.per_line`) — an earlier version wrote
`pdftotext_per_line` there, and the limit silently excused nothing (review S1).

Prints one JSON object: {"reproduces": bool, "detail": {...}}
"""
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)

import pymupdf
import pypdfium2

from conformance.adapters import fonts
from conformance.checks import metrics

LINE = "سطر عربي واحد بلا محارف اتجاه في المصدر."


def main() -> int:
    font = fonts.path("amiri")
    tmp = tempfile.mkdtemp(prefix="ctrl-poppler-bidi-")
    pdf = os.path.join(tmp, "written-by-mupdf.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 120), LINE, fontname="Amiri", fontfile=font, fontsize=14)
    doc.save(pdf)
    doc.close()
    out = subprocess.run(["pdftotext", "-q", "-enc", "UTF-8", pdf, "-"],
                         capture_output=True, text=True, timeout=120).stdout
    ref_doc = pypdfium2.PdfDocument(pdf)
    ref = ref_doc[0].get_textpage().get_text_range()
    ref_doc.close()
    lines = max(1, len([ln for ln in out.splitlines() if ln.strip()]))
    per_line = metrics.bidi_count(out) // lines
    detail = {"producer": f"PyMuPDF {pymupdf.__version__}", "per_line": per_line,
              "pdftotext_total": metrics.bidi_count(out), "pdfium_total": metrics.bidi_count(ref),
              "lines": lines, "text": out}
    reproduces = per_line >= 1 and metrics.bidi_count(ref) == 0
    print(json.dumps({"reproduces": reproduces, "detail": detail}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
