#!/usr/bin/env python3
"""A NEW failing rule must not slip into a baseline through --write (review P3, twice).

The generator exists so the numbers are measured, not typed — but «measured» also means «whatever the build
did», and a regression measured into the table is still a regression. `--write` refuses a set that GAINS a
rule unless the caller says `--accept-new`.

The test works on COPIES of the real baseline files: if the guard ever regresses, a test run must not be able
to edit what the gate reads. It also requires the refusal to SAY so, not merely return 1 — a crash would
otherwise read as a refusal.

Run: python3 scripts/test_baseline_guard.py
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import verapdf_baseline as B  # noqa: E402

BASELINES = ("verapdf-baseline.toml", "verapdf-baseline-report.toml", "verapdf-baseline-najd.toml")


def _run(argv, rules):
    """main() with the MEASUREMENT shimmed; returns (rc, stdout)."""
    real_rules, real_docs = B.failing_rules, B.DOCS
    B.failing_rules = lambda pdf, flavour: set(rules)     # a rule no document has ever failed
    B.DOCS = (("guide", "guide.pdf", "verapdf-baseline.toml"),)
    buf = io.StringIO()
    sys.argv = ["verapdf_baseline.py"] + argv
    try:
        with contextlib.redirect_stdout(buf):
            rc = B.main()
    finally:
        B.failing_rules, B.DOCS = real_rules, real_docs
    return rc, buf.getvalue()


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="baseline-guard-")
    for n in BASELINES:
        shutil.copyfile(os.path.join(ROOT, n), os.path.join(tmp, n))
    before = {n: open(os.path.join(tmp, n), "rb").read() for n in BASELINES}

    d = fitz.open()                       # the measurement is shimmed; the PDF only has to exist
    d.new_page()
    d.save(os.path.join(tmp, "guide.pdf"))
    d.close()

    # 1. a new rule without --accept-new: refused, says why, writes nothing
    rc, out = _run(["--root", tmp, "--baselines-dir", tmp, "--write"], {"9.9.9-1"})
    said = "REFUSED" in out and "9.9.9-1" in out
    untouched = all(open(os.path.join(tmp, n), "rb").read() == v for n, v in before.items())

    # 2. the same run with --accept-new: written — the refusal was the only thing stopping it
    rc2, out2 = _run(["--root", tmp, "--baselines-dir", tmp, "--write", "--accept-new"], {"9.9.9-1"})
    gained = 'failing = ["9.9.9-1"]' in open(os.path.join(tmp, "verapdf-baseline.toml"), encoding="utf-8").read()

    # 3. the real files were never touched by either run
    real_ok = all(open(os.path.join(ROOT, n), "rb").read() == v for n, v in before.items())

    ok = rc == 1 and said and untouched and rc2 == 0 and gained and real_ok
    print(f"{'PASS' if ok else 'FAIL'} baseline-guard - refused (rc={rc}, said={said}) · nothing written "
          f"({untouched}) · --accept-new writes ({rc2}, {gained}) · the real files untouched ({real_ok})")
    if not ok:
        print("\nBASELINE GUARD FAILED\n" + out + "\n" + out2)
        return 1
    print("\nBASELINE GUARD PASSED — a regression cannot be written into a baseline by accident")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
