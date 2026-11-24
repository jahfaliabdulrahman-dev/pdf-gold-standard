"""PDFium — Chrome, Edge and every Chromium-based viewer's text engine (pypdfium2)."""
from importlib.metadata import version as dist_version

import pypdfium2

NAME = "pdfium"


def version() -> str:
    return dist_version("pypdfium2")          # the pinned distribution, not the bundled core's own number


def text(path: str) -> str:
    return text_many([path])[0]


def pages_many(paths: list[str]) -> list[list[str]]:
    """The same reading, one string per page — the checker's only way to name a page honestly.

    Every `PdfTextPage` and `PdfPage` is closed as soon as its string is read: PDFium keeps native buffers
    behind both handles, and a 500-page document measured on the checker leaked one page and one text page
    per page until the document closed. `test_pdfium_close.py` proves the calls with a fake module.
    """
    out = []
    for path in paths:
        doc = pypdfium2.PdfDocument(path)
        try:
            pages = []
            for page in doc:
                try:
                    textpage = page.get_textpage()
                    try:
                        pages.append(textpage.get_text_range())
                    finally:
                        textpage.close()
                finally:
                    page.close()
            out.append(pages)
        finally:
            doc.close()
    return out


def text_many(paths: list[str]) -> list[str]:
    return ["\n".join(pages) for pages in pages_many(paths)]
