#!/usr/bin/env python3
"""The control for `mupdf-ar-digit-reversal`: MuPDF writes the file, MuPDF misreads it, PDFium reads it right.

A limit is only a limit if the reader fails on a file this pipeline did not produce. This file's producer is
PyMuPDF itself (`insert_text` with the Amiri face), so "the file's text layer is wrong" is not available as an
explanation: MuPDF wrote what MuPDF reads.

Prints one JSON object: {"reproduces": bool, "detail": {...}}
Exit 0 even when it does not reproduce — the caller refuses the limit and says so; a crashing control is a
different failure.
"""
import json
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)

import pymupdf
import pypdfium2

from conformance.adapters import fonts

TRUTH = "٢٠٢٦"


def main() -> int:
    font = fonts.path("amiri")
    with tempfile.TemporaryDirectory(prefix="ctrl-mupdf-digits-") as tmp:
        pdf = os.path.join(tmp, "written-by-mupdf.pdf")
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 120), TRUTH, fontname="Amiri", fontfile=font, fontsize=24)
        doc.save(pdf)
        doc.close()
        mupdf_read = pymupdf.open(pdf)[0].get_text().strip()
        pdfium_doc = pypdfium2.PdfDocument(pdf)
        try:
            textpage = pdfium_doc[0].get_textpage()
            try:
                pdfium_read = textpage.get_text_range().strip()
            finally:
                textpage.close()
        finally:
            pdfium_doc.close()
    reproduces = (mupdf_read == TRUTH[::-1] and pdfium_read == TRUTH)
    print(json.dumps({
        "reproduces": reproduces,
        "detail": {"producer": f"PyMuPDF {pymupdf.__version__}", "truth": TRUTH,
                   "mupdf_read": mupdf_read, "pdfium_read": pdfium_read},
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
