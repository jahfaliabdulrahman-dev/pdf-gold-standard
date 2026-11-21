#!/usr/bin/env python3
"""The per-font ToUnicode rules — the one place the blind report can over-alarm a whole producer.

Measured on the owner's corpus: a simple TrueType font without `/ToUnicode` (FrutigerLTArabic, Helvetica)
made every drawn code count as a "gap" — 409 font signals over 55 files, and every file high. Matterhorn
31-027 allows that absence when the encoding or glyph names carry the mapping, so the rule is:

  · simple font, no /ToUnicode        → declared in the report, NOT a signal (the reader still reads it)
  · composite font, no /ToUnicode     → signal: nothing names its codes
  · a map exists and misses codes     → signal with the count
  · PUA / U+FFFD / U+0000 / U+FEFF / .notdef → signal (Matterhorn 31-028…31-030)
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
            "pua": 0, "replacement": 0, "zero_value": 0, "bom": 0}
    base.update(kw)
    return {"fonts": {"F1|%s" % base["family"]: base}}


# 1 · simple font, no ToUnicode: no signal, a note, and the row still reports its numbers
signals, rows = blind._font_signals(row(tounicode=False, missing_unicode=10))
check("simple-no-tounicode-not-a-signal", not signals, str(signals))
check("simple-no-tounicode-declared", rows and rows[0]["note"] and "31-027" in rows[0]["note"], str(rows))
check("simple-no-tounicode-counts-kept", rows and rows[0]["missing_unicode"] == 10, str(rows))

# 2 · composite font, no ToUnicode: the codes have no name at all
signals, _ = blind._font_signals(row(subtype="/Type0", two_byte=True, tounicode=False, missing_unicode=10))
check("composite-no-tounicode-is-high", any(s["id"] == "tounicode-gaps" and s["level"] == "high"
                                            for s in signals), str(signals))

# 3 · a map exists and misses codes: the SHARE decides the level (clean maximum 0, declared floor 1%)
signals, _ = blind._font_signals(row(missing_unicode=3, codes=100), gap_high=0.01)
check("gaps-over-1pct-is-high", any(s["level"] == "high" and "3 of 100" in s["detail"] for s in signals),
      str(signals))
signals, _ = blind._font_signals(row(missing_unicode=4, codes=1536), gap_high=0.01)
check("gaps-under-1pct-is-medium", any(s["level"] == "medium" and "4 of 1536" in s["detail"] for s in signals),
      str(signals))
signals, _ = blind._font_signals(row(missing_unicode=6, codes=6), gap_high=0.01)
check("empty-map-is-high", any(s["level"] == "high" for s in signals), str(signals))

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
