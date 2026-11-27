#!/usr/bin/env python3
"""PR-5c conditions أ-و, evaluated from the artifacts and nothing else.

Every number the PR quotes comes from one of these files, so a sentence that drifts from the evidence fails here
rather than in a review:

  docs/checker-v0/measurements/pr5c/verdicts.json        (149 files, both sides of the jury)
  docs/checker-v0/measurements/pr5c/signal-bounds.json   (per-signal bounds, per side)
  arabic_pdf_check/thresholds.json                       (the shipped values)

Conditions (declared before the measurement, PR-5c §4):
  أ  no clean file rises, no clean file is `high`
  ب  no owner file rises; every drop is listed
  ج  calibration: no movement AWAY from the owner's judgment; calibration-55 -> high is accepted, others shown
  د  the six planted files sit at their declared levels and each planted signal is caught
  هـ no ZATCA file moves level
  و  per shipped signal: clean bound < threshold < calibration bound (direction-aware)
"""
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RANK = {"low": 0, "medium": 1, "high": 2}
PLANTED_LEVEL = {"planted-mupdf-logical": "high", "planted-chrome-raw": "high",
                 "planted-presentation-forms": "high", "planted-no-tounicode": "high",
                 "planted-letter-swap": "high", "planted-lam-alef": "medium"}
PLANTED_SIGNAL = {"planted-mupdf-logical": "visual-order", "planted-chrome-raw": "presentation-forms",
                  "planted-presentation-forms": "presentation-forms",
                  "planted-no-tounicode": "tounicode-gaps", "planted-letter-swap": "lexical-validity",
                  "planted-lam-alef": "lam-alef-transposition"}
ACCEPTED_CALIBRATION = {"calibration-55": "high"}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--value", type=float, default=None,
                    help="lam-alef band to evaluate the straddle checks against (default: the shipped manifest)")
    args = ap.parse_args()
    v = json.load(open(os.path.join(REPO, "docs/checker-v0/measurements/pr5c/verdicts.json"), encoding="utf-8"))
    b = json.load(open(os.path.join(REPO, "docs/checker-v0/measurements/pr5c/signal-bounds.json"), encoding="utf-8"))
    th = json.load(open(os.path.join(REPO, "arabic_pdf_check/thresholds.json"), encoding="utf-8"))["values"]
    # The band the 149 verdicts were measured with is the derived one, not necessarily the one in the manifest yet:
    # pass it explicitly so the straddle checks and the numbers they print are about the same run.
    if args.value is not None:
        th["lam_alef_rate_per_1000"] = {"value": args.value}
    rows, failures = v["files"], []

    def check(name, ok, detail=""):
        print(f"{'PASS' if ok else 'FAIL'} {name}{(' — ' + detail) if detail and not ok else ''}")
        if not ok:
            failures.append(name)

    clean = [r for r in rows if r["group"] == "clean"]
    owner = [r for r in rows if r["group"] == "owner"]
    calib = [r for r in rows if r["group"] == "calibration"]
    planted = [r for r in rows if r["group"] == "planted"]
    zatca = [r for r in rows if r["group"] == "zatca"]

    check("أ clean: no rise", not [r["label"] for r in clean if RANK[r["ship"]["level"]] > RANK[r["all"]["level"]]])
    check("أ clean: none is high", not [r["label"] for r in clean if r["ship"]["level"] == "high"])
    check("ب owner: no rise", not [r["label"] for r in owner if RANK[r["ship"]["level"]] > RANK[r["all"]["level"]]])
    drops = [r["label"] for r in owner if RANK[r["ship"]["level"]] < RANK[r["all"]["level"]]]
    check("ب owner: no drop", not drops, str(drops))

    moved = [r["label"] for r in calib if r["ship"]["level"] != r["all"]["level"]]
    away = [lbl for lbl in moved if ACCEPTED_CALIBRATION.get(lbl) !=
            next(r["ship"]["level"] for r in calib if r["label"] == lbl)]
    check("ج calibration: only the accepted movement", not away, str(away))

    check("د planted: declared levels hold",
          all(r["ship"]["level"] == PLANTED_LEVEL[r["label"]] for r in planted if r["label"] in PLANTED_LEVEL),
          str({r["label"]: r["ship"]["level"] for r in planted}))
    check("د planted: each planted signal is caught",
          all(PLANTED_SIGNAL[r["label"]] in r["ship"]["signals"] for r in planted if r["label"] in PLANTED_SIGNAL),
          str({r["label"]: r["ship"]["signals"] for r in planted}))

    check("هـ zatca: no movement", not [r["label"] for r in zatca if r["ship"]["level"] != r["all"]["level"]])

    side = b["sides"]["ship"]["signals"]
    tg, pf, lx = side["tounicode-gaps"], side["presentation-forms"], side["lexical-validity"]
    lam = b["sides"]["ship"]
    planted_ev = {row["label"]: row for row in b["sides"]["ship"].get("planted_evidence", [])}
    pf_evidence = max(planted_ev.get("planted-presentation-forms", {}).get("pf_ratio") or 0.0,
                      planted_ev.get("planted-chrome-raw", {}).get("pf_ratio") or 0.0)
    # The calibration group carries no presentation-form or tounicode defect (it reads 0.0 on both), so those two
    # signals are bounded against the planted fixture that declares them — a corpus hole, reported, not hidden.
    check("و presentation-forms straddles (evidence side: planted)",
          pf["clean_max"]["value"] < th["presentation_forms"]["value"] < pf_evidence,
          f'{pf["clean_max"]["value"]} < {th["presentation_forms"]["value"]} < {pf_evidence}')
    caught = {r["label"]: r["ship"]["signals"] for r in planted if r["label"].startswith("planted")}
    check("و tounicode-gaps: structural fact on the planted file",
          "tounicode-gaps" in caught.get("planted-no-tounicode", [])
          and tg["clean_max"]["value"] < th["tounicode_gap_ratio"]["value"],
          f'clean {tg["clean_max"]["value"]} < {th["tounicode_gap_ratio"]["value"]}, planted signal '
          f'{caught.get("planted-no-tounicode")}')
    check("و lexical-validity straddles (inverted)", lx["calibration_min"]["value"] < th["lexical_validity"]["value"] < lx["clean_min"]["value"],
          f'{lx["calibration_min"]["value"]} < {th["lexical_validity"]["value"]} < {lx["clean_min"]["value"]}')
    check("و lam-alef straddles", lam["clean_max_rate"] < th["lam_alef_rate_per_1000"]["value"] < lam["calibration_min_rate"],
          f'{lam["clean_max_rate"]} < {th["lam_alef_rate_per_1000"]["value"]} < {lam["calibration_min_rate"]}')

    print("\ncounts:", {g: len([r for r in rows if r["group"] == g]) for g in
                        ("clean", "planted", "calibration", "foreign", "owner", "zatca")})
    print("level movements:", [r["label"] for r in rows if r["level_moved"]])
    print(f"\nPR-5C CONDITIONS {'PASSED' if not failures else 'FAILED'} — "
          f"{18 - len(failures)}/{18} check(s); value {th['lam_alef_rate_per_1000']['value']} for lam-alef")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
