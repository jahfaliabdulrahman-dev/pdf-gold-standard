#!/usr/bin/env python3
"""How much text sits inside each kind of /Artifact — and whether any of it is outside the declared band.

The rule the review asked for: every artifact that carries text is page furniture, it must be TYPED as
pagination and it must sit in the band; untyped artifact text is what used to disappear from a screen reader.
This is the measurement, printed per document, not a prose claim.

Usage: PDF_SPEC=<spec> python3 scripts/artifact_inventory.py a.pdf [b.pdf ...]
Exit 1 when an untyped artifact carries text, or any artifact text is outside the band.
"""
import os
import sys

import pikepdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import spec_loader  # noqa: E402
from pdfops import artifact_shows, form_resolver, outside_bands, props_of  # noqa: E402


def main() -> int:
    NS = spec_loader.load()
    bands = list(getattr(NS, "FURNITURE_BANDS", []))
    bad = 0
    for path in sys.argv[1:]:
        counts, strays, pages = {}, [], 0
        with pikepdf.open(path) as pdf:
            pages = len(pdf.pages)
            for pi, page in enumerate(pdf.pages, 1):
                instr = list(pikepdf.parse_content_stream(page))
                resolve, props = form_resolver(page), props_of(page)
                for kind, n in artifact_shows(instr, resolve, props).items():
                    counts[kind] = counts.get(kind, 0) + n
                strays += [f"p{pi} {k} y={y:.0f}" for k, y in outside_bands(instr, bands, resolve, props)]
        untyped = counts.get("artifact", 0)
        ok = untyped == 0 and not strays
        print(f"{'PASS' if ok else 'FAIL'} {os.path.basename(path):24s} {pages} pages · bands {bands or '[]'} · "
              f"pagination {counts.get('pagination', 0)} · untyped {untyped} · outside {strays[:3] or 0}")
        bad += 0 if ok else 1
    if bad:
        print(f"\nARTIFACT INVENTORY FAILED — {bad} document(s) carry artifact text that is untyped or outside")
        return 1
    print("\nARTIFACT INVENTORY PASSED — every artifact text is typed pagination and inside the band")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
