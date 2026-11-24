#!/usr/bin/env python3
"""Control for `pdfium-rtl-row-order`: does THIS PDFium still read the row value-before-label?

The file is built by Chrome from a declared source (a two-column key/value table: «الفاتورة» then
«INV-2026-0042»), so the expected order is the source's, not a reader's. The control then reads it with
PDFium and asks one question: does the identifier come BEFORE its label on the line? If yes, the declared
behaviour is still true on this install; if no, the declaration is stale and must not be printed.

Prints one JSON object on stdout:
  {"reproduces": true|false, "detail": {...}, "reader": "pdfium", "reader_version": "5.15.2"}
"""
import json
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, REPO)

from conformance.adapters import chrome          # noqa: E402
from conformance.readers import pdfium           # noqa: E402

CASE = {
    "id": "pdfium-row-control",
    "category": "table-rtl",
    "lang": "ar",
    "font": "plex",
    "note": "G#5b: a key/value row whose value starts with Latin letters (the shape F uses)",
    "blocks": [
        {"type": "heading", "level": 1, "text": "فاتورة"},
        {"type": "table", "header": ["البند", "القيمة"],
         "rows": [["الفاتورة", "INV-2026-0042"], ["الرقم الضريبي", "310123456700003"]]},
    ],
}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pdfium-row-") as work:
        pdf = os.path.join(work, "control.pdf")
        chrome.render_case(CASE, pdf, "chrome")
        text = pdfium.text(pdf)
    line = next((ln for ln in text.splitlines() if "INV-2026-0042" in ln), None)
    if line is None:
        print(json.dumps({"reproduces": False, "reader": "pdfium",
                          "reader_version": pdfium.version(),
                          "detail": {"problem": "the control file carries no identifier line",
                                     "text": text[:200]}}, ensure_ascii=False))
        return 0
    value_before_label = line.find("INV-2026-0042") < line.find("الفاتورة")
    print(json.dumps({"reproduces": bool(value_before_label), "reader": "pdfium",
                      "reader_version": pdfium.version(),
                      "detail": {"line": line.strip()[:80],
                                 "expected": "الفاتورة INV-2026-0042",
                                 "value_before_label": bool(value_before_label)}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
