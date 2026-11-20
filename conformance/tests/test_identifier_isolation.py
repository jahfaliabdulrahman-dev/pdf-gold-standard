#!/usr/bin/env python3
"""G#5: a declared identifier starts on its own display line; the inline layout is the defect.

Measured (2026-11-20): in one paragraph, `الفاتورة: INV-2026-0042` is read `-2026-0042INV` by PDFium and
`0042-2026-INV` by PDFKit. Source isolation (`<bdi dir=ltr>`, `span`, `inline-block`) and LRM/RLM/LRI/LRE/RLE
marks at the edges did not fix both readers (a trailing LRM fixed PDFKit only). The producer rule that does fix
both is one `<br>` before a **declared** identifier (the `INV-` prefix, the IBAN ungrouped or grouped in
4-digit blocks), while the case's logical text is unchanged (a line break is whitespace to `metrics.N`), so the
truth and the other readers' floors do not move.

The rule is a declared format, not a shape: `PDF-1.7`, `ISO-9001`, `COVID-19`, `PDF/UA-1` and `PDF/A-3` must not
take a line of their own; a slash-suffixed invoice and a grouped IBAN after an Arabic label must. The trigger is
Arabic or the paragraph start (the RTL template); a Latin-only line is deliberately left untouched.

Runs: `python3 conformance/tests/test_identifier_isolation.py` (needs CHROME_PATH).
"""
import os
import re
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

from conformance.adapters import chrome, html
from conformance.checks import metrics, structure
from conformance.corpus import cases
from conformance.readers import text_many, version_of

FAILED = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def _version_tuple(text: str) -> tuple[int, int]:
    """`PDFKit 15.8.2` -> (15, 8); the test's version gate, not a reader decision."""
    parts = re.findall(r"\d+", text or "")
    return (int(parts[0]), int(parts[1])) if len(parts) >= 2 else (0, 0)


def texts(pdf: str) -> dict:
    return {"pdfium": text_many("pdfium", [pdf])[0], "pdfkit": text_many("pdfkit", [pdf])[0]}


def measured(pdf: str, case: dict) -> dict:
    truth = structure._truth_text(case)
    return {name: metrics.measure(text, truth)["metrics"] for name, text in texts(pdf).items()}


def main() -> int:
    # The declared formats: positives get a line of their own, negatives never do.
    positives = {
        "invoice": "الفاتورة: INV-2026-0042",
        "invoice-slash": "الفاتورة: INV-2026-0042/1",
        "iban": "الآيبان: SA0380000000608010167519",
        "iban-grouped": "الآيبان: SA03 8000 0000 6080 1016 7519",
        "line-start": "INV-2026-0042 — الفاتورة",
    }
    negatives = {
        "latin-label": "IBAN: SA03 8000 0000 6080 1016 7519",
        "version": "الإصدار PDF-1.7",
        "standard": "المواصفة ISO-9001",
        "disease": "جائحة COVID-19",
        "pdfua": "معيار PDF/UA-1",
        "pdfa": "معيار PDF/A-3",
        "lowercase-version": "الإصدار v2.3.6",
    }
    for name, text in positives.items():
        rendered = html._inline(text)
        check(f"format:{name}", "<br>" in rendered, rendered)
    for name, text in negatives.items():
        rendered = html._inline(text)
        check(f"format:{name}:no-break", "<br>" not in rendered, rendered)

    corpus = {c["id"]: c for c in cases.load_all()}
    tmp = tempfile.mkdtemp(prefix="identifier-isolation-")
    cids = ("num-invoice-latn", "num-ids-latn-in-arab")
    kit_version = version_of("pdfkit")

    for cid in cids:
        if cid not in corpus:
            check(f"{cid}:case-exists", False, "the case is missing from the corpus")
            continue
        case = corpus[cid]
        out = os.path.join(tmp, f"{cid}.pdf")
        chrome.render_case(case, out, "chrome")
        got = measured(out, case)
        check(f"{cid}:pdfium:separated", got["pdfium"]["exact"] == 1.0,
              f"exact {got['pdfium']['exact']} order {got['pdfium']['order']:.2f}")
        if _version_tuple(kit_version) < (27, 2):
            print(f"NOTE {cid}:pdfkit:separated - {kit_version} < 27.2.1: the split-layout exact is a declared "
                  f"older-reader limit (order {got['pdfkit']['order']:.2f}); the certificate PASS is on 27.2.1")
        else:
            check(f"{cid}:pdfkit:separated", got["pdfkit"]["exact"] == 1.0,
                  f"exact {got['pdfkit']['exact']} order {got['pdfkit']['order']:.2f}")

    # The defect half: the same cases with the break disabled. Assert the specific misreadings (an empty or
    # garbage layer also has exact 0.0, so an exact-only check would pass vacuously).
    html.BREAK_IDENTIFIERS = False
    try:
        for cid in cids:
            if cid not in corpus:
                continue
            case = corpus[cid]
            out = os.path.join(tmp, f"{cid}-inline.pdf")
            chrome.render_case(case, out, "chrome")
            got = texts(out)
            check(f"{cid}:inline:non-empty", bool(got["pdfium"].strip()) and bool(got["pdfkit"].strip()),
                  repr(got)[:200])
            if cid == "num-invoice-latn":
                check("num-invoice-latn:inline:pdfium", "-2026-0042INV" in got["pdfium"], got["pdfium"][-120:])
                check("num-invoice-latn:inline:pdfkit", "0042-2026-INV" in got["pdfkit"], got["pdfkit"][-120:])
            else:
                check("num-ids-latn-in-arab:inline:pdfium",
                      "SA0380000000608010167519 :الآيبان" in got["pdfium"]
                      and "INV-2026-0042 :الفاتورة" in got["pdfium"], got["pdfium"][-160:])
                check("num-ids-latn-in-arab:inline:pdfkit", "0042-2026-INV" in got["pdfkit"], got["pdfkit"][-120:])
    finally:
        html.BREAK_IDENTIFIERS = True

    if FAILED:
        print("\nTEST FAILED —", FAILED)
        return 1
    print("\nIDENTIFIER-ISOLATION GUARD PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
