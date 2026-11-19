#!/usr/bin/env python3
"""Fetch the two pinned fonts into `fonts/full/` and print their sha256 — the setup step of the corpus.

The files are not committed (the owner's decision is open); this script is the reproducible substitute: the
URLs are pinned to the commit that last changed each file in google/fonts, and the bytes are checked against
the recorded sha256 before anything can use them.

    python3 -m conformance.adapters.fetch_fonts
"""
import sys

from . import fonts


def main() -> int:
    for key, entry in fonts.FONTS.items():
        path = fonts.path(key)
        print(f"{entry['file']:<40} {fonts.sha256_of(path)}  {path}")
        print(f"  {entry['family']} · {entry['homepage']} · {fonts.LICENCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
