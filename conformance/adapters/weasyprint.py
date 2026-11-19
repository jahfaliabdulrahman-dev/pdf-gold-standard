"""case -> the same HTML -> WeasyPrint 70 -> PDF.

WeasyPrint takes ONE `--pdf-variant` per file (its own `--help`: `{pdf/a-3b … pdf/ua-1 …}`), so an engine that
cannot put PDF/UA-1 and PDF/A-3b in one file produces two: `<id>.ua.pdf` (the one measured — tagged, and the
accessibility claim) and `<id>.a3b.pdf`. The assignment calls that a result, and the bakeoff report states it.

It runs in its own venv (`.venv-bakeoff`) with pinned versions, and needs pango/harfbuzz from Homebrew on the
loader path: `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`. Both are recorded in the report.
"""
import hashlib
import os
import shutil
import subprocess
import tempfile

from . import fonts, html

NAME = "weasyprint"
DEFAULT_BIN = os.path.expanduser("~/Projects/pdf-gold-standard/.venv-bakeoff/bin/weasyprint")
LIB_PATH = "/opt/homebrew/lib"


class BuildError(RuntimeError):
    pass


def binary() -> str:
    path = os.environ.get("WEASYPRINT_PATH") or DEFAULT_BIN
    if not os.path.exists(path):
        raise BuildError(f"weasyprint is not installed at {path} (set WEASYPRINT_PATH)")
    return path


def _env() -> dict:
    return {**os.environ, "DYLD_FALLBACK_LIBRARY_PATH": LIB_PATH}


def version() -> str:
    r = subprocess.run([binary(), "--version"], capture_output=True, text=True, timeout=120, env=_env())
    if r.returncode != 0:
        raise BuildError(f"weasyprint --version failed: {(r.stderr or r.stdout).strip()[-200:]}")
    return (r.stdout or r.stderr).strip().replace("WeasyPrint version ", "")


def render_case(case: dict, out_pdf: str) -> dict:
    fonts.path(case["font"])
    work = tempfile.mkdtemp(prefix="weasy-case-")
    try:
        src = os.path.join(work, "case.html")
        markup = html.render(case)
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(markup)
        a3b = out_pdf[:-4] + ".a3b.pdf"
        for variant, target in (("pdf/ua-1", out_pdf), ("pdf/a-3b", a3b)):
            r = subprocess.run([binary(), "--pdf-variant", variant, "--pdf-tags",
                                "--pdf-identifier", case["id"], src, target],
                               capture_output=True, text=True, timeout=300, env=_env())
            if r.returncode != 0 or not os.path.exists(target):
                raise BuildError(f"weasyprint {variant} failed for {case['id']}: "
                                 f"{(r.stderr or r.stdout).strip()[-300:]}")
        return {"engine": "weasyprint", "engine_version": version(), "postprocess": False,
                "source_sha256": hashlib.sha256(markup.encode("utf-8")).hexdigest(),
                "second_file": os.path.basename(a3b), "a3b_path": a3b,
                "variants": {"measured": "pdf/ua-1", "also": "pdf/a-3b"}}
    finally:
        shutil.rmtree(work, ignore_errors=True)
