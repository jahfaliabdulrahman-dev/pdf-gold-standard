"""pdf.js — the permissively-licensed reader the shipped Linux install needs for a fourth vote.

Apache-2.0 (`pdfjs-dist`), so it may ship where PyMuPDF's AGPL may not. It runs one Node process for the whole
batch (the same shape as `pdfkit`), through `isolate` with the same timeout, and it returns what `pdf.js` gives:
no BiDi normalisation, no reordering, no repair. A reader that fixes text cannot be measured against the others.

`pdfjs-dist` is pinned in `package.json` + `package-lock.json` (integrity hash included) and installed with
`npm ci` into `node_modules/`, which is never committed. Absent Node or absent install is a one-line reason, the
same way `mupdf.py` names its extra.
"""
import json
import os
import shutil
import subprocess

from . import PDFJS_INSTALL

NAME = "pdfjs"
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "pdfjs_text.mjs")
NODE_MODULES = os.path.join(HERE, "node_modules", "pdfjs-dist")


def _node() -> str:
    path = shutil.which("node")
    if not path:
        raise RuntimeError(f"`node` is not on PATH — the pdf.js reader needs Node (any LTS), then {PDFJS_INSTALL}")
    if not os.path.isfile(SCRIPT):
        raise RuntimeError(f"{os.path.basename(SCRIPT)} is missing")
    if not os.path.isdir(NODE_MODULES):
        raise RuntimeError(f"pdfjs-dist is not installed — {PDFJS_INSTALL}")
    return path


def _run(paths: list[str]) -> dict:
    if not paths:
        _node()
        return {"version": _version(), "pages": {}, "texts": {}}
    r = subprocess.run([_node(), SCRIPT, *paths], capture_output=True, text=True, timeout=300, cwd=HERE)
    if r.returncode != 0:
        raise RuntimeError(f"node/pdf.js failed: {(r.stderr or r.stdout).strip()[:200]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"pdf.js output is not JSON: {r.stdout[:120]!r} ({exc})") from None


def _version() -> str:
    with open(os.path.join(NODE_MODULES, "package.json"), encoding="utf-8") as fh:
        return str(json.load(fh)["version"])


def version() -> str:
    """The version of `pdfjs-dist` — never a browser version: what is measured is this package."""
    _node()
    return _version()


def text(path: str) -> str:
    return text_many([path])[0]


def _absolute(paths: list[str]) -> list[str]:
    """The child runs with `cwd=HERE`, so a relative path must be resolved before it is handed over — the same
    trap `isolate.read` was fixed for, and the same symptom if it is not: the reader reports a file that exists
    as missing."""
    return [os.path.abspath(p) for p in paths]


def pages_many(paths: list[str]) -> list[list[str]]:
    """One string per page — the interface every reader implements (`text = "\n".join(pages)`)."""
    wanted = _absolute(paths)
    payload = _run(wanted)
    return [["\n".join(page) for page in payload["pages"].get(p, [])] for p in wanted]


def text_many(paths: list[str]) -> list[str]:
    wanted = _absolute(paths)
    payload = _run(wanted)
    return [payload["texts"].get(p, "") for p in wanted]
