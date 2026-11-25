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

It is a READER signal, never a file one: the file is allowed to store text in visual order (most producers
do), so «this file stores visual order» is a fact, not a defect — only a reader that fails to reconstruct the
order is. Declared limit (in the report's `not_judged`): when every installed reader returns the same reversed
order, there is no voter to disagree and the signal is silent; the file-level arm needs the source text
(reference mode) or per-glyph geometry, and neither is this module.
"""
from __future__ import annotations

from conformance.checks import lexical


def segments(text: str, vocab: frozenset[str]) -> list[tuple[tuple[str, ...], int]]:
    """[(canonical words of the line's Arabic segment, letter-reversed count)] for lines with ≥2 Arabic words.

    The tokenizer is `lexical.words` — the checker's one definition of an Arabic run (≥3 letters, normalized).
    A word that is absent from the lexicon but whose reverse is present is canonicalised to its reverse and
    counted as letter-reversed: that reading is a visual one, and it does not vote here.
    """
    out = []
    for line in (text or "").splitlines():
        runs = lexical.words(line)
        if len(runs) < 2:
            continue
        words, reversed_count = [], 0
        for word in runs:
            if word in vocab:
                words.append(word)
            elif word[::-1] in vocab:
                words.append(word[::-1])
                reversed_count += 1
            else:
                words.append(word)
        out.append((tuple(words), reversed_count))
    return out


def findings(texts: dict[str, str], vocab: frozenset[str]) -> dict[str, list[dict]]:
    """{reader: [{words, reversed_of, voters}]} — the readers whose segment order is a strict majority's reverse.

    Grouping is by the word MULTISET of the line, so two readers that wrap the line differently still compare,
    and a reader that dropped or invented a word does not silently enter a group it does not belong to.
    """
    per_reader = {name: segments(text, vocab) for name, text in (texts or {}).items()}
    groups: dict[tuple[str, ...], list[tuple[str, tuple[str, ...]]]] = {}
    for name, rows in per_reader.items():
        for words, reversed_count in rows:
            if reversed_count:
                continue                      # a visual reading is `visual-order`'s finding, not a voter here
            groups.setdefault(tuple(sorted(words)), []).append((name, words))
    out: dict[str, list[dict]] = {}
    for members in groups.values():
        votes = [words for _name, words in members]
        if len(votes) < 3:
            continue                          # one or two readings are not a majority of anything
        majority = max(set(votes), key=votes.count)
        need = len(votes) // 2 + 1
        if votes.count(majority) < need:
            continue                          # a split has no ground truth, so it raises nothing
        if majority == majority[::-1]:
            continue                          # a palindrome cannot be told apart from its reverse
        for name, words in members:
            if words == majority[::-1]:
                out.setdefault(name, []).append({"words": list(words), "reversed_of": list(majority),
                                                 "voters": len(votes)})
    return out
