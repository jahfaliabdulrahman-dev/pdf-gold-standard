#!/usr/bin/env python3
"""Every claim in `adapters/html.py` that a rule exists BECAUSE an engine misbehaves must have a living witness.

The review's rule, as a test: a line of template CSS that avoids a measured defect either comes with a case that
reproduces that defect, or it and its claim both go. `ENGINE_BEHAVIOURS` is the declaration; this file builds
each one and asserts both halves — the defect appears where the table says it appears, and the produced file
does not carry it. A claim whose case is missing from the corpus fails here too.

Runs: `python3 conformance/tests/test_engine_behaviour.py` (needs CHROME_PATH for the two build rows).
"""
import os
import re
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)

import pikepdf
import pypdfium2

from conformance.adapters import chrome, html
from conformance.corpus import cases

FAILED = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""))
    if not ok:
        FAILED.append(name)


def layer(pdf: str) -> str:
    doc = pypdfium2.PdfDocument(pdf)
    text = "\n".join(p.get_textpage().get_text_range() for p in doc)
    doc.close()
    return text


def type3_fonts(pdf: str) -> list[str]:
    """Every Type3 font in the file, by object number. A synthesised bold is printed as Type3."""
    with pikepdf.open(pdf) as p:
        out = []
        for obj in p.objects:
            if isinstance(obj, pikepdf.Dictionary) and str(obj.get("/Subtype")) == "/Type3":
                out.append(f"{obj.objgen}:{obj.get('/BaseFont')}")
        return out


def rows_in_order(text: str, first: str, last: str) -> bool:
    a, b = text.find(first), text.find(last)
    return a != -1 and b != -1 and a < b


