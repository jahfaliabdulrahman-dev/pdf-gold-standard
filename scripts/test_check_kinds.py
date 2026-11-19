#!/usr/bin/env python3
"""C0 guard: every check declares its kind, and the inventory table matches the code.

What this proves (and how it can fail):
  1. `verify_pdf.CHECK_KIND` covers exactly the checks the gate declares (`spec_base.CHECK_NAMES`) —
     no check without a kind, no kind without a check.
  2. Every value is `generic` or `calibrated`.
  3. `docs/conformance/check-inventory.md` has one row per check, same set in both directions.
  4. The guard itself bites: a check whose comparison is TRUE but which declares no kind is still a
     failure. Without this control, (1) would pass on a gate that silently ignored unknown names.

Usage: .venv/bin/python scripts/test_check_kinds.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

import spec_base  # noqa: E402
import verify_pdf  # noqa: E402

DOC = os.path.join(HERE, "..", "docs", "conformance", "check-inventory.md")
KINDS = {"generic", "calibrated"}
fails = []


def check(name, ok, detail):
    print(("PASS " if ok else "FAIL ") + name + " - " + detail)
    if not ok:
        fails.append(name)


declared = set(spec_base.CHECK_NAMES)
kinds = dict(verify_pdf.CHECK_KIND)
check("kinds-cover-checks", set(kinds) == declared,
      f"{len(kinds)} kinded · {len(declared)} declared"
      + ("" if set(kinds) == declared else
         f" · missing {sorted(declared - set(kinds))} · extra {sorted(set(kinds) - declared)}"))
check("kinds-are-two-values", set(kinds.values()) <= KINDS, f"values {sorted(set(kinds.values()))}")

# The table: rows shaped `| n | `name` | kind | reason |`. The name and kind are read from the document;
# the count is compared to the code, so a deleted or duplicated row breaks this test rather than a reader's trust.
rows = []
for line in open(DOC, encoding="utf-8"):
    m = re.match(r"\|\s*\d+\s*\|\s*`([^`]+)`\s*\|\s*(generic|calibrated)\s*\|", line)
    if m:
        rows.append((m.group(1), m.group(2)))
doc_names = [n for n, _ in rows]
check("doc-row-count", len(rows) == len(kinds), f"{len(rows)} rows · {len(kinds)} checks in code")
check("doc-names-match", len(set(doc_names)) == len(doc_names) and set(doc_names) == set(kinds),
      "same set" if set(doc_names) == set(kinds) else
      f"only in doc {sorted(set(doc_names) - set(kinds))} · only in code {sorted(set(kinds) - set(doc_names))}")
drift = [(n, k, kinds.get(n)) for n, k in rows if kinds.get(n) != k]
check("doc-kinds-match", not drift, f"{len(drift)} drifting row(s)" + (f": {drift[:3]}" if drift else ""))

# The control: a passing check with no kind must FAIL. This is the mutation the acceptance asks for,
# carried inside the test so it cannot rot: `make_checker({})` is the gate with an empty registry.
check_fn, fails_run, ran = verify_pdf.make_checker({"known": "generic"})
check_fn("known", True, "a real comparison")
check_fn("phantom-no-kind", True, "this comparison is TRUE and it must still fail the gate")
check("guard-bites", fails_run == ["phantom-no-kind"] and ran == ["known", "phantom-no-kind"],
      f"fails {fails_run} · ran {len(ran)}")
# And the real registry keeps it true: the phantom is not in CHECK_KIND.
check("phantom-not-registered", "phantom-no-kind" not in kinds, "the control name is not a real check")

counts = {k: sorted(n for n, v in kinds.items() if v == k) for k in sorted(KINDS)}
print(f"\nDERIVED: {len(kinds)} checks · {len(counts['generic'])} generic · {len(counts['calibrated'])} calibrated")
if fails:
    print(f"TEST FAILED — {fails}")
    raise SystemExit(1)
print("CHECK-KIND GUARD PASSED")
