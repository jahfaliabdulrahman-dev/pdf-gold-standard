"""Turn a visually-ordered line back into logical order — and refuse to guess.

Chrome paints an Arabic line by placing words from right to left, so a text run merged in content order holds
the characters in *visual* order. PDFium runs the bidi algorithm on whatever it finds (cpdf_textpage.cpp:854,
`CFX_BidiString(str, auto_order=true)`), so a visual string reverses Arabic twice — accidentally correct — and
reverses an embedded Latin run once, which is how "Business Process Model and Notation" becomes
"Notation and Model Process Business", parentheses included.

The inversion is only trusted when it survives a round trip: `bidi(logical)` must reproduce the input string
character for character. A line that does not round-trip is reported, never silently rewritten.
"""

from __future__ import annotations

from bidi.algorithm import get_display

# Bidi mirrors these while laying text out; inverting a mirror reverses it again.
MIRROR = str.maketrans({"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<"})

# Strong-LTR characters that belong to one run when the line is read left to right.
LTR_EXTRA = " .:-/,'\""


def to_logical(visual: str, base_dir: str = "R") -> str:
    """Reverse the line, then re-reverse each LTR run and un-mirror the brackets.

    `visual` is the line read left to right (ascending x), which is how the glyphs sit on the page.
    """
    reversed_line = visual[::-1]
    out: list[str] = []
    i = 0
    while i < len(reversed_line):
        ch = reversed_line[i]
        if ch.isascii() and ch.isalnum():
            j = i
            while j < len(reversed_line):
                c = reversed_line[j]
                if c.isascii() and (c.isalnum() or c in LTR_EXTRA):
                    j += 1
                else:
                    break
            out.append(reversed_line[i:j][::-1])
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out).translate(MIRROR)


def roundtrip_ok(visual: str, logical: str, base_dir: str = "R") -> bool:
    """True only when the bidi algorithm reproduces the exact visual string from `logical`."""
    try:
        return get_display(logical, base_dir=base_dir) == visual
    except Exception:
        return False


def invert_verified(visual: str, base_dir: str = "R") -> tuple[str | None, str]:
    """(logical, "") when verified; (None, reason) when the line must be left alone."""
    if not visual:
        return None, "empty line"
    guess = to_logical(visual, base_dir)
    if roundtrip_ok(visual, guess, base_dir):
        return guess, ""
    # a second candidate: no mirroring (some producers emit already-mirrored brackets)
    plain = guess.translate(MIRROR)
    if roundtrip_ok(visual, plain, base_dir):
        return plain, ""
    return None, "does not round-trip"


def _self_test() -> int:
    cases = [
        # (visual, expected logical)
        ("(Business Process Model and Notation)", "(Business Process Model and Notation)"),
        ("اهانربتخا", "اختبرناها"),
        ("2026 لودجلا", "الجدول 2026"),
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
