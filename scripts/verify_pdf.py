#!/usr/bin/env python3
"""Delivery gate — verify a built PDF against the Gold Standard and nav_spec.py.

Usage: python3 scripts/verify_pdf.py out.pdf

Exit 0 = every check passed; exit 1 = at least one FAIL (names printed). The same script runs
locally, inside build.py (before publishing) and in CI. Every check compares element by element
against nav_spec — never a count or a sorted set, which two swapped buttons would still pass.
A check that cannot read what it needs FAILS; it never passes by default.
"""
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pymupdf as fitz  # noqa: E402

import nav_spec as NS  # noqa: E402

fails: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    print(("PASS " if ok else "FAIL ") + name + " - " + detail)
    if not ok:
        fails.append(name)


def goto_links(page):
    return [l for l in page.get_links() if l.get("kind") == fitz.LINK_GOTO]


def gate(doc) -> list[str]:
    fails.clear()

    # 1. page count = intended build
    check("pages", doc.page_count == NS.PAGES, f"{doc.page_count} (expected {NS.PAGES})")
    if doc.page_count != NS.PAGES:
        return fails  # every later check maps by page index; stop rather than report noise

    # 2. viewer preferences: single page + right-to-left reading
    cat = doc.pdf_catalog()
    layout = doc.xref_get_key(cat, "PageLayout")[1]
    check("single-page", layout == "/SinglePage", layout)
    kind, val = doc.xref_get_key(cat, "ViewerPreferences")
    vp = doc.xref_object(int(val.split()[0])) if kind == "xref" else val
    check("rtl-direction", "/Direction/R2L" in vp.replace(" ", ""), " ".join(vp.split())[:70])

    # 3. nav buttons: each slot -> its own expected target; no self-links; no strip links elsewhere
    bad = []
    for i, page in enumerate(doc):
        strip = [l for l in goto_links(page) if abs(l["from"].y0 - NS.NAV_Y0) < 2]
        if i not in NS.NAV_PAGES:
            if strip:
                bad.append(f"p{i+1}: {len(strip)} unexpected nav links")
            continue
        for role, x in NS.SLOTS.items():
            hits = [l for l in strip if abs(l["from"].x0 - x) < 2]
            want = NS.nav_target(role, i)
            if len(hits) != 1:
                bad.append(f"p{i+1} {role}: {len(hits)} links in slot")
            elif hits[0]["page"] != want:
                bad.append(f"p{i+1} {role}: ->{hits[0]['page']+1} want {want+1}")
            elif want == i:
                bad.append(f"p{i+1} {role}: self-link")
        if len(strip) != len(NS.SLOTS):
            bad.append(f"p{i+1}: {len(strip)} strip links, want {len(NS.SLOTS)}")
    check("nav-buttons", not bad, "; ".join(bad[:4]) or f"{len(NS.NAV_PAGES)} pages x {len(NS.SLOTS)} slots")

    # 3b. render: every nav slot must show ink ON THE PAGE. Links, outline and text can all be right while the
    # strip itself is not drawn (CSS change, missing icon, something painted over it) — only pixels can tell.
    # Measured on the real build at 300 dpi: 0.14–0.36 of a slot differs from its background; a dead slot: 0.00.
    dead, seen = [], []
    for i in NS.NAV_PAGES:
        for role, x in NS.SLOTS.items():
            clip = fitz.Rect(x + 2, NS.NAV_Y0 + 2, x + NS.NAV_W - 2, NS.NAV_Y1 - 2)
            pm = doc[i].get_pixmap(dpi=300, clip=clip, colorspace=fitz.csGRAY)
            px = pm.samples
            bg = statistics.median(px)
            on = [k for k, v in enumerate(px) if abs(v - bg) > NS.SLOT_INK_CONTRAST]
            ink = len(on) / len(px)
            seen.append(ink)
            if not NS.SLOT_INK_MIN <= ink <= NS.SLOT_INK_MAX:
                dead.append(f"p{i+1} {role}: ink {ink:.2f}")
                continue
            # the right icon, not just some ink: centre of mass of the ink against the icon's measured signature
            cx = sum(k % pm.stride for k in on) / len(on) / pm.width - 0.5
            cy = sum(k // pm.stride for k in on) / len(on) / pm.height - 0.5
            wx, wy = NS.SLOT_SHAPE[role]
            if abs(cx - wx) > NS.SLOT_SHAPE_TOL or abs(cy - wy) > NS.SLOT_SHAPE_TOL:
                dead.append(f"p{i+1} {role}: icon centre ({cx:+.2f},{cy:+.2f}), expected ({wx:+.2f},{wy:+.2f})")
    check("render", not dead, "; ".join(dead[:6]) or
          f"{len(NS.NAV_PAGES)} pages x {len(NS.SLOTS)} slots: each icon drawn in its own slot (ink {min(seen):.2f}-{max(seen):.2f})")

    # 4. outline = spec (titles, levels, pages)
    toc = doc.get_toc()
    check("outline", toc == NS.TOC, f"{len(toc)} entries (expected {len(NS.TOC)})")

    # 5. contents page: clickable rows top-to-bottom -> spec targets, and printed page numbers equal them
    rows = sorted(goto_links(doc[NS.CONTENTS]), key=lambda l: l["from"].y0)
    got = [l["page"] for l in rows]
    check("contents-links", got == NS.TOC_ROWS, f"{[g+1 for g in got]} (expected {[t+1 for t in NS.TOC_ROWS]})")
    printed = printed_page_numbers(doc[NS.CONTENTS])
    want = [t + 1 for t in NS.TOC_ROWS]
    outline_pages = {e[2] for e in NS.TOC}
    check("contents-numbers", printed == want and set(want) <= outline_pages,
          f"printed {printed} vs links/outline {want}" if printed else "could not parse printed numbers")

    # 6. external links on the references page
    uris = [l.get("uri") for l in sorted(doc[NS.REF_PAGE].get_links(), key=lambda l: l["from"].y0)
            if l.get("kind") == fitz.LINK_URI]
    check("ref-links", uris == NS.REF_URLS, f"{len(uris)} URIs")

    # 7. fonts: house family only; the basmala page may add the macOS vocalisation face
    foreign = []
    for i, page in enumerate(doc):
        allowed_extra = NS.BASMALA_FACES if i == NS.BASMALA else set()
        for f in page.get_fonts():
            name = f[3].split("+")[-1]
            if not name:
                foreign.append(f"p{i+1}:<unnamed {f[1]}>")
            elif not name.startswith(NS.HOUSE_FONT_PREFIX) and name not in allowed_extra:
                foreign.append(f"p{i+1}:{name}")
    check("fonts", not foreign, ", ".join(sorted(set(foreign))[:6]) or f"only {NS.HOUSE_FONT_PREFIX}* (+ {'/'.join(sorted(NS.BASMALA_FACES))} on the basmala page)")

    # 8. title metadata
    title = (doc.metadata or {}).get("title", "")
    check("title", bool(title), title[:60])

    # 9. no blank / overflow pages: far below the median text, excluding cover + contents, and no image
    body = [i for i in range(doc.page_count) if i not in (NS.COVER, NS.CONTENTS)]
    lens = {i: len("".join(doc[i].get_text().split())) for i in body}
    med = statistics.median(lens.values())
    def image_cover(page):          # share of the page under images; overlaps counted once per image, capped at 1
        area = sum(abs(r & page.rect) for im in page.get_images() for r in page.get_image_rects(im[0]))
        return min(1.0, area / abs(page.rect))
    low = {i: image_cover(doc[i]) for i, n in lens.items() if n < 0.15 * med}
    blank = [f"p{i+1}({lens[i]} chars, images cover {c:.0%})" for i, c in low.items() if c < NS.BLANK_EXEMPT_IMAGE_COVER]
    check("no-blank-pages", not blank, ", ".join(blank) or
          f"median {med:.0f} chars; low-text pages excused by image cover: " + (", ".join(f"p{i+1} {c:.0%}" for i, c in low.items()) or "none"))

    # 9b. tagged PDF, as README declares: language, marked content, structure tree
    lang = doc.xref_get_key(cat, "Lang")[1].strip("()")
    marked = "true" in doc.xref_get_key(cat, "MarkInfo")[1].replace(" ", "").split("/Marked")[-1][:5]
    tree = doc.xref_get_key(cat, "StructTreeRoot")[0] == "xref"
    missing = [n for n, ok in ((f"Lang={NS.LANG}", lang == NS.LANG), ("MarkInfo/Marked", marked), ("StructTreeRoot", tree)) if not ok]
    check("tagged", not missing, "missing: " + ", ".join(missing) if missing else f"Lang={lang}, Marked, structure tree")

    # 10. text layer: every glyph carries ONE base code point (scripts/fix_text_layer.py). Presentation Forms or
    #     multi-letter entries are what makes readers reverse letters inside ligatures (لأ→ال، في→يف).
    bad_tu = text_layer_violations(doc)
    check("text-layer", not bad_tu, "; ".join(bad_tu[:3]) or "one base code point per glyph")

    # 11. copy fidelity, measured with PDFium (Chrome/Edge's engine) against the words of the source HTML
    rec, seq = copy_fidelity(doc)
    ok = rec is not None and rec >= NS.COPY_MIN_RECALL and seq >= NS.COPY_MIN_SEQUENCE
    check("copy-fidelity", ok, f"recall {rec:.3f} / sequence {seq:.3f} (min {NS.COPY_MIN_RECALL} / {NS.COPY_MIN_SEQUENCE})"
          if rec is not None else "could not read source HTML or PDF text")

    # 12. line order for stream-order readers: MuPDF (PyMuPDF, RAG extractors) must return each line's words in order
    _, mseq = copy_fidelity(doc, engine="mupdf")
    check("line-order", mseq is not None and mseq >= NS.MUPDF_MIN_SEQUENCE,
          f"MuPDF sequence {mseq:.3f} (min {NS.MUPDF_MIN_SEQUENCE})" if mseq is not None else "could not read source HTML or PDF text")

    # 13. vocalised text: the basmala must copy exactly, marks on their letters (PDFium and MuPDF)
    import re as _re
    import unicodedata as _ud
    ctrl = _re.compile("[\u2060\u200b\u200e\u200f\u202a-\u202e\u2066-\u2069]")
    norm = lambda t: _ud.normalize("NFC", ctrl.sub("", t))
    want = _ud.normalize("NFC", NS.VOCALISED)
    got = {"MuPDF": norm(doc[NS.BASMALA].get_text())}
    try:
        import pypdfium2
        got["PDFium"] = norm(pypdfium2.PdfDocument(doc.tobytes())[NS.BASMALA].get_textpage().get_text_range())
    except ImportError:
        got["PDFium"] = ""
    missing = [k for k, t in got.items() if want not in t]
    check("vocalised", not missing, f"basmala not exact in {missing}" if missing else "basmala exact in PDFium and MuPDF")
    return list(fails)


PRES_FORM = lambda ch: 0xFB50 <= ord(ch) <= 0xFDFF or 0xFE70 <= ord(ch) <= 0xFEFF


def text_layer_violations(doc) -> list[str]:
    import re
    import unicodedata
    out, seen = [], set()
    for page in doc:
        for xref, *_ in page.get_fonts():
            if xref in seen:
                continue
            seen.add(xref)
            kind, tu = doc.xref_get_key(xref, "ToUnicode")
            if kind != "xref":
                continue
            data = doc.xref_stream(int(tu.split()[0])).decode("latin1")
            pairs = []
            for blk in re.findall(r"beginbfchar(.*?)endbfchar", data, re.S):
                pairs += re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk)
            # ranges map codes too: <lo> <hi> <dst> (dst counts up) and <lo> <hi> [<d1> <d2> ...]
            for blk in re.findall(r"beginbfrange(.*?)endbfrange", data, re.S):
                for lo, hi, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]+>|\[[^\]]*\])", blk):
                    if dst.startswith("["):
                        pairs += [(f"{int(lo, 16) + k:04X}", h) for k, h in enumerate(re.findall(r"<([0-9A-Fa-f]+)>", dst))]
                    else:
                        h = dst.strip("<>")
                        pairs += [(f"{c:04X}", h[:-4] + f"{int(h[-4:], 16) + c - int(lo, 16):04X}") for c in range(int(lo, 16), int(hi, 16) + 1)]
            for cid, hx in pairs:
                txt = bytes.fromhex(hx).decode("utf-16-be", "replace")
                letters = [c for c in txt if unicodedata.category(c) != "Mn"]
                if any(PRES_FORM(c) for c in txt) or len(letters) > 1:
                    out.append(f"xref {xref} cid {cid}: {txt!r}")
    return out


