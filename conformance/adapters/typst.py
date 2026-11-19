"""case -> Typst source -> PDF, at Typst's own settings.

Only flags that appear in the installed `typst compile --help` are used (pasted in the bakeoff appendix):
`--pdf-standard a-3b,ua-1` (both standards in one file), `--font-path`, `--ignore-system-fonts` (the case's
font is the only face — a fallback would hide a missing glyph), and `--creation-timestamp` (determinism).

Markup is emitted as `text("...")` expressions, never as bare content: a case may contain `#`, `[`, `]`, `*`,
`_`, `<`, `>` or a line starting with `-`, all of which are Typst markup. A quoted string is the one form that
cannot be reinterpreted.

The ordered-list marker is Typst's own `numbering` with Arabic-Indic digits. If the installed version refuses
that pattern, the build refuses too — it does not silently fall back to `1.`, because the marker is text and a
silent fallback would be a different document.
"""
import os
import shutil
import subprocess
import tempfile

from ..corpus.truth import arabic_indic
from . import fonts

NAME = "typst"
# installed outside the repository: version + sha256 recorded in docs/engine-bakeoff/README.md
DEFAULT_BIN = os.path.expanduser("~/.local/bakeoff/typst-aarch64-apple-darwin/typst")


class BuildError(RuntimeError):
    pass


def binary() -> str:
    path = os.environ.get("TYPST_PATH") or DEFAULT_BIN
    if not os.path.exists(path):
        raise BuildError(f"typst is not installed at {path} (set TYPST_PATH)")
    return path


def version() -> str:
    r = subprocess.run([binary(), "--version"], capture_output=True, text=True, timeout=60)
    return (r.stdout or r.stderr).strip().replace("typst ", "")


def _q(text: str, hash_: bool = True) -> str:
    """One case string as a Typst expression — quoted, so no markup character is interpreted.

    `hash_=False` inside `#table(..)`/`#enum(..)`: those arguments are already code mode, and a second `#`
    is an error (measured: «you are already in code mode — try removing the `#`»).
    """
    body = '"' + str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    return ("#text(" if hash_ else "text(") + body + ")"


def _heading(level: int, text: str) -> str:
    return "=" * level + " " + _q(text)


def _table(block: dict) -> str:
    header = block["header"]
    rows = [header] if header and not isinstance(header[0], list) else list(header)
    cells = [c for r in rows + list(block["rows"]) for c in r]
    width = len(rows[0])
    body = ", ".join(_q(c, hash_=False) for c in cells)
    # `table.header(..)` repeats on a page break; the corpus declares its header once, so it is a plain row
    # group — the same decision as the HTML template, for the same reason.
    return f"#table(columns: {width}, {body})"


def _list(block: dict) -> str:
    items = ", ".join(_q(i, hash_=False) for i in block["items"])
    return f"#enum({items})" if block["ordered"] else f"#list({items})"


def source(case: dict) -> str:
    fam = fonts.family(case["font"])
    kinds = {1: "20pt", 2: "16pt", 3: "13pt"}
    lines = [
        f'#set document(title: "{case["id"]}")',
        '#set page(paper: "a4", margin: 20mm)',
        f'#set text(lang: "ar", font: "{fam}", size: 12pt, dir: rtl)',
        "#set par(leading: 0.65em, spacing: 1.1em)",
        '#set heading(numbering: none)',
        '#set enum(numbering: "' + arabic_indic(1) + '.")',
    ]
    for level in (1, 2, 3):
        lines.append(f"#show heading.where(level: {level}): set text(size: {kinds[level]}, weight: 400)")
    lines.append("")
    for block in case["blocks"]:
        kind = block["type"]
        if kind == "heading":
            lines.append(_heading(block["level"], block["text"]))
        elif kind == "paragraph":
            if block.get("align") == "justify":
                lines.append("#par(justify: true)[" + _q(block["text"]) + "]")
                lines.append("#par(justify: false)[]")
            else:
                lines.append(_q(block["text"]))
        elif kind == "list":
            lines.append(_list(block))
        elif kind == "table":
            lines.append(_table(block))
        lines.append("")
    return "\n".join(lines)


def render_case(case: dict, out_pdf: str) -> dict:
    font_dir = os.path.dirname(fonts.path(case["font"]))
    work = tempfile.mkdtemp(prefix="typst-case-")
    try:
        src = os.path.join(work, "case.typ")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(source(case))
        r = subprocess.run([binary(), "compile", "--root", work,
                            "--font-path", font_dir, "--ignore-system-fonts",
                            "--pdf-standard", "a-3b,ua-1",
                            "--creation-timestamp", "1763510400",       # 2026-11-19T00:00:00Z, fixed
                            src, out_pdf],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not os.path.exists(out_pdf):
            raise BuildError(f"typst failed for {case['id']}: {(r.stderr or r.stdout).strip()[-300:]}")
        return {"engine": "typst", "engine_version": version(), "postprocess": False,
                "source_sha256": __import__("hashlib").sha256(open(src, "rb").read()).hexdigest()}
    finally:
        shutil.rmtree(work, ignore_errors=True)
