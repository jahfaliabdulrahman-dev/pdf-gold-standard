"""pdfminer.six (through pdfplumber) — the pure-Python extractor inside many document pipelines.

One dependency serves two purposes on purpose: the same library is a declared reader AND the structure-tree
source for the structural checks (`page.structure_tree`). Two libraries reading the same file would be two
interpretations to keep in step.
"""
from importlib.metadata import version as dist_version

import pdfplumber

NAME = "pdfminer"


def version() -> str:
    return f"pdfplumber {dist_version('pdfplumber')} · pdfminer.six {dist_version('pdfminer.six')}"


def text(path: str) -> str:
    return text_many([path])[0]


def text_many(paths: list[str]) -> list[str]:
    out = []
    for path in paths:
        with pdfplumber.open(path) as pdf:
            out.append("\n".join((page.extract_text() or "") for page in pdf.pages))
    return out
