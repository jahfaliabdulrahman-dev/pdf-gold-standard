#!/usr/bin/env python3
"""Floors are promises: `accept` must refuse a run that lowers one.

The defect this test closes: `accept` replaced every case's block with the run's values, so a green-looking
`--accept` after a regression rewrote the floor to the regression and the gate forgot the defect. Four controls:

  1. a first accept records the run's floors;
  2. a lower `exact` is refused, and the file is unchanged;
  3. a higher defect count is refused;
  4. `allow_lower=True` is the deliberate rebase and writes the lower value.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from conformance import ratchet

fails = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (" - " + detail if detail else ""))
    if not ok:
        fails.append(name)


def _results(exact: float = 1.0, bidi: int = 0) -> dict:
    return {
        "readers": {"pdfium": {"available": True, "version": "9.9.9"}},
        "cases": [{
            "id": "one-case",
            "per_reader": {"pdfium": {
                "metrics": {"exact": exact, "word_f1": exact, "order": exact,
                            "digit_runs": exact, "skeleton_exact": exact},
                "defects": {"bidi": bidi, "presentation_forms": 0, "pua": 0,
                            "replacement": 0, "tatweel_excess": 0, "zero_width": 0},
            }},
        }],
    }


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="ratchet-test-")
    path = os.path.join(tmp, "ratchet.json")
    try:
        ratchet.accept(_results(1.0), path)
        floor = json.load(open(path, encoding="utf-8"))["pdfium"]["floors"]["9.9.9"]["cases"]["one-case"]
        check("first-accept-records", floor["exact"] == 1.0, str(floor["exact"]))

        before = open(path, encoding="utf-8").read()
        try:
            ratchet.accept(_results(0.5), path)
            refused = False
        except SystemExit as exc:
            refused = "RATCHET REFUSED" in str(exc)
        check("lower-exact-refused", refused)
        check("file-unchanged-on-refusal", open(path, encoding="utf-8").read() == before)

        try:
            ratchet.accept(_results(1.0, bidi=1), path)
            refused_bidi = False
        except SystemExit as exc:
            refused_bidi = "defect bidi" in str(exc)
        check("higher-defect-refused", refused_bidi)

        ratchet.accept(_results(0.5), path, allow_lower=True)
        floor = json.load(open(path, encoding="utf-8"))["pdfium"]["floors"]["9.9.9"]["cases"]["one-case"]
        check("force-writes-the-rebase", floor["exact"] == 0.5, str(floor["exact"]))

        bad, _ = ratchet.check(_results(0.4), path)
        check("check-still-fails-below-floor", any("exact" in b for b in bad), "; ".join(bad[:2]))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\nRATCHET-FLOOR GUARD {'PASSED' if not fails else 'FAILED — ' + str(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
