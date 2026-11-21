#!/usr/bin/env python3
"""Build the measurement sets for `arabic-pdf-check` — deterministically, outside the repository.

Four planted files, each a named defect, and one clean base built by the pipeline itself:

  1. `planted-mupdf-logical`   — MuPDF writes logical Arabic (as it does), and 4 of the 5 readers return it
                                 reversed. Measured, not assumed: the file stores logical order and most
                                 readers paste it backwards.
  2. `planted-chrome-raw`      — the corpus case built by the raw engine, before `fix_text_layer`: the text
                                 layer carries presentation forms.
  3. `planted-presentation-forms` — MuPDF writes the same text with the presentation-form characters.
  4. `planted-no-tounicode`    — the clean Chrome file with every `/ToUnicode` removed: drawn codes with no
                                 Unicode value (Matterhorn 10-001 / 31-027).

No generated PDF is committed (the assignment's rule; and a fixture that drifts from its generator is a
measurement of the wrong file). `build_all` is imported by the tests, and the CLI writes the set to a
directory outside the repository for a manual run.
"""
import argparse
import os
import sys
import tempfile

import pikepdf
import pymupdf

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

from arafix.unicode_tables import PF_TO_BASE            # noqa: E402  (arafix is a declared dependency)
from conformance.adapters import chrome, fonts         # noqa: E402
from conformance.corpus import cases as corpus_cases   # noqa: E402

TEXT = "التاريخ ٢٠٢٦ والمبلغ 1,250.75 ريال.\nهذا سطر عربي ثانٍ للاختبار."
CASE_ID = "num-invoice-latn"

PLANTED = {
    "planted-mupdf-logical": "visual-order",
    "planted-chrome-raw": "presentation-forms",
    "planted-presentation-forms": "presentation-forms",
    "planted-no-tounicode": "tounicode-gaps",
}


def _mupdf_pdf(body: str, path: str) -> str:
    doc = pymupdf.open()
    try:
        page = doc.new_page(width=595, height=842)
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 800), body,
                            fontname="plex", fontfile=fonts.path("plex"), fontsize=14)
        doc.save(path)
    finally:
        doc.close()
    return path


def _presentation_forms(text: str) -> str:
    """The same letters as Arabic Presentation Forms — what a producer that bakes its output writes."""
    to_pf = {}
    for pf, base in PF_TO_BASE.items():
        to_pf.setdefault(base, pf)
    return "".join(to_pf.get(ch, ch) for ch in text)


def _strip_tounicode(source: str, path: str) -> str:
    removed = 0
    with pikepdf.open(source) as pdf:
        for page in pdf.pages:
            res = page.obj.get("/Resources")
            node = page.obj
            while res is None and node.get("/Parent") is not None:
                node = node.get("/Parent")
                res = node.get("/Resources")
            for _name, font in ((res or {}).get("/Font") or {}).items():
                if "/ToUnicode" in font:
                    del font["/ToUnicode"]
                    removed += 1
        if not removed:
            raise RuntimeError(f"{source}: no /ToUnicode to remove — the planted file would not be planted")
        pdf.save(path)
    return path


def build_all(out_dir: str | None = None) -> dict:
    """{'clean': path, 'planted': {name: path}} — refuses if the pipeline's own engine is unavailable."""
    out_dir = out_dir or tempfile.mkdtemp(prefix="checker-fixtures-")
    os.makedirs(out_dir, exist_ok=True)
    case = corpus_cases.by_id([CASE_ID])[0]
    clean = os.path.join(out_dir, "clean-chrome.pdf")
    chrome.render_case(case, clean, "chrome")
    raw = os.path.join(out_dir, "planted-chrome-raw.pdf")
    chrome.render_case(case, raw, "chrome-raw")
    planted = {
        "planted-mupdf-logical": _mupdf_pdf(TEXT, os.path.join(out_dir, "planted-mupdf-logical.pdf")),
        "planted-chrome-raw": raw,
        "planted-presentation-forms": _mupdf_pdf(_presentation_forms(TEXT),
                                                 os.path.join(out_dir, "planted-presentation-forms.pdf")),
        "planted-no-tounicode": _strip_tounicode(clean, os.path.join(out_dir, "planted-no-tounicode.pdf")),
    }
    return {"clean": clean, "planted": planted, "dir": out_dir}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None, help="a directory outside the repository")
    a = ap.parse_args()
    built = build_all(a.out)
    print(f"clean   {built['clean']}")
    for name, path in built["planted"].items():
        print(f"{name:28} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
