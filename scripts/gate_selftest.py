#!/usr/bin/env python3
"""Prove the gate can fail: a gate never seen failing is unverified.

Usage: python3 scripts/gate_selftest.py built.pdf

The built PDF must PASS. Then each mutation is applied to an in-memory copy, and the gate must
exit non-zero AND name the expected check. A POSITIVE mutation is a valid variant of the document
(an indirect MarkInfo) that must still PASS — it proves the gate rejects the defect, not the form.

Exit 0 only if every mutation lands on the right side. The mutation count is declared in nav_spec
(GATE_MUTATIONS) and checked here, so an unregistered mutation cannot hide.
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pymupdf as fitz  # noqa: E402
import pikepdf  # noqa: E402

import spec_loader  # noqa: E402

NS = spec_loader.load()  # noqa: E402
import verify_pdf as G  # noqa: E402

SRC = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"
OLD_CHECKS, OLD_SOURCE = NS.GATE_CHECKS, NS.SOURCE_HTML
_RESTORE = []
# A mutation whose precondition this document does not meet — a page with no art, a document with no
# form fields. It is neither a catch nor a miss: the suite reports how many actually applied, and the
# spec must declare that number.
NA = object()
# The suite this file carries. A spec declares how many of them APPLY to its document (GATE_MUTATIONS)
# and names the ones that do not (GATE_NA); the difference is checked, so neither a deleted mutation nor
# a silent skip can hide behind a stable number.
from spec_base import MUTATION_SUITE_SIZE as SUITE_SIZE  # derived: the suite and the spec cannot disagree


class _NotApplicable(Exception):
    """Raised inside a pikepdf mutation callback when the document lacks the object to mutate."""


def restore_all() -> None:
    while _RESTORE:
        _RESTORE.pop()()


def fresh():
    return fitz.open(SRC)


def reread(doc):
    return fitz.open("pdf", doc.tobytes())


def strip_link(doc, i, role):
    x = NS.SLOTS[role]
    return next(l for l in doc[i].get_links() if abs(l["from"].x0 - x) < 2 and abs(l["from"].y0 - NS.NAV_Y0) < 2)


# ---------------------------------------------------------------- source-level variants
def _source_variant(transform):
    """Point the gate at a temporary variant of the source HTML (a real end-to-end mutation)."""
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", NS.SOURCE_HTML), encoding="utf-8").read()
    new = transform(src)
    if new == src:                 # the source carries nothing of that kind: the mutation cannot apply
        return NA
    fd, path = tempfile.mkstemp(suffix=".html"); os.close(fd)
    open(path, "w", encoding="utf-8").write(new)
    NS.SOURCE_HTML = path

    def undo():
        NS.SOURCE_HTML = OLD_SOURCE
        os.unlink(path)
    _RESTORE.append(undo)


def rename_nav_class(doc):
    # a benign refactor (HTML + CSS renamed together, page unchanged) must not silence the strongest check
    if not NS.NAV_PAGES:               # a print copy carries no strip: there is no class to rename
        return NA
    cls = NS.NAV_CLASS
    return _source_variant(lambda s: s.replace(f'class="{cls}"', 'class="navbar"')
                           .replace(f".{cls}{{", ".navbar{").replace(f".{cls} ", ".navbar ").replace(f".{cls},", ".navbar,"))


def stale_back_cover(doc):
    # only the BACK cover still announces the previous version — the last occurrence, whatever its date
    # suffix: the guide prints «الإصدار … — نوفمبر» and najd prints «الإصدار ١٫٠» alone.
    def fn(s):
        needle = f"الإصدار {NS.GUIDE_VERSION_AR}"
        k = s.rfind(needle)
        if k < 0:
            return s
        return s[:k] + "الإصدار ٢٫٢" + s[k + len(needle):]
    return _source_variant(fn)


def icon_input_lost(doc):
    # the cheap form of H2: the gate's own input disappears
    if not NS.NAV_PAGES:               # no strip, no icons to lose
        return NA
    real = G.source_icons
    G.source_icons = lambda: []
    _RESTORE.append(lambda: setattr(G, "source_icons", real))


def wrong_printed_count(doc):
    # the document's printed count no longer matches the live number of checks
    NS.GATE_CHECKS = OLD_CHECKS + 1
    _RESTORE.append(lambda: setattr(NS, "GATE_CHECKS", OLD_CHECKS))


# ---------------------------------------------------------------- document mutations
def swap_next_prev(doc):
    if not NS.NAV_PAGES:               # a print copy carries no strip links to swap
        return NA
    i = NS.NAV_PAGES[2]
    a, b = strip_link(doc, i, "next"), strip_link(doc, i, "prev")
    a["page"], b["page"] = b["page"], a["page"]
    doc[i].update_link(a); doc[i].update_link(b)


def self_link(doc):
    if not NS.NAV_PAGES:
        return NA
    i = NS.NAV_PAGES[-1]
    a = strip_link(doc, i, "next"); a["page"] = i
    doc[i].update_link(a)


def whiteout_strip(doc):
    # every link still points where it should, but the buttons are no longer drawn on one page
    if not NS.NAV_PAGES:
        return NA
    p = doc[NS.NAV_PAGES[0]]
    p.draw_rect(fitz.Rect(40, NS.NAV_Y0 - 10, 210, NS.NAV_Y1 + 14), color=None, fill=(1, 1, 1), overlay=True)


def whiteout_body(doc):
    # H1: the page body painted white; text stays extractable, so every text check still passes
    p = doc[6]
    p.draw_rect(fitz.Rect(0, NS.NAV_Y1 + 8, p.rect.width, p.rect.height - 60), color=None, fill=(1, 1, 1), overlay=True)


def whiteout_sparse_page(doc):
    # the page with the least ink (0.8%): an absolute +-0.02 tolerance alone could not see this
    p = doc[1]
    p.draw_rect(fitz.Rect(0, NS.NAV_Y1 + 8, p.rect.width, p.rect.height - 60), color=None, fill=(1, 1, 1), overlay=True)


def _drop_images(doc, page_idx):
    p = doc[page_idx]
    ims = p.get_images()
    if not ims:
        return NA                # a page with no art: «drop the art» describes nothing to do
    for im in ims:
        p.delete_image(im[0])


def drop_cover_art(doc):
    return _drop_images(doc, NS.COVER)


def drop_divider_art(doc):
    return _drop_images(doc, 3)          # the first divider page


def drop_image_object(doc):
    # one of the four QR codes on the references page disappears; its text link is untouched
    p = doc[NS.REF_PAGE]
    ims = p.get_images()
    if not ims:
        return NA
    p.delete_image(ims[0][0])


def swap_icons(doc):
    # both arrows are drawn and both links are right, but each arrow sits in the other's slot
    if not NS.NAV_PAGES:
        return NA
    p = doc[NS.NAV_PAGES[1]]
    rect = {r: fitz.Rect(NS.SLOTS[r], NS.NAV_Y0, NS.SLOTS[r] + NS.NAV_W, NS.NAV_Y1) for r in ("next", "prev")}
    pix = {r: p.get_pixmap(dpi=300, clip=rect[r]) for r in rect}
    p.insert_image(rect["next"], pixmap=pix["prev"]); p.insert_image(rect["prev"], pixmap=pix["next"])


def foreign_icon(doc):
    # a different icon in the "next" slot: a disc with the arrow's own ink share and centre of mass
    import math
    if not NS.NAV_PAGES:
        return NA
    x = NS.SLOTS["next"]; slot = fitz.Rect(x, NS.NAV_Y0, x + NS.NAV_W, NS.NAV_Y1)
    inner = fitz.Rect(x + 2, NS.NAV_Y0 + 2, x + NS.NAV_W - 2, NS.NAV_Y1 - 2)
    p = doc[NS.NAV_PAGES[2]]
    px = p.get_pixmap(dpi=72, clip=fitz.Rect(slot.x0, slot.y0, slot.x0 + 1, slot.y0 + 1))          # the slot's background colour
    bg = tuple(c / 255 for c in px.pixel(0, 0)[:3])
    fg = tuple(1 - c for c in bg) if abs(sum(bg) / 3 - 0.5) > 0.2 else (1, 1, 1)
    ink, cx, cy = NS.SLOT_SHAPE["next"][:3]
    p.draw_rect(slot, color=None, fill=bg, overlay=True)
    r = math.sqrt(ink * inner.width * inner.height / math.pi)
    p.draw_circle(fitz.Point(inner.x0 + (0.5 + cx) * inner.width, inner.y0 + (0.5 + cy) * inner.height), r, color=None, fill=fg, overlay=True)


def moment_matched_icon(doc):
    # not an arrow at all: horizontal stripes in a rectangle chosen to match the arrow's five-number signature
    # (ink share, centre of mass, spread) — only a comparison of the SHAPE can tell
    if not NS.NAV_PAGES:
        return NA
    x = NS.SLOTS["next"]; slot = fitz.Rect(x, NS.NAV_Y0, x + NS.NAV_W, NS.NAV_Y1)
    inner = fitz.Rect(x + 2, NS.NAV_Y0 + 2, x + NS.NAV_W - 2, NS.NAV_Y1 - 2)
    p = doc[NS.NAV_PAGES[3]]
    bg = tuple(c / 255 for c in p.get_pixmap(dpi=72, clip=fitz.Rect(slot.x0, slot.y0, slot.x0 + 1, slot.y0 + 1)).pixel(0, 0)[:3])
    fg = tuple(1 - c for c in bg) if abs(sum(bg) / 3 - 0.5) > 0.2 else (1, 1, 1)
    ink, cx, cy, sx, sy = NS.SLOT_SHAPE["next"]
    w, h = sx * 12 ** 0.5 * inner.width, sy * 12 ** 0.5 * inner.height          # uniform rectangle with that spread
    box = fitz.Rect(0, 0, w, h) + (inner.x0 + (0.5 + cx) * inner.width - w / 2, inner.y0 + (0.5 + cy) * inner.height - h / 2) * 2
    p.draw_rect(slot, color=None, fill=bg, overlay=True)
    n = 6; duty = ink * inner.width * inner.height / (w * h)                    # stripes thin enough to match the ink share
    for k in range(n):
        y = box.y0 + (k + 0.5 - duty / 2) * h / n
        p.draw_rect(fitz.Rect(box.x0, y, box.x1, y + duty * h / n), color=None, fill=fg, overlay=True)


def extra_printed_number(doc):
    # one more page number printed in the contents column than there are rows
    p = doc[NS.CONTENTS]
    xs = [c["bbox"][0] for b in p.get_text("rawdict")["blocks"] for l in b.get("lines", []) for sp in l["spans"] for c in sp["chars"] if c["c"].isdigit()]
    if not xs:
        return NA
    p.insert_text((min(xs), p.rect.height - 120), "9", fontname="helv", fontsize=11)


def wrong_source_stamp(doc):
    # a file built from another source: provenance is a claim, wherever it is written
    def fn(p):
        with p.open_metadata() as m:
            m["xmpMM:DocumentID"] = "sha256:" + "0" * 64
    return _pikemutate(doc, fn)


def stale_version(doc):
    # the title still announces the previous version
    md = dict(doc.metadata); md["title"] = md["title"].replace(NS.GUIDE_VERSION_AR, "٢٫١"); doc.set_metadata(md)


def blank_text_page_with_decor(doc):
    # the same overflow artifact, plus a small decorative image: "has an image" must not excuse an empty page
    i = blank_page(doc)
    if i is NA:
        return NA
    doc[i].insert_image(fitz.Rect(300, 400, 332, 432), pixmap=fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 32, 32), False))


def bfrange_two_letters(doc):
    # two letters on one glyph, written as a range instead of a bfchar entry
    x = _tounicode_xref(doc); s = doc.xref_stream(x)
    doc.update_stream(x, s.replace(b"endbfchar", b"endbfchar\n1 beginbfrange\n<F000> <F000> [<06440627>]\nendbfrange", 1))


def drop_tagging(doc):
    doc.xref_set_key(doc.pdf_catalog(), "Lang", "null")
    doc.xref_set_key(doc.pdf_catalog(), "MarkInfo", "null")


def markinfo_indirect(doc):
    # a VALID PDF: MarkInfo as an indirect object instead of a direct dictionary. Must still PASS (H4).
    cat = doc.pdf_catalog()
    kind, val = doc.xref_get_key(cat, "MarkInfo")
    if kind == "xref":
        raise SystemExit("selftest: MarkInfo is already indirect - the positive mutation is vacuous")
    x = doc.get_new_xref()
    doc.update_object(x, "<< " + val.strip().strip("<<").strip().rstrip(">>").strip() + " >>")
    doc.xref_set_key(cat, "MarkInfo", f"{x} 0 R")


def ltr(doc):
    doc.xref_set_key(doc.pdf_catalog(), "ViewerPreferences", "<</Direction/L2R>>")


def two_page_layout(doc):
    doc.xref_set_key(doc.pdf_catalog(), "PageLayout", "/TwoPageRight")


def drop_outline_entry(doc):
    doc.set_toc(NS.TOC[:-1])


def swap_contents_rows(doc):
    rows = sorted([l for l in doc[NS.CONTENTS].get_links() if l.get("kind") == fitz.LINK_GOTO], key=lambda l: l["from"].y0)
    rows[0]["page"], rows[1]["page"] = rows[1]["page"], rows[0]["page"]
    doc[NS.CONTENTS].update_link(rows[0]); doc[NS.CONTENTS].update_link(rows[1])


def foreign_font(doc):
    doc[5].insert_text((60, 700), "->", fontname="helv", fontsize=9)   # a typed symbol in a non-house face


def blank_page(doc):
    # the overflow artifact: a text page reduced to its footer — body text gone, nav strip and footer kept
    # A print copy has no strip pages: any content page will do, so the mutation still applies to it.
    pages = NS.NAV_PAGES or range(1, doc.page_count)
    i = next((k for k in pages if not doc[k].get_images()), None)
    if i is None:
        return NA
    p = doc[i]
    p.add_redact_annot(fitz.Rect(0, NS.NAV_Y1 + 10, p.rect.width, p.rect.height - 60))
    p.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    return i


def delete_paragraph(doc):
    # H5: ~18 words vanish from a body page (one paragraph); every AGGREGATE ratio still passes
    # A print copy has no strip pages, but it still has body pages: use one, not a strip-dependent index.
    p = doc[NS.NAV_PAGES[2] if NS.NAV_PAGES else 2]
    lines = []
    for b in p.get_text("rawdict")["blocks"]:
        for line in b.get("lines", []):
            txt = "".join(c["c"] for s in line["spans"] for c in s["chars"])
            n = len(G.source_words(txt))
            if n and line["bbox"][1] > NS.NAV_Y1 + 10 and line["bbox"][3] < p.rect.height - 60:
                lines.append((line["bbox"], n))
    lines.sort(key=lambda l: -l[0][1])
    removed = 0
    for bbox, n in lines:
        if removed >= 18:
            break
        p.add_redact_annot(fitz.Rect(bbox)); removed += n
    p.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    if removed < 18:
        return NA


def _footer_span(doc, i):
    for b in doc[i].get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = s["text"].strip()
                if t and all(ch.isdigit() for ch in t) and NS.FOOTER_Y_MIN <= s["bbox"][1] <= NS.FOOTER_Y_MAX:
                    return s["bbox"]
    return None


def drop_footer_number(doc):
    spans = {i: _footer_span(doc, i) for i in (4, 5, 8)}
    if any(r is None for r in spans.values()):
        return NA
    for i, r in spans.items():
        p = doc[i]
        p.add_redact_annot(fitz.Rect(r))
        p.apply_redactions()


def swap_footer_numbers(doc):
    p = doc[4]
    r = _footer_span(doc, 4)
    if r is None:
        return NA
    r = fitz.Rect(r)
    p.add_redact_annot(r); p.apply_redactions()
    p.insert_text((r.x0, r.y1 - 2), "9", fontname="helv", fontsize=8)


def move_footer_up(doc):
    p = doc[4]
    r = _footer_span(doc, 4)
    if r is None:
        return NA
    r = fitz.Rect(r)
    p.add_redact_annot(r); p.apply_redactions()
    p.insert_text((r.x0, 500), "5", fontname="helv", fontsize=8)


def break_ref_link(doc):
    links = sorted([l for l in doc[NS.REF_PAGE].get_links() if l.get("kind") == fitz.LINK_URI], key=lambda l: l["from"].y0)
    if not links:
        return NA
    links[0]["uri"] = "https://example.invalid/broken"
    doc[NS.REF_PAGE].update_link(links[0])


def _tounicode_xref(doc, page=4):
    """ToUnicode stream of the body font with the most entries on a text page."""
    best = None
    for xref, *_ in doc[page].get_fonts():
        kind, tu = doc.xref_get_key(xref, "ToUnicode")
        if kind == "xref":
            x = int(tu.split()[0]); n = doc.xref_stream(x).count(b"<")
            best = max(best or (0, x), (n, x))
    return best[1] if best else None


def presentation_form(doc):
    # Chrome's raw mapping: an Arabic glyph mapped to its Presentation Form (ﺎ U+FE8E) instead of ا
    x = _tounicode_xref(doc)
    if x is None:
        return NA
    s = doc.xref_stream(x)
    if b"<0627>" not in s:
        return NA
    doc.update_stream(x, s.replace(b"<0627>", b"<FE8E>", 1))


def swapped_letters(doc):
    # copy produces the wrong letters while every glyph still has exactly one base code point
    x = _tounicode_xref(doc)
    if x is None:
        return NA
    s = doc.xref_stream(x)
    if b"<0627>" not in s or b"<0644>" not in s:
        return NA
    doc.update_stream(x, s.replace(b"<0627>", b"<TMP0>").replace(b"<0644>", b"<0627>").replace(b"<TMP0>", b"<0644>"))


def split_text_objects(doc):
    # back to one text object per word: MuPDF forgets the direction at each BT and returns the words reversed
    _, before = G.copy_fidelity(doc, engine="mupdf")
    changed = False
    for page in doc:
        for x in page.get_contents():
            s = doc.xref_stream(x)
            if b"/ReversedChars BMC" not in s:
                continue
            doc.update_stream(x, s.replace(b"/ReversedChars BMC", b"ET\nBT\n/ReversedChars BMC"))
            changed = True
    if not changed:
        return NA                # no direction-marked run in this document: nothing to split
    _, after = G.copy_fidelity(doc, engine="mupdf")
    # A document whose lines each carry one direction does not lose word order when the objects are split
    # (measured: 0.929 -> 0.925). Counting it as «caught» would need a threshold tuned to the mutation, so it
    # is declared not applicable instead.
    if before is None or after is None or before - after < 0.01:
        return NA


def pagination_body_text(doc):
    """A top-level /Artifact /Pagination block whose text sits in the body, not the furniture band.

    The tag says «furniture» and veraPDF accepts it; only the position can tell it from the running footer.
    A space is shown, so no word and no ink changes — the probe is the position alone.
    """
    import pikepdf

    def fn(p):
        page = p.pages[0]
        streams = page.Contents if isinstance(page.Contents, pikepdf.Array) else [page.Contents]
        body = b"\n".join(bytes(st.read_bytes()) for st in streams)
        font = b"/F1"
        try:
            font = str(next(iter(page.Resources["/Font"].keys()))).encode()
        except Exception:
            pass
        inject = (b"\nq\n/Artifact << /Type /Pagination >> BDC\nBT\n" + font +
                  b" 12 Tf\n1 0 0 1 100 400 Tm\n( ) Tj\nET\nEMC\nQ\n")
        page.Contents = p.make_stream(inject + body)

    return _pikemutate(doc, fn)


def artifact_body_text(doc):
    """An UNTYPED /Artifact BMC carrying a body line (review P1).

    `/Artifact` with no `/Type` is what the producer's own wrapper used to write, and every check accepted it:
    a body line inside it disappears from a screen reader while the file still passes veraPDF. Position is
    the only thing that can tell it from the footer, so the gate must judge it by position.
    """
    import pikepdf

    def fn(p):
        page = p.pages[0]
        streams = page.Contents if isinstance(page.Contents, pikepdf.Array) else [page.Contents]
        body = b"\n".join(bytes(st.read_bytes()) for st in streams)
        font = b"/F1"
        try:
            font = str(next(iter(page.Resources["/Font"].keys()))).encode()
        except Exception:
            pass
        inject = (b"\nq\n/Artifact BMC\nBT\n" + font +
                  b" 12 Tf\n1 0 0 1 100 400 Tm\n( ) Tj\nET\nEMC\nQ\n")
        page.Contents = p.make_stream(inject + body)

    return _pikemutate(doc, fn)


def artifact_by_name(doc):
    """`/Artifact /P1 BDC` — the properties come from a NAMED list, not an inline dictionary (review P1).

    A reader that only looks at the operand's shape sees a bare name and gives up; the name resolves through
    /Resources /Properties and the block is an untyped artifact holding a body line.
    """
    import pikepdf

    def fn(p):
        page = p.pages[0]
        streams = page.Contents if isinstance(page.Contents, pikepdf.Array) else [page.Contents]
        body = b"\n".join(bytes(st.read_bytes()) for st in streams)
        font = b"/F1"
        try:
            font = str(next(iter(page.Resources["/Font"].keys()))).encode()
        except Exception:
            pass
        props = page.Resources.get("/Properties", pikepdf.Dictionary())
        props["/P1"] = pikepdf.Dictionary(Type=pikepdf.Name("/Foo"))
        page.Resources["/Properties"] = props
        inject = (b"\nq\n/Artifact /P1 BDC\nBT\n" + font +
                  b" 12 Tf\n1 0 0 1 100 400 Tm\n( ) Tj\nET\nEMC\nQ\n")
        page.Contents = p.make_stream(inject + body)

    return _pikemutate(doc, fn)


def form_xobject_text(doc):
    """A body line drawn from inside a Form XObject invoked inside an artifact (review P2).

    The page's stream carries no text at all: a gate that does not follow `Do` (with the form's /Matrix) sees
    nothing and passes.
    """
    import pikepdf

    def fn(p):
        page = p.pages[0]
        form = p.make_stream(b"BT /F1 12 Tf 1 0 0 1 100 0 Tm ( ) Tj ET")
        form["/Type"] = pikepdf.Name("/XObject")
        form["/Subtype"] = pikepdf.Name("/Form")
        form["/Matrix"] = pikepdf.Array([1, 0, 0, 1, 0, 400])
        form["/Resources"] = page.Resources
        xo = page.Resources.get("/XObject", pikepdf.Dictionary())
        xo["/FxForm"] = form
        page.Resources["/XObject"] = xo
        streams = page.Contents if isinstance(page.Contents, pikepdf.Array) else [page.Contents]
        body = b"\n".join(bytes(st.read_bytes()) for st in streams)
        inject = b"\nq\n/Artifact BMC\n/FxForm Do\nEMC\nQ\n"
        page.Contents = p.make_stream(inject + body)

    return _pikemutate(doc, fn)


def wrong_mark(doc):
    # a kasra that copies as a fatha: the vocalised line is no longer exact
    if not getattr(NS, "VOCALISED_CLAIM", True):
        return NA                # the document claims nothing about its marks, so the check is off
    changed = False
    for xref, *_ in doc[NS.BASMALA].get_fonts():
        kind, tu = doc.xref_get_key(xref, "ToUnicode")
        if kind == "xref":
            x = int(tu.split()[0]); s = doc.xref_stream(x)
            if b"<0650>" in s:
                doc.update_stream(x, s.replace(b"<0650>", b"<064E>")); changed = True
    if not changed:
        return NA


def drop_page(doc):
    if doc.page_count <= 7:
        return NA
    doc.delete_page(7)


def _pikemutate(doc, fn):
    """Round-trip through pikepdf (the library that wrote the feature) and return a new fitz doc."""
    import io
    import pikepdf
    with pikepdf.open(io.BytesIO(doc.tobytes())) as pdf:
        fn(pdf)
        buf = io.BytesIO()
        pdf.save(buf)
    return fitz.open("pdf", buf.getvalue())


def drop_page_labels(doc):
    if doc.xref_get_key(doc.pdf_catalog(), "PageLabels")[0] == "null":
        return NA
    return _pikemutate(doc, lambda p: p.Root.__delitem__("/PageLabels"))


def rename_destination(doc):
    def fn(p):
        if "/Names" not in p.Root or "/Dests" not in p.Root.Names:
            raise _NotApplicable
        p.Root.Names.Dests.Names[0] = pikepdf.String("cover-renamed")
    try:
        return _pikemutate(doc, fn)
    except _NotApplicable:
        return NA


def drop_xmp_title(doc):
    def fn(p):
        with p.open_metadata() as m:
            del m["dc:title"]
    return _pikemutate(doc, fn)


def strip_output_intent(doc):
    return _pikemutate(doc, lambda p: p.Root.__delitem__("/OutputIntents"))


def break_box_order(doc):
    def fn(p):
        p.pages[0].obj["/TrimBox"] = pikepdf.Array([50, 50, 500, 800])
        p.pages[0].obj["/BleedBox"] = pikepdf.Array([100, 100, 400, 700])   # Bleed inside Trim: invalid
    return _pikemutate(doc, fn)


def drop_attachment(doc):
    def fn(p):
        if "manifest.json" not in p.attachments:
            raise _NotApplicable
        del p.attachments["manifest.json"]
        p.Root.AF = pikepdf.Array([s.obj for n, s in p.attachments.items()])
    try:
        return _pikemutate(doc, fn)
    except _NotApplicable:
        return NA



def art_over_dpi(doc):
    # an image above the ceiling: a 600-dpi raster placed over the cover art
    from PIL import Image
    import io
    buf = io.BytesIO()
    # 530x780 pt = 7.36x10.83 in; at 600 dpi that is 4417x6500 px -> page art above the 300 cap
    Image.new("RGB", (4417, 6500), "white").save(buf, "JPEG")
    pix = fitz.Pixmap(buf.getvalue())
    doc[0].insert_image(fitz.Rect(30, 30, 560, 810), pixmap=pix, overlay=True)


def drop_parent_tree(doc):
    def fn(p):
        if "/StructTreeRoot" not in p.Root or "/ParentTree" not in p.Root.StructTreeRoot:
            raise _NotApplicable
        del p.Root.StructTreeRoot["/ParentTree"]
    try:
        return _pikemutate(doc, fn)
    except _NotApplicable:
        return NA


def field_without_tu(doc):
    def fn(p):
        if "/AcroForm" not in p.Root or "/Fields" not in p.Root.AcroForm or not p.Root.AcroForm.Fields:
            raise _NotApplicable
        del p.Root.AcroForm.Fields[0]["/TU"]
    try:
        return _pikemutate(doc, fn)
    except _NotApplicable:
        return NA


def paragraph_under_document(doc):
    """Page furniture tagged as a paragraph: a reader then reads the running head after the last section."""
    def fn(p):
        root = p.Root.get("/StructTreeRoot")
        if root is None:
            raise _NotApplicable
        kids = root.get("/K")
        kids = list(kids) if isinstance(kids, pikepdf.Array) else [kids]
        doc_el = next((k for k in kids if str(k.get("/S")) == "/Document"), None)
        ch = doc_el.get("/K") if doc_el is not None else None
        if not isinstance(ch, pikepdf.Array) or not ch:
            raise _NotApplicable
        ch[0]["/S"] = pikepdf.Name("/P")          # one section reported as a paragraph under /Document
    try:
        return _pikemutate(doc, fn)
    except _NotApplicable:
        return NA


def _rewrite_manifest(p, change):
    """Replace manifest.json with `change(parsed)` in the shape postprocess writes it.

    `change` returns None when the document lacks what this mutation needs — reported as NA, never a crash.
    """
    import json
    if "manifest.json" not in p.attachments:
        raise _NotApplicable
    man = json.loads(p.attachments["manifest.json"].get_file().read_bytes())
    if change(man) is None:
        raise _NotApplicable
    data = json.dumps(man, ensure_ascii=False, indent=1).encode()
    del p.attachments["manifest.json"]
    new = pikepdf.AttachedFileSpec(p, data, mime_type="application/json", filename="manifest.json")
    new.obj["/AFRelationship"] = pikepdf.Name("/Source")
    new.obj["/Params"] = pikepdf.Dictionary(ModDate=pikepdf.String("D:20261114210000+03'00'"))
    p.attachments["manifest.json"] = new
    p.Root.AF = pikepdf.Array([s.obj for n, s in p.attachments.items()])


def wrong_chrome_version(doc):
    """The manifest names another Chrome: every ink and order number in this file was measured on the pin."""
    def change(man):
        v = str(man.get("chrome_version") or "")
        if not v:
            return None
        man["chrome_version"] = ("0" if not v.startswith("0") else "1") + v[1:]
        return man
    try:
        return _pikemutate(doc, lambda p: _rewrite_manifest(p, change))
    except _NotApplicable:
        return NA


def missing_rendered_hash(doc):
    """The manifest lost the key the gate compares: a file bound to nothing must fail by name."""
    def change(man):
        if not man.get("rendered_sha256"):
            return None
        del man["rendered_sha256"]
        return man
    try:
        return _pikemutate(doc, lambda p: _rewrite_manifest(p, change))
    except _NotApplicable:
        return NA


def rendered_mismatch(doc):
    """The manifest names a markup whose hash this spec does not derive: the file is not from this build."""
    def change(man):
        h = str(man.get("rendered_sha256") or "")
        if not h:
            return None
        man["rendered_sha256"] = ("1" if h[0] != "1" else "2") + h[1:]
        return man
    try:
        return _pikemutate(doc, lambda p: _rewrite_manifest(p, change))
    except _NotApplicable:
        return NA


def print_copy_with_icons(doc):
    """A page that draws the strip while being judged as a print copy: the PAGE must convict it.

    The drawing is injected (not inherited from a screen build), so the mutation also applies to a
    document that is already a print copy — otherwise the gate would be proven only on the variant
    that is not shipped.
    """
    old = getattr(NS, "NAV_VISIBLE", True)
    NS.NAV_VISIBLE = False
    _RESTORE.append(lambda: setattr(NS, "NAV_VISIBLE", old))
    x = NS.SLOTS["next"]
    doc[0].draw_rect(fitz.Rect(x + 4, NS.NAV_Y0 + 4, x + 16, NS.NAV_Y1 - 4), color=(0, 0, 0), fill=(0, 0, 0))


def link_without_contents(doc):
    def fn(p):
        for page in p.pages:
            for a in page.obj.get("/Annots", []):
                if a.get("/Subtype") == pikepdf.Name.Link:
                    if "/Contents" not in a:
                        continue
                    del a["/Contents"]
                    return
        raise _NotApplicable
    try:
        return _pikemutate(doc, fn)
    except _NotApplicable:
        return NA


def _add_form(p, page, name, body, matrix=(1, 0, 0, 1, 0, 0), resources=None):
    form = p.make_stream(body)
    form["/Type"] = pikepdf.Name("/XObject")
    form["/Subtype"] = pikepdf.Name("/Form")
    form["/Matrix"] = pikepdf.Array(list(matrix))
    form["/Resources"] = resources if resources is not None else page.Resources
    xo = page.Resources.get("/XObject", pikepdf.Dictionary())
    xo[name] = form
    page.Resources["/XObject"] = xo
    return form


def _prepend(p, page, inject: bytes):
    streams = page.Contents if isinstance(page.Contents, pikepdf.Array) else [page.Contents]
    body = b"\n".join(bytes(st.read_bytes()) for st in streams)
    page.Contents = p.make_stream(inject + b"\n" + body)


def text_in_form(doc):
    """Text that exists ONLY inside a Form XObject invoked as TAGGED content: the band cannot see it.

    A model that follows `Do` would judge it; the boundary refuses the structure itself.
    """
    def fn(p):
        page = p.pages[0]
        _add_form(p, page, "/FxTagged", b"BT /F1 12 Tf 1 0 0 1 100 0 Tm ( ) Tj ET")
        _prepend(p, page, b"q\n/FxTagged Do\nQ")
    return _pikemutate(doc, fn)


def nested_form(doc):
    """A Form XObject that carries its own Form XObjects — depth the model does not interpret."""
    def fn(p):
        page = p.pages[0]
        inner = p.make_stream(b"")
        inner["/Type"] = pikepdf.Name("/XObject")
        inner["/Subtype"] = pikepdf.Name("/Form")
        inner["/BBox"] = pikepdf.Array([0, 0, 10, 10])
        res = pikepdf.Dictionary({"/XObject": pikepdf.Dictionary({"/FxInner": inner})})
        outer = _add_form(p, page, "/FxOuter", b"", resources=res)
        outer["/BBox"] = pikepdf.Array([0, 0, 10, 10])
        _prepend(p, page, b"q\n/FxOuter Do\nQ")
    return _pikemutate(doc, fn)


def unresolved_do_in_form(doc):
    """A form that invokes a name its own resources do not carry: the chain that hid from a resolver-first scan.

    The boundary promises «Do deeper than 1 is refused» — the refusal must not depend on the lookup succeeding.
    """
    def fn(p):
        page = p.pages[0]
        outer = _add_form(p, page, "/FxChain", b"q /Missing Do Q", resources=pikepdf.Dictionary({}))
        outer["/BBox"] = pikepdf.Array([0, 0, 10, 10])
        _prepend(p, page, b"q\n/FxChain Do\nQ")
    return _pikemutate(doc, fn)


def text_rise(doc):
    """A glyph drawn off its baseline (Ts): the model does not track where it lands."""
    def fn(p):
        _prepend(p, p.pages[0], b"BT /F1 12 Tf 4 Ts ( ) Tj ET")
    return _pikemutate(doc, fn)


def rotated_artifact_text(doc):
    """Artifact text under a rotated matrix: an axis-aligned band cannot judge where it sits."""
    def fn(p):
        _prepend(p, p.pages[0],
                b"/Artifact BMC q 0 1 -1 0 200 200 cm BT /F1 12 Tf ( ) Tj ET Q EMC")
    return _pikemutate(doc, fn)


# (mutation, expected check, must_stay_green)
MUTATIONS = [
    (swap_next_prev, "nav-buttons", False),
    (self_link, "nav-buttons", False),
    (whiteout_strip, "render", False),
    (swap_icons, "render", False),
    (foreign_icon, "render", False),
    (moment_matched_icon, "render", False),
    (icon_input_lost, "render", False),
    (rename_nav_class, "render", False),
    (whiteout_body, "page-ink", False),
    (whiteout_sparse_page, "page-ink", False),
    (drop_cover_art, "page-ink", False),
    (drop_divider_art, "page-ink", False),
    (drop_image_object, "page-images", False),
    (ltr, "rtl-direction", False),
    (two_page_layout, "single-page", False),
    (drop_outline_entry, "outline", False),
    (swap_contents_rows, "contents-links", False),
    (extra_printed_number, "contents-numbers", False),
    (drop_footer_number, "footer-numbers", False),
    (swap_footer_numbers, "footer-numbers", False),
    (move_footer_up, "footer-numbers", False),
    (break_ref_link, "ref-links", False),
    (foreign_font, "fonts", False),
    (stale_back_cover, "version-consistency", False),
    (blank_page, "no-blank-pages", False),
    (blank_text_page_with_decor, "no-blank-pages", False),
    (delete_paragraph, "page-words", False),
    (drop_tagging, "tagged", False),
    (markinfo_indirect, "tagged", True),          # positive: a valid indirect reference must stay green
    (wrong_source_stamp, "provenance", False),
    (stale_version, "title", False),
    (presentation_form, "text-layer", False),
    (bfrange_two_letters, "text-layer", False),
    (swapped_letters, "copy-fidelity", False),
    (split_text_objects, "line-order", False),
    (wrong_mark, "vocalised", False),
    (wrong_printed_count, "gate-claims", False),
    (drop_page_labels, "page-labels", False),
    (rename_destination, "named-destinations", False),
    (drop_xmp_title, "xmp", False),
    (strip_output_intent, "output-intent", False),
    (break_box_order, "output-intent", False),
    (drop_attachment, "attachments", False),
    (art_over_dpi, "art-dpi", False),
    (drop_parent_tree, "pdfua", False),
    (field_without_tu, "acroform", False),
    (link_without_contents, "link-tagging", False),
    (paragraph_under_document, "tagged-structure", False),
    (pagination_body_text, "furniture-band", False),
    (wrong_chrome_version, "chrome-version", False),
    (artifact_body_text, "furniture-band", False),
    (artifact_by_name, "furniture-band", False),
    (form_xobject_text, "furniture-band", False),
    (text_in_form, "pdf-model", False),
    (nested_form, "pdf-model", False),
    (unresolved_do_in_form, "pdf-model", False),
    (text_rise, "pdf-model", False),
    (rotated_artifact_text, "pdf-model", False),
    (missing_rendered_hash, "provenance", False),
    (rendered_mismatch, "provenance", False),
    (print_copy_with_icons, "render", False),
    (drop_page, "pages", False),
]

if __name__ == "__main__":
    try:
        base = G.gate(fresh())
    except G.GateInput as exc:                    # a missing floor/claim is an input error, named, not a crash
        print(f"\nFAIL input - {exc}")
        raise SystemExit("SELFTEST FAILED — the gate refused its input before judging it")
    print(f"\nbaseline: {'PASS' if not base else 'FAIL ' + str(base)}")
    missed = ["baseline"] if base else []
    declared_na = dict(getattr(NS, "GATE_NA", {}))
    # The documents CI builds must exercise the whole suite: an exemption there would mean a mutation
    # the pipeline never proves — and CI is the only place nobody is watching.
    if getattr(NS, "__name__", "") in ("nav_spec", "report_spec") and declared_na:
        print(f"SELFTEST FAILED — {NS.__name__} declares GATE_NA but is built by CI; fix the document, not the suite")
        raise SystemExit(1)
    names = {m[0].__name__ for m in MUTATIONS}
    if len(MUTATIONS) != SUITE_SIZE:
        print(f"SELFTEST FAILED — the suite holds {len(MUTATIONS)} mutations, SUITE_SIZE says {SUITE_SIZE}")
        raise SystemExit(1)
    if set(declared_na) - names:
        print(f"SELFTEST FAILED — the spec declares n/a for names the suite does not hold: {sorted(set(declared_na) - names)}")
        raise SystemExit(1)
    if len(MUTATIONS) - len(declared_na) != NS.GATE_MUTATIONS:
        print(f"SELFTEST FAILED — {len(MUTATIONS)} mutations − {len(declared_na)} declared n/a "
              f"!= the {NS.GATE_MUTATIONS} the spec declares")
        raise SystemExit(1)
    applied = 0
    for mutate, expect, green in MUTATIONS:
        name = mutate.__name__
        declared = name in declared_na
        d = fresh()
        try:
            out = mutate(d)          # a mutation may return a re-serialised document (pikepdf round-trip)
            if out is NA:
                if declared:
                    print(f"\n>>> {name:24s} declared n/a — {declared_na[name]}\n")
                else:
                    print(f"\n>>> {name:24s} NOT APPLICABLE but the spec does not declare it\n")
                    missed.append(name + " (undeclared n/a)")
                continue
            if out is not None and hasattr(out, "page_count"):
                d = out
            try:
                failed = G.gate(reread(d))
            except G.GateInput as exc:             # the mutation broke the FILE, not the rule: say so
                print(f"\n>>> {name}: the gate refused the mutated file as input ({exc})")
                missed.append(name + " (input refusal)")
                continue
        finally:
            restore_all()
            NS.SOURCE_HTML, NS.GATE_CHECKS = OLD_SOURCE, OLD_CHECKS
        if declared:
            # A declared exemption means «this document cannot exhibit the defect». If the mutation DID
            # apply, the declaration is wrong: either the gate now catches it (stale) or it does not
            # (a real miss). Both fail — an exemption may never licence a miss.
            stale = (not green) and expect in failed
            print(f"\n>>> {name:24s} declared n/a, yet the mutation applied and the gate says {failed} — "
                  f"{'STALE EXEMPTION' if stale else 'MISSED, not exempt'}\n")
            missed.append(name + (" (stale exemption)" if stale else " (declared n/a but applied)"))
            continue
        applied += 1
        ok = (not failed) if green else (expect in failed)
        print(f"\n>>> {name:24s} expect {'PASS' if green else 'FAIL ' + expect:20s} -> "
              f"{'CAUGHT' if ok else 'MISSED'} {failed}\n")
        if not ok:
            missed.append(name)
    if applied != NS.GATE_MUTATIONS:
        print(f"SELFTEST FAILED — {applied} mutations applied to this document, the spec declares {NS.GATE_MUTATIONS}")
        missed.append(f"applicable:{applied}!={NS.GATE_MUTATIONS}")
    # The blank-page rule does not depend on the document's size (copy-fidelity does: one lost page of 50 is 2% of the
    # words and would pass). Proven on a synthetic 50-page document, outside the 12-page gate.
    big = fitz.open()
    for k in range(50):
        big.new_page().insert_text((72, 100), "word " * 60, fontname="helv", fontsize=10)
    big[30].add_redact_annot(big[30].rect); big[30].apply_redactions()
    big[30].insert_image(fitz.Rect(300, 400, 332, 432), pixmap=fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 32, 32), False))
    blank, _, _ = G.blank_pages(reread(big), range(50))
    ok = len(blank) == 1 and blank[0].startswith("p31(")
    print(f">>> 50-page document, page 31 emptied + 32pt image -> {'CAUGHT' if ok else 'MISSED'} {blank}\n")
    if not ok:
        missed.append("blank_page_in_50")
    # The print-copy predicate, on a page built for it: a rectangle inside a slot must be found, and a
    # document that draws no icon must come back empty. A predicate never seen finding anything proves
    # nothing — and the whole-document mutation also fails on the real strip, so it cannot isolate this one.
    probe = fitz.open()
    probe_page = probe.new_page(width=595, height=842)
    slot_x = NS.SLOTS["next"]
    probe_page.draw_rect(fitz.Rect(slot_x + 4, NS.NAV_Y0 + 4, slot_x + 16, NS.NAV_Y1 - 4),
                         color=(0, 0, 0), fill=(0, 0, 0))
    found = G.slot_drawings(probe)
    ok = len(found) == 1 and "next" in found[0]
    print(f">>> slot_drawings, one rect inside a slot -> {'CAUGHT' if ok else 'MISSED'} {found}\n")
    if not ok:
        missed.append("slot_drawings_positive")
    if not getattr(NS, "NAV_VISIBLE", True):
        empty = G.slot_drawings(fresh())
        ok = not empty
        print(f">>> slot_drawings, the print document -> {'CLEAN' if ok else 'MISSED'} {empty[:2]}\n")
        if not ok:
            missed.append("slot_drawings_negative")
    # Malformed inputs: the CLI must refuse BY NAME (non-zero, no traceback), not crash inside a check.
    import subprocess, tempfile
    data = open(SRC, "rb").read()
    with tempfile.TemporaryDirectory() as tmp:
        trunc = os.path.join(tmp, "truncated.pdf")
        open(trunc, "wb").write(data[: len(data) // 2])
        enc = os.path.join(tmp, "encrypted.pdf")
        import pikepdf
        with pikepdf.open(SRC) as pdf:
            pdf.save(enc, encryption=pikepdf.Encryption(owner="selftest-owner", user="selftest-user", R=6))
        for path, want in ((trunc, "truncated"), (enc, "encrypted")):
            r = subprocess.run([sys.executable, G.__file__, path], capture_output=True, text=True)
            out = r.stdout + r.stderr
            ok = r.returncode != 0 and want in r.stdout and "Traceback" not in out
            print(f">>> {os.path.basename(path):14s} -> {'CAUGHT' if ok else 'MISSED'} "
                  f"exit {r.returncode}: {r.stdout.strip()[:110]}\n")
            if not ok:
                missed.append(f"input:{want}")
    if missed:
        print(f"SELFTEST FAILED — not caught: {missed}")
        raise SystemExit(1)
    print(f"SELFTEST PASSED — baseline clean, {applied}/{applied} applicable mutations on the right side "
          f"({sum(1 for m in MUTATIONS if m[2])} positive, {len(declared_na)} declared n/a for this document)")
