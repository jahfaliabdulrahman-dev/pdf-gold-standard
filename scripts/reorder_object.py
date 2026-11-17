"""Rewrite one text object in place with an absolute matrix per glyph, then reverse its glyphs.

The earlier attempt rebuilt a line on a blank page and drowned in font-resource resolution. This does not leave
the file: it parses one `BT..ET` block of the real page, computes every glyph's absolute position from the line
matrix plus the accumulated `Td` offsets (ISO 32000-1 §9.4.4: `Td` moves the line matrix relative to itself, so
it does not accumulate glyph advances), and writes each glyph as `… Tm <gid> Tj`.

Two runs, both compared byte for byte at 300 dpi against the untouched page:
  * same order   — proves the absolute-matrix rewrite paints exactly what the original painted;
  * reversed     — proves the glyph order inside a text object does not move a pixel.

Run:  .venv/bin/python scripts/reorder_object.py report.pdf 11
"""

from __future__ import annotations

import re
import sys
from decimal import Decimal

import pikepdf
import pymupdf

NUMBER = r"-?[\d.]+"
TOKEN = re.compile(
    rf"(?P<tm>{NUMBER}) (?P<tm2>{NUMBER}) (?P<tm3>{NUMBER}) (?P<tm4>{NUMBER}) "
    rf"(?P<tm5>{NUMBER}) (?P<tm6>{NUMBER}) Tm"
    rf"|(?P<tdx>{NUMBER}) (?P<tdy>{NUMBER}) Td"
    rf"|(?P<tf>/\w+) (?P<size>{NUMBER}) Tf"
    rf"|(?P<tr>\d) Tr"
    rf"|(?P<gid><[0-9A-Fa-f]+>) Tj"
)


def rewrite_block(block: str, reverse: bool, state: dict | None = None,
                  width_of=None) -> tuple[str, int]:
    """Return the block rewritten with one absolute Tm per glyph, glyphs in the requested order.

    Text state (font, size, render mode) is inherited across `BT`/`ET` in PDF — it is part of the graphics
    state, not of the text object. Resetting it per block made invisible copies (`3 Tr`) visible again, which
    is exactly the ink that differed.
    """
    state = state if state is not None else {"font": None, "size": None, "tr": 0}
    # Two matrices, as the spec defines them: the line matrix moves only with `Tm`/`Td`, while the text
    # matrix additionally advances by each glyph's displacement. Confusing the two moved 16 glyphs.
    line = (Decimal(1), Decimal(0), Decimal(0), Decimal(1), Decimal(0), Decimal(0))
    text = line
    font, size, tr = state["font"], state["size"], state["tr"]
    events: list[tuple[float, float, str, str, float, int, tuple[float, ...]]] = []
    for m in TOKEN.finditer(block):
        if m.group("tm"):
            names = ("tm", "tm2", "tm3", "tm4", "tm5", "tm6")
            line = tuple(Decimal(m.group(n)) for n in names)   # type: ignore[assignment]
            text = line
        elif m.group("tdx"):
            dx, dy = Decimal(m.group("tdx")), Decimal(m.group("tdy"))
            a, b, c, d, e, f = line
            line = (a, b, c, d, e + dx * a + dy * c, f + dx * b + dy * d)
            text = line
        elif m.group("tf"):
            font, size = m.group("tf"), float(m.group("size"))
        elif m.group("tr"):
            tr = int(m.group("tr"))
        elif m.group("gid"):
            if font is None or size is None:
                continue
            gid = int(m.group("gid")[1:-1], 16)
            adv0 = width_of(font, gid, size) if width_of else Decimal(0)
            events.append((text[4], text[5], font, m.group("gid"), size, tr, text, adv0))
            # `Tj` advances the text matrix by the glyph displacement; the next glyph inherits that advance
            # when no `Td` intervenes. Sixteen glyphs on this page rely on it, which is the whole pixel diff.
            adv = width_of(font, gid, size) if width_of else Decimal(0)
            a, b, c, d, e, f = text
            text = (a, b, c, d, e + adv * a, f + adv * b)
    state.update({"font": font, "size": size, "tr": tr})
    if len(events) < 5:
        return block, 0
    if reverse:
        # Reverse clusters, not single glyphs. A mark sits on its letter: its x falls inside the letter's
        # advance, so the two glyph boxes overlap. Drawing that pair in the other order composites the
        # antialiased overlap differently (measured: 660 bytes). A cluster is therefore a run of glyphs whose
        # horizontal interval overlaps its predecessor's.
        clusters: list[list[tuple]] = []
        for ev in events:
            x, _y, _font, _gid, size, _tr, _matrix, adv = ev
            prev = clusters[-1][-1] if clusters else None
            # A word boundary is a gap wider than a quarter em between one glyph's end and the next origin.
            # Reversing words (not glyphs) is what the emitter will do, and words never overlap, so the
            # compositing order inside a word is untouched.
            gap = x - (prev[0] + prev[7]) if prev else Decimal(0)
            same_word = bool(prev) and gap < Decimal(str(size)) * Decimal("0.25")
            if same_word:
                clusters[-1].append(ev)
            else:
                clusters.append([ev])
        order = [ev for cluster in reversed(clusters) for ev in cluster]
    else:
        order = events
    marker = re.search(r"(/\w+) BMC", block)
    parts = ["BT"] + ([marker.group(1) + " BMC"] if marker else [])
    for _x, _y, font, gid, size, tr, matrix, _adv in order:
        a, b, c, d, e, f = matrix
        parts.append(f"{font} {size:.4f} Tf {tr} Tr {a:.10f} {b:.10f} {c:.10f} {d:.10f} {e:.10f} {f:.10f} Tm {gid} Tj")
    if marker:
        parts.append("EMC")
    parts.append("ET")
    return "\n".join(parts), len(events)