def copy_fidelity(doc, engine="pdfium"):
    """(recall, sequence) of the source words in the engine's extraction; sequence counts words in order."""
    import collections
    import difflib
    import html
    import re
    import unicodedata
    try:
        import pypdfium2
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", NS.SOURCE_HTML), encoding="utf-8").read()
    except (ImportError, OSError):
        return None, None
    bidi = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c\u0640]")
    marks = re.compile("[\u064B-\u0652\u0653-\u0655\u0670]")
    word = re.compile(r"[\u0621-\u064A\u0671]+|[\u0660-\u0669]+|[A-Za-z][A-Za-z0-9.]*")
    words = lambda t: word.findall(marks.sub("", unicodedata.normalize("NFC", bidi.sub("", t))))
    src = re.sub(r"<(style|script|svg)\b.*?</\1>", " ", src, flags=re.S | re.I)
    truth = words(html.unescape(re.sub(r"<[^>]+>", " ", src)))
    if engine == "mupdf":
        got = words("\n".join(p.get_text() for p in doc))
    else:
        pd = pypdfium2.PdfDocument(doc.tobytes())
        got = words("\n".join(pd[i].get_textpage().get_text_range() for i in range(len(pd))))
    if not truth or not got:
        return None, None
    ct, cg = collections.Counter(truth), collections.Counter(got)
    recall = sum(min(ct[w], cg[w]) for w in ct) / len(truth)
    sm = difflib.SequenceMatcher(None, truth, got, autojunk=False)
    return recall, sum(b.size for b in sm.get_matching_blocks()) / len(truth)


