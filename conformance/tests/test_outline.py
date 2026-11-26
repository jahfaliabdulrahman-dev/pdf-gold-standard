#!/usr/bin/env python3
"""The outline is read with pikepdf, and the three files it cannot read are REFUSED, not shortened.

Why this test exists: the check compares an exact count of (level, title) pairs, so every place pikepdf's
defaults quietly repair or truncate the tree is a place the verdict moves without a word. Each branch below is a
measured difference from `pymupdf.get_toc()` (2026-11-26), not a hypothetical:

  · an item with no `/Title`  — pikepdf (non-strict) invents `""`, MuPDF reports nothing, counts differ;
  · a `/Next` cycle           — pikepdf (non-strict) stops silently at the repeated object;
  · 66 nested levels          — `max_depth` cuts at 64 without an error (a 66-level outline reads as 65).

The test builds each file with pikepdf and asserts this module refuses, with a reason. It needs no PyMuPDF.
"""
import os
import sys

import pikepdf
from pikepdf import Dictionary, Name, String

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from conformance import outline                                     # noqa: E402
from conformance.outline import OutlineError                        # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def blank(tmp, name):
    path = os.path.join(tmp, name)
    with pikepdf.new() as pdf:
        pdf.add_blank_page(page_size=(595, 842))
        pdf.save(path)
    return path


def titleless(tmp):
    path = blank(tmp, "titleless.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        root = pdf.make_indirect(Dictionary(Type=Name.Outlines))
        item = pdf.make_indirect(Dictionary(Parent=root))
        item["/Next"] = item
        root["/First"], root["/Last"] = item, item
        pdf.Root["/Outlines"] = root
        pdf.save()
    return path


def cycle(tmp):
    path = blank(tmp, "cycle.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        root = pdf.make_indirect(Dictionary(Type=Name.Outlines))
        item = pdf.make_indirect(Dictionary(Title=String("once"), Parent=root))
        item["/Next"] = item
        root["/First"], root["/Last"] = item, item
        pdf.Root["/Outlines"] = root
        pdf.save()
    return path


def deep(tmp, levels):
    path = blank(tmp, f"deep{levels}.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        root = pdf.make_indirect(Dictionary(Type=Name.Outlines))
        parent, first = root, None
        for i in range(levels):                    # raw dictionaries: the Outline writer would truncate at save
            item = pdf.make_indirect(Dictionary(Title=String(f"L{i + 1}"), Parent=parent))
            if first is None:
                first = item
            else:
                parent["/First"] = item
            parent = item
        root["/First"] = first
        pdf.Root["/Outlines"] = root
        pdf.save()
    return path


def nested(tmp):
    path = blank(tmp, "nested.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        with pdf.open_outline() as ol:
            a = pikepdf.OutlineItem("المستوى الأول", 0)
            b = pikepdf.OutlineItem("الثاني", 0)
            c = pikepdf.OutlineItem("الثالث", 0)
            b.children.append(c)
            a.children.append(b)
            ol.root.append(a)
        pdf.save()
    return path


import tempfile                                                      # noqa: E402

with tempfile.TemporaryDirectory(prefix="outline-") as tmp:
    got = outline.entries(nested(tmp))
    check("levels-start-at-one-and-nest", got == [(1, "المستوى الأول"), (2, "الثاني"), (3, "الثالث")], str(got))

    for name, path in (("titleless", titleless(tmp)), ("cycle", cycle(tmp)), ("66 levels", deep(tmp, 66))):
        try:
            got = outline.entries(path)
            check(f"refuses-a-{name}-outline", False, f"returned {len(got)} entries instead of raising")
        except OutlineError as exc:
            check(f"refuses-a-{name}-outline", True, "")
            print(f"     {name}: {exc}"[:160])

    got = outline.entries(deep(tmp, 20))
    check("twenty-levels-are-read-in-full", len(got) == 20, f"{len(got)} entries")

    # A document this pipeline built: the check's expectations are written against MuPDF's numbering, so a real
    # file with an outline must come back non-empty (the macOS job has one; elsewhere the branch is skipped).
    real = os.path.join(REPO, "guide-v2-ar.pdf")
    if os.path.isfile(real):
        got = outline.entries(real)
        check("a-built-document-has-its-outline", len(got) > 0 and all(lvl >= 1 for lvl, _ in got), str(got[:3]))
    else:
        print("SKIP a-built-document-has-its-outline — guide-v2-ar.pdf is not in this checkout")

print()
if fails:
    print(f"OUTLINE FAILED — {fails}")
    raise SystemExit(1)
print("OUTLINE READ PASSED — parity where it holds, a refusal with a reason where it does not")
