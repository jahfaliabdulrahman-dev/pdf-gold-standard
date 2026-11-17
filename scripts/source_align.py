"""Locate a drawn line back in the markup it came from.

Inverting the visual order reaches ~90% of lines and stops there: a mixed line has nested bidi levels, and a
neutral between two different directions cannot be placed from the picture alone. The remaining lines are not
lost — the markup that Chrome printed still holds them in logical order. What cannot be assumed is that the
drawn text equals the written text: only 4 of 26 mixed lines appear verbatim, because dashes, brackets and
non-breaking spaces change between source and paint.

So matching is done on *anchors* — Latin words and digit groups, which no bidi reordering touches — and the
window between the first and the last anchor is taken as the line's logical text. Everything else is reported
as unmatched instead of guessed.
"""

from __future__ import annotations

import html
import re
import unicodedata

ANCHOR = re.compile(r"[A-Za-z]{2,}|\d+")
TAG = re.compile(r"<[^>]+>")
ARABIC_DIGITS = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}


def source_text(path: str) -> str:
    """Visible text of an HTML file, with tags, entities and scripts removed."""
    raw = open(path, encoding="utf-8", errors="strict").read()
    raw = re.sub(r"<(script|style)\b.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = TAG.sub(" ", raw)
    raw = html.unescape(raw)
    return unicodedata.normalize("NFC", raw)


def tokens(text: str) -> list[str]:
    return text.split()


def norm(token: str) -> str:
    """Comparison form: case-folded, Arabic-Indic digits to ASCII, punctuation stripped."""
    t = token.translate(ARABIC_DIGITS).casefold()
    return "".join(ch for ch in t if ch.isalnum())


def anchors(line: str) -> list[str]:
    """Latin words and numbers in the order they were drawn — bidi never reorders these inside a run."""
    return [norm(m.group(0)) for m in ANCHOR.finditer(line)]


def find_window(source_tokens: list[str], wanted: list[str]) -> tuple[int, int] | None:
    """Smallest window of source tokens that holds every anchor in order, then grows to word boundaries."""
    if not wanted:
        return None
    flat = [norm(t) for t in source_tokens]
    # anchor positions in the source that match the first wanted token
    starts = [i for i, t in enumerate(flat) if t == wanted[0]]
    best: tuple[int, int] | None = None
    for s in starts:
        i, j = s, 0
        while i < len(flat) and j < len(wanted):
            if flat[i] == wanted[j]:
                j += 1
            i += 1
        if j == len(wanted):
            window = (s, i)
            if best is None or (window[1] - window[0]) < (best[1] - best[0]):
                best = window
    return best


def recover(line: str, source_tokens: list[str]) -> tuple[str | None, str]:
    """(logical text, "") when a source window is found; (None, reason) otherwise."""
    wanted = anchors(line)
    if not wanted:
        return None, "no anchors"
    window = find_window(source_tokens, wanted)
    if window is None:
        return None, "anchors not found in source"
    start, end = window
    # grow to whole words: the anchors sit inside words only when punctuation split them
    text = " ".join(source_tokens[start:end])
    return text, ""


if __name__ == "__main__":
    import sys

    from logical_order import invert_verified

    import pymupdf

    pdf, src = sys.argv[1], sys.argv[2]
    toks = tokens(source_text(src))
    total = failed = recovered = 0
    samples: list[tuple[str, str]] = []
    for page in pymupdf.open(pdf):
        for block in page.get_text("rawdict")["blocks"]:
            for line in block.get("lines", []):
                chars = [c for s in line["spans"] for c in s.get("chars", [])]
                if not chars:
                    continue
                visual = "".join(c["c"] for c in sorted(chars, key=lambda c: c["bbox"][0]))
                total += 1
                logical, _ = invert_verified(visual)
                if logical is not None:
                    continue
                failed += 1
                text, why = recover(visual, toks)
                if text is None:
                    if len(samples) < 5:
                        samples.append((visual[:50], why))
                else:
                    recovered += 1
    print(f"{pdf}: lines={total} not-invertible={failed} recovered-from-source={recovered} "
          f"({100 * recovered / max(1, failed):.1f}% of failures)")
    for visual, why in samples:
        print("   miss:", repr(visual), "-", why)