def printed_page_numbers(page) -> list[int]:
    """Page numbers printed in the contents table, top to bottom.

    Chrome's text layer is visual-order, so multi-digit numbers come out reversed in plain text
    («١٠» -> «٠١»). Read digit glyphs with positions, group them into numbers by line, rebuild each
    number left-to-right, and keep the LEFT column (the page column in an RTL table)."""
    nums = []
    for b in page.get_text("rawdict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                ds = [c for c in s["chars"] if c["c"].isdigit()]
                if ds and len(ds) == len("".join(c["c"] for c in s["chars"]).strip()):
                    ds.sort(key=lambda c: c["bbox"][0])
                    val = int("".join(str(int(c["c"])) for c in ds))   # int() reads Arabic-Indic digits
                    nums.append((round(ds[0]["bbox"][1]), ds[0]["bbox"][0], val))
    if not nums:
        return []
    xs = sorted({round(x) for _, x, _ in nums})
    gaps = [(xs[k + 1] - xs[k], k) for k in range(len(xs) - 1)]
    if not gaps:
        return []
    cut = xs[max(gaps)[1]] + max(gaps)[0] / 2       # split the two columns at the widest x gap
    left = sorted((y, v) for y, x, v in nums if x < cut)
    return [v for _, v in left]


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"
    failed = gate(fitz.open(pdf))
    if failed:
        print(f"\n{len(failed)} gate(s) FAILED: {failed}")
        raise SystemExit(1)
    print("\nALL GATES PASSED")
