"""Read back the text a reader extracts from the generated appearance streams.

Each widget's /AP is turned into the only thing page 0 draws, and PDFium's own
text page is asked for the characters. A shaped run writes glyph ids, which the
document's /ToUnicode need not cover, so the stream carries the run's characters
as /ActualText (ISO 32000-1, 14.9.4); this stage is what holds that claim.

Whitespace at the edges of a run is compared loosely: PDFium places a marked
content sequence's text at the position of its first text object, so a space
that sits at the visual edge of a run comes out at the front of that run instead
of its back. Every other character is compared exactly.

Run:  .venv/bin/python scripts/pdfium_fields/measure_text.py after.pdf \
          --pdfium-out ~/pdfium/pdfium/out/Release
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import pikepdf
from pikepdf import Dictionary, Name

# field -> the value it holds, as the extractor should read it back.
EXPECTED = {
    "ar": "لا",
    "q0": "الصفحة",
    "ltr_mixed": "abc الصفحة def",
    "mixed": "الصفحة 5 من 10",
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

    for failure in failures:
        print("FAIL", failure)
    print("RESULT", "PASS" if not failures else "FAIL")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
