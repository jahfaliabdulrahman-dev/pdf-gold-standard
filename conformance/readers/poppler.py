"""poppler's `pdftotext` — the reference command-line extractor on Linux and in most pipelines.

The binary is resolved once, from `CONFORMANCE_PDFTOTEXT` if it is set, otherwise from PATH. The variable exists
because the floors are recorded per VERSION: a host whose package manager ships a different poppler must point
at the pinned build instead of silently measuring a version the ratchet has never seen (which fails by name —
the right outcome, but a confusing one when the cause is a code path rather than a reader).
"""
import os
import re
import shutil
import subprocess

NAME = "poppler"


def binary() -> str:
    explicit = os.environ.get("CONFORMANCE_PDFTOTEXT")
    if explicit:
        if not os.access(explicit, os.X_OK):
            raise RuntimeError(f"CONFORMANCE_PDFTOTEXT={explicit!r} is not executable")
        return explicit
    found = shutil.which("pdftotext")
    if not found:
        raise RuntimeError("pdftotext is not on PATH and CONFORMANCE_PDFTOTEXT is unset — install poppler, or "
                           "point the variable at the pinned build whose floors the ratchet holds")
    return found


def version() -> str:
    r = subprocess.run([binary(), "-v"], capture_output=True, text=True)
    m = re.search(r"pdftotext version ([0-9][^\s]*)", (r.stderr or "") + (r.stdout or ""))
    if not m:
        raise RuntimeError(f"pdftotext -v printed no version: {(r.stderr or r.stdout)[:120]!r}")
    return m.group(1)


def text(path: str) -> str:
    return text_many([path])[0]


def pages_many(paths: list[str]) -> list[list[str]]:
    """The same reading, one string per page: pdftotext separates pages with U+000C, and `N` treats it as
    whitespace — so joining these pages with a newline is the same text the reader returned."""
    out = []
    for text in text_many(paths):
        pages = text.split("\f")
        if pages and pages[-1] == "":
            pages.pop()
        out.append(pages)
    return out


def text_many(paths: list[str]) -> list[str]:
    out = []
    for path in paths:
        r = subprocess.run([binary(), "-q", "-enc", "UTF-8", path, "-"],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            # A tool that failed on a file is not a reader that read zero characters: an exact 0 attributed to
            # the reader would enter the ratchet as that reader's floor (review F9).
            raise RuntimeError(f"pdftotext exited {r.returncode} on {path}: {(r.stderr or '').strip()[:160]}")
        out.append(r.stdout)
    return out
