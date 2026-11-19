"""PDFium — Chrome, Edge and every Chromium-based viewer's text engine (pypdfium2)."""
from importlib.metadata import version as dist_version

import pypdfium2

NAME = "pdfium"


def version() -> str:
    return dist_version("pypdfium2")          # the pinned distribution, not the bundled core's own number


def text(path: str) -> str:
    return text_many([path])[0]


def text_many(paths: list[str]) -> list[str]:
    out = []
    for path in paths:
        doc = pypdfium2.PdfDocument(path)
        try:
            out.append("\n".join(page.get_textpage().get_text_range() for page in doc))
        finally:
            doc.close()
    return out
