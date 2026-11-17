"""Prove the end claim the plan needs: a line rebuilt from its own glyph positions paints the same pixels.

`emit_proof.py` showed that order does not matter once every glyph carries an absolute matrix. This takes the
next step: rebuild one line of the real page on a blank page of the same size, with the same fonts, sizes and
colours, then compare the rendered crop against the crop of the original page at 300 dpi.

Run:  .venv/bin/python scripts/emit_line_proof.py report.pdf 11 "Business"
"""

from __future__ import annotations

import os
import re
import sys

import pikepdf
import pymupdf

from fix_text_layer import parse_tu


def pick_line(page: pymupdf.Page, needle: str):
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(c["c"] for s in line["spans"] for c in s.get("chars", []))
            if needle in text:
                return line
    raise SystemExit("line not found")


def rgb(color) -> tuple[float, float, float]:
    if isinstance(color, (tuple, list)):          # get_texttrace already reports 0-255 components
        r, g, b = (list(color) + [0, 0, 0])[:3]
        return r / 255, g / 255, b / 255
    return ((color >> 16) & 255) / 255, ((color >> 8) & 255) / 255, (color & 255) / 255


def main() -> int:
    path, page_no, needle = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    doc = pymupdf.open(path)
    page = doc[page_no - 1]
    line = pick_line(page, needle)
    rect = pymupdf.Rect(line["bbox"])

    # get_texttrace reports what was actually drawn: glyph id, font, size, origin — not an approximation
    glyphs: list[dict] = []
    for span in page.get_texttrace():
        for ch in span.get("chars", []):
            unicode_char, gid, origin = ch[0], ch[1], ch[2]
            if not (rect.y0 - 1 <= origin[1] <= rect.y1 + 1 and rect.x0 - 1 <= origin[0] <= rect.x1 + 1):
                continue
            glyphs.append({"gid": gid, "char": unicode_char, "x": origin[0], "y": origin[1],
                           "size": span["size"], "font": span["font"], "color": span["color"]})

    src = pikepdf.open(path)
    cid_by_font: dict[str, dict[str, int]] = {}
    resource_of: dict[str, str] = {}
    for name, obj in src.pages[page_no - 1].Resources.Font.items():
        tu = obj.get("/ToUnicode")
        if tu is None:
            continue
        base = re.sub(r"^[A-Z]{6}\+", "", str(obj.get("/BaseFont", "")).lstrip("/"))   # drop the subset tag
        res = str(name).lstrip("/")
        resource_of[base] = res
        # one map per font: a CID is only meaningful together with the font that defines it
        cid_by_font[res] = {ch: cid for cid, ch in
                            parse_tu(bytes(tu.read_bytes()).decode("latin-1")).items()}

    out = pikepdf.new()
    w, h = float(page.rect.width), float(page.rect.height)
    blank = out.add_blank_page(page_size=(w, h))
    copied = pikepdf.Dictionary()
    for name, obj in src.pages[page_no - 1].Resources.Font.items():
        copied[name] = out.copy_foreign(obj)
    blank.Resources = pikepdf.Dictionary(Font=copied)

    cmds = [f"1 1 1 rg 0 0 {w:.3f} {h:.3f} re f"]      # the paper the original was printed on
    for span in glyphs:
        # PyMuPDF truncates the font name to 22 characters, so the best match is the longest shared prefix
        wanted = span["font"]
        candidates = [(len(os.path.commonprefix([base, wanted])), res) for base, res in resource_of.items()]
        best = max(candidates, default=(0, None))
        font = best[1] if best[0] >= 10 else None
        if font is None:
            continue
        r, g, b = rgb(span["color"])
        cmds.append(f"{r:.4f} {g:.4f} {b:.4f} rg")
        cmds.append(f"/{font} {span['size']:.4f} Tf")
        gid = span["gid"]
        if gid is None:
            continue
        x, y = span["x"], span["y"]
        cmds.append(f"1 0 0 1 {x:.4f} {h - y:.4f} Tm <{gid:04X}> Tj")
    blank.Contents = out.make_stream("\n".join(cmds).encode("latin-1"))
    out.save("/tmp/line-rebuilt.pdf")

    dpi = 300
    scale = dpi / 72
    clip = pymupdf.Rect(rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
    before = page.get_pixmap(dpi=dpi, clip=clip)
    after = pymupdf.open("/tmp/line-rebuilt.pdf")[0].get_pixmap(dpi=dpi, clip=clip)

    if (before.width, before.height) != (after.width, after.height):
        print("size mismatch", before.width, before.height, after.width, after.height)
        return 1
    diff = sum(1 for a, b in zip(before.samples, after.samples) if a != b)
    total = len(before.samples)
    print(f"line {rect} at {dpi}dpi: {total} bytes, differing {diff} ({100 * diff / total:.4f}%)")
    after.save("/tmp/line-after.png")
    before.save("/tmp/line-before.png")
    return 0 if diff == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
