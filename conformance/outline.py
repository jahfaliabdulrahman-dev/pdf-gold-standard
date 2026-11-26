"""The outline, read without PyMuPDF — the AGPL engine is not on the checker's path.

`structure.evaluate` compares a document's `/Outlines` against the headings its case declares. It used to read
that list with `pymupdf.get_toc()`, which dragged an AGPLv3-or-commercial dependency into the shipped package for
one function. pikepdf (MPL-2.0, already a dependency) reads the same tree.

Parity is measured, not assumed (2026-11-26, this repository): `guide-v2-ar.pdf` 12/12 · `najd.pdf` 11/11 ·
`report.pdf` 19/19 · `report-print.pdf` 19/19 · a synthetic 20-level outline 20/20 — identical levels and titles
against `pymupdf.get_toc()`, zero differences. `conformance/tests/test_outline.py` re-checks that equality
whenever PyMuPDF happens to be installed.

Where the two disagree, this module **refuses with a reason** instead of guessing, and every case below is a
measured one:

    an item without `/Title`   MuPDF 0 entries        · we raise (ISO 32000 §12.3.3 makes /Title required)
    a `/Next` cycle            MuPDF 0 entries        · we raise (pikepdf stops silently without strict)
    66 nested levels           MuPDF 66 entries       · we raise (pikepdf cuts at `max_depth`, no error)
    `/Outlines` not a dict     MuPDF 0 entries        · we raise (pikepdf raises ValueError/AttributeError)
    `/First` not a dict        MuPDF 1 blank entry    · we raise

So `entries()` has exactly two outcomes — a list, or `OutlineError` — and the caller's `except OutlineError`
covers everything a file can do. That totality is the point: a check that crashes is not a check.

Three rules, each a measured difference from pikepdf's defaults:

  · **`strict=True`.** By default pikepdf repairs what it reads: an item with no `/Title` becomes an entry with
    an empty title (a COUNT difference against MuPDF, and this check compares counts), and a cycle stops the
    walk silently. Strict raises `OutlineStructureError`, which becomes `OutlineError` here.
  · **The depth cut is caught, not inherited.** `max_depth` is a recursion bound, and pikepdf drops everything
    below it without a word: a 66-level outline reads as 65 entries at `max_depth=64`. An item that carries
    `/First` but arrives with no children was cut (or its `/First` is not a dictionary) — either way the list is
    not the document's, so the caller is told instead of being handed a shorter outline.
  · **No `with` around `open_outline()`.** Its `__exit__` re-serialises `/Outlines` into the document. This
    module is a reader; when the caller passes the document it already opened, a write-back would be a silent
    mutation of somebody else's file. `Outline.root` loads lazily, so the object is read without the manager.
"""
import pikepdf

MAX_DEPTH = 64


class OutlineError(RuntimeError):
    """The outline exists but cannot be read as a tree — the caller records a failed check, never a number."""


def entries(source) -> list[tuple[int, str]]:
    """[(level, title)] with levels starting at 1 — MuPDF's numbering, so the check's expectations do not move.

    `source` is a `pikepdf.Pdf` the caller already opened (one parse per certificate), or a path for a caller that
    holds no document.
    """
    if isinstance(source, pikepdf.Pdf):
        return _entries(source)
    with pikepdf.open(source) as pdf:
        return _entries(pdf)


def _entries(pdf) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    # The shape is checked here, not left to pikepdf: a non-dictionary `/Outlines` made pikepdf return an EMPTY
    # tree on some inputs and raise on others (measured 2026-11-26), and "0 entries" reads as "this document has
    # no outline" — the one answer that would let a broken outline pass as a comparison, not a refusal.
    outlines = pdf.Root.get("/Outlines")
    if outlines is not None and not isinstance(outlines, pikepdf.Dictionary):
        raise OutlineError(f"/Outlines is not a dictionary (found {outlines!r}) — refusing to read it")
    try:
        _walk(pdf.open_outline(strict=True, max_depth=MAX_DEPTH).root, 1, out)
    except OutlineError:
        raise
    except pikepdf.OutlineStructureError as exc:
        raise OutlineError(str(exc)) from exc
    except Exception as exc:            # a non-dictionary /Outlines, a broken /First, a pikepdf parser error
        raise OutlineError(f"{type(exc).__name__}: {exc}") from exc
    return out


def _walk(items, level: int, out: list[tuple[int, str]]) -> None:
    for item in items:
        if "/First" in item.obj and not item.children:
            raise OutlineError(f"outline cut at level {level}: the item is deeper than {MAX_DEPTH} levels, "
                               f"or its /First is not a dictionary — refusing a truncated outline")
        out.append((level, str(item.title)))
        if item.children:
            _walk(item.children, level + 1, out)
