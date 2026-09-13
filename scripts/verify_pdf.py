#!/usr/bin/env python3
"""Verify a built PDF against the Gold Standard checklist.

Usage: python3 scripts/verify_pdf.py out.pdf [expected_pages] [expected_links]

Exit 0 = artifact passes every gate; exit 1 = a gate failed (details printed).
This is the same gate the CI workflow runs — a build that fails it is not a release.
"""
import sys

import fitz

PDF = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"
PAGES = int(sys.argv[2]) if len(sys.argv) > 2 else 12
LINKS = int(sys.argv[3]) if len(sys.argv) > 3 else 42

fails = []


def check(name: str, ok: bool, detail: str) -> None:
    print(("PASS " if ok else "FAIL ") + name + " - " + detail)
    if not ok:
        fails.append(name)


doc = fitz.open(PDF)

check("pages", doc.page_count == PAGES, f"{doc.page_count} (expected {PAGES})")

total_links = sum(len(p.get_links()) for p in doc)
check("links", total_links == LINKS, f"{total_links} (expected {LINKS})")

outline = doc.get_toc()
check("outline", len(outline) >= PAGES, f"{len(outline)} entries")

cat = doc.pdf_catalog()
layout = doc.xref_get_key(cat, "PageLayout")[1]
check("single-page", layout == "/SinglePage", str(layout))

vpx = doc.xref_get_key(cat, "ViewerPreferences")
check("viewer-prefs", vpx[0] != "null", str(vpx[1])[:40])

fonts = {f[3] for p in doc for f in p.get_fonts()}
check("fonts-embedded", bool(fonts), ", ".join(sorted(fonts))[:90])

md = doc.metadata or {}
check("title", bool(md.get("title")), str(md.get("title"))[:80])

if fails:
    print(f"\n{len(fails)} gate(s) FAILED: {fails}")
    raise SystemExit(1)
print("\nALL GATES PASSED")
