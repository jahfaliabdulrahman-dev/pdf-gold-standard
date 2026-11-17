"""Build the field fixtures that the appearance-stream measurement runs on.

REQUIRES `najd/Najd-Regular.ttf` (not shipped: the licence forbids redistributing the font); the
fixtures are what the unpublished PDFium branch `arabic-field-shaping@974afb6` is measured with.

Four widgets on one page:

  ar            Type0/Identity-H subset, value «لا»        the ligature case
  mixed         same font, value «الصفحة 5 من 10»          Arabic with digits
  latin         Helvetica, value «Business»                 classic field control
  nonidentity   same font, CIDToGIDMap as a stream, «لا»   the guard control

The Type0 font is a fontTools subset with `layout_features=['*']` and
`retain_gids=True`: it keeps GSUB (so «لا» shapes to one glyph) and keeps the
original glyph ids (so a CID can be the glyph id, ISO 32000-1 §9.7.5.2 NOTE 2).
`/W` carries each glyph's advance and `/ToUnicode` maps every emitted glyph —
including the ligature — back to the characters that produced it.

Run:  .venv/bin/python scripts/pdfium_fields/build_field_pdf.py out.pdf
"""

from __future__ import annotations

import argparse
import io
import pathlib

import pikepdf
import uharfbuzz as hb
from fontTools import subset
from fontTools.ttLib import TTFont
from pikepdf import Array, Dictionary, Name, String

PAGE_W = 612
PAGE_H = 792

# (name, default appearance, value, quadding, right x, top y, width)
FIELDS = [
    ("ar", "/F0 24 Tf 0 0 0 rg", "لا", 2, 560, 690, 300),
    ("mixed", "/F0 24 Tf 0 0 0 rg", "الصفحة 5 من 10", 2, 560, 610, 420),
    ("latin", "/F1 14 Tf 0 0 0 rg", "Business", 0, 560, 530, 200),
    ("nonidentity", "/F2 24 Tf 0 0 0 rg", "لا", 2, 560, 450, 300),
    # The two placement cases: a right-to-left run inside a left-to-right line,
    # and a single right-to-left run in a left-aligned field.
    ("ltr_mixed", "/F0 24 Tf 0 0 0 rg", "abc الصفحة def", 0, 560, 370, 420),
    ("q0", "/F0 24 Tf 0 0 0 rg", "الصفحة", 0, 560, 290, 420),
    ("center", "/F0 24 Tf 0 0 0 rg", "الصفحة", 1, 560, 210, 420),
    # A cluster of a base letter and the marks drawn over it: one cluster of
    # several glyphs, the shape a per-glyph CMap would have to name. Measured,
    # not gated -- docs/27 4 records what it does today.
    ("vocalized", "/F0 24 Tf 0 0 0 rg", "مُحَمَّد", 2, 560, 130, 420),
]


def subset_font(font_path: pathlib.Path, text: str) -> tuple[bytes, TTFont]:
    """A layout-preserving subset that keeps the original glyph ids."""
    opts = subset.Options()
    opts.layout_features = ["*"]
    opts.retain_gids = True
    opts.notdef_outline = True
    font = subset.load_font(str(font_path), opts)
    sub = subset.Subsetter(options=opts)
    sub.populate(unicodes=sorted({ord(ch) for ch in text}))
    sub.subset(font)
    buf = io.BytesIO()
    subset.save_font(font, buf, opts)
    data = buf.getvalue()
    return data, TTFont(io.BytesIO(data))


def shaped_glyphs(ttf_bytes: bytes, text: str) -> list[tuple[int, int, int]]:
    """(glyph id, cluster start, cluster end) in the visual order HarfBuzz lays out."""
    face = hb.Face(ttf_bytes)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    clusters = sorted({info.cluster for info in buf.glyph_infos})
    glyphs = []
    for info in buf.glyph_infos:
        start = info.cluster
        end = next((c for c in clusters if c > start), len(text))
        glyphs.append((info.codepoint, start, end))
    return glyphs


def to_unicode_map(ttf: TTFont) -> dict[int, str]:
    """Glyph id -> character from the program's own cmap.

    This is what a producer writes: each character maps to its base form, which
    is also what the unpatched writer resolves through when it looks a character
    up in reverse (CPDF_CIDFont::CharCodeFromUnicode). Listing the contextual
    forms here as well would make the unpatched path draw them — the reverse
    lookup keeps the last entry it sees for a character — and the comparison
    between the two builds would stop meaning anything.
    """
    entries: dict[int, str] = {}
    order = ttf.getGlyphOrder()
    for code, name in sorted(ttf.getBestCmap().items()):
        if name in order:
            entries.setdefault(order.index(name), chr(code))
    return entries


