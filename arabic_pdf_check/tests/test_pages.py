#!/usr/bin/env python3
"""A page number is measured, not invented: every reader's page view is the same reading it returned.

For each available reader: joining its pages with a newline must give a text that `N` treats as identical to
`text()` — otherwise the examples would carry page numbers from a different reading, which is worse than no
page number at all. A reader without `pages_many` is DECLARED `pages: unsupported` by the report (it still
reads through `text_many`; `test_blind` proves that branch); it is never reported as a reading of zero.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from conformance.checks.metrics import N                         # noqa: E402
from conformance.readers import available, pages_many, text_many  # noqa: E402

PDF = os.path.join(REPO, "tests", "vocalised_raw.pdf")
FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


ok, missing = available()
check("readers-available", len(ok) >= 4, f"{sorted(ok)} missing={missing}")
for name in ok:
    text = text_many(name, [PDF])[0]
    pages = pages_many(name, [PDF])
    check(f"{name}:pages-present-or-unsupported",
          pages is None or (len(pages) >= 1 and len(pages[0]) >= 1),
          "a reader with pages_many returned zero pages")
    if not pages:
        continue
    joined = "\n".join(pages[0])
    check(f"{name}:same-reading", N(joined) == N(text),
          f"pages={len(pages[0])} chars {len(N(joined))} vs {len(N(text))}")

print()
if FAILS:
    print(f"PAGES FAILED — {FAILS}")
    raise SystemExit(1)
print("PAGES PASSED — every reader's page view is its own reading")
