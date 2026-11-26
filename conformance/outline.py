"""The outline, read without PyMuPDF — the AGPL engine is not on the checker's path.

`structure.evaluate` compares a document's `/Outlines` against the headings its case declares. It used to read
that list with `pymupdf.get_toc()`, which dragged an AGPLv3-or-commercial dependency into the shipped package for
one function. pikepdf (MPL-2.0, already a dependency) reads the same tree.

Parity is measured, not assumed (2026-11-26, this repository):

    guide-v2-ar.pdf 12/12 · najd.pdf 11/11 · report.pdf 19/19 · report-print.pdf 19/19
    a nested 3-level outline 15/15 · a 20-level outline 20/20

and the two files where this module **refuses instead of guessing** — a declared divergence, not a regression:

    an item without `/Title`      MuPDF 0 entries · we raise OutlineError (ISO 32000 §12.3.3 makes it required)
    a `/Next` cycle               MuPDF 0 entries · we raise OutlineError
    66 nested levels              MuPDF 66 entries · we raise OutlineError (pikepdf stops at `max_depth`)

Two rules make the parity hold, and both are measured differences from pikepdf's defaults:

  · **`strict=True`.** By default pikepdf repairs what it reads: an item with no `/Title` becomes an entry with
    an empty title (a COUNT difference against MuPDF, and this check compares counts), and a cycle stops the
    walk silently. Strict raises `OutlineStructureError`, which becomes `OutlineError` here.
  · **The depth cut is caught, not inherited.** `max_depth` is a recursion bound, and pikepdf drops everything
    below it without a word: a 66-level outline reads as 65 entries at `max_depth=64`. An item that carries
    `/First` but arrives with no children was cut (or its `/First` is not a dictionary) — either way the list is
    not the document's, so the caller is told instead of being handed a shorter outline.
"""
import pikepdf

MAX_DEPTH = 64


class OutlineError(RuntimeError):
    """The outline exists but cannot be read as a tree — the caller records a failed check, never a number."""


def entries(pdf_path: str) -> list[tuple[int, str]]:
    """[(level, title)] with levels starting at 1 — MuPDF's numbering, so the check's expectations do not move."""
    out: list[tuple[int, str]] = []
    with pikepdf.open(pdf_path) as pdf:
        try:
            with pdf.open_outline(strict=True, max_depth=MAX_DEPTH) as outline:
                _walk(outline.root, 1, out)
        except pikepdf.OutlineStructureError as exc:
            raise OutlineError(str(exc)) from exc
    return out


def _walk(items, level: int, out: list[tuple[int, str]]) -> None:
    for item in items:
        if "/First" in item.obj and not item.children:
            raise OutlineError(f"outline cut at level {level}: the item is deeper than {MAX_DEPTH} levels, "
                               f"or its /First is not a dictionary — refusing a truncated outline")
        out.append((level, str(item.title)))
        if item.children:
            _walk(item.children, level + 1, out)
