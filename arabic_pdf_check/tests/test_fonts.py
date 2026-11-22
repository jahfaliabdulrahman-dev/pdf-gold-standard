#!/usr/bin/env python3
"""The per-font ToUnicode rules — the one place the blind report can over-alarm a whole producer.

Measured on the owner's corpus: a simple TrueType font without `/ToUnicode` (FrutigerLTArabic, Helvetica)
made every drawn code count as a "gap" — 409 font signals over 55 files, and every file high. Matterhorn
31-027 allows that absence when the encoding or glyph names carry the mapping, so the rule is:

  · simple font, no /ToUnicode        → declared in the report ONLY for a standard encoding (or none at
    all, where the built-in mapping is not verified here); a custom encoding is a signal
  · composite font, no /ToUnicode     → signal: nothing names its codes
  · a map exists and misses codes     → signal with the count; high only when a gap sits inside a word
  · symbol font (name, or all codes PUA) → its PUA icons are noted, never raised
  · PUA / U+FFFD / U+0000 / U+FEFF / .notdef in a text font → signal (Matterhorn 31-028…31-030)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from arabic_pdf_check import blind                          # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def row(**kw):
    base = {"name": "/F1", "family": "TestFont", "subtype": "/TrueType", "embedded": True,
            "tounicode": True, "two_byte": False, "codes": 10, "notdef": 0, "missing_unicode": 0,
            "missing_in_word": 0, "missing_codes": {}, "glyph_names": {}, "encoding": "",
            "encoding_differences": False, "pua": 0, "replacement": 0, "zero_value": 0, "bom": 0}
    base.update(kw)
    return {"fonts": {"F1|%s" % base["family"]: base}}


# 1 · simple font, no ToUnicode: declared ONLY when a standard encoding names the codes (Matterhorn 31-027)
signals, rows = blind._font_signals(row(tounicode=False, missing_unicode=10, encoding="/WinAnsiEncoding"))
check("simple-no-tounicode-standard-is-not-a-signal", not signals, str(signals))
check("simple-no-tounicode-declared", rows and rows[0]["note"] and "31-027" in rows[0]["note"], str(rows))
check("simple-no-tounicode-counts-kept", rows and rows[0]["missing_unicode"] == 10, str(rows))
signals, rows = blind._font_signals(row(tounicode=False, missing_unicode=10))
check("simple-no-tounicode-no-encoding-declared", not signals and rows and "not verified" in (rows[0]["note"] or ""),
      str(rows))
# ... and a custom encoding is NOT the exception: nothing verifies its mapping.
signals, _ = blind._font_signals(row(tounicode=False, missing_unicode=10, encoding="/CustomEncoding"))
check("simple-no-tounicode-custom-is-high",
      any(s["level"] == "high" and "not verifiable" in s["detail"] for s in signals), str(signals))
# The certificate gate consumes the same verdict with gap_high=0: a custom encoding must FAIL it, not be
# declared — this is the mutation the owner's P3 asked for, expressed at the rule the gate calls.
from conformance.checks import structure                   # noqa: E402
verdict = structure.font_verdicts(row(tounicode=False, missing_unicode=10, encoding="/CustomEncoding"), 0.0)[0]
check("gate-custom-encoding-fails", verdict["level"] == "high",
      str(verdict["problems"]))
signals, rows = blind._font_signals(row(tounicode=False, missing_unicode=10, encoding="/WinAnsiEncoding",
                                     encoding_differences=True))
check("simple-no-tounicode-differences-declared",
      not signals and rows and "not verified" in (rows[0]["note"] or ""), str(rows))

# 2 · composite font, no ToUnicode: the codes have no name at all
signals, _ = blind._font_signals(row(subtype="/Type0", two_byte=True, tounicode=False, missing_unicode=10))
check("composite-no-tounicode-is-high", any(s["id"] == "tounicode-gaps" and s["level"] == "high"
                                            for s in signals), str(signals))

# 3 · a map exists and misses codes: the SHARE decides, and a gap must sit INSIDE a word to be high
signals, _ = blind._font_signals(row(missing_unicode=3, codes=100, missing_in_word=3), gap_high=0.01)
check("gaps-inside-words-over-1pct-is-high",
      any(s["level"] == "high" and "3 of 100" in s["detail"] for s in signals), str(signals))
signals, _ = blind._font_signals(row(missing_unicode=3, codes=100, missing_in_word=0), gap_high=0.01)
check("gaps-between-words-are-medium",
      any(s["level"] == "medium" and "between words" in s["detail"] for s in signals), str(signals))
signals, _ = blind._font_signals(row(missing_unicode=4, codes=1536, missing_in_word=4), gap_high=0.01)
check("gaps-under-1pct-is-medium", any(s["level"] == "medium" and "4 of 1536" in s["detail"] for s in signals),
      str(signals))
signals, _ = blind._font_signals(row(missing_unicode=6, codes=6), gap_high=0.01)
check("empty-map-is-high", any(s["level"] == "high" for s in signals), str(signals))

# 4 · a symbol font's PUA icons are not a text defect; a text font's PUA still is
signals, rows = blind._font_signals(row(family="Wingdings", codes=13, pua=13))
check("symbol-pua-is-not-a-signal", not signals and rows[0]["symbol"] is True, str(signals))
signals, rows = blind._font_signals(row(family="Wingdings", subtype="/Type0", two_byte=True, codes=13, pua=13))
check("symbol-pua-composite-is-not-a-signal", not signals and rows[0]["symbol"] is True, str(signals))
signals, _ = blind._font_signals(row(family="Calibri", codes=100, pua=2))
check("text-pua-is-high", any("private use" in s["detail"] for s in signals), str(signals))

# 4 · the four mapped-value defects
for field, marker in (("pua", "private use"), ("replacement", "U+FFFD"), ("zero_value", "U+0000"),
                      ("bom", "U+FEFF")):
    signals, _ = blind._font_signals(row(**{field: 2}))
    check(f"mapped-{field}-is-high", any(marker in s["detail"] for s in signals), str(signals))

# 5 · .notdef drawn
signals, _ = blind._font_signals(row(notdef=4))
check("notdef-is-high", any(".notdef" in s["detail"] for s in signals), str(signals))

# 6 · a clean row produces nothing
signals, rows = blind._font_signals(row(codes=500))
check("clean-row-is-silent", not signals and rows[0]["note"] is None, str(signals))

print()
if FAILS:
    print(f"FONT RULES FAILED — {FAILS}")
    raise SystemExit(1)
print("FONT RULES PASSED — the Matterhorn exception is declared, every real gap is a signal")
