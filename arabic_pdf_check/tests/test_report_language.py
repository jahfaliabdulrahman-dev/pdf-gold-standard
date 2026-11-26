#!/usr/bin/env python3
"""The report a customer reads, on the install that ships: Arabic, coherent, and never a verdict it cannot carry.

Two rules are proved here, both from PR-4.2:

1. **A structural fact is not a vote.** A composite font with no `/ToUnicode`, a code mapped to U+0000, U+FFFD or
   a PUA, a drawn `.notdef` — those are facts the FILE carries. On a three-reader install the file verdict is
   withheld, and `tounicode-gaps` must still be `cause: file`. What the vote decides is the recovery DOWNGRADE,
   and that grant is withheld instead.

2. **The Markdown says it in Arabic and does not contradict itself.** With `risk.file.level = null` the header
   says «لا حكم» with the reason built from the numbers; the cause line does not say «الملف» when there is no file
   verdict; a withheld signal is printed in its own section with «محجوب: N من M قرّاء»; and no English sentence
   leaks into the header lines (identifiers inside backticks are not sentences).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from arabic_pdf_check import blind, markdown                       # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def report_from(reader_names: tuple[str, ...]) -> dict:
    """`check` as the shipped install would run it: the real modules, only the voting set is narrowed."""
    ok_all, missing = blind.available()
    ok = {n: m for n, m in ok_all.items() if n in reader_names}
    dropped = {n: why for n, why in missing.items() if n not in reader_names}
    dropped.update({n: "NotInTheShippedSet: not installed by `pip install -e .`"
                    for n in ok_all if n not in reader_names})
    real = blind.available
    blind.available = lambda: (ok, dropped)
    try:
        with open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"), encoding="utf-8") as fh:
            thresholds = json.load(fh)
        return blind.check(os.path.join(REPO, "tests", "vocalised_raw.pdf"), thresholds)
    finally:
        blind.available = real


BARE = report_from(("pdfium", "poppler", "pdfminer"))
md = markdown.render_blind(BARE)
lines = md.splitlines()

# ---------------------------------------------------------------- 1. the fact survives the shrunken jury
gaps = [s for s in BARE["signals"] if s["id"] == "tounicode-gaps"]
check("tounicode-gap-is-a-file-fact-on-three-readers",
      bool(gaps) and all(s["cause"] == "file" for s in gaps),
      str([(s["id"], s["cause"], s.get("withheld_from_file_level")) for s in BARE["signals"]]))
check("tounicode-gap-is-not-marked-withheld",
      not any(s.get("withheld_from_file_level") for s in gaps), str(gaps[:1]))
check("the-vote-derived-signal-is-the-one-withheld",
      any(s.get("withheld_from_file_level") for s in BARE["signals"] if s["id"] != "tounicode-gaps")
      or not [s for s in BARE["signals"] if s["id"] in ("visual-order", "lexical-validity",
                                                        "lam-alef-transposition")],
      str([(s["id"], bool(s.get("withheld_from_file_level"))) for s in BARE["signals"]]))

# ---------------------------------------------------------------- 2. the Markdown is Arabic and coherent
check("file-verdict-is-withheld", BARE["risk"]["file"]["level"] is None, str(BARE["risk"]["file"]))
check("header-says-no-verdict-in-arabic",
      any("**حكم الملف:** لا حكم" in ln for ln in lines), "\n".join(lines[:6]))
check("the-reason-is-built-from-the-numbers",
      any(re.search(r"قرأ \d+ من \d+", ln) and re.search(r"يحتاج \d+", ln) for ln in lines[:6]),
      "\n".join(lines[:6]))
check("no-english-withheld-sentence-in-the-markdown",
      "no file-level verdict" not in md, "the machine field must not be pasted into the Arabic page")
check("the-cause-line-does-not-blame-the-file",
      not any("السبب: الملف" in ln for ln in lines[:8]), "\n".join(lines[:8]))
check("a-withheld-signal-has-its-own-section",
      any("إشارات محجوبة عن حكم الملف" in ln for ln in lines)
      and any(re.search(r"محجوب: \d+ من \d+", ln) for ln in lines),
      "\n".join(ln for ln in lines if "محجوب" in ln))
check("a-withheld-signal-is-tagged-per-reader",
      not any(re.search(r"\((عالٍ|متوسط|منخفض), الملف — محجوب", ln) for ln in lines),
      "a withheld signal must not carry the file as its cause")

# The header is the part a person skims: identifiers in backticks (`sha…`) are not sentences, words are.
header = [ln for ln in lines[:8] if ln.strip()]
def latin_sentence(line: str) -> bool:
    stripped = re.sub(r"`[^`]*`", "", line)          # identifiers
    stripped = re.sub(r"[0-9.,:%·—\-]", "", stripped)
    return bool(re.search(r"[A-Za-z]{3,}\s+[A-Za-z]{3,}", stripped))

check("the-header-carries-no-english-sentence",
      not any(latin_sentence(ln) for ln in header),
      "\n".join(ln for ln in header if latin_sentence(ln)))

print()
if fails:
    print(f"REPORT LANGUAGE FAILED — {len(fails)}: {', '.join(fails)}")
    raise SystemExit(1)
print("REPORT LANGUAGE PASSED — the fact stays a fact, the Markdown stays Arabic and never claims a verdict "
      "the jury could not carry")
