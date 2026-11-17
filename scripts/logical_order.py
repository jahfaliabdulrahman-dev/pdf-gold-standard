"""Turn a visually-ordered line back into logical order — and refuse to guess.

Chrome paints an Arabic line by placing words from right to left, so a text run merged in content order holds
the characters in *visual* order. PDFium runs the bidi algorithm on whatever it finds (cpdf_textpage.cpp:854,
`CFX_BidiString(str, auto_order=true)`), so a visual string reverses Arabic twice — accidentally correct — and
reverses an embedded Latin run once, which is how "Business Process Model and Notation" becomes
"Notation and Model Process Business", parentheses included.

Rules this module follows (decided with Qwen, docs/textlayer/02-qwen.md):
  * hidden controls (tab, ZWSP, LRM/RLM, word joiner, BOM) are removed: once positions are explicit they only
    confuse a second bidi pass;
  * the base direction is not assumed — both are tried and only a round-trip match is accepted;
  * Arabic-Indic digits (bidi class AN) behave like a left-to-right number run, not like Arabic letters;
  * a line that does not round-trip is reported, never silently rewritten.
"""

from __future__ import annotations

import unicodedata

from bidi.algorithm import get_display

# Bidi mirrors these while laying text out; inverting a mirror reverses it again.
MIRROR = str.maketrans({"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<"})

# Controls that carry no ink and no reading meaning once the position is explicit.
INVISIBLE = dict.fromkeys(map(ord, "\t\n\r\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2060\ufeff"))

STRONG_L = {"L"}
STRONG_R = {"R", "AL"}
DIGITS = {"EN", "AN"}
NEUTRAL_JOIN = {" ", "\u00a0", "\u060c", ".", ",", ":", ";", "-", "/", "\u061f", "\u00b7", "\u2022", "\u2013", "\u2014"}


def clean(text: str) -> str:
    """Drop the controls that only matter to a bidi engine that no longer has to run."""
    return text.translate(INVISIBLE)


def _kinds(text: str) -> list[str]:
    out = []
    for ch in text:
        cls = unicodedata.bidirectional(ch) or "ON"
        if cls in STRONG_L:
            out.append("L")
        elif cls in STRONG_R:
            out.append("R")
        elif cls in DIGITS:
            out.append("NUM")
        else:
            out.append("ON")
    return out


def _runs(text: str) -> list[tuple[str, str]]:
    runs: list[tuple[str, str]] = []
    for ch, kind in zip(text, _kinds(text)):
        if runs and runs[-1][0] == kind:
            runs[-1] = (kind, runs[-1][1] + ch)
        else:
            runs.append((kind, ch))
    return runs


def _absorb_neutrals(runs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """A space or a comma between two runs of the same kind belongs to that kind, as UBA rules N1/N2 do."""
    out = list(runs)
    changed = True
    while changed:
        changed = False
        for i, (kind, chunk) in enumerate(out):
            if kind != "ON" or not all(c in NEUTRAL_JOIN for c in chunk):
                continue
            left = next((k for k, _ in reversed(out[:i]) if k != "ON"), None)
            right = next((k for k, _ in out[i + 1:] if k != "ON"), None)
            if left is not None and left == right:
                out[i] = (left, chunk)
                changed = True
                break
    return out


def to_logical(visual: str, base_dir: str = "R") -> str:
    """Invert the display order for the given base direction.

    Base RTL: bidi reversed the order of the runs and reversed every RTL run's characters; the LTR runs
    read forward. Base LTR: the run order is untouched and only the RTL runs were reversed.
    """
    runs = _absorb_neutrals(_runs(visual))
    seq = list(reversed(runs)) if base_dir == "R" else runs
    pieces = []
    for kind, chunk in seq:
        pieces.append(chunk if kind in {"L", "NUM"} else chunk[::-1])
    return "".join(pieces).translate(MIRROR)


def roundtrip_ok(visual: str, logical: str, base_dir: str = "R") -> bool:
    """True only when the bidi algorithm reproduces the exact visual string from `logical`."""
    try:
        return get_display(logical, base_dir=base_dir) == visual
    except Exception:
        return False


def invert_verified(visual: str, base_dir: str | None = None) -> tuple[str | None, str]:
    """(logical, "") when a candidate passes the round trip; (None, reason) when the line must be left alone.

    Both base directions are tried: a line that starts with Latin text has an LTR base in every reader, and
    forcing RTL on it inverted the whole sentence instead of its Arabic runs.
    """
    visual = clean(visual)
    if not visual.strip():
        return None, "empty line"
    for base in ([base_dir] if base_dir else ["R", "L"]):
        for mirror in (True, False):
            guess = to_logical(visual, base)
            if not mirror:
                guess = guess.translate(MIRROR)
            if roundtrip_ok(visual, guess, base):
                return guess, ""
    return None, "does not round-trip"


def _self_test() -> int:
    cases = [
        ("(Business Process Model and Notation)", "(Business Process Model and Notation)"),
        ("اهانربتخا", "اختبرناها"),
        ("2026 لودجلا", "الجدول 2026"),
        ("١٢٣ ددعلا", "العدد ١٢٣"),
        ("PROOF REPORT · يسدنه ريرقت", "PROOF REPORT · تقرير هندسي"),
    ]
    bad = 0
    for visual, expected in cases:
        got, why = invert_verified(visual)
        ok = got == expected
        print(("ok  " if ok else "FAIL"), repr(visual), "->", repr(got), why)
        bad += 0 if ok else 1
    return bad


if __name__ == "__main__":
    raise SystemExit(1 if _self_test() else 0)
