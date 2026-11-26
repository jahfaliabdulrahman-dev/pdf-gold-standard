#!/usr/bin/env python3
"""The Arabic acceptance, on whatever reader matrix the machine has — the same rules on macOS and Linux.

`checker-linux` used to prove the matrix on a LATIN file and call it a day: the API's target platform (Linux)
had no Arabic acceptance at all (audit of 2026-11-25, item 1). This is that acceptance, as one command:

  · every planted fixture is at its declared level (`checker_fixtures.PLANTED_LEVEL`, default `high`) with its
    named signal in the FILE signals — a near-miss level is not a pass;
  · every clean file stays `file != high` (a reader's high risk is that reader's, never the file's);
  · the readers that must participate are named, and the ones that must be missing are named: PDFKit is
    macOS-only, and a Linux run that silently has it (or silently lacks poppler) is not this run.

Fixtures are built here (`--build`) because a generated PDF in the repository drifts from its generator. The
clean documents are passed as paths: CI hands over the guide the build job produced, so the acceptance is on a
real Arabic document the pipeline wrote, not on a fixture.
"""
import argparse
import json
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import checker_fixtures                                                          # noqa: E402
from arabic_pdf_check import blind                                               # noqa: E402

LEVELS = blind.LEVELS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixtures", default=None, help="a directory outside the repository for the built fixtures")
    ap.add_argument("--build", action="store_true", help="build the fixtures (needs Chrome and the fonts)")
    ap.add_argument("--clean", action="append", default=[], metavar="PDF",
                    help="a clean Arabic document that must stay file != high (repeatable)")
    ap.add_argument("--require-readers", default="",
                    help="comma-separated readers that MUST participate")
    ap.add_argument("--require-missing", default="",
                    help="comma-separated readers that MUST be missing (e.g. pdfkit on Linux)")
    ap.add_argument("--thresholds", default=os.path.join(REPO, "arabic_pdf_check", "thresholds.json"))
    a = ap.parse_args()

    with open(a.thresholds, encoding="utf-8") as fh:
        thresholds = json.load(fh)
    ok, missing = blind.available()
    present = set(ok)
    want = {n for n in a.require_readers.split(",") if n}
    absent = {n for n in a.require_missing.split(",") if n}
    problems = []
    if want - present:
        problems.append(f"required reader(s) did not participate: {sorted(want - present)} "
                        f"(present: {sorted(present)}; missing: {sorted(missing)})")
    if absent & present:
        problems.append(f"reader(s) that must be absent participated: {sorted(absent & present)}")
    if absent - set(missing):
        problems.append(f"reader(s) declared missing are not even declared: {sorted(absent - set(missing))}")
    print(f"readers: {sorted(present)} · missing: {sorted(missing)}")

    failures = list(problems)
    if a.build:
        built = checker_fixtures.build_all(a.fixtures or tempfile.mkdtemp(prefix="checker-fixtures-"))
    else:
        if not a.fixtures:
            ap.error("--fixtures is required unless --build is passed")
        # The same names `build_all` writes, read back from the directory: a path that does not exist is a
        # failure named here, never a skipped fixture.
        built = {"planted": {name: os.path.join(a.fixtures, f"{name}.pdf") for name in checker_fixtures.PLANTED}}
        for name, path in built["planted"].items():
            if not os.path.exists(path):
                failures.append(f"{name}: fixture is missing at {path}")

    for name, path in built["planted"].items():
        rep = blind.check(path, thresholds)
        expected = checker_fixtures.PLANTED[name]
        declared = checker_fixtures.PLANTED_LEVEL.get(name, "high")
        ids = [s["id"] for s in rep["signals"]]
        level = rep["risk"]["file"]["level"]
        good = level in LEVELS and LEVELS[level] >= LEVELS[declared] and expected in ids
        print(f"   {name:28} file={level:6} declared={declared:6} signals={ids} {'PASS' if good else 'FAIL'}")
        if not good:
            failures.append(f"{name}: file={level} (declared {declared}), signals={ids}, expected {expected}")

    for path in a.clean:
        if not os.path.exists(path):
            failures.append(f"clean document is missing: {path}")
            continue
        rep = blind.check(path, thresholds)
        level = rep["risk"]["file"]["level"]
        ids = [s["id"] for s in rep["signals"]]
        good = level != "high"
        print(f"   clean {os.path.basename(path):28} file={level:6} signals={ids} {'PASS' if good else 'FAIL'}")
        if not good:
            failures.append(f"clean document {os.path.basename(path)} is high: {ids}")

    if failures:
        print("ARABIC ACCEPTANCE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("ARABIC ACCEPTANCE PASSED — every planted fixture at its declared level with its named signal, "
          "no clean document high, on the readers this machine actually has")
    return 0


if __name__ == "__main__":
    sys.exit(main())