def build_cmap(entries: dict[int, str]) -> bytes:
    lines = [
        "/CIDInit /ProcSet findresource begin",
        "12 dict begin",
        "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Identity-UCS def",
        "/CMapType 2 def",
        "1 begincodespacerange",
        "<0000> <FFFF>",
        "endcodespacerange",
        f"{len(entries)} beginbfchar",
    ]
    for gid, chars in sorted(entries.items()):
        lines.append(f"<{gid:04X}> <{chars.encode('utf-16-be').hex().upper()}>")
    lines += [
        "endbfchar",
        "endcmap",
        "CMapName currentdict /CMap defineresource pop",
        "end",
        "end",
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def add_type0_font(pdf: pikepdf.Pdf, ttf_bytes: bytes, ttf: TTFont,
                   entries: dict[int, str], cid_to_gid_stream: bool) -> pikepdf.Object:
    scale = 1000.0 / ttf["head"].unitsPerEm

    def pdf_width(width: int) -> int:
        return int(round(width * scale))

    order = ttf.getGlyphOrder()
    cmap = ttf.getBestCmap()
    hmtx = ttf["hmtx"]
    head, hhea, os2 = ttf["head"], ttf["hhea"], ttf["OS/2"]

    descriptor = pdf.make_indirect(Dictionary(
        Type=Name("/FontDescriptor"),
        FontName=Name("/NajdFixture"),
        Flags=4,
        FontBBox=Array([pdf_width(head.xMin), pdf_width(head.yMin),
                        pdf_width(head.xMax), pdf_width(head.yMax)]),
        ItalicAngle=0,
        Ascent=pdf_width(hhea.ascent),
        Descent=pdf_width(hhea.descent),
        CapHeight=pdf_width(getattr(os2, "sCapHeight", hhea.ascent)),
        StemV=80,
        FontFile2=pdf.make_stream(ttf_bytes),
    ))

    # Every glyph the program can draw gets its own width. A subset that only
    # lists the characters would leave the shaped and contextual forms on the
    # default width, and the field would be laid out at one em per glyph.
    widths = Array()
    for gid, name in enumerate(order):
        if name in hmtx.metrics:
            widths.append(gid)
            widths.append(Array([pdf_width(hmtx.metrics[name][0])]))

    cid_dict = Dictionary(
        Type=Name("/Font"),
        Subtype=Name("/CIDFontType2"),
        BaseFont=Name("/NajdFixture"),
        CIDSystemInfo=Dictionary(Registry=String("Adobe"),
                                 Ordering=String("Identity"), Supplement=0),
        FontDescriptor=descriptor,
        DW=1000,
        W=widths,
    )
    if cid_to_gid_stream:
        # A real non-identity map: CID n selects glyph n+1, so the guard is
        # tested against the case it exists for, not against an identity map
        # that merely happens to be a stream.
        table = bytearray()
        for gid in range(len(order)):
            table += min(gid + 1, len(order) - 1).to_bytes(2, "big")
        cid_dict["/CIDToGIDMap"] = pdf.make_stream(bytes(table))
    else:
        cid_dict["/CIDToGIDMap"] = Name("/Identity")

    type0 = pdf.make_indirect(Dictionary(
        Type=Name("/Font"),
        Subtype=Name("/Type0"),
        BaseFont=Name("/NajdFixture"),
        Encoding=Name("/Identity-H"),
        DescendantFonts=Array([pdf.make_indirect(cid_dict)]),
    ))
    type0["/ToUnicode"] = pdf.make_stream(build_cmap(entries))
    return type0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=pathlib.Path)
    parser.add_argument("--font", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[2]
                        / "najd" / "Najd-Regular.ttf")
    args = parser.parse_args()

    # The Type0 font covers the fields that use it; `latin` is set in Helvetica,
    # so its letters stay out of the subset.
    text = "".join(value for name, _, value, *_ in FIELDS if name != "latin")
    ttf_bytes, ttf = subset_font(args.font, text)
    entries = to_unicode_map(ttf)

    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(PAGE_W, PAGE_H))
    type0 = add_type0_font(pdf, ttf_bytes, ttf, entries, cid_to_gid_stream=False)
    type0_alt = add_type0_font(pdf, ttf_bytes, ttf, entries, cid_to_gid_stream=True)
    helvetica = pdf.make_indirect(Dictionary(
        Type=Name("/Font"), Subtype=Name("/Type1"), BaseFont=Name("/Helvetica"),
        Encoding=Name("/WinAnsiEncoding")))

    annots = Array()
    for name, da, value, quadding, x, y, width in FIELDS:
        annots.append(pdf.make_indirect(Dictionary(
            Type=Name("/Annot"),
            Subtype=Name("/Widget"),
            FT=Name("/Tx"),
            Rect=Array([x - width, y, x, y + 40]),
            T=String(name),
            V=String(value),
            DA=String(da),
            Q=quadding,
            F=4,
            P=page.obj,
        )))

    page["/Annots"] = annots
    pdf.Root["/AcroForm"] = Dictionary(
        Fields=annots,
        DA=String("/F0 24 Tf 0 0 0 rg"),
        # The producer ships the form without appearances and asks the reader to
        # build them from /V and /DA (ISO 32000-1, Table 218).
        NeedAppearances=True,
        DR=Dictionary(Font=Dictionary(F0=type0, F1=helvetica, F2=type0_alt)),
    )

    pdf.save(args.out)
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes), "
          f"font subset {len(ttf_bytes)} bytes, {len(entries)} ToUnicode entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
