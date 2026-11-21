#!/usr/bin/env python3
"""The thresholds in the package are the ones the measurement derived — and nothing else is shipped.

  · presentation forms: value == max(declared, clean maximum)
  · orientation majority: value == max(declared, clean maximum share)
  · the metric form of reader disagreement is REFUSED: its clean minimum is recorded in `observed.refused`,
    no threshold key exists for it, and the blind report only uses the deterministic page-empty form.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
THRESHOLDS = os.path.join(REPO, "arabic_pdf_check", "thresholds.json")
MEASUREMENTS = os.path.join(REPO, "docs", "checker-v0", "measurements", "thresholds.json")

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


th = json.load(open(THRESHOLDS, encoding="utf-8"))
observed = th.get("observed") or {}
check("measured-at", bool(th.get("measured_at")), str(th.get("measured_at")))
check("command-recorded", "checker_measure.py" in (th.get("command") or ""), str(th.get("command")))
check("clean-set-size", int(observed.get("clean_files", 0)) >= 70, str(observed.get("clean_files")))

pf = th["values"]["presentation_forms"]
check("presentation-forms-derived",
      abs(pf["value"] - round(max(pf["declared"], observed["clean_max_presentation_forms"]), 4)) < 1e-9,
      f"value {pf['value']} declared {pf['declared']} clean {observed.get('clean_max_presentation_forms')}")
maj = th["values"]["visual_order_majority"]
check("majority-derived",
      abs(maj["value"] - round(max(maj["declared"], observed["clean_max_visual_share"]), 4)) < 1e-9,
      f"value {maj['value']} declared {maj['declared']} clean {observed.get('clean_max_visual_share')}")
gap = th["values"]["tounicode_gap_ratio"]
check("gap-ratio-derived",
      abs(gap["value"] - round(max(gap["declared"], observed["clean_max_gap_ratio"]), 4)) < 1e-9,
      f"value {gap['value']} declared {gap['declared']} clean {observed.get('clean_max_gap_ratio')}")

check("no-disagreement-threshold", not any(k.startswith("disagreement") for k in th["values"]),
      str(sorted(th["values"])))
check("refusal-recorded", "reader-disagreement-metric" in (observed.get("refused") or {}),
      str(observed.get("refused")))
check("clean-min-pair-recorded", "clean_min_pair_f1" in observed, "")

measured = json.load(open(MEASUREMENTS, encoding="utf-8")) if os.path.exists(MEASUREMENTS) else None
check("committed-measurement-matches", measured is not None and
      measured["values"] == th["values"] and measured["observed"] == observed,
      "docs/checker-v0/measurements/thresholds.json is stale — re-run scripts/checker_measure.py")

print()
if fails:
    print(f"THRESHOLDS FAILED — {fails}")
    raise SystemExit(1)
print("THRESHOLDS PASSED — the shipped values are the measured ones")
