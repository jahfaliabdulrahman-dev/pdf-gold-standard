#!/usr/bin/env python3
"""What structures the pipeline actually produces — measured per document, against the declared boundary.

The gate no longer tries to interpret every PDF that could exist; it declares the model this pipeline
produces and refuses the rest by name (pdfops.model_boundary). This prints that model, so the declaration
is a measurement and not a hope: a Chrome upgrade that starts emitting text inside a Form XObject, a nested
form, a text rise or rotated artifact text shows up here first.

Usage: python3 scripts/constructs.py a.pdf [b.pdf ...]
Exit 1 if any document leaves the boundary.
"""
import os
import sys

import pikepdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from pdfops import model_stats  # noqa: E402

COLS = ("document", "forms@1", "nested", "text-in-form", "Ts", "rotated cm", "verdict")


def main() -> int:
    rows, bad = [], 0
    for path in sys.argv[1:]:
        with pikepdf.open(path) as pdf:
            violations, st = model_stats(pdf)
        rows.append((os.path.basename(path), st["forms"], st["nested"], st["text_in_form"], st["rise"],
                     st["rotated_cm"], "PASS" if not violations else "FAIL"))
        for v in violations[:4]:
            print(f"    {v}")
        bad += 0 if not violations else 1
    widths = [max(len(str(r[i])) for r in [COLS] + rows) for i in range(len(COLS))]
    for r in [COLS] + rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))
    if bad:
        print(f"\nCONSTRUCTS FAILED — {bad} document(s) leave the declared model: refuse by name, do not interpret")
        return 1
    print("\nCONSTRUCTS PASSED — every document is inside the declared model "
          "(forms at depth 1 carrying no text, no nesting, no Ts, no rotated artifact text)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
