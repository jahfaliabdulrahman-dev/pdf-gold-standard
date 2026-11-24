"""MuPDF (PyMuPDF) — the engine under most RAG extractors and many Linux viewers."""
import pymupdf

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
