#!/usr/bin/env python3
"""The comparison arithmetic is a contract: clean minimum, broken maximum, and separation are
computed from the same population; an unjudged reading is not a zero. No PDFs, no readers."""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import lexicon_compare as C  # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def row(set_, label, ratios, runs=100, name=None):
    def scores(key):
        return {f"r{i}": {"runs": runs, "known": int(round(ratios[key][i] * runs)), "ratio": ratios[key][i]}
                for i in range(len(ratios[key]))}
    out = {"set": set_, "label": label, "scores": {"current": scores("current"), "wiki": scores("wiki")}}
    if name:
        out["name"] = name
    return out


records = [
    row("clean", "a", {"current": [0.80, 0.90], "wiki": [0.85, 0.95]}),
    row("clean", "b", {"current": [0.90, 0.70], "wiki": [0.95, 0.80]}),
    row("calibration", "cal-1", {"current": [0.40, 0.50], "wiki": [0.35, 0.45]}, name="cal-1"),
    row("known-bad", "known", {"current": [0.20, 0.30], "wiki": [0.25, 0.35]}),
    row("clean", "short", {"current": [0.00, 0.00], "wiki": [0.00, 0.00]}, runs=5),  # not judged
]
s = C.summarize(records, "current", min_runs=20)
check("clean-min-by-reader", s["clean_min_by_reader"] == {"r0": 0.8, "r1": 0.7}, s["clean_min_by_reader"])
check("clean-median-by-reader",
      {k: round(v, 4) for k, v in s["clean_median_by_reader"].items()} == {"r0": 0.85, "r1": 0.8},
      s["clean_median_by_reader"])
check("clean-file-min", s["clean_file_min"] == 0.7, s["clean_file_min"])
check("broken-max", s["broken_max"] == 0.5, s["broken_max"])
check("separation-all", s["separation_all"] == 0.2, s["separation_all"])
check("separation-lexical-only", s["separation_lexical_only"] == 0.4, s["separation_lexical_only"])
check("separation-by-reader", s["separation_by_reader"] == {"r0": 0.4, "r1": 0.2}, s["separation_by_reader"])
check("short-not-judged", s["clean_judged"] == 2, s["clean_judged"])
check("calibration-judged", s["calibration_judged"] == 1, s["calibration_judged"])
check("known-bad-label", "known-bad" in s["calibration"], s["calibration"])

w = C.summarize(records, "wiki", min_runs=20)
check("wiki-clean-min", w["clean_file_min"] == 0.8, w["clean_file_min"])
check("wiki-broken-max", w["broken_max"] == 0.45, w["broken_max"])
check("wiki-separation", w["separation_all"] == 0.35, w["separation_all"])
check("wiki-separation-lexical-only", w["separation_lexical_only"] == 0.45, w["separation_lexical_only"])

print()
if fails:
    print(f"LEXICON COMPARE FAILED — {fails}")
    raise SystemExit(1)
print("LEXICON COMPARE PASSED — the separation uses judged readings, not missing ones")
