"""The declared reader matrix: name, version, text. A reader that cannot run says so — it never passes.

Two rules the code enforces:
  · `version()` is mandatory and is printed in every output. A number measured on an unnamed reader is a
    number nobody can reproduce.
  · an unavailable reader is `n/a` **with its reason** (missing tool, non-macOS, import error). The
    certificate carries it in `tier1_unavailable[]` when the reader is tier-1, so a certificate that ran
    with PDFium alone cannot be mistaken for one that ran both.
"""
import importlib

MATRIX = ("pdfium", "pdfkit", "mupdf", "poppler", "pdfminer")     # order: tier-1 first
TIER1 = ("pdfium", "pdfkit")


def load(name: str):
    return importlib.import_module(f"conformance.readers.{name}")


def available() -> tuple[dict, dict]:
    """({name: module}, {name: reason}) — every reader is in exactly one of the two."""
    ok, missing = {}, {}
    for name in MATRIX:
        try:
            mod = load(name)
            mod.version()                     # prove the tool exists before claiming a number from it
            ok[name] = mod
        except Exception as exc:
            missing[name] = f"{type(exc).__name__}: {exc}"
    return ok, missing


def text_many(name: str, paths: list[str]) -> list[str]:
    mod = load(name)
    if hasattr(mod, "text_many"):
        return mod.text_many(paths)
    return [mod.text(p) for p in paths]


def pages_many(name: str, paths: list[str]) -> list[list[str]] | None:
    """The same reading, page by page — `None` when a reader cannot name its pages.

    A caller that needs a page must not invent one: `None` is a value, and the checker prints
    `page: null` with that reader named instead of a guess.
    """
    mod = load(name)
    if hasattr(mod, "pages_many"):
        return mod.pages_many(paths)
    return None


def version_of(name: str) -> str:
    return load(name).version()
