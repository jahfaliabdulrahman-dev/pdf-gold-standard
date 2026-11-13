#!/usr/bin/env python3
"""Prove the gate can fail: a gate never seen failing is unverified.

Usage: python3 scripts/gate_selftest.py built.pdf

The built PDF must PASS. Then each mutation is applied to an in-memory copy, and the gate must
exit non-zero AND name the expected check. Exit 0 only if every mutation is caught.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pymupdf as fitz  # noqa: E402

import nav_spec as NS  # noqa: E402
import verify_pdf as G  # noqa: E402

SRC = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"


def fresh():
    return fitz.open(SRC)


def reread(doc):
    return fitz.open("pdf", doc.tobytes())


def strip_link(doc, i, role):
    x = NS.SLOTS[role]
    return next(l for l in doc[i].get_links() if abs(l["from"].x0 - x) < 2 and abs(l["from"].y0 - NS.NAV_Y0) < 2)


def swap_next_prev(doc):
    i = NS.NAV_PAGES[2]
    a, b = strip_link(doc, i, "next"), strip_link(doc, i, "prev")
    a["page"], b["page"] = b["page"], a["page"]
    doc[i].update_link(a); doc[i].update_link(b)


def self_link(doc):
    i = NS.NAV_PAGES[-1]
    a = strip_link(doc, i, "next"); a["page"] = i
    doc[i].update_link(a)


def whiteout_strip(doc):
    # every link still points where it should, but the buttons are no longer drawn on one page
    p = doc[NS.NAV_PAGES[0]]
    p.draw_rect(fitz.Rect(40, NS.NAV_Y0 - 10, 210, NS.NAV_Y1 + 14), color=None, fill=(1, 1, 1), overlay=True)


def swap_icons(doc):
    # both arrows are drawn and both links are right, but each arrow sits in the other's slot
    p = doc[NS.NAV_PAGES[1]]
    rect = {r: fitz.Rect(NS.SLOTS[r], NS.NAV_Y0, NS.SLOTS[r] + NS.NAV_W, NS.NAV_Y1) for r in ("next", "prev")}
    pix = {r: p.get_pixmap(dpi=300, clip=rect[r]) for r in rect}
    p.insert_image(rect["next"], pixmap=pix["prev"]); p.insert_image(rect["prev"], pixmap=pix["next"])


def blank_text_page_with_decor(doc):
    # the same overflow artifact, plus a small decorative image: "has an image" must not excuse an empty page
    i = blank_page(doc)
    doc[i].insert_image(fitz.Rect(300, 400, 332, 432), pixmap=fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 32, 32), False))


def bfrange_two_letters(doc):
    # two letters on one glyph, written as a range instead of a bfchar entry
    x = _tounicode_xref(doc); s = doc.xref_stream(x)
    doc.update_stream(x, s.replace(b"endbfchar", b"endbfchar\n1 beginbfrange\n<F000> <F000> [<06440627>]\nendbfrange", 1))


def drop_tagging(doc):
    doc.xref_set_key(doc.pdf_catalog(), "Lang", "null")
    doc.xref_set_key(doc.pdf_catalog(), "MarkInfo", "null")


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
    i = next(k for k in NS.NAV_PAGES if not doc[k].get_images())
    p = doc[i]
    p.add_redact_annot(fitz.Rect(0, NS.NAV_Y1 + 10, p.rect.width, p.rect.height - 60))
    p.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    return i


def _tounicode_xref(doc, page=4):
    """ToUnicode stream of the body font with the most entries on a text page."""
    best = None
    for xref, *_ in doc[page].get_fonts():
        kind, tu = doc.xref_get_key(xref, "ToUnicode")
        if kind == "xref":
            x = int(tu.split()[0]); n = doc.xref_stream(x).count(b"<")
            best = max(best or (0, x), (n, x))
    return best[1]


def presentation_form(doc):
    # Chrome's raw mapping: an Arabic glyph mapped to its Presentation Form (ﺎ U+FE8E) instead of ا
    x = _tounicode_xref(doc); s = doc.xref_stream(x)
    doc.update_stream(x, s.replace(b"<0627>", b"<FE8E>", 1))


def swapped_letters(doc):
    # copy produces the wrong letters while every glyph still has exactly one base code point
    x = _tounicode_xref(doc); s = doc.xref_stream(x)
    doc.update_stream(x, s.replace(b"<0627>", b"<TMP0>").replace(b"<0644>", b"<0627>").replace(b"<TMP0>", b"<0644>"))


def split_text_objects(doc):
    # back to one text object per word: MuPDF forgets the direction at each BT and returns the words reversed
    for page in doc:
        for x in page.get_contents():
            doc.update_stream(x, doc.xref_stream(x).replace(b"/ReversedChars BMC", b"ET\nBT\n/ReversedChars BMC"))


def wrong_mark(doc):
    # a kasra that copies as a fatha: the vocalised line is no longer exact
    for xref, *_ in doc[NS.BASMALA].get_fonts():
        kind, tu = doc.xref_get_key(xref, "ToUnicode")
        if kind == "xref":
            x = int(tu.split()[0]); s = doc.xref_stream(x)
            if b"<0650>" in s: doc.update_stream(x, s.replace(b"<0650>", b"<064E>"))


def drop_page(doc):
    doc.delete_page(7)


MUTATIONS = [
    (swap_next_prev, "nav-buttons"),
    (self_link, "nav-buttons"),
    (whiteout_strip, "render"),
    (swap_icons, "render"),
    (ltr, "rtl-direction"),
    (two_page_layout, "single-page"),
    (drop_outline_entry, "outline"),
    (swap_contents_rows, "contents-links"),
    (foreign_font, "fonts"),
    (blank_page, "no-blank-pages"),
    (blank_text_page_with_decor, "no-blank-pages"),
    (drop_tagging, "tagged"),
    (presentation_form, "text-layer"),
    (bfrange_two_letters, "text-layer"),
    (swapped_letters, "copy-fidelity"),
    (split_text_objects, "line-order"),
    (wrong_mark, "vocalised"),
    (drop_page, "pages"),
]

if __name__ == "__main__":
    base = G.gate(fresh())
    print(f"baseline: {'PASS' if not base else 'FAIL ' + str(base)}\n")
    missed = ["baseline"] if base else []
    for mutate, expect in MUTATIONS:
        d = fresh(); mutate(d); failed = G.gate(reread(d))
        ok = expect in failed
        print(f"\n>>> {mutate.__name__:20s} expect FAIL {expect:16s} -> {'CAUGHT' if ok else 'MISSED'} {failed}\n")
        if not ok:
            missed.append(mutate.__name__)
    if missed:
        print(f"SELFTEST FAILED — not caught: {missed}")
        raise SystemExit(1)
    print(f"SELFTEST PASSED — baseline clean, {len(MUTATIONS)}/{len(MUTATIONS)} mutations caught")
