"""MuPDF (PyMuPDF) — the engine under most RAG extractors and many Linux viewers."""
import pymupdf

NAME = "mupdf"


def version() -> str:
    return str(pymupdf.__version__)


def text(path: str) -> str:
    doc = pymupdf.open(path)
    try:
        return "\n".join(str(page.get_text("text") or "") for page in doc)
    finally:
        doc.close()


def text_many(paths: list[str]) -> list[str]:
    return [text(p) for p in paths]
