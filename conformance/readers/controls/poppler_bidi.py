#!/usr/bin/env python3
"""The control for `poppler-bidi-decorations`: pdftotext decorates lines of a file it did not write.

The file is Chrome's own output (`chrome-raw`): the engine, without any post-processing of ours. One Arabic
paragraph, no bidi controls in the source. pdftotext wraps the line in U+202A…U+202C; PDFium, reading the same
file, returns none. The measured `per_line` is what the limit is allowed to excuse.

Prints one JSON object: {"reproduces": bool, "detail": {"per_line": n, ...}}
"""
import json
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)

import pypdfium2
import pymupdf

from conformance.adapters import chrome
from conformance.checks import metrics

CASE = {
    "id": "ctrl-poppler-bidi", "category": "controls", "lang": "ar", "font": "plex",
    "blocks": [{"type": "paragraph", "text": "سطر عربي واحد بلا محارف اتجاه في المصدر."}],
    "note": "control file: produced by Chrome, not by the pipeline",
}


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="ctrl-poppler-bidi-")
    pdf = os.path.join(tmp, "chrome-raw.pdf")
    chrome.render_case(CASE, pdf, engine="chrome-raw")
    import subprocess
    out = subprocess.run(["pdftotext", "-q", "-enc", "UTF-8", pdf, "-"],
                         capture_output=True, text=True, timeout=120).stdout
    doc = pypdfium2.PdfDocument(pdf)
    ref = doc[0].get_textpage().get_text_range()
    doc.close()
    lines = max(1, len([ln for ln in out.splitlines() if ln.strip()]))
    per_line = metrics.bidi_count(out) // lines
    detail = {"producer": f"Chrome for Testing {chrome.chrome_bin()[1]}", "pdftotext_per_line": per_line,
              "pdftotext_total": metrics.bidi_count(out), "pdfium_total": metrics.bidi_count(ref),
              "lines": lines, "text": out}
    reproduces = per_line >= 1 and metrics.bidi_count(ref) == 0
    print(json.dumps({"reproduces": reproduces, "detail": detail}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
