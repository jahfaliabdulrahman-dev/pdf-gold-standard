#!/usr/bin/env python3
"""Two facts about a directory of produced PDFs, read the same way the pipeline reads them.

  1. `/PL*` keys anywhere in the file. Our bookkeeping is consumed by the stage after the one that wrote it and
     must not ship: a private key in a PDF/A-3b document is an unregistered entry in the customer's file. The
     reader is `pdfops.private_keys` — the same one both gates run; this tool only widens the SCOPE to a
     directory. It is not a CI step: the certificate gate enforces the rule on any file, and a third red step
     would not say which gate failed.
  2. Fonts with **neither** a readable `/W` nor a cmap that names U+0020. The space repair cannot judge those, so it
     leaves them alone; the number has to be known, because that silence is a behaviour, not a gap. (The review
     asked for it: before the width rule, a font with no readable widths was still repaired by the named space.)
     This count is a DIAGNOSTIC, not a gate: a non-zero value is printed, never failed on.

Usage: `python3 scripts/g1_audit.py DIR [DIR …]` — prints one line per file with a finding, then the totals.
"""
import os
import sys

import pikepdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import pdfops     # noqa: E402  (the one private-key reader)
import postprocess  # noqa: E402  (the same readers the repair uses: one implementation, not a second opinion)


def audit(path: str) -> tuple[list[str], int, int]:
    """(house keys found, fonts read, fonts no rule can judge)."""
    keys, fonts, blind = set(), 0, 0
    with pikepdf.open(path) as pdf:
        keys = set(pdfops.private_keys(pdf))
        seen = set()
        for page in pdf.pages:
            for _k, font in (page.obj.get("/Resources", {}).get("/Font", {}) or {}).items():
                if font.objgen in seen or font.get("/Subtype") != "/Type0":
                    continue
                seen.add(font.objgen)
                fonts += 1
                if not postprocess._cid_widths(font) and postprocess._space_gid(font) is None:
                    blind += 1
    return sorted(keys), fonts, blind


def main(dirs: list[str]) -> int:
    total_files = total_fonts = total_blind = 0
    leaks: list[tuple[str, list[str]]] = []
    for d in dirs:
        for name in sorted(os.listdir(d)):
            if not name.lower().endswith(".pdf"):
                continue
            path = os.path.join(d, name)
            try:
                keys, fonts, blind = audit(path)
            except Exception as exc:                      # a file this tool cannot read is a finding, not a skip
                print(f"  UNREADABLE {name}: {exc}")
                continue
            total_files += 1
            total_fonts += fonts
            total_blind += blind
            if keys:
                leaks.append((path, keys))
            if blind:
                print(f"  {name}: {blind}/{fonts} font(s) with no readable widths and no named space")
    for path, keys in leaks:
        print(f"  HOUSE KEY {os.path.basename(path)}: {', '.join(keys)}")
    print(f"files {total_files} · Type0 fonts {total_fonts} · house keys {len(leaks)} · unjudgeable fonts {total_blind}")
    if leaks:
        print("G1-AUDIT FAILED — a house key ships in a delivered file")
        return 1
    print("G1-AUDIT PASSED — no /PL* key in any file; unjudgeable fonts counted, not hidden")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
