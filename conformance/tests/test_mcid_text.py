#!/usr/bin/env python3
"""The tag reader must read every shape a producer writes — not only the one our pipeline happens to write.

Two defects were found by E3 on competitors' files, and neither could be seen on our own output:

  · `TJ` takes ONE array operand (`[(...)-40(...)]TJ`), and the reader iterated the operand list instead of the
    array, so the decoder received an Array and returned b"" — a silent empty string.
  · `/Resources` is inheritable (PDF 32000-1 §7.7.3.4); reading only the page's own key found no fonts at all.

Both made three checks accuse Typst and WeasyPrint of carrying no text. This test builds a page in each shape by
hand — no engine, no corpus — and asserts the reader returns the text and the MCID it was written under.
"""
import os
import sys
import tempfile

import pikepdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from conformance.checks import mcid_text          # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def make_pdf(path: str, operator: str) -> None:
    """One page, one font with a two-byte ToUnicode, one tagged span drawn with `Tj` or `TJ`."""
    pdf = pikepdf.Pdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary({
        "/Type": pikepdf.Name("/Font"), "/Subtype": pikepdf.Name("/Type0"),
        "/BaseFont": pikepdf.Name("/TestFont"),
        "/Encoding": pikepdf.Name("/Identity-H"),
        "/DescendantFonts": pdf.make_indirect(pikepdf.Array([pikepdf.Dictionary({
            "/Type": pikepdf.Name("/Font"), "/Subtype": pikepdf.Name("/CIDFontType2"),
            "/BaseFont": pikepdf.Name("/TestFont"),
            "/CIDSystemInfo": pikepdf.Dictionary({"/Registry": pikepdf.String("Adobe"),
                                                  "/Ordering": pikepdf.String("Identity"),
                                                  "/Supplement": 0}),
            "/FontDescriptor": pikepdf.Dictionary({"/Type": pikepdf.Name("/FontDescriptor"),
                                                   "/FontName": pikepdf.Name("/TestFont"),
                                                   "/Flags": 4, "/FontBBox": [0, 0, 1000, 1000],
                                                   "/ItalicAngle": 0, "/Ascent": 800, "/Descent": -200,
                                                   "/CapHeight": 700, "/StemV": 80}),
            "/DW": 1000,
        })])),
        "/ToUnicode": pdf.make_stream(
            b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
            b"/CMapName /Test def 1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
            b"2 beginbfchar <0001> <0628> <0002> <0627> endbfchar\n"
            b"endcmap CMapName currentdict /CMap defineresource pop end end\n"),
    }))
    draw = b"<00010002> Tj" if operator == "Tj" else b"[<00010002>] TJ"
    content = b"/Span << /MCID 0 >> BDC\nBT\n/F1 12 Tf\n" + draw + b"\nET\nEMC\n"
    page = pikepdf.Dictionary({
        "/Type": pikepdf.Name("/Page"), "/MediaBox": [0, 0, 595, 842], "/Contents": pdf.make_stream(content),
        "/Resources": pikepdf.Dictionary({"/Font": pikepdf.Dictionary({"/F1": font})}),
    })
    pdf.pages.append(pikepdf.Page(page))
    pdf.save(path)


def make_pdf_inherited(path: str) -> None:
    """The same page, but `/Resources` lives on the /Pages node — legal, and how Typst/WeasyPrint write."""
    pdf = pikepdf.Pdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary({
        "/Type": pikepdf.Name("/Font"), "/Subtype": pikepdf.Name("/Type0"),
        "/BaseFont": pikepdf.Name("/TestFont"), "/Encoding": pikepdf.Name("/Identity-H"),
        "/DescendantFonts": pdf.make_indirect(pikepdf.Array([pikepdf.Dictionary({
            "/Type": pikepdf.Name("/Font"), "/Subtype": pikepdf.Name("/CIDFontType2"),
            "/BaseFont": pikepdf.Name("/TestFont"),
            "/CIDSystemInfo": pikepdf.Dictionary({"/Registry": pikepdf.String("Adobe"),
                                                  "/Ordering": pikepdf.String("Identity"),
                                                  "/Supplement": 0}),
            "/FontDescriptor": pikepdf.Dictionary({"/Type": pikepdf.Name("/FontDescriptor"),
                                                   "/FontName": pikepdf.Name("/TestFont"),
                                                   "/Flags": 4, "/FontBBox": [0, 0, 1000, 1000],
                                                   "/ItalicAngle": 0, "/Ascent": 800, "/Descent": -200,
                                                   "/CapHeight": 700, "/StemV": 80}),
            "/DW": 1000,
        })])),
        "/ToUnicode": pdf.make_stream(
            b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
            b"/CMapName /Test def 1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
            b"2 beginbfchar <0001> <0628> <0002> <0627> endbfchar\n"
            b"endcmap CMapName currentdict /CMap defineresource pop end end\n"),
    }))
    page = pikepdf.Dictionary({"/Type": pikepdf.Name("/Page"), "/MediaBox": [0, 0, 595, 842],
                               "/Contents": pdf.make_stream(b"/Span << /MCID 0 >> BDC\nBT\n/F1 12 Tf\n"
                                                           b"[<00010002>] TJ\nET\nEMC\n")})
    root = pdf.make_indirect(pikepdf.Dictionary({
        "/Type": pikepdf.Name("/Pages"), "/Kids": pdf.make_indirect(pikepdf.Array([page])), "/Count": 1,
        "/Resources": pikepdf.Dictionary({"/Font": pikepdf.Dictionary({"/F1": font})}),
    }))
    page["/Parent"] = root
    pdf.Root["/Pages"] = root
    pdf.save(path)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="mcid-text-")
    for operator in ("Tj", "TJ"):
        path = os.path.join(tmp, f"{operator}.pdf")
        make_pdf(path, operator)
        scan = mcid_text.scan(path)
        check(f"tj-array:{operator}", scan["text"].get((1, 0)) == "با",
              f"got {scan['text']!r} codes={scan['codes']}")
    path = os.path.join(tmp, "inherited.pdf")
    make_pdf_inherited(path)
    scan = mcid_text.scan(path)
    check("inherited-resources", scan["text"].get((1, 0)) == "با",
          f"got {scan['text']!r} fonts={list(scan['fonts'])}")
    # The per-font rows are the checker's numbers: they must sum to the file totals, or two readers of the
    # same file would report two different gap counts.
    check("per-font-rows-sum-to-file-totals",
          sum(r["codes"] for r in scan["fonts"].values()) == scan["codes"]
          and sum(r["missing_unicode"] for r in scan["fonts"].values()) == scan["missing_unicode"]
          and sum(r["notdef"] for r in scan["fonts"].values()) == scan["notdef"],
          f"codes {sum(r['codes'] for r in scan['fonts'].values())}/{scan['codes']} "
          f"gaps {sum(r['missing_unicode'] for r in scan['fonts'].values())}/{scan['missing_unicode']}")
    print()
    if FAILS:
        print(f"MCID-TEXT GUARD FAILED — {len(FAILS)}: {', '.join(FAILS)}")
        return 1
    print("MCID-TEXT GUARD PASSED — Tj, TJ arrays and inherited /Resources all read")
    return 0


if __name__ == "__main__":
    sys.exit(main())
