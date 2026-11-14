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

import nav_spec as NS  # noqa: E402
import verify_pdf as G  # noqa: E402

SRC = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"
OLD_CHECKS, OLD_SOURCE = NS.GATE_CHECKS, NS.SOURCE_HTML
_RESTORE = []


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
def _source_variant(transform) -> None:
    """Point the gate at a temporary variant of the source HTML (a real end-to-end mutation)."""
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", NS.SOURCE_HTML), encoding="utf-8").read()
    fd, path = tempfile.mkstemp(suffix=".html"); os.close(fd)
    open(path, "w", encoding="utf-8").write(transform(src))
    NS.SOURCE_HTML = path

    def undo():
        NS.SOURCE_HTML = OLD_SOURCE
        os.unlink(path)
    _RESTORE.append(undo)


def rename_nav_class(doc):
    # a benign refactor (HTML + CSS renamed together, page unchanged) must not silence the strongest check
    _source_variant(lambda s: s.replace('class="nav"', 'class="navbar"')
                    .replace(".nav{", ".navbar{").replace(".nav ", ".navbar ").replace(".nav,", ".navbar,"))


def stale_back_cover(doc):
    # only the BACK cover still announces the previous version
    _source_variant(lambda s: s.replace(f"الإصدار {NS.GUIDE_VERSION_AR} — نوفمبر", "الإصدار ٢٫٢ — نوفمبر"))


def icon_input_lost(doc):
    # the cheap form of H2: the gate's own input disappears
    real = G.source_icons
    G.source_icons = lambda: []
    _RESTORE.append(lambda: setattr(G, "source_icons", real))


def wrong_printed_count(doc):
    # the document's printed count no longer matches the live number of checks
    NS.GATE_CHECKS = OLD_CHECKS + 1
    _RESTORE.append(lambda: setattr(NS, "GATE_CHECKS", OLD_CHECKS))


# ---------------------------------------------------------------- document mutations
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
    for im in p.get_images():
        p.delete_image(im[0])


def drop_cover_art(doc):
    _drop_images(doc, NS.COVER)


def drop_divider_art(doc):
    _drop_images(doc, 3)          # the first divider page


def drop_image_object(doc):
    # one of the four QR codes on the references page disappears; its text link is untouched
    p = doc[NS.REF_PAGE]
    p.delete_image(p.get_images()[0][0])


def swap_icons(doc):
    # both arrows are drawn and both links are right, but each arrow sits in the other's slot
    p = doc[NS.NAV_PAGES[1]]
    rect = {r: fitz.Rect(NS.SLOTS[r], NS.NAV_Y0, NS.SLOTS[r] + NS.NAV_W, NS.NAV_Y1) for r in ("next", "prev")}
    pix = {r: p.get_pixmap(dpi=300, clip=rect[r]) for r in rect}
    p.insert_image(rect["next"], pixmap=pix["prev"]); p.insert_image(rect["prev"], pixmap=pix["next"])


def foreign_icon(doc):
    # a different icon in the "next" slot: a disc with the arrow's own ink share and centre of mass
    import math
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
    i = next((k for k in NS.NAV_PAGES if not doc[k].get_images()), None)
    if i is None:
        raise SystemExit("selftest: no text-only page among NAV_PAGES to blank - adjust blank_page()")
    p = doc[i]
    p.add_redact_annot(fitz.Rect(0, NS.NAV_Y1 + 10, p.rect.width, p.rect.height - 60))
    p.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    return i


def delete_paragraph(doc):
    # H5: ~18 words vanish from a body page (one paragraph); every AGGREGATE ratio still passes
    p = doc[NS.NAV_PAGES[2]]
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
        raise SystemExit(f"selftest: delete_paragraph removed only {removed} words - adjust it")


def _footer_span(doc, i):
    for b in doc[i].get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = s["text"].strip()
                if t and all(ch.isdigit() and ord(ch) < 128 for ch in t) and NS.FOOTER_Y_MIN <= s["bbox"][1] <= NS.FOOTER_Y_MAX:
                    return s["bbox"]
    raise SystemExit(f"selftest: no footer span on p{i+1} - adjust _footer_span()")


def drop_footer_number(doc):
    for i in (4, 5, 8):
        p = doc[i]
        p.add_redact_annot(fitz.Rect(_footer_span(doc, i)))
        p.apply_redactions()


def swap_footer_numbers(doc):
    p = doc[4]
    r = fitz.Rect(_footer_span(doc, 4))
    p.add_redact_annot(r); p.apply_redactions()
    p.insert_text((r.x0, r.y1 - 2), "9", fontname="helv", fontsize=8)


def move_footer_up(doc):
    p = doc[4]
    r = fitz.Rect(_footer_span(doc, 4))
    p.add_redact_annot(r); p.apply_redactions()
    p.insert_text((r.x0, 500), "5", fontname="helv", fontsize=8)


def break_ref_link(doc):
    links = sorted([l for l in doc[NS.REF_PAGE].get_links() if l.get("kind") == fitz.LINK_URI], key=lambda l: l["from"].y0)
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
    return _pikemutate(doc, lambda p: p.Root.__delitem__("/PageLabels"))


def rename_destination(doc):
    def fn(p):
        p.Root.Names.Dests.Names[0] = pikepdf.String("cover-renamed")
    return _pikemutate(doc, fn)


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
        del p.attachments["source.html"]
        p.Root.AF = pikepdf.Array([s.obj for n, s in p.attachments.items()])
    return _pikemutate(doc, fn)



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
        del p.Root.StructTreeRoot["/ParentTree"]
    return _pikemutate(doc, fn)


def field_without_tu(doc):
    def fn(p):
        del p.Root.AcroForm.Fields[0]["/TU"]
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
    (drop_page, "pages", False),
]

if __name__ == "__main__":
    base = G.gate(fresh())
    print(f"\nbaseline: {'PASS' if not base else 'FAIL ' + str(base)}")
    missed = ["baseline"] if base else []
    if len(MUTATIONS) != NS.GATE_MUTATIONS:
        print(f"SELFTEST FAILED — {len(MUTATIONS)} mutations registered, nav_spec declares {NS.GATE_MUTATIONS}")
        raise SystemExit(1)
    for mutate, expect, green in MUTATIONS:
        d = fresh()
        try:
            out = mutate(d)          # a mutation may return a re-serialised document (pikepdf round-trip)
            if out is not None and hasattr(out, "page_count"):
                d = out
            failed = G.gate(reread(d))
        finally:
            restore_all()
            NS.SOURCE_HTML, NS.GATE_CHECKS = OLD_SOURCE, OLD_CHECKS
        ok = (not failed) if green else (expect in failed)
        print(f"\n>>> {mutate.__name__:24s} expect {'PASS' if green else 'FAIL ' + expect:20s} -> "
              f"{'CAUGHT' if ok else 'MISSED'} {failed}\n")
        if not ok:
            missed.append(mutate.__name__)
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
    print(f"SELFTEST PASSED — baseline clean, {len(MUTATIONS)}/{len(MUTATIONS)} mutations on the right side "
          f"({sum(1 for m in MUTATIONS if m[2])} positive)")
