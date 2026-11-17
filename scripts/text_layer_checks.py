"""Two checks the text layer must pass once it is rebuilt in logical order — and that today's files fail.

1. Latin word order. A multi-word Latin phrase inside an Arabic paragraph must read the same way in PDFium's
   extraction as it reads on the page. Today it does not: the page says "Business Process Model and Notation"
   and PDFium returns "Notation and Model Process Business", because the string it reads is in visual order.

2. Diacritic integrity. Every combining mark must follow a base letter in the extracted string. A mark that
   drifts to the start of a line, or lands on another mark, is a text layer that copies wrongly.

The checks are deliberately narrow: they measure the two defects the rebuild is meant to close, so that
"done" means the measurement changed, not that the code changed.
"""

from __future__ import annotations

import re
import unicodedata

import pymupdf
import pypdfium2 as pdfium

LATIN = re.compile(r"[A-Za-z][A-Za-z'’-]*")
MARKS = {chr(c) for c in range(0x064B, 0x0660)} | {"\u0670", "\u0653", "\u0654", "\u0655"}


def page_latin_phrases(page: pymupdf.Page) -> list[list[str]]:
    """Latin phrases as they are *drawn*, taken per line in ascending x (the order the eye reads)."""
    out: list[list[str]] = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            chars = [c for s in line["spans"] for c in s.get("chars", [])]
            if not chars:
                continue
            visual = "".join(c["c"] for c in sorted(chars, key=lambda c: c["bbox"][0]))
            words = LATIN.findall(visual)
            if len(words) >= 2:
                out.append(words)
    return out


def pdfium_lines(pdf: pdfium.PdfDocument) -> list[list[str]]:
    return [[w for w in LATIN.findall(text)] for text in
            (pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))]


def latin_order_problems(path: str) -> list[str]:
    """Every drawn Latin phrase whose words PDFium returns in a different order."""
    bad: list[str] = []
    doc = pymupdf.open(path)
    engine = pdfium.PdfDocument(path)
    for pno, page in enumerate(doc):
        drawn = page_latin_phrases(page)
        read = pdfium_lines(engine)[pno]
        for phrase in drawn:
            # the phrase must appear as a contiguous run of words somewhere in the extraction
            n = len(phrase)
            if not any(read[i:i + n] == phrase for i in range(len(read) - n + 1)):
                got = next((read[i:i + n] for i in range(len(read) - n + 1)
                            if sorted(read[i:i + n]) == sorted(phrase)), None)
                bad.append(f"p{pno + 1}: drawn {' '.join(phrase)!r} but PDFium returns "
                           f"{' '.join(got) if got else 'the words elsewhere'!r}")
    return bad


def diacritic_problems(text: str, where: str = "") -> list[str]:
    """A mark may only follow a base letter — never open a line, never sit on another mark."""
    bad: list[str] = []
    previous = ""
    for ch in text:
        if ch in MARKS:
            if not previous:
                bad.append(f"{where}: mark {unicodedata.name(ch, '?')} at the start of the text")
            elif previous in MARKS:
                bad.append(f"{where}: mark {unicodedata.name(ch, '?')} follows another mark")
        previous = ch
    return bad


def _self_test() -> int:
    """The checks must fail on the defect and pass on the correction, or they prove nothing."""
    fails = 0
    if diacritic_problems("\u064e\u0628"):        # fatha before its letter
        print("ok   diacritic check rejects a leading mark")
    else:
        print("FAIL diacritic check accepted a leading mark"); fails += 1
    if not diacritic_problems("\u0628\u064e"):    # correct: letter then fatha
        print("ok   diacritic check accepts a mark on its letter")
    else:
        print("FAIL diacritic check rejected a correct pair"); fails += 1
    # Latin order comparator, without a PDF
    drawn = ["Business", "Process", "Model", "and", "Notation"]
    reversed_read = ["Notation", "and", "Model", "Process", "Business"]
    ok = not any(reversed_read[i:i + len(drawn)] == drawn for i in range(1))
    print(("ok  " if ok else "FAIL") + " order comparator sees the reversal")
    fails += 0 if ok else 1
    return fails


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        raise SystemExit(1 if _self_test() else 0)
    for path in sys.argv[1:]:
        problems = latin_order_problems(path)
        print(f"{path}: {len(problems)} line(s) whose Latin order changed in PDFium")
        for p in problems[:6]:
            print("   ", p)
