#!/usr/bin/env python3
"""G#5: the producer starts a composite identifier on its own display line; the inline layout is the defect.

Measured (2026-11-20): in one paragraph, `الفاتورة: INV-2026-0042` is read `-2026-0042INV` by PDFium and
`0042-2026-INV` by PDFKit. Source isolation (`<bdi dir=ltr>`, `span`, `inline-block`) and LRM/RLM/LRI/LRE/RLE
marks at the edges did not fix both readers (a trailing LRM fixed PDFKit only). The producer rule that does
fix both is one `<br>` before the identifier when it follows Arabic: the identifier starts a separate display
line, while the case's logical text is unchanged (a line break is whitespace to `metrics.N`), so the truth and
the other readers' floors do not move.

This test builds the two cases with the rule (exact 1.0 in both tier-1 readers) and with the rule disabled
(`html._ARABIC` made never-matching) to show the defect it exists for. If a reader ever accepts the inline
layout, the defect half fails and the design can be revisited.

Runs: `python3 conformance/tests/test_identifier_isolation.py` (needs CHROME_PATH).
"""
import os
import re
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

import pypdfium2

from conformance.adapters import chrome, html
from conformance.checks import metrics, structure
from conformance.corpus import cases
from conformance.readers import text_many

FAILED = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def pdfium_text(pdf: str) -> str:
    doc = pypdfium2.PdfDocument(pdf)
    text = "\n".join(p.get_textpage().get_text_range() for p in doc)
    doc.close()
    return text


def measured(pdf: str, case: dict) -> dict:
    truth = structure._truth_text(case)
    out = {"pdfium": pdfium_text(pdf), "pdfkit": text_many("pdfkit", [pdf])[0]}
    return {name: metrics.measure(text, truth)["metrics"] for name, text in out.items()}


def main() -> int:
    corpus = {c["id"]: c for c in cases.load_all()}
    tmp = tempfile.mkdtemp(prefix="identifier-isolation-")
    cids = ("num-invoice-latn", "num-ids-latn-in-arab")

    for cid in cids:
        if cid not in corpus:
            check(f"{cid}:case-exists", False, "the case is missing from the corpus")
            continue
        case = corpus[cid]
        out = os.path.join(tmp, f"{cid}.pdf")
        chrome.render_case(case, out, "chrome")
        got = measured(out, case)
        for reader in ("pdfium", "pdfkit"):
            check(f"{cid}:{reader}:separated", got[reader]["exact"] == 1.0,
                  f"exact {got[reader]['exact']} order {got[reader]['order']:.2f}")

    # The witness: the same case with the line-break rule disabled. `_inline` still isolates the amount; only
    # the identifier break disappears, which is the layout the readers reorder.
    original = html._ARABIC
    html._ARABIC = re.compile(r"(?!x)x")
    try:
        for cid in cids:
            if cid not in corpus:
                continue
            case = corpus[cid]
            out = os.path.join(tmp, f"{cid}-inline.pdf")
            chrome.render_case(case, out, "chrome")
            got = measured(out, case)
            for reader in ("pdfium", "pdfkit"):
                check(f"{cid}:{reader}:inline-broken", got[reader]["exact"] == 0.0,
                      f"exact {got[reader]['exact']} — the inline layout no longer reproduces the defect; "
                      f"revisit the G#5 producer rule")
    finally:
        html._ARABIC = original

    if FAILED:
        print("\nTEST FAILED —", FAILED)
        return 1
    print("\nIDENTIFIER-ISOLATION GUARD PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
