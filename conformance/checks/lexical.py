"""Lexical validity — do the readers' words exist in Arabic, or are they only shaped like Arabic?

The measured problem this answers (owner's review, 2026-11-23): two files with the SAME structural fact — a
/ToUnicode map that covers none of the drawn codes — have opposite realities. In one, the readers infer the
letters from the embedded font and return real words; in the other they return letters that are individually
correct and lexically nonexistent ("إضدب مدب اةعدب…"). A structural scan cannot tell them apart; the words can.

Method, deterministic and declared:
  · each reader's text is split into Arabic-letter runs of ≥3 letters (digits and Arabic punctuation are not
    letters, so «٢٠٢٦» is not a word);
  · a run counts as known when it is in the lexicon, or when its reverse is (a visual-order run reads
    backwards, and that is a different signal's finding — here it is evidence the letters are real);
  · normalization: arafix's presentation-form fold, then diacritics/tatweel removed and the hamza/alef,
    ya, ta-marbuta and waw/ya-hamza variants folded;
  · the ratio is `known / runs` — never printed as a percentage in a report (the assignment's rule), only
    as counts.

The lexicon is FrequencyWords' Arabic 50k list (OpenSubtitles 2018), MIT for the code and **CC-BY-SA-4.0 for
the content** — open, attributed in `data/LICENSE-ar_words.txt`. arafix's bundled core lexicon (1,716 entries,
curated for lam-alef ambiguity) was measured first and refused: it knows 0.1–3.1% of the words of a correct
Arabic document, so it cannot separate a valid text from a garbled one.

This is a LEXICON, not a language model: a correct document full of proper nouns and dialect will score lower,
which is why the threshold is derived from measured sets and why a failing majority — never one reader — is
what raises the file.
"""
from __future__ import annotations

import gzip
import os
import re
import unicodedata
from functools import lru_cache

from conformance.checks.visual_order import fold, lam_alef

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ar_words_50k.txt.gz")
SOURCE = "FrequencyWords ar_50k (OpenSubtitles 2018) — CC-BY-SA-4.0"
MIN_LETTERS = 3

ARABIC_RUN = re.compile(r"[\u0621-\u063A\u0641-\u064A\u066E-\u06D3\u06FA-\u06FF]+")
DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")


def normalize(word: str) -> str:
    """The one normalization — declared above, applied to the text AND to the lexicon at load time."""
    word = fold(word)                            # arafix's fold, through the one wrapper (visual_order.fold)
    word = unicodedata.normalize("NFC", word)
    word = DIACRITICS.sub("", word)
    for src, dst in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"), ("ى", "ي"), ("ة", "ه"),
                     ("ؤ", "و"), ("ئ", "ي")):
        word = word.replace(src, dst)
    return word


@lru_cache(maxsize=1)
def lexicon() -> frozenset[str]:
    with gzip.open(DATA, "rt", encoding="utf-8") as fh:
        return frozenset(normalize(w) for w in fh.read().split("\n") if w)


def words(text: str) -> list[str]:
    """Arabic runs of at least MIN_LETTERS — punctuation, Latin and digits are not words here.

    Tokenising happens AFTER the one normalization (fold → strip tashkeel/tatweel → fold the letter
    variants): cutting first broke every word that carried a mark or a kashida, and turned presentation
    forms into `[]`. The lexicon is normalized the same way at load, so a token and an entry are comparable.
    """
    return [w for w in ARABIC_RUN.findall(normalize(text or "")) if len(w) >= MIN_LETTERS]


def validity(text: str) -> dict:
    """{'runs', 'known', 'ratio', 'reversed', 'lam_alef'} for one reader's text; ratio is a count, not a claim."""
    runs = words(text)
    n_sure, _n_maybe = lam_alef(text or "")
    if not runs:
        return {"runs": 0, "known": 0, "ratio": 0.0, "reversed": 0, "lam_alef": int(n_sure)}
    vocab = lexicon()
    known = back = 0
    for w in runs:
        n = normalize(w)
        if n in vocab:
            known += 1
        elif n[::-1] in vocab:
            known += 1
            back += 1
    return {"runs": len(runs), "known": known, "ratio": round(known / len(runs), 4), "reversed": back,
            "lam_alef": int(n_sure)}
