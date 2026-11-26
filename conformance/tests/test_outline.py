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


def not_a_dictionary(tmp, kind):
    """`/Outlines` as something that is not a dictionary, or `/First` as a string — pikepdf raises ValueError or
    AttributeError from inside; the module must turn that into a refusal, not let it escape into `certify`."""
    path = blank(tmp, f"outlines-{kind}.pdf")
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        if kind == "int":
            pdf.Root["/Outlines"] = 5
        elif kind == "string":
            pdf.Root["/Outlines"] = String("not a tree")
        elif kind == "array":
            pdf.Root["/Outlines"] = pikepdf.Array([1, 2])
        elif kind == "first-string":
            root = pdf.make_indirect(Dictionary(Type=Name.Outlines))
            root["/First"] = String("nope")
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

    for name, path in (("titleless", titleless(tmp)), ("cycle", cycle(tmp)), ("66 levels", deep(tmp, 66)),
                       ("non-dictionary /Outlines", not_a_dictionary(tmp, "int")),
                       ("string /Outlines", not_a_dictionary(tmp, "string")),
                       ("array /Outlines", not_a_dictionary(tmp, "array")),
                       ("string /First", not_a_dictionary(tmp, "first-string"))):
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
        # Parity against the engine that used to read this — the ONE place it can be checked, and only where
        # PyMuPDF happens to be installed (the macOS conformance job). A pikepdf bump that changes the walk
        # fails here instead of silently moving a certificate.
        try:
            import pymupdf
        except ImportError:
            print("SKIP parity-against-mupdf — PyMuPDF is not installed here (it is an optional extra)")
        else:
            doc = pymupdf.open(real)
            try:
                want = [(int(lvl), title) for lvl, title, _ in doc.get_toc()]
            finally:
                doc.close()
            check("parity-against-mupdf", got == want, f"ours {got[:2]} vs mupdf {want[:2]}")
            # The same document through the OPEN-document form: one parse, identical answer.
            with pikepdf.open(real) as pdf:
                check("open-document-form-is-the-same", outline.entries(pdf) == got)
    else:
        print("SKIP a-built-document-has-its-outline — guide-v2-ar.pdf is not in this checkout")

print()
if fails:
    print(f"OUTLINE FAILED — {fails}")
    raise SystemExit(1)
print("OUTLINE READ PASSED — parity where it holds, a refusal with a reason where it does not")
