#!/usr/bin/env python3
"""Tokenising AFTER normalization: vocalised, kashida and presentation-form Arabic must still be words.

The measured defect (probe_audit.py, 2026-11-24): `words()` cut the raw text, so every diacritic and every
tatweel split a word, and presentation forms produced no run at all. The four cases below are the audit's;
the fifth is lam-alef, which must survive as one token.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from conformance.checks import lexical                    # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


cases = {
    "vocalised": "لِلْمُستخدمين العَرَبيّة الكِتَاب",
    "kashida": "المملـــكة العـــربية السعـــودية",
    "presentation": "ﺍﻟﻌﺮﺑﻴﺔ ﺍﻟﻜﺘﺎﺏ",
    "lam-alef": "لأن",
}
expected = {"vocalised": 3, "kashida": 3, "presentation": 2, "lam-alef": 1}
for name, text in cases.items():
    got = lexical.words(text)
    check(f"{name}:count", len(got) == expected[name], f"{got}")
    check(f"{name}:whole-tokens", all(len(w) >= 3 for w in got), f"{got}")

check("presentation:not-empty", bool(lexical.words(cases["presentation"])), "[]")
check("vocalised:one-word", lexical.words("لِلْمُستخدمين") == ["للمستخدمين"],
      str(lexical.words("لِلْمُستخدمين")))
check("kashida:one-word", lexical.words("المملـــكة") == ["المملكه"], str(lexical.words("المملـــكة")))
check("plain:unchanged", lexical.words("للمستخدمين العربية الكتاب") ==
      ["للمستخدمين", "العربيه", "الكتاب"], str(lexical.words("للمستخدمين العربية الكتاب")))
check("lam-alef:one-token", lexical.words("لأن") == ["لان"], str(lexical.words("لأن")))

# The lexicon is normalized at load; every token is comparable to it by the same function.
check("lexicon-normalized", lexical.normalize("العَرَبيّة") in lexical.lexicon(),
      "the normalized word is not in the normalized lexicon")

# PR-2: both lists load, and the explicit path is the only seam (the checker reads SHIPPED_DATA by default).
current = lexical.lexicon(lexical.BASELINE_DATA)
wiki = lexical.lexicon(lexical.SHIPPED_DATA)
check("two-lexicons-load", len(current) > 35_000 and len(wiki) > 45_000, f"{len(current)} / {len(wiki)}")
check("shipped-is-default", lexical.lexicon() == wiki, "the default is not the shipped list")
check("baseline-not-default", lexical.lexicon(lexical.BASELINE_DATA) != lexical.lexicon(),
      "the baseline is being served as the shipped list")

print()
if fails:
    print(f"LEXICAL FAILED — {fails}")
    raise SystemExit(1)
print("LEXICAL PASSED — no token is cut before the one normalization")
