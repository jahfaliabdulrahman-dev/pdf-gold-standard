#!/usr/bin/env python3
"""The shipped lam-alef density must BE the midpoint of its two measured bounds — re-derived, not trusted.

`thresholds.json` carries the literal 6.2 and a prose source. A literal with a prose source is a claim: it
cannot fail. This guard recomputes the value from the deposited measurement
(`docs/checker-v0/measurements/lam-alef-separation.json`) with the formula the source states — the geometric
midpoint of the clean maximum and the broken minimum — and fails when the literal and the evidence disagree.

It also crosses the two artifacts: the calibration sha256 in the separation artifact must be the sha256 the
calibration manifest publishes for the same file, so neither can be edited alone.
"""
import json
import math
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SEP = os.path.join(REPO, "docs", "checker-v0", "measurements", "lam-alef-separation.json")
CAL = os.path.join(REPO, "docs", "checker-v0", "measurements", "calibration.json")
TH = os.path.join(REPO, "arabic_pdf_check", "thresholds.json")
PYTHON_LESSON = "٣ - درس - البايثون.pdf"

passed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if not condition:
        print(f"FAIL {name} — {detail}")
        raise SystemExit(1)
    passed += 1
    print(f"PASS {name}")


def main() -> int:
    sep = json.load(open(SEP, encoding="utf-8"))
    cal = json.load(open(CAL, encoding="utf-8"))
    th = json.load(open(TH, encoding="utf-8"))

    rows = {f["label"]: f for f in sep["files"]}
    broken = rows.get("calibration:python-lesson")
    check("artifact: the calibration row exists", broken is not None, str(sorted(rows)))
    if broken is None:
        return 1
    clean_rows = {k: v for k, v in rows.items() if k.startswith("doc:")}
    check("artifact: the four clean documents exist", len(clean_rows) == 4, str(sorted(clean_rows)))

    # the cross-artifact identity: one sha256 per file, published by both artifacts
    published = next((f["sha256"] for f in cal["files"] if f["name"] == PYTHON_LESSON), None)
    check("cross-artifact: calibration.json and the separation artifact name one file",
          published == broken["sha256"], f"{published} != {broken['sha256']}")

    broken_rates = [v["rate_per_1000"] for v in broken["readers"].values() if v["lam_alef"]]
    broken_min = min(broken_rates)
    check("artifact: the broken side has a measured density", bool(broken_rates), str(broken_rates))
    clean_max = max(v["rate_per_1000"] for row in clean_rows.values() for v in row["readers"].values()
                    if v["rate_per_1000"] is not None)

    value = th["values"]["lam_alef_rate_per_1000"]["value"]
    derived = round(math.sqrt(clean_max * broken_min), 1)
    check("separation: the shipped value is the geometric midpoint of the measured bounds",
          abs(derived - value) < 0.05, f"derived {derived} vs shipped {value} (clean {clean_max}, broken {broken_min})")
    check("separation: the clean maximum is below the value", clean_max < value, f"{clean_max} !< {value}")
    check("separation: the broken minimum is above the value", broken_min > value, f"{broken_min} !> {value}")

    # the rate needs a floor: both measured populations must sit inside the judged range
    min_runs = th["values"]["lam_alef_min_runs"]["value"]
    all_runs = [v["runs"] for row in sep["files"] for v in row["readers"].values()]
    check("floor: every measured reading is inside the judged range",
          min(all_runs) >= min_runs, f"min runs {min(all_runs)} < floor {min_runs}")

    print(f"\nLAM-ALEF SEPARATION PASSED — {passed} check(s); value {value} = sqrt({clean_max} x {broken_min})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
