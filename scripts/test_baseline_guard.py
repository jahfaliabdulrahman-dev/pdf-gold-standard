#!/usr/bin/env python3
"""A NEW failing rule must not slip into a baseline through --write (review P3).

The generator exists so the numbers are measured, not typed — but «measured» also means «whatever the build
did», and a regression measured into the table is still a regression. `--write` refuses a set that GAINS a
rule unless the caller says `--accept-new`.

Run: python3 scripts/test_baseline_guard.py
"""
import os
import sys
import tempfile

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import verapdf_baseline as B  # noqa: E402


def main() -> int:
    before = {n: open(os.path.join(os.path.dirname(HERE), n), "rb").read() for n in
              ("verapdf-baseline.toml", "verapdf-baseline-report.toml", "verapdf-baseline-najd.toml")}
    # The test needs a PDF that exists, not a measured one: the measurement itself is shimmed below.
    tmp = tempfile.mkdtemp(prefix="baseline-guard-")
    pdf = os.path.join(tmp, "guide.pdf")
    d = fitz.open()
    d.new_page()
    d.save(pdf)
    d.close()
    real_rules, real_docs = B.failing_rules, B.DOCS
    B.failing_rules = lambda pdf, flavour: {"9.9.9-1"}      # a rule no document has ever failed
    B.DOCS = (("guide", "guide.pdf", "verapdf-baseline.toml"),)
    sys.argv = ["verapdf_baseline.py", "--root", tmp, "--write"]
    try:
        rc = B.main()
    finally:
        B.failing_rules, B.DOCS = real_rules, real_docs
    untouched = all(open(os.path.join(os.path.dirname(HERE), n), "rb").read() == v for n, v in before.items())
    ok = rc == 1 and untouched
    print(f"{'PASS' if ok else 'FAIL'} baseline-guard - a new failing rule is refused (rc={rc}) and no file "
          f"changed ({untouched})")
    if not ok:
        print("\nBASELINE GUARD FAILED")
        return 1
    print("\nBASELINE GUARD PASSED — a regression cannot be written into a baseline by accident")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