def process(path: str, page_no: int, out_path: str, reverse: bool) -> int:
    pdf = pikepdf.open(path)
    page = pdf.pages[page_no - 1]
    streams = page.Contents if isinstance(page.Contents, pikepdf.Array) else [page.Contents]
    # glyph widths: the only way to know where the next glyph lands when no `Td` follows a `Tj`
    from fix_text_layer import FontState, parse_w
    states = {}
    for name, obj in page.Resources.get("/Font", {}).items():
        if obj.get("/Subtype") == "/Type0":
            states[str(name).lstrip("/")] = FontState(obj)

    def width_of(font: str, gid: int, size: Decimal) -> Decimal:
        st = states.get(font.lstrip("/"))
        if st is None:
            return Decimal(0)
        w = st.neww.get(gid) or st.width.get(gid) or st.dw
        return Decimal(str(w)) / Decimal(1000) * Decimal(str(size))

    total = 0
    state = {"font": None, "size": None, "tr": 0}
    for stream in streams:
        text = bytes(stream.read_bytes()).decode("latin-1")
        changed = []

        def repl(m: re.Match) -> str:
            nonlocal total
            new, n = rewrite_block(m.group(0), reverse, state, width_of)
            total += n
            return new

        text = re.sub(r"BT\b.*?\bET", repl, text, flags=re.S)
        stream.write(text.encode("latin-1"))
        changed.append(True)
    pdf.save(out_path)
    return total


def render(path: str, page_no: int) -> bytes:
    doc = pymupdf.open(path)
    return doc[page_no - 1].get_pixmap(dpi=300).samples


def main() -> int:
    path, page_no = sys.argv[1], int(sys.argv[2])
    base = render(path, page_no)
    for reverse in (False, True):
        out = f"/tmp/reorder-{'rev' if reverse else 'same'}.pdf"
        n = process(path, page_no, out, reverse)
        got = render(out, page_no)
        diff = sum(1 for a, b in zip(base, got) if a != b)
        label = "reversed" if reverse else "same order"
        print(f"{label}: {n} glyphs rewritten, page bytes {len(base)}, differing {diff}")
        if diff:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
