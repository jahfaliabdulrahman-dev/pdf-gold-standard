#!/usr/bin/env python3
"""Font intake gate — accept a font only if it can actually typeset Arabic in a PDF.

Why this exists: a font that lacks a glyph ships a `.notdef` box and no existing gate notices; a font
without the Arabic joining features ships disconnected letters; a variable font needs a static instance
before it can go into a form /DR (PDF has no variable-font axis). All three are cheap to check here and
expensive to discover in a delivered file.

Usage:
    font_intake.py FONT.ttf [--corpus FILE ...] [--json]

Exit codes: 0 = accepted, 1 = rejected (the reasons are printed), 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from fontTools.ttLib import TTFont

# Letters whose joining behaviour is the whole point; if these are missing the font cannot type Arabic.
ARABIC_LETTERS = "ابتثجحخدذرزسشصضطظعغفقكلمنهويءأإآؤئىة"
TASHKEEL = "\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0653\u0654\u0655"
PUNCT = "،؛؟٪﷼«»…"
DIGITS = "0123456789٠١٢٣٤٥٦٧٨٩"
JOIN_FEATURES = {"init", "medi", "fina", "rlig"}
MARK_FEATURES = {"mark", "mkmk", "curs"}


def load(path: str) -> TTFont:
    return TTFont(path, fontNumber=0)


def names(font: TTFont) -> dict[int, str]:
    """Every language's text for each nameID, joined — a licence line may live in one language only."""
    buckets: dict[int, list[str]] = {}
    for rec in font["name"].names:
        try:
            text = rec.toUnicode().strip()
        except Exception:
            continue
        if text and text not in buckets.setdefault(rec.nameID, []):
            buckets[rec.nameID].append(text)
    return {k: " | ".join(v) for k, v in buckets.items()}


def features(font: TTFont, table: str) -> set[str]:
    if table not in font:
        return set()
    try:
        records = getattr(font[table].table, "FeatureList", None)
        if records is None:
            return set()
        return {r.FeatureTag for r in records.FeatureRecord}
    except Exception:
        return set()


def check(path: str, corpora: list[str]) -> dict:
    font = load(path)
    n = names(font)
    cmap = font.getBestCmap() or {}
    gsub, gpos = features(font, "GSUB"), features(font, "GPOS")
    axes = [(a.axisTag, a.minValue, a.defaultValue, a.maxValue) for a in font["fvar"].axes] if "fvar" in font else []

    licence_text = " ".join(n.get(i, "") for i in (0, 13, 14))
    low = licence_text.lower()
    # A grant exists if the font names a public licence or points at one. "All rights reserved" alone is
    # not a grant — but it is also not a prohibition of embedding, only of shipping the font itself.
    granted = "open font license" in low or "ofl" in low or bool(n.get(14)) or "public domain" in low
    restricted = not granted and ("all rights reserved" in low or not n.get(13))

    required = set(ARABIC_LETTERS + TASHKEEL + PUNCT + DIGITS)
    missing_required = sorted(f"{c} (U+{ord(c):04X})" for c in required if ord(c) not in cmap)

    corpus_missing: dict[str, list[str]] = {}
    for path_like in corpora:
        text = open(path_like, encoding="utf-8").read()
        chars = {c for c in text if c.strip() and ord(c) > 127}
        gap = sorted(c for c in chars if ord(c) not in cmap)
        if gap:
            corpus_missing[path_like] = gap

    problems: list[str] = []
    if not cmap:
        problems.append("no cmap: the font maps no characters")
    if not JOIN_FEATURES <= gsub:
        problems.append(f"GSUB lacks Arabic joining features: {sorted(JOIN_FEATURES - gsub)} — letters would print disconnected")
    if not (gpos & MARK_FEATURES):
        problems.append(f"GPOS lacks mark positioning ({sorted(MARK_FEATURES)}) — tashkeel would not sit on its letter")
    if missing_required:
        problems.append(f"missing core Arabic characters: {len(missing_required)} — e.g. {missing_required[:6]}")
    for path_like, gap in corpus_missing.items():
        problems.append(f"{path_like}: missing {len(gap)} character(s) used by the document — {gap[:8]}")

    return {
        "path": path,
        "family": n.get(1, ""),
        "version": n.get(5, ""),
        "glyphs": font["maxp"].numGlyphs,
        "cmap": len(cmap),
        "upem": font["head"].unitsPerEm,
        "variable_axes": axes,
        "gsub": sorted(gsub),
        "gpos": sorted(gpos),
        "licence": licence_text.strip()[:160] or "(none declared)",
        "redistribution_unclear": restricted,
        "corpus_missing": corpus_missing,
        "problems": problems,
        "verdict": "ACCEPT" if not problems else "REJECT",
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Gate a font before it enters the PDF pipeline.")
    ap.add_argument("font")
    ap.add_argument("--corpus", action="append", default=[], help="text file whose characters must all exist")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv[1:])
    if not os.path.exists(args.font):
        print(f"usage error: no such font: {args.font}", file=sys.stderr)
        return 2
    report = check(args.font, args.corpus)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['verdict']}: {report['family']} ({report['version']})")
        print(f"  glyphs={report['glyphs']} cmap={report['cmap']} upem={report['upem']} axes={report['variable_axes']}")
        print(f"  licence: {report['licence']}")
        if report["redistribution_unclear"]:
            print("  NOTE: no explicit redistribution grant — embedding in a document is fine, shipping the font is not.")
        for p in report["problems"]:
            print(f"  FAIL {p}")
    return 0 if report["verdict"] == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
