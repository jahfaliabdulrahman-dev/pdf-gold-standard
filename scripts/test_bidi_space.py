#!/usr/bin/env python3
"""The space-mapping repair must be decided by a NAMED mark, not by how often a glyph is drawn.

Two defects, one rule each:

  · Chrome sometimes maps the glyph it uses for a SPACE to a bidi control (U+200F). Readers that trust
    /ToUnicode then read every word boundary as a control — measured on Najd, one page's word order went
    0.14 -> 0.83 when it was repaired. Such a glyph must be renamed to U+0020 even when the page draws it ONCE
    (a single-word caption is still a word with a space), which is why a "drawn at least N times" threshold is
    wrong and was removed.
  · A directional mark that OUR text layer placed must never be renamed. The layer publishes those CIDs in
    `/PLMarkCids`; renaming one turns a deliberate LRM into a space and reverses a correctly ordered amount in
    Preview (measured: `-6,006.965` read back as `6,006.965-` while the page printed the sign on the left).

No engine, no corpus: two pages are built by hand.
"""
import os
import sys

import pikepdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import postprocess  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def cmap(mapping: dict[int, str]) -> bytes:
    body = "".join(f"<{cid:04X}> <{ord(ch):04X}>\n" for cid, ch in mapping.items())
    return ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
            "/CMapName /T def 1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
            f"{len(mapping)} beginbfchar\n{body}endbfchar\n"
            "endcmap CMapName currentdict /CMap defineresource pop end end\n").encode("latin-1")


def build(path: str, mark_cids: list[int] | None, occurrences: int) -> None:
    """One page, one Type0 font: CID 3 is mapped to U+200F with a space's advance, CID 5 is a word glyph."""
    pdf = pikepdf.Pdf.new()
    desc = pikepdf.Dictionary({"/Type": pikepdf.Name("/FontDescriptor"), "/FontName": pikepdf.Name("/T"),
                               "/Flags": 4, "/FontBBox": [0, 0, 1000, 1000], "/ItalicAngle": 0,
                               "/Ascent": 800, "/Descent": -200, "/CapHeight": 700, "/StemV": 80})
    font = pdf.make_indirect(pikepdf.Dictionary({
        "/Type": pikepdf.Name("/Font"), "/Subtype": pikepdf.Name("/Type0"), "/BaseFont": pikepdf.Name("/T"),
        "/Encoding": pikepdf.Name("/Identity-H"),
        "/DescendantFonts": pdf.make_indirect(pikepdf.Array([pikepdf.Dictionary({
            "/Type": pikepdf.Name("/Font"), "/Subtype": pikepdf.Name("/CIDFontType2"), "/BaseFont": pikepdf.Name("/T"),
            "/CIDSystemInfo": pikepdf.Dictionary({"/Registry": pikepdf.String("Adobe"),
                                                  "/Ordering": pikepdf.String("Identity"), "/Supplement": 0}),
            "/FontDescriptor": desc, "/DW": 600, "/W": pikepdf.Array([3, pikepdf.Array([236.0]),
                                                                     5, pikepdf.Array([600.0])]),
        })])),
        "/ToUnicode": pdf.make_stream(cmap({3: "\u200f", 5: "\u0628"})),
    }))
    if mark_cids:
        font["/PLMarkCids"] = pikepdf.Array(mark_cids)
    word = b"<0005> Tj"
    content = b"BT\n/F1 12 Tf\n1 0 0 -1 72 700 Tm\n" + word
    for _ in range(occurrences - 1):
        content += b" <0003> Tj" + word            # a space between words, drawn `occurrences - 1` times
    content += b"\nET\n"
    page = pikepdf.Dictionary({"/Type": pikepdf.Name("/Page"), "/MediaBox": [0, 0, 595, 842],
                               "/Contents": pdf.make_stream(content),
                               "/Resources": pikepdf.Dictionary({"/Font": pikepdf.Dictionary({"/F1": font})})})
    pages = pdf.make_indirect(pikepdf.Dictionary({"/Type": pikepdf.Name("/Pages"),
                                                  "/Kids": pdf.make_indirect(pikepdf.Array([page])), "/Count": 1}))
    page["/Parent"] = pages
    pdf.Root["/Pages"] = pages
    pdf.save(path)


def mapping_of(path: str) -> dict[str, str]:
    with pikepdf.open(path) as pdf:
        font = pdf.pages[0].obj["/Resources"]["/Font"]["/F1"]
        src = font["/ToUnicode"].read_bytes().decode("latin-1")
    import re
    return dict(re.findall(r"<([0-9A-Fa-f]{4})>\s*<([0-9A-Fa-f]{4})>", src))


def main() -> int:
    tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), "bidi-space-guard")
    os.makedirs(tmp, exist_ok=True)

    one = os.path.join(tmp, "one-space.pdf")
    build(one, None, occurrences=2)                # ONE space on the page
    with pikepdf.open(one) as pdf:
        postprocess.feature_bidi_space(pdf)
        pdf.save(one + ".out")
    got = mapping_of(one + ".out").get("0003")
    check("single-space-repaired", got == "0020", f"CID 3 maps to {got!r}, expected '0020'")

    marked = os.path.join(tmp, "marked.pdf")
    build(marked, [3], occurrences=2)
    with pikepdf.open(marked) as pdf:
        postprocess.feature_bidi_space(pdf)
        pdf.save(marked + ".out")
    got = mapping_of(marked + ".out").get("0003")
    check("declared-mark-preserved", got == "200F", f"CID 3 maps to {got!r}, expected '200F'")

    print()
    if FAILS:
        print(f"BIDI-SPACE GUARD FAILED — {len(FAILS)}: {', '.join(FAILS)}")
        return 1
    print("BIDI-SPACE GUARD PASSED — a single space is repaired, a declared mark is not")
    return 0


if __name__ == "__main__":
    sys.exit(main())
