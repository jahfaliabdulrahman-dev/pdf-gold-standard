"""Read back the text a reader extracts from the generated appearance streams.

Each widget's /AP is turned into the only thing page 0 draws, and PDFium's own
text page is asked for the characters. A shaped run writes glyph ids, which the
document's /ToUnicode need not cover, so the stream draws the run with a copy of
the font whose /ToUnicode maps each glyph id to the character it carries
(ISO 32000-1, 9.10.3); this stage is what holds that claim.

Two fields are read more loosely, each for a reason that is measured and
recorded in docs/pdfium-arabic-fields/:

* Whitespace is normalised, because a space at the visual edge of a run comes
  back at the front of it.
* A vocalized word is compared as one of each character and its letters in the
  order a reader walks them, because a mark is drawn above the baseline and
  PDFium's text page starts a new line at a raised glyph, so the word comes back
  in visual order with breaks between the letters and their marks. The order of
  the marks inside one cluster is the shaper's, not the map's; which glyph draws
  which character is what the codes above pin against HarfBuzz (docs 29, 5).

Run:  .venv/bin/python scripts/pdfium_fields/measure_text.py after.pdf \
          --pdfium-out ~/pdfium/pdfium/out/Release
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import unicodedata

import pikepdf
from pikepdf import Dictionary, Name

# field -> the value it holds, as the extractor should read it back.
EXPECTED = {
    "ar": "لا",
    "q0": "الصفحة",
    "ltr_mixed": "abc الصفحة def",
    "mixed": "الصفحة 5 من 10",
}

# field -> the characters it holds, in any order. A base letter and the marks
# over it are drawn on different baselines, which splits them into separate
# lines when a reader walks the page; see the module comment.
CHARACTERS_ONLY = {
    "vocalized": "مُحَمَّد",
}


def appearance_only(source: pathlib.Path, field: str,
                    target: pathlib.Path) -> None:
    """Rewrite `source` so its page draws only the field's appearance."""
    pdf = pikepdf.open(source)
    page = pdf.pages[0]
    for annot in page["/Annots"]:
        if str(annot["/T"]) != field:
            continue
        stream = annot["/AP"]["/N"]
        if "/Subtype" not in stream:
            # The baseline build writes an appearance without /Subtype /Form,
            # which strict readers reject; the two shapes stay comparable.
            stream["/Subtype"] = Name("/Form")
        xobjects = Dictionary()
        xobjects[Name("/Fm0")] = stream
        resources = Dictionary()
        resources[Name("/XObject")] = xobjects
        page["/Resources"] = resources
        page["/Contents"] = pdf.make_stream(b"q 1 0 0 1 10 10 cm /Fm0 Do Q")
        del page["/Annots"]
        pdf.save(target)
        return
    raise SystemExit(f"field {field} not found in {source}")


def extracted(probe: pathlib.Path, pdf: pathlib.Path) -> str:
    out = subprocess.run([str(probe), str(pdf)], check=True, capture_output=True,
                         text=True).stdout.strip()
    prefix = out.split("text=", 1)
    if len(prefix) != 2:
        raise SystemExit(f"unexpected probe output: {out}")
    text = prefix[1]
    # The probe escapes every non-ASCII unit as \uXXXX.
    return bytes(text, "ascii").decode("unicode_escape")


def is_mark(unit):
    return unicodedata.category(unit) == "Mn"


def normalized(text: str) -> str:
    return " ".join(text.split())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=pathlib.Path)
    parser.add_argument("--pdfium-out", type=pathlib.Path, required=True)
    parser.add_argument("--work", type=pathlib.Path, default=None)
    args = parser.parse_args()

    probe = args.pdfium_out / "text_probe"
    if not probe.exists():
        raise SystemExit(f"no text_probe at {probe}")
    work = args.work or args.pdf.parent / "text"
    work.mkdir(parents=True, exist_ok=True)

    failures = []
    for field, expected in EXPECTED.items():
        page = work / f"{field}.pdf"
        appearance_only(args.pdf, field, page)
        got = extracted(probe, page)
        print(f"{field:12s} text={got!r}")
        if normalized(got) != normalized(expected):
            failures.append(f"{field}: {got!r} != {expected!r}")

    for field, expected in CHARACTERS_ONLY.items():
        page = work / f"{field}.pdf"
        appearance_only(args.pdf, field, page)
        got = extracted(probe, page)
        characters = [unit for unit in got if not unit.isspace()]
        # No character lost and none drawn twice, and the letters in the order a
        # reader walks them -- the text's own order reversed. The marks of one
        # cluster keep the order the shaper chose for them, which the map does
        # not decide; which glyph draws which character is what the codes above
        # pin against HarfBuzz.
        letters = [unit for unit in characters if not is_mark(unit)]
        expected_letters = [unit for unit in reversed(expected) if not is_mark(unit)]
        print(f"{field:12s} characters={characters!r}")
        if sorted(characters) != sorted(expected):
            failures.append(
                f"{field}: {sorted(characters)!r} != {sorted(expected)!r}"
            )
        elif letters != expected_letters:
            failures.append(
                f"{field}: letters {letters!r} are not the way round a reader "
                f"walks them {expected_letters!r}"
            )

    for failure in failures:
        print("FAIL", failure)
    print("RESULT", "PASS" if not failures else "FAIL")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
