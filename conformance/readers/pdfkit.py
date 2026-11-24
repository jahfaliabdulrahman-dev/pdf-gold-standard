"""PDFKit (macOS Preview) — tier-1: what the user's own copy-paste goes through.

The extraction runs in Swift (`pdfkit_text.swift`), one process for the whole batch, and the version it
reports is the OS's PDFKit. On a machine without Swift or PDFKit the reader raises, and the matrix prints
`n/a` with that reason — a missing tier-1 reader is not a pass.
"""
import json
import os
import shutil
import subprocess
import tempfile

NAME = "pdfkit"
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdfkit_text.swift")


def _swift() -> str:
    path = shutil.which("swift")
    if not path:
        raise RuntimeError("`swift` is not on PATH — PDFKit extraction needs the Swift toolchain (macOS only)")
    if not os.path.exists(SCRIPT):
        raise RuntimeError(f"{os.path.basename(SCRIPT)} is missing")
    return path


def _run(paths: list[str]) -> dict:
    # PDFKit creates a `TemporaryDirectory.*/.keep-directory` in TMPDIR on every document; left alone it
    # accumulates one directory per reading. The child gets a private TMPDIR and the wrapper removes it, so a
    # check that reads five files leaves zero.
    with tempfile.TemporaryDirectory(prefix="pdfkit-run-") as tmp:
        env = {**os.environ, "TMPDIR": tmp}
        r = subprocess.run([_swift(), SCRIPT, *paths], capture_output=True, text=True, timeout=300, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"swift/PDFKit failed: {(r.stderr or r.stdout).strip()[:200]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"PDFKit output is not JSON: {r.stdout[:120]!r} ({exc})") from None


def version() -> str:
    _swift()
    return str(_run([])["version"])


def text(path: str) -> str:
    return text_many([path])[0]


def pages_many(paths: list[str]) -> list[list[str]]:
    """The same reading, one string per page (see `pdfium.pages_many`)."""
    payload = _run(paths)
    return [payload["pages"].get(p, []) for p in paths]


def text_many(paths: list[str]) -> list[str]:
    payload = _run(paths)
    return [payload["texts"].get(p, "") for p in paths]
