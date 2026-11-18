#!/usr/bin/env python3
"""The footer number is read from where the digits are DRAWN, not from what a text says.

MuPDF returns an Arabic-Indic run reversed (measured on a number MuPDF itself wrote: ٢٠٢٦ → ٦٢٠٢), so the old
rule was «if the token is missing from PDFium's page text and its reverse is present, take the reverse». When
the page prints BOTH numbers — ١٢ in the footer and ٢١ in the body — the reverse is always present, and the
footer read 21 (B4). A numeral is written left-to-right in Arabic as well as in Latin, so the span's digits
sorted by x give the value whatever string the reader built.

Run: python3 scripts/test_digit_value.py
"""
import os
import sys

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import verify_pdf as V  # noqa: E402


def span(*pairs):
    """A MuPDF span whose string order is `pairs` but whose glyphs sit at the given x positions."""
    return {"chars": [{"c": c, "bbox": (x0, 0.0, x1, 0.0)} for c, x0, x1 in pairs]}


CASES = (
    # (label, span, expect) — the first is the defect: the string is ٢١ (MuPDF's reversal), the drawing is ١٢
    ("string reversed, drawn ١٢ (footer 12 with 21 in the body)", span(("٢", 60, 66), ("١", 54, 60)), 12),
    ("string in order, drawn ٢١", span(("٢", 54, 60), ("١", 60, 66)), 21),
    ("Latin 21 drawn left-to-right", span(("2", 54, 60), ("1", 60, 66)), 21),
    ("two numerals in one span is not a footer", span(("١", 54, 60), ("٢", 60, 66), ("٢", 120, 126), ("١", 126, 132)), None),
    # the cover's version and year sit in the same band: digits inside a sentence are not a footer
    ("digits inside a sentence", span(("٤", 508.9, 506.6), ("١", 504.4, 502.3), ("ن", 495.4, 491.6)), None),
)


def main() -> int:
    failed = 0
    for label, s, want in CASES:
        got = V._digit_value(s)
        ok = got == want
        print(f"{'PASS' if ok else 'FAIL'} digit-value - {label}: {got!r} (want {want!r})")
        failed += 0 if ok else 1

    # Page level: the footer band of a synthetic page, with the other number printed in the body.
    # A Base-14 font has no Arabic-Indic digits (they come out as middots), so the page is set in the same
    # family the documents print with; a missing font is a failure of the fixture, not a reason to skip.
    font = "/System/Library/Fonts/GeezaPro.ttc"
    if not os.path.exists(font):
        raise SystemExit(f"fixture: {font} is missing — this test needs a font that carries U+0660..U+0669")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((54, 800), "١٢", fontsize=12, fontname="Geeza", fontfile=font)  # footer band 770..830
    page.insert_text((54, 100), "٢١", fontsize=12, fontname="Geeza", fontfile=font)  # body: the reverse token
    got = V.footer_numbers(page)
    ok = got == [12]
    print(f"{'PASS' if ok else 'FAIL'} footer-band - a synthetic page printing ١٢ in the footer and ٢١ in the "
          f"body reads {got} (want [12])")
    failed += 0 if ok else 1
    doc.close()

    if failed:
        print(f"\nDIGIT VALUE TEST FAILED — {failed} case(s)")
        return 1
    print("\nDIGIT VALUE TEST PASSED — geometry decides, and the reverse token on the page changes nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
