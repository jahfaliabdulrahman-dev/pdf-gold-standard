"""poppler's `pdftotext` — the reference command-line extractor on Linux and in most pipelines."""
import re
import shutil
import subprocess

NAME = "poppler"


def version() -> str:
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext is not on PATH (brew install poppler)")
    r = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True)
    m = re.search(r"pdftotext version ([0-9][^\s]*)", (r.stderr or "") + (r.stdout or ""))
    if not m:
        raise RuntimeError(f"pdftotext -v printed no version: {(r.stderr or r.stdout)[:120]!r}")
    return m.group(1)


def text(path: str) -> str:
    return text_many([path])[0]


def text_many(paths: list[str]) -> list[str]:
    out = []
    for path in paths:
        r = subprocess.run(["pdftotext", "-q", "-enc", "UTF-8", path, "-"],
                           capture_output=True, text=True, timeout=120)
        out.append(r.stdout)
    return out