def main() -> int:
    corpus = {c["id"]: c for c in cases.load_all()}
    tmp = tempfile.mkdtemp(prefix="behaviour-")

    for row in html.ENGINE_BEHAVIOURS:
        cid, engine = row["case"], row["engine"]
        if cid not in corpus:
            check(f"{row['id']}:case-exists", False, f"{cid} is declared but not in the corpus")
            continue
        check(f"{row['id']}:case-exists", True, cid)
        out = os.path.join(tmp, f"{row['id']}.pdf")

        # The defect half: the same case with the identifier break disabled (`_inline` still isolates the
        # amount). Without this branch the rule's cause would be prose; the fixed half alone cannot fail if a
        # reader ever accepts the inline layout.
        if row["id"] == "identifier-own-line":
            chrome.render_case(corpus[cid], out, engine)
            fixed = layer(out)
            check(f"{row['id']}:fixed", "INV-2026-0042" in fixed,
                  "" if "INV-2026-0042" in fixed else repr(fixed[-120:]))
            out2 = os.path.join(tmp, f"{row['id']}-inline.pdf")
            arabic = html._ARABIC
            html._ARABIC = re.compile(r"(?!x)x")
            try:
                chrome.render_case(corpus[cid], out2, engine)
            finally:
                html._ARABIC = arabic
            broken = layer(out2)
            check(f"{row['id']}:reproduces", "INV-2026-0042" not in broken,
                  "" if "INV-2026-0042" not in broken else "the inline layout no longer reproduces the defect")
            continue

        # The defect half: render with the pre-fix `_cell` (empty cells return "") and show that Chrome drops
        # the cell. Without this branch the rule's cause would be prose; the fixed half alone cannot fail if
        # Chrome ever stops dropping cells.
        if row["id"] == "empty-cell-dropped":
            from conformance.checks import structure as gate_structure
            original = html._cell
            html._cell = lambda t: "" if html._no_substance(t) else original(t)
            try:
                chrome.render_case(corpus[cid], out, engine)
            finally:
                html._cell = original
            with pikepdf.open(out) as pdf:
                table = next(n for n in gate_structure.read_tree(pdf).walk() if n.tag == "/Table")
                rows = [len([c for c in r.children if c.tag in ("/TD", "/TH")])
                        for r in table.children if r.tag == "/TR"]
            checks = {c["id"]: c for c in gate_structure.evaluate(
                out, corpus[cid], {"postprocess": True}, run_verapdf=True)}
            check(f"{row['id']}:reproduces", rows == [3, 2, 2],
                  f"rows {rows}" + ("" if rows == [3, 2, 2] else " — the dropped cell is no longer reproducible"))
            check(f"{row['id']}:tables-fail", checks["tables"]["status"] == "fail", checks["tables"]["reason"])
            check(f"{row['id']}:ua1-fail", checks["verapdf-ua1"]["status"] == "fail",
                  checks["verapdf-ua1"]["reason"])
            continue

        chrome.render_case(corpus[cid], out, engine)
        text = layer(out)

        if row["expect"] == "the case's rows are NOT in reading order":
            ok = not rows_in_order(text, "رسوم", "خدمات")
            check(f"{row['id']}:reproduces", ok,
                  "rows ARE reversed/shredded on the raw engine" if ok else f"rows stayed in order: {text!r}")
        elif row["expect"] == "the case's rows ARE in reading order":
            ok = rows_in_order(text, "رسوم", "خدمات")
            check(f"{row['id']}:reproduces", ok, "rows in order under a declared page box" if ok else text[:120])
        elif row["expect"] == "no Type3 font in the file":
            found = type3_fonts(out)
            check(f"{row['id']}:reproduces", not found,
                  "no Type3 font" if not found else f"Type3 fonts: {found}")
        else:
            check(f"{row['id']}:reproduces", False, f"unknown expectation {row['expect']!r}")

    # And the produced file for every declared bold case must also be Type3-free.
    for cid in ("bld-word", "bld-heading", "bld-th"):
        if cid not in corpus:
            check(f"{cid}:built", False, "bold case missing")
            continue
        out = os.path.join(tmp, f"{cid}.pdf")
        chrome.render_case(corpus[cid], out, "chrome")
        found = type3_fonts(out)
        check(f"{cid}:no-type3", not found, "no Type3" if not found else str(found))

    # --- the empty cell keeps its cell -------------------------------------------------------------
    # Chrome drops a cell with no content from the structure tree; veraPDF UA-1 then fails 7.2-43. The
    # producer writes one non-breaking space (`metrics.N` collapses it, so it adds no word). This control
    # fails if that space is removed: the rows go back to 3,2,2.
    from conformance.checks import structure as gate_structure

    check("empty-cell:html", html._cell("") == "&#160;" and html._cell("  ") == "&#160;"
          and html._cell("\u200f") == "&#160;" and html._cell("\u200b\u200f") == "&#160;",
          "an empty, whitespace-only or format-only cell is one &#160;")
    cid = "tbl-empty-cell"
    if cid not in corpus:
        check("empty-cell:case-exists", False, "the case is missing from the corpus")
    else:
        out = os.path.join(tmp, "tbl-empty-cell.pdf")
        chrome.render_case(corpus[cid], out, "chrome")
        with pikepdf.open(out) as pdf:
            table = next(n for n in gate_structure.read_tree(pdf).walk() if n.tag == "/Table")
            rows = [len([c for c in r.children if c.tag in ("/TD", "/TH")])
                    for r in table.children if r.tag == "/TR"]
        check("empty-cell:rows", rows == [3, 3, 3], f"rows {rows}")
        checks = {c["id"]: c for c in gate_structure.evaluate(
            out, corpus[cid], {"postprocess": True}, run_verapdf=True)}
        check("empty-cell:tables", checks["tables"]["status"] == "pass", checks["tables"]["reason"])
        check("empty-cell:ua1", checks["verapdf-ua1"]["status"] == "pass", checks["verapdf-ua1"]["reason"])
        check("empty-cell:tagged-text", checks["tagged-text"]["status"] == "pass",
              checks["tagged-text"]["reason"])
        check("empty-cell:all-text-tagged", checks["all-text-tagged"]["status"] == "pass",
              checks["all-text-tagged"]["reason"])

    print(f"\nDECLARED BEHAVIOURS: {len(html.ENGINE_BEHAVIOURS)}")
    if FAILED:
        print("TEST FAILED —", FAILED)
        return 1
    print("ENGINE-BEHAVIOUR GUARD PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
