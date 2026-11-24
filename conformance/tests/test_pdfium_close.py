#!/usr/bin/env python3
"""Every PDFium text page and page is closed — proven with a fake module, not with a comment.

pypdfium2's `PdfTextPage` and `PdfPage` hold native buffers; the old one-liner
`[page.get_textpage().get_text_range() for page in doc]` never closed either. A fake module records the
calls, so the test fails if a future edit drops a `finally`.
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from conformance.readers import pdfium                   # noqa: E402

fails = []
closed = {"text": 0, "page": 0, "doc": 0}


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


class FakeTextPage:
    def get_text_range(self):
        return "نص الصفحة"

    def close(self):
        closed["text"] += 1


class FakePage:
    def get_textpage(self):
        return FakeTextPage()

    def close(self):
        closed["page"] += 1


class FakeDoc:
    def __init__(self, path):
        self.pages = [FakePage(), FakePage(), FakePage()]

    def __iter__(self):
        return iter(self.pages)

    def close(self):
        closed["doc"] += 1


original = pdfium.pypdfium2
pdfium.pypdfium2 = types.SimpleNamespace(PdfDocument=FakeDoc)
try:
    got = pdfium.pages_many(["a.pdf"])
finally:
    pdfium.pypdfium2 = original

check("three-pages-read", got == [["نص الصفحة"] * 3], str(got))
check("text-pages-closed", closed["text"] == 3, str(closed))
check("pages-closed", closed["page"] == 3, str(closed))
check("document-closed", closed["doc"] == 1, str(closed))

print()
if fails:
    print(f"PDFIUM CLOSE FAILED — {fails}")
    raise SystemExit(1)
print("PDFIUM CLOSE PASSED — one text page and one page per page, closed in a finally")
