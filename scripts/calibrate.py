#!/usr/bin/env python3
"""Measure a build and write the numbers the gate needs into its spec module.

The gate compares the file against a MEASURED table (ink per page, words per page, images per page, printed
footers). Those numbers cannot be guessed and must never be hand-tuned to make a failing build pass: this
script derives them from a build that the author has looked at, and prints the exact block to paste.

Usage:
    PDF_SPEC=report_spec python3 scripts/calibrate.py out.pdf            # print the block
    PDF_SPEC=report_spec python3 scripts/calibrate.py out.pdf --write    # patch the spec file in place

`--write` rewrites ONLY the marked blocks (`# >>> CALIBRATED`, `# <<< CALIBRATED`) and the four scalars, so a
spec's prose and geometry survive. No measurement is taken from a PDF the gate has already refused for a
structural reason: ink is only meaningful on the intended page count.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import pymupdf as fitz  # noqa: E402

import spec_loader  # noqa: E402
import verify_pdf as G  # noqa: E402

NS = spec_loader.load()


def measure(pdf_path: str) -> dict:
    doc = G.open_for_gate(pdf_path)
    if doc.page_count != NS.PAGES:
        raise SystemExit(f"refusing to calibrate: {doc.page_count} pages, spec says {NS.PAGES}")
    # The numbers are the truth the gate will hold the NEXT build to, so they may only be taken from a
    # build the CURRENT gate accepts: otherwise calibrating a broken file blesses the defect.
    # The numbers are the truth the NEXT build is held to, so they may only come from a build whose
    # STRUCTURE the gate already accepts. Calibration-dependent checks are the ones this tool exists to
    # fill; any other failure means the build is broken and measuring it would bless the defect.
    CALIBRATION_ONLY = {"page-ink", "page-words", "page-images", "footer-numbers"}
    fails = G.gate(doc)
    blocking = [f for f in fails if f not in CALIBRATION_ONLY]
    if blocking:
        raise SystemExit(f"refusing to calibrate: the build fails {', '.join(blocking)}")
    texts = G.pdfium_texts(doc)
    if texts is None:
        raise SystemExit("refusing to calibrate: PDFium cannot read the text, so word counts would be zero")
    ink, words, images, footer = {}, {}, {}, {}
    for i, page in enumerate(doc):
        frac, cells = G.page_ink(page)
        ink[i] = (round(frac, 4), tuple(round(c, 4) for c in cells))
        n_img, cover = G.image_inventory(page)
        if n_img:
            images[i] = (n_img, round(cover, 4))
        words[i] = len(G.source_words(texts[i])) if i < len(texts) else 0
        nums = G.footer_numbers(page, texts[i] if i < len(texts) else None, limit=doc.page_count)
        if nums:
            footer[i] = nums[0]
    return {"ink": ink, "words": words, "images": images, "footer": footer,
            "mupdf": G.copy_fidelity(doc, engine="mupdf")[1],
        "pages": doc.page_count, "links": sum(len(G.goto_links(p)) for p in doc) + sum(
                len([l for l in p.get_links() if l.get("kind") == fitz.LINK_URI]) for p in doc)}


def block(name: str, value_src: str) -> str:
    """A marked block holding SOURCE TEXT, not a repr: the numbers must land as Python literals."""
    return f"# >>> CALIBRATED {name}\n{name} = {value_src}\n# <<< CALIBRATED {name}\n"


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"
    m = measure(path)
    ink_src = "{\n" + "".join(f"    {k}: ({v[0]}, {v[1]}),\n" for k, v in m["ink"].items()) + "}"
    words_src = "{" + ", ".join(f"{k}: {v}" for k, v in m["words"].items()) + "}"
    images_src = "{" + ", ".join(f"{k}: {v}" for k, v in m["images"].items()) + "}"
    footer_src = "{" + ", ".join(f"{k}: {v}" for k, v in m["footer"].items()) + "}"
    # The ratchet is the document's own measured order minus drift; it can never fall below the floor three
    # documents once shared, so the gate would refuse a spec that tried to buy green by lowering it.
    line_src = f"{max(0.75, round(m['mupdf'] - 0.02, 3)):.3f}"
    new = {
        "PAGE_INK": ink_src, "PAGE_WORDS": words_src, "IMAGE_PAGES": images_src, "FOOTER": footer_src,
        "LINE_ORDER_MIN": line_src,
        "EXPECTED_LINKS": str(m["links"]),
    }
    print(f"pages={m['pages']} links={m['links']}")
    if "--write" not in sys.argv:
        for name, val in new.items():
            print(block(name, val))
        return
    spec_file = os.path.join(HERE, "..", NS.__name__ + ".py")
    src = open(spec_file, encoding="utf-8").read()
    # Read the OLD value before the calibrated blocks are rewritten: for a spec whose EXPECTED_LINKS sits
    # inside a marked block, reading it afterwards compares the new number with itself and the guard never fires.
    old_links = re.search(r"^EXPECTED_LINKS = (\d+)", src, re.M)
    if old_links and int(old_links.group(1)) > m["links"] and "--force" not in sys.argv:
        raise SystemExit(f"refusing to lower EXPECTED_LINKS {old_links.group(1)} -> {m['links']}: "
                         "a lost link is a defect, not a new baseline (pass --force only if the design changed)")
    for name, val in new.items():
        pat = re.compile(rf"# >>> CALIBRATED {name}\n.*?\n# <<< CALIBRATED {name}\n", re.S)
        if not pat.search(src):
            raise SystemExit(f"{name}: no marked block in {spec_file}")
        src = pat.sub(lambda _m: block(name, val), src)
    open(spec_file, "w", encoding="utf-8").write(src)
    print("written:", spec_file)


if __name__ == "__main__":
    main()
