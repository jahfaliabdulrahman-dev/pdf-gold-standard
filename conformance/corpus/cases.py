"""Case files: the one source of a case's text, and the only input `truth()` may read.

Schema (engine-neutral: no HTML, no Typst, no engine flag lives in a case):

  {
    "id": "<unique, ascii, hyphenated>",
    "category": "<one of CATEGORY_MINIMUMS>",
    "lang": "ar",
    "font": "plex" | "amiri",
    "blocks": [
      {"type": "heading",   "level": 1..6, "text": "..."},
      {"type": "paragraph", "text": "...", "align": "justify" (optional)},
      {"type": "list",      "ordered": true|false, "items": ["...", ...]},
      {"type": "table",     "header": ["a", "b"] | [["a","b"], ["c","d"]],
                            "rows": [["...", "..."], ...]}
    ],
    "note": "where the case comes from, or the incident it stands for"
  }

`header` may be one row (list of strings) or several (list of lists) — a two-row header is a real table
shape and a gate that cannot express it cannot test it. An optional `align: "justify"` is the only styling
input: justification is where an engine adds kashida that is not in the source, and that is a case.

Validation is strict and refuses by name: an unknown block type, a table row whose width differs from the
header, a heading level outside 1–6, a duplicate id, an empty block list. A case that cannot be built is a
case, not a silent skip.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CASES_DIR = os.path.join(HERE, "cases")
BLOCK_TYPES = {"heading", "paragraph", "list", "table"}


class CaseError(ValueError):
    """A case file that violates the schema — refused by name, never skipped."""


def case_paths() -> list[str]:
    if not os.path.isdir(CASES_DIR):
        return []
    return sorted(os.path.join(CASES_DIR, f) for f in os.listdir(CASES_DIR) if f.endswith(".json"))


def validate(case: dict, where: str = "<memory>") -> None:
    def bad(msg: str) -> None:
        raise CaseError(f"{where}: {msg}")

    for key in ("id", "category", "lang", "font", "blocks", "note"):
        if key not in case:
            bad(f"missing «{key}»")
    if not isinstance(case["id"], str) or not case["id"] or any(c.isspace() for c in case["id"]):
        bad(f"id {case.get('id')!r} is not a single ascii token")
    if case["font"] not in ("plex", "amiri"):
        bad(f"font {case['font']!r} is not plex|amiri")
    if case["lang"] != "ar":
        bad(f"lang {case['lang']!r}: this corpus is Arabic; another language is another corpus")
    if case.get("plain") not in (None, True, False):
        bad(f"plain {case.get('plain')!r} must be true|false (true = the bare fragment a customer hands over: "
            f"no @page, no line-height, no body reset)")
    if not isinstance(case["blocks"], list) or not case["blocks"]:
        bad("blocks is empty")
    for i, b in enumerate(case["blocks"]):
        if b.get("bold") not in (None, True, False):
            bad(f"block {i}: bold {b.get('bold')!r} must be true|false")
        t = b.get("type")
        if t not in BLOCK_TYPES:
            bad(f"block {i}: type {t!r} is not one of {sorted(BLOCK_TYPES)}")
        if t == "heading":
            if not isinstance(b.get("level"), int) or not 1 <= b["level"] <= 6:
                bad(f"block {i}: heading level {b.get('level')!r} is not 1..6")
            if not b.get("text"):
                bad(f"block {i}: heading without text")
        elif t == "paragraph":
            if not b.get("text"):
                bad(f"block {i}: paragraph without text")
            if b.get("align") not in (None, "justify"):
                bad(f"block {i}: align {b.get('align')!r} is not justify")
        elif t == "list":
            if not isinstance(b.get("ordered"), bool):
                bad(f"block {i}: ordered must be true|false")
            if not b.get("items") or not all(b["items"]):
                bad(f"block {i}: list without items")
        elif t == "table":
            header = b.get("header")
            rows = b.get("rows")
            if not header or not isinstance(header, list):
                bad(f"block {i}: table without header")
            width = len(header[0]) if isinstance(header[0], list) else len(header)
            if width < 1:
                bad(f"block {i}: table header has no columns")
            if isinstance(header[0], list):
                for h in header:
                    if len(h) != width:
                        bad(f"block {i}: header rows differ in width")
            if b.get("width") not in (None, "100%", "90%", "auto"):
                bad(f"block {i}: width {b.get('width')!r} is not one of 100%|90%|auto")
            if not isinstance(rows, list) or not rows:
                bad(f"block {i}: table without rows")
            for r, row in enumerate(rows):
                if len(row) != width:
                    bad(f"block {i}: row {r} has {len(row)} cells, header has {width}")


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        case = json.load(fh)
    validate(case, os.path.basename(path))
    return case


def load_all() -> list[dict]:
    cases = [load(p) for p in case_paths()]
    seen = {}
    for case, path in zip(cases, case_paths()):
        if case["id"] in seen:
            raise CaseError(f"duplicate id {case['id']!r}: {os.path.basename(path)} and {seen[case['id']]}")
        seen[case["id"]] = os.path.basename(path)
    return cases


def by_id(ids=None) -> list[dict]:
    cases = load_all()
    if not ids or ids == ["all"]:
        return cases
    want = set(ids)
    got = {c["id"] for c in cases}
    missing = sorted(want - got)
    if missing:
        raise CaseError(f"no such case(s): {missing}")
    return [c for c in cases if c["id"] in want]


def sha256_of(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()
