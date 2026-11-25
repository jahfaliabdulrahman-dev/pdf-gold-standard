"""Segment order — a reader that returns a mixed line's Arabic segment as the exact reverse of every other reader.

The gap this closes (audit of 2026-11-25, item 10; first measured by PR-3): PDFium returns 11 of the 16 ZATCA
PDF/A-3 samples with correct letters and REVERSED word order inside the Arabic segment («ضريبية فاتورة» for
«فاتورة ضريبية»). `arafix` scores each reader's letters, so it returns −1.00 («logical») and the report says
nothing — 55 segments in 11 files were invisible.

The mechanism, and why it is a consensus:

  · UAX #9 §3.4 rule L2 defines the displayed order as the per-level reversal of the stored order, so two
    readers of one line differ by a reversal of the LTR/RTL runs, never by an arbitrary permutation. The
    segment this module compares is the maximal Arabic run of ≥2 words on a line; the reversal it detects is
    the exact reverse of that word sequence (`words[::-1]`), which is what a run-level reordering produces.
  · The blind mode has no source text, so the only ground truth is the readers themselves: a strict majority
    of the readers that produced the same multiset of words on the same line defines the order, and a reader
    whose order is its exact reverse is the outlier. That is the same voting rule the checker already uses for
    orientation and lexical validity.
  · A reader whose words are letter-reversed is NOT a voter: a visual reading is `visual-order`'s finding, and
    counting it here would report one defect twice.

The comparison is on NORMALISED words (the checker's one normalisation, through `lexical.words`), but the
evidence carries the words the reader actually returned: a report that prints a normalised excerpt is not
quoting the file, and a customer comparing «مدرسه» against their «مدرسة» would be right to distrust it.

It is a READER signal, never a file one: the file is allowed to store text in visual order (most producers
do), so «this file stores visual order» is a fact, not a defect — only a reader that fails to reconstruct the
order is. Declared limit (in the report's `not_judged`): when every installed reader returns the same reversed
order, there is no voter to disagree and the signal is silent; the file-level arm needs the source text
(reference mode) or per-glyph geometry, and neither is this module. A second declared limit: two readers are
compared only when their word multisets agree, so a reader that merges or splits lines is not in the group it
does not match — its silence there is not a clean reading.
"""
from __future__ import annotations

from conformance.checks import lexical, visual_order


def segments(text: str, vocab: frozenset[str]) -> list[dict]:
    """One row per line with ≥2 Arabic words: canonical words, the raw words, and the letter-reversed count.

    The tokenizer is `lexical.words` — the checker's one definition of an Arabic run (≥3 letters, normalized).
    A word that is absent from the lexicon but whose reverse is present is canonicalised to its reverse and
    counted as letter-reversed: that reading is a visual one, and it does not vote here.
    """
    out = []
    for line in (text or "").splitlines():
        # `raw` is the line's words as READ — presentation forms folded to letters (the detector's one fold),
        # but before the variant folding and mark stripping the comparison needs. `lexical.words` returns the
        # fully normalised tokens, so it cannot serve as the excerpt.
        # Marks and tatweel are stripped BEFORE tokenising, exactly as `lexical.words` does: a word carrying a
        # mark would otherwise be cut into fragments and a line could fall below its two-word floor.
        stripped = lexical.DIACRITICS.sub("", visual_order.fold(line))
        raw = [w for w in lexical.ARABIC_RUN.findall(stripped) if len(w) >= lexical.MIN_LETTERS]
        if len(raw) < 2:
            continue
        canonical, reversed_count = [], 0
        for word in raw:
            n = lexical.normalize(word)
            if n in vocab:
                canonical.append(n)
            elif n[::-1] in vocab:
                canonical.append(n[::-1])
                reversed_count += 1
            else:
                canonical.append(n)
        out.append({"words": tuple(canonical), "raw": tuple(raw), "letter_reversed": reversed_count})
    return out


def findings(texts: dict[str, str], vocab: frozenset[str],
             pages: dict[str, list[str]] | None = None) -> dict[str, list[dict]]:
    """{reader: [{words, raw, reversed_of, voters, page}]} — the readers whose segment order is a majority's reverse.

    Grouping is by the word MULTISET of the line, so two readers that wrap the line differently still compare,
    and a reader that dropped or invented a word does not silently enter a group it does not belong to.
    `pages` is the checker's per-page reading, used only to name the page of an example.
    """
    per_reader = {name: segments(text, vocab) for name, text in (texts or {}).items()}
    groups: dict[tuple[str, ...], list[tuple[str, dict]]] = {}
    for name, rows in per_reader.items():
        for row in rows:
            if row["letter_reversed"]:
                continue                      # a visual reading is `visual-order`'s finding, not a voter here
            groups.setdefault(tuple(sorted(row["words"])), []).append((name, row))
    out: dict[str, list[dict]] = {}
    for members in groups.values():
        votes = [row["words"] for _name, row in members]
        if len(votes) < 3:
            continue                          # one or two readings are not a majority of anything
        majority = max(set(votes), key=votes.count)
        need = len(votes) // 2 + 1
        if votes.count(majority) < need:
            continue                          # a split has no ground truth, so it raises nothing
        if majority == majority[::-1]:
            continue                          # a palindrome cannot be told apart from its reverse
        for name, row in members:
            if row["words"] == majority[::-1]:
                out.setdefault(name, []).append({
                    "words": list(row["words"]), "raw": list(row["raw"]),
                    "reversed_of": list(majority), "voters": len(votes),
                    "page": _page_of(pages, name, row["raw"])})
    return out


def _page_of(pages: dict[str, list[str]] | None, reader: str, raw: tuple[str, ...]) -> int | None:
    """The page whose text contains the line's raw words, in order — `None` when the reader has no page view."""
    if not pages or not pages.get(reader):
        return None
    line = " ".join(raw)
    for i, page in enumerate(pages[reader], 1):
        if line and line in (page or ""):
            return i
    return None
