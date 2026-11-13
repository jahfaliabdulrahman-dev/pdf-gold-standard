#!/usr/bin/env python3
"""Fully vocalised paragraphs must copy exactly — and the test must be able to fail.

Usage: python3 scripts/test_vocalised.py

tests/vocalised_raw.pdf is Chrome's untouched output for two paragraphs of fully vocalised text (Surah 93, GeezaPro,
printed on macOS); tests/vocalised_truth.txt is the text of one paragraph. The raw file must score BELOW the bar
(a test never seen failing is unverified); after scripts/fix_text_layer.py every word must come back with its marks,
in order, from PDFium and MuPDF, and not one pixel may change.
"""
import difflib
import os
import re
import sys
import tempfile
import unicodedata

import pikepdf
import pymupdf
import pypdfium2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fix_text_layer  # noqa: E402

RAW = os.path.join(HERE, "..", "tests", "vocalised_raw.pdf")
TRUTH = os.path.join(HERE, "..", "tests", "vocalised_truth.txt")
CTRL = re.compile("[⁠‎‏‪-‮⁦-⁩؜ـ\x00]")
norm = lambda t: unicodedata.normalize("NFC", CTRL.sub("", t))


def extract(path):
    doc = pypdfium2.PdfDocument(path)
    return {"PDFium": "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc))),
            "MuPDF": "\n".join(p.get_text() for p in pymupdf.open(path))}


def exact(text, want):
    got = norm(text).split()
    return sum(b.size for b in difflib.SequenceMatcher(None, want, got, autojunk=False).get_matching_blocks()) / len(want)


def r2l(src, dst):
    """build.py declares the document right-to-left; PDFium orders a line by that flag."""
    with pikepdf.open(src) as pdf:
        pdf.Root.ViewerPreferences = pikepdf.Dictionary(Direction=pikepdf.Name.R2L)
        pdf.save(dst)


if __name__ == "__main__":
    one = norm(open(TRUTH, encoding="utf-8").read()).split()
    want = one + one                                     # the fixture prints the paragraph twice
    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        raw, mid, fixed = (os.path.join(tmp, n) for n in ("raw.pdf", "mid.pdf", "fixed.pdf"))
        r2l(RAW, raw)
        stats = fix_text_layer.process(RAW, mid); r2l(mid, fixed)
        print(f"fix_text_layer: {stats}")
        for engine, text in extract(raw).items():
            s = exact(text, want); ok = s < 0.5
            print(f"{'PASS' if ok else 'FAIL'} raw-must-fail/{engine} - {s:.3f} (must be < 0.5)")
            if not ok: failed.append(f"raw-must-fail/{engine}")
        for engine, text in extract(fixed).items():
            s = exact(text, want); ok = s == 1.0
            print(f"{'PASS' if ok else 'FAIL'} vocalised-paragraphs/{engine} - {s:.3f} of {len(want)} words exact with their marks, in order")
            if not ok: failed.append(f"vocalised-paragraphs/{engine}")
        # nothing but the text may be pasted: no invisible filler for the drawn marks, no lines made of it
        for engine, text in extract(fixed).items():
            extra = sorted({f"U+{ord(c):04X}" for c in text if not ("\u0600" <= c <= "\u06ff") and c not in " \t\r\n\u200f"})
            lines = [l for l in text.splitlines() if l.strip()]
            ok = not extra and len(lines) == 8
            print(f"{'PASS' if ok else 'FAIL'} clean-paste/{engine} - {len(lines)} text lines (8 printed), foreign characters: {extra or 'none'}")
            if not ok: failed.append(f"clean-paste/{engine}")
        a, b = pymupdf.open(RAW), pymupdf.open(fixed)
        diff = sum(a[i].get_pixmap(dpi=150).samples != b[i].get_pixmap(dpi=150).samples for i in range(len(a)))
        print(f"{'PASS' if not diff else 'FAIL'} pixels - {diff} page(s) differ at 150 dpi")
        if diff: failed.append("pixels")
    if failed:
        print(f"\nTEST FAILED: {failed}"); raise SystemExit(1)
    print("\nTEST PASSED")
