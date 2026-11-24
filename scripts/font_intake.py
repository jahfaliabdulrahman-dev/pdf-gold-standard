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


def licence_state(names: dict[int, str]) -> tuple[str, bool, bool]:
    """(licence text, granted, redistribution_unclear) — a URL in nameID 14 is not a licence grant.

    nameID 13 is the licence description and nameID 0 the copyright notice: those carry TEXT, and an open
    licence named there is a grant. nameID 14 is a URL; a commercial EULA link lives there too, and treating
    its presence as a grant made every font with a licence link look redistributable. The URL is kept for
    the report, never counted as permission.
    """
    licence_text = " ".join(names.get(i, "") for i in (0, 13, 14)).strip()
    grant_text = " ".join(names.get(i, "") for i in (0, 13)).lower()
    granted = any(token in grant_text for token in (
        "open font license", "ofl", "apache license", "apache 2", "general public license", "gpl",
        "bitstream vera", "cc0", "creative commons zero", "public domain"))
    restricted = not granted
    return licence_text[:160] or "(none declared)", granted, restricted


def embedding_permission(fs: int | None) -> str:
    """What the font's OS/2.fsType actually grants, read from the file — not inferred from nameID 0/13/14."""
    if fs is None:
        return "no OS/2 table: the licence text is the only source"
    level = fs & 0x000F
    names = {0: "installable", 2: "restricted licence", 4: "preview & print", 8: "editable"}
    extra = []
    if fs & 0x0100:
        extra.append("no subsetting (0x0100)")
    if fs & 0x0200:
        extra.append("bitmap only (0x0200)")
    return f"fsType=0x{fs:04X}: " + names.get(level, f"unknown level {level}") + ("; " + ", ".join(extra) if extra else "")


def check(path: str, corpora: list[str]) -> dict:
    font = load(path)
    n = names(font)
    cmap = font.getBestCmap() or {}
    gsub, gpos = features(font, "GSUB"), features(font, "GPOS")
    fs_type = font["OS/2"].fsType if "OS/2" in font else None
    axes = [(a.axisTag, a.minValue, a.defaultValue, a.maxValue) for a in font["fvar"].axes] if "fvar" in font else []

    licence_text, _granted, restricted = licence_state(n)

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
    # The embedding permission is a GATE, not a printout: a face whose OS/2 forbids what the pipeline
    # does must be refused here, before it enters a document.
    if fs_type is not None:
        if fs_type & 0x0002:          # bit 1: restricted licence embedding (also set in 0x0003)
            problems.append(f"OS/2.fsType=0x{fs_type:04X} (restricted licence bit): the font does not permit embedding")
        if fs_type & 0x0100:
            problems.append("OS/2.fsType bit 0x0100 (no subsetting): the pipeline ships a subset of every page font")
        if fs_type & 0x0200:
            problems.append("OS/2.fsType bit 0x0200 (bitmap only): the pipeline embeds an outline font")

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
        "licence_url": n.get(14, ""),
        "os2_fsType": fs_type,
        "embedding": embedding_permission(fs_type),
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
        print(f"  embedding: {report['embedding']}")
        if report["redistribution_unclear"]:
            print("  NOTE: the name table grants no redistribution — the embedding field above says what OS/2 allows.")
        for p in report["problems"]:
            print(f"  FAIL {p}")
    return 0 if report["verdict"] == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
