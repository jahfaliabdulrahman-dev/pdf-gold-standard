#!/usr/bin/env python3
"""`pdftotext` gets `--` before an absolute path, so a file named `-layout.pdf` is read, not parsed as flags.

The audit's small item: the reader passed the path bare. poppler 26.11.0 accepts `--`; Ubuntu's build must too,
which is why the Linux job runs this test. The fixture is written by PyMuPDF (a producer that is not the
pipeline), and the file is copied to the hostile name inside a temp directory.
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

import pymupdf                                             # noqa: E402
from conformance.adapters import fonts                      # noqa: E402
from conformance.readers import poppler                     # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


try:
    binary = poppler.binary()
except RuntimeError as exc:
    print(f"SKIP poppler-dash: {exc}")
    raise SystemExit(0)

with tempfile.TemporaryDirectory(prefix="poppler-dash-") as tmp:
    source = os.path.join(tmp, "source.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 120), "سطر عربي واحد", fontname="Amiri", fontfile=fonts.path("amiri"), fontsize=14)
    doc.save(source)
    doc.close()
    dashed = os.path.join(tmp, "-layout.pdf")
    shutil.copy(source, dashed)
    try:
        text = poppler.text_many([os.path.abspath(dashed)])[0]
        check("dash-name:read", bool(text.strip()), repr(text[:80]))
    except Exception as exc:
        check("dash-name:read", False, f"{type(exc).__name__}: {exc}")

print()
if fails:
    print(f"POPPLER DASH FAILED — {fails}")
    raise SystemExit(1)
print(f"POPPLER DASH PASSED — {binary} reads a path that starts with a dash")
