"""Prove that a line can be re-emitted glyph by glyph, in any order, without moving a single pixel.

The trick that makes logical-order output safe: every glyph carries its own absolute text matrix (`Tm`), so the
order inside the text object stops mattering — the position is written, not inherited. This script rebuilds one
line that way (first in drawing order, then in reversed order) and compares both renders against the original
line, pixel by pixel.

Run:  .venv/bin/python scripts/emit_proof.py report.pdf 11
"""

from __future__ import annotations

import sys

import pymupdf
import pikepdf


def line_glyphs(page: pymupdf.Page, needle: str) -> tuple[list[dict], pymupdf.Rect]:
    """Characters of the first line containing `needle`, in drawing order (left to right)."""
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            chars = [c for s in line["spans"] for c in s.get("chars", [])]
            if needle not in "".join(c["c"] for c in chars):
                continue
            glyphs = []
            for span in line["spans"]:
                for ch in span.get("chars", []):
                    glyphs.append({
                        "c": ch["c"],
                        "x": ch["origin"][0],
                        "y": ch["origin"][1],
                        "size": span["size"],
                        "font": span["font"],
                    })
            return glyphs, pymupdf.Rect(line["bbox"])
    raise SystemExit("line not found")


def build_page(src: pikepdf.Pdf, glyphs: list[dict], rect: pymupdf.Rect, order: str) -> pikepdf.Pdf:
    """A one-page PDF holding the same glyphs at the same coordinates, emitted in `order`."""
    out = pikepdf.new()
    page = out.add_blank_page(page_size=(float(rect.width) + 40, float(rect.height) + 40))
    # reuse the source's font resources wholesale: the glyph ids belong to those fonts
    copied = pikepdf.Dictionary()
    for name, obj in src.pages[0].Resources.Font.items():
        copied[name] = out.copy_foreign(obj)      # a foreign object must be copied, never linked across documents
    page.Resources = pikepdf.Dictionary(Font=copied)
    cmds = []
    height = float(rect.height) + 40
    sequence = glyphs if order == "draw" else list(reversed(glyphs))
    for g in sequence:
        x = g["x"] - float(rect.x0) + 20
        y = height - (g["y"] - float(rect.y0)) - 10
        font = src.pages[0].Resources.Font and _pick_font(src, g["font"])
        if font is None:
            continue
        cmds.append(f"/{font} {g['size']:.4f} Tf 1 0 0 1 {x:.4f} {y:.4f} Tm <{g['cid']:04X}> Tj")
    page.Contents = out.make_stream("\n".join(cmds).encode("latin-1"))
    return out


_FONT_CACHE: dict[str, str] = {}


def _pick_font(src: pikepdf.Pdf, base_font: str) -> str | None:
    """The resource name of the first font whose BaseFont starts with what PyMuPDF reported."""
    if base_font in _FONT_CACHE:
        return _FONT_CACHE[base_font]
    for name, obj in src.pages[0].Resources.Font.items():
        if str(obj.get("/BaseFont", "")).lstrip("/").startswith(base_font.split("-")[0]):
            _FONT_CACHE[base_font] = str(name).lstrip("/")
            return _FONT_CACHE[base_font]
    return None


def main() -> int:
    path, page_no = sys.argv[1], int(sys.argv[2])
    doc = pymupdf.open(path)
    page = doc[page_no - 1]
    glyphs, rect = line_glyphs(page, "Business")

    src = pikepdf.open(path)
    # CID per character from the font's ToUnicode reverse map (the same map the reader uses)
    from fix_text_layer import parse_tu  # local import: the repo's own parser

    cid_of: dict[str, int] = {}
    for name, obj in src.pages[page_no - 1].Resources.Font.items():
        tu = obj.get("/ToUnicode")
        if tu is None:
            continue
        for cid, ch in parse_tu(bytes(tu.read_bytes()).decode("latin-1")).items():
            cid_of.setdefault(ch, cid)
    for g in glyphs:
        g["cid"] = cid_of.get(g["c"], 0)

    renders = {}
    for order in ("draw", "reverse"):
        built = build_page(src, glyphs, rect, order)
        built.save(f"/tmp/emit-{order}.pdf")
        d = pymupdf.open(f"/tmp/emit-{order}.pdf")
        renders[order] = d[0].get_pixmap(dpi=300)
    same = renders["draw"].samples == renders["reverse"].samples
    print("draw vs reversed: identical pixels =", same,
          "| bytes:", len(renders["draw"].samples))
    if not same:
        diff = sum(1 for a, b in zip(renders["draw"].samples, renders["reverse"].samples) if a != b)
        print("differing bytes:", diff)
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
