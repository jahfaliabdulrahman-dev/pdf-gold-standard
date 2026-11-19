#!/usr/bin/env python3
"""The four Preview (`pdfkit`) money failures, classified — and the trigger matrix behind them.

This is a DIAGNOSTIC, not a gate. It builds the corpus money cases twice (the installed pipeline and raw
Chrome) and a set of controlled one-block probes, then prints each reader's exact reading. The question it
answers is the G#1b one: *what* does Preview get wrong in an amount, and under which conditions.

Measured with PDFKit 27.2.1 (macOS 27.2) and pypdfium2 5.15.2 on CfT 157.0.8103.78. The internal rule of
PDFKit is not observable (closed framework), so this script claims only what it prints: the reading, the
metrics, and which probe conditions reproduce the split. `fix_text_layer` is not the cause: for every corpus
case the `chrome-raw` reading is printed beside the installed one.

Usage: `CHROME_PATH=<CfT binary> python3 scripts/preview_money_probe.py [--out DIR]`
"""
import argparse
import os
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REPO)

from conformance.adapters import chrome                      # noqa: E402
from conformance.checks import metrics                       # noqa: E402
from conformance.corpus import cases as corpus_cases         # noqa: E402
from conformance.corpus.truth import truth                   # noqa: E402
from conformance.readers import text_many                    # noqa: E402

CORPUS = ("mon-decimal-table", "mon-negative-hindi", "mon-riyal-sign", "mon-rs-abbrev")
HEADING = {"type": "heading", "level": 1, "text": "مبلغ"}
PROBES = {
    "no-separator": "المبلغ ١٢٠٠٠٠٠ ريال.",
    "decimal-3-3": "المبلغ ١٢٣٫٤٠٠ ريال.",
    "decimal-4-3": "المبلغ ١٢٣٤٫٠٠٠ ريال.",
    "thousands+decimal": "المبلغ ١٬٢٠٠٫٠٠٠ ريال.",
    "latin-ascii": "المبلغ 1,200.000 ريال.",
    "line-start": "-٦٬٠٠٦٫٩٦٥",                 # the amount is the whole line, first and last glyph run
}


def read(reader: str, path: str) -> str:
    return text_many(reader, [path])[0]


def shape(text: str) -> str:
    """The reading with letter FORM differences folded — NFKC maps a presentation form to its base letter, and
    Chrome's raw `/ToUnicode` carries a NUL for a glyph it cannot name. The line/fragment structure is kept:
    that is what this probe compares."""
    return unicodedata.normalize("NFKC", text).replace("\x00", "")


def exact(reader: str, path: str, case: dict) -> float:
    return metrics.measure(read(reader, path), truth(case))["metrics"]["exact"]


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--out", default=None, help="directory for the built PDFs (default: a temp dir, removed)")
    args = ap.parse_args()
    out = args.out or tempfile.mkdtemp(prefix="preview-money-")
    os.makedirs(out, exist_ok=True)
    print(f"out: {out}")

    cases = {c["id"]: c for c in corpus_cases.load_all()}
    print("\n## the corpus money cases — installed pipeline vs raw Chrome\n")
    print(f"{'case':22s} {'pdfium':>7s} {'pdfkit':>7s} {'pk-raw':>7s} {'raw-fails':>9s}  same-shape?")
    raw_fails = 0
    for cid in CORPUS:
        case = cases[cid]
        fixed = os.path.join(out, f"{cid}.pdf")
        raw = os.path.join(out, f"{cid}.raw.pdf")
        chrome.render_case(case, fixed, "chrome")
        chrome.render_case(case, raw, "chrome-raw")
        pk_fixed, pk_raw = read("pdfkit", fixed), read("pdfkit", raw)
        raw_failed = exact("pdfkit", raw, case) != 1.0
        raw_fails += int(raw_failed)
        print(f"{cid:22s} {exact('pdfium', fixed, case):7.0f} {exact('pdfkit', fixed, case):7.0f} "
              f"{exact('pdfkit', raw, case):7.0f} {int(raw_failed):9d}  "
              f"{'yes' if shape(pk_fixed) == shape(pk_raw) else 'no'}")

    print("\n## Preview's reading of the four failures\n")
    for cid in CORPUS:
        case = cases[cid]
        fixed = os.path.join(out, f"{cid}.pdf")
        print(f"--- {cid}\n    truth : {truth(case)!r}\n    pdfkit: {read('pdfkit', fixed)!r}")

    print("\n## controlled probes (one paragraph under a heading, chrome engine)\n")
    print(f"{'probe':18s} {'text':30s} {'pdfium':>7s} {'pdfkit':>7s}")
    for name, text in PROBES.items():
        case = {"id": f"probe-{name}", "category": "money", "lang": "ar", "font": "plex",
                "note": "preview money probe", "blocks": [HEADING, {"type": "paragraph", "text": text}]}
        path = os.path.join(out, f"probe-{name}.pdf")
        chrome.render_case(case, path, "chrome")
        print(f"{name:18s} {text:30s} {exact('pdfium', path, case):7.0f} {exact('pdfkit', path, case):7.0f}")
        if exact("pdfkit", path, case) != 1.0:
            print(f"{'':18s} pdfkit reads {read('pdfkit', path)!r}")

    print("\n## the sign at line start (the G#1 open case)\n")
    case = {"id": "probe-line-start", "category": "money", "lang": "ar", "font": "plex",
            "note": "signed amount is the whole line", "blocks": [HEADING, {"type": "paragraph", "text": PROBES["line-start"]}]}
    path = os.path.join(out, "probe-line-start.pdf")
    chrome.render_case(case, path, "chrome")
    print(f"truth : {truth(case)!r}")
    print(f"pdfium: {read('pdfium', path)!r}  (exact {exact('pdfium', path, case):.0f})")
    print(f"pdfkit: {read('pdfkit', path)!r}  (exact {exact('pdfkit', path, case):.0f})")

    if raw_fails != len(CORPUS):
        print(f"\n{len(CORPUS) - raw_fails} of {len(CORPUS)} failures do NOT reproduce on raw Chrome — the text layer")
        print("is a factor for those cases and this probe cannot attribute them to Chrome.")
        return 1
    print("\nAll four failures reproduce on Chrome's own output (pdfkit exact 0 before fix_text_layer), so the")
    print("split is Chrome's. `same-shape?` says whether our layer changes the fragment grouping; it does for")
    print("the cases marked no — the failure is present either way. The probes name the conditions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
