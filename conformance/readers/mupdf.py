"""MuPDF (PyMuPDF) — the engine under most RAG extractors and many Linux viewers.

**Optional, and declared as such.** PyMuPDF is AGPLv3-or-commercial; the checker must install and run without it,
so this reader is not a dependency of the package. It arrives with an extra:

    pip install 'arabic-pdf-check[mupdf]'

When it is absent the import below raises with that sentence rather than a bare `ModuleNotFoundError`, because
`readers.available()` prints this reason into every report — a reader that cannot run says WHY, in words the
customer can act on, instead of a traceback's.
"""
try:
    import pymupdf
except ImportError as exc:      # the declared absence — the matrix carries this sentence into the report
    raise ImportError(
        "optional extra not installed — pip install 'arabic-pdf-check[mupdf]' "
        "(PyMuPDF is AGPLv3 or commercial; the shipped checker runs without it)") from exc

NAME = "mupdf"


def version() -> str:
    return str(pymupdf.__version__)


def text(path: str) -> str:
    return text_many([path])[0]


def pages_many(paths: list[str]) -> list[list[str]]:
    """The same reading, one string per page (see `pdfium.pages_many`)."""
    out = []
    for path in paths:
        doc = pymupdf.open(path)
        try:
            out.append([str(page.get_text("text") or "") for page in doc])
        finally:
            doc.close()
    return out


def text_many(paths: list[str]) -> list[str]:
    return ["\n".join(pages) for pages in pages_many(paths)]
