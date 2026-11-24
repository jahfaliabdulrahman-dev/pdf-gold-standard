#!/usr/bin/env python3
"""PR-2: re-measure the separation of each signal on the SAME clean / planted / calibration files.

The shipped thresholds each rest on a separation claim. This script re-derives the claim from raw
measurements, signal by signal, and writes the table used by the PR-2 evidence:

  · clean       — the four real documents + the 66 corpus cases (70 files), five readers;
  · planted     — the five fixtures whose named defect each signal must catch;
  · calibration — the owner's three named files, with their declared defect types.

No owner text is stored. The three calibration files are named because the assignment names them;
the other 52 owner files never enter this script.

    python3 scripts/signal_separation.py --clean-dir <66-case-pdf-dir> --out docs/checker-v0/measurements/pr2

The clean directory is required: rendering 66 cases again is not the point of this measurement, and the
rendered set is the same case ids. Use `scripts/checker_measure.py` to render it.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import subprocess
import sys
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import checker_fixtures                                                   # noqa: E402
import checker_measure                                                    # noqa: E402

CALIBRATION = ["نظام الشركات 1439 سعد الخنفري.pdf", "٣ - درس - البايثون.pdf", "7  - درس - مهارات التواصل.pdf"]
SEPARATION = 0.20
SIGNALS = ("presentation-forms", "visual-order", "tounicode-gaps", "lexical-validity",
           "numerals-mixed", "lam-alef-transposition", "no-text-layer")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stats(values: list[float]) -> dict:
    values = [v for v in values if v is not None]
    return {"n": len(values), "min": min(values) if values else None,
            "median": round(st.median(values), 4) if values else None,
            "max": max(values) if values else None}


def _git() -> dict:
    head = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--untracked-files=no"],
                                capture_output=True, text=True, check=True).stdout.strip())
    return {"head": head, "dirty": dirty}


def _lam_readers(raw: dict) -> dict:
    return {n: v["lam_alef"] for n, v in raw["lexical_by_reader"].items() if v.get("lam_alef")}


def _cal_defect_type(name: str, calibration: dict) -> str:
    for row in calibration["files"]:
        if row["name"] == name:
            return row["defect_type"]
    raise SystemExit(f"REFUSED — {name} has no defect_type in calibration.json")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clean-dir", required=True, help="directory containing the 66 rendered corpus case PDFs")
    ap.add_argument("--planted-dir", default=None, help="directory containing the 5 planted PDFs (build if absent)")
    ap.add_argument("--owner-dir", default=os.path.expanduser(os.environ.get("OWNER_CORPUS_DIR", "")))
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "checker-v0", "measurements", "pr2"))
    a = ap.parse_args()
    if not a.owner_dir or not os.path.isdir(a.owner_dir):
        ap.error("the owner corpus is private: set OWNER_CORPUS_DIR or pass --owner-dir")
    os.makedirs(a.out, exist_ok=True)

    base = json.load(open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"), encoding="utf-8"))
    calibration = json.load(open(os.path.join(REPO, "docs", "checker-v0", "measurements", "calibration.json"),
                                 encoding="utf-8"))
    clean = checker_measure.clean_files(a.clean_dir, reuse=True)
    if len(clean) != 70:
        raise SystemExit(f"REFUSED — clean set is {len(clean)}, expected 70")
    if a.planted_dir:
        planted = {name: os.path.join(a.planted_dir, f"{name}.pdf") for name in checker_fixtures.PLANTED}
        missing = [p for p in planted.values() if not os.path.exists(p)]
        if missing:
            raise SystemExit(f"REFUSED — planted files missing: {missing}")
    else:
        planted = checker_fixtures.build_all()["planted"]
    cal_paths = [os.path.join(a.owner_dir, name) for name in CALIBRATION]
    for p in cal_paths:
        if not os.path.exists(p):
            raise SystemExit(f"REFUSED — calibration file not found: {p}")

    clean_rows = []
    for label, path in clean:
        row = checker_measure.raw(path)
        row["label"] = label
        clean_rows.append(row)
    planted_rows = {name: checker_measure.raw(path) for name, path in planted.items()}
    cal_rows = {}
    for path in cal_paths:
        name = os.path.basename(path)
        cal_rows[name] = checker_measure.raw(path)

    signal_table = {}

    def add(signal: str, direction: str, clean_values: list[float], broken_values: list[float],
            threshold, source: str, *, required: float = SEPARATION, note: str = ""):
        clean_stats = _stats(clean_values)
        broken_stats = _stats(broken_values)
        if direction == "higher-is-worse":
            separation = (None if clean_stats["max"] is None or broken_stats["min"] is None
                          else round(broken_stats["min"] - clean_stats["max"], 4))
        else:
            separation = (None if clean_stats["min"] is None or broken_stats["max"] is None
                          else round(clean_stats["min"] - broken_stats["max"], 4))
        signal_table[signal] = {"direction": direction, "clean": clean_stats, "broken": broken_stats,
                                "threshold": threshold, "separation": separation,
                                "required_separation": required,
                                "passes": None if separation is None else separation >= required,
                                "source": source, "note": note}

    # presentation forms — file text layer, higher is worse
    add("presentation-forms", "higher-is-worse",
        [r["pf_ratio"] for r in clean_rows],
        [planted_rows["planted-presentation-forms"]["pf_ratio"]],
        base["values"]["presentation_forms"]["value"], "planted-presentation-forms")

    # visual order — the share of readers that read reversed, structural majority
    add("visual-order", "higher-is-worse",
        [r["visual_share"] for r in clean_rows],
        [planted_rows["planted-mupdf-logical"]["visual_share"]],
        round(3 / 5, 2),
        "planted-mupdf-logical",
        note="the threshold is the structural majority (3 of 5 readers), not a measured number")

    # ToUnicode — the planted file has no map at all; its missing-code count is the direct measurement.
    # `gap_ratio_max` only counts fonts that HAVE a map, so it is zero on this fixture by construction;
    # the signal's real fact is the count of drawn codes without a Unicode value.
    clean_missing = [r["missing_unicode"] for r in clean_rows]
    broken_missing = planted_rows["planted-no-tounicode"]["missing_unicode"]
    signal_table["tounicode-gaps"] = {
        "direction": "higher-is-worse",
        "clean": _stats(clean_missing),
        "broken": {"n": 1, "min": broken_missing, "median": broken_missing, "max": broken_missing},
        "threshold": f"{base['values']['tounicode_gap_ratio']['value']} gap ratio (fonts that HAVE a map)",
        "separation": broken_missing - max(clean_missing),
        "required_separation": 1,
        "passes": broken_missing > max(clean_missing),
        "source": "planted-no-tounicode",
        "note": "measured as a count of drawn codes without a Unicode value; the ratio in the manifest "
                "is the gate for fonts that carry a map, not for a font with no map at all"}

    # lexical — higher is better
    add("lexical-validity", "higher-is-better",
        [r["lexical_min"] for r in clean_rows if r["lexical_min"] is not None],
        [planted_rows["planted-letter-swap"]["lexical_max"]],
        base["values"]["lexical_validity"]["value"], "planted-letter-swap")

    # numerals — a medium signal, not a 0.20 separation; the calibration file is the measured positive
    mixed_clean = [r["mixed_numbers"] for r in clean_rows]
    mixed_cal = [r["mixed_numbers"] for r in cal_rows.values()]
    signal_table["numerals-mixed"] = {
        "direction": "higher-is-worse", "clean": _stats(mixed_clean),
        "broken": {"n": 1, "min": max(mixed_cal), "median": max(mixed_cal), "max": max(mixed_cal)},
        "threshold": "medium at > 0; no numeric floor", "separation": None, "required_separation": None,
        "passes": None, "source": "owner calibration",
        "note": "a count of numbers mixing digit systems; the owner's `نظام الشركات` is the positive"}

    # lam-alef — measured, but not shipped as a file-level signal; the Python item's correction
    lam_clean = [r["lam_alef_max"] for r in clean_rows]
    lam_cal = {name: _lam_readers(row) for name, row in cal_rows.items()}
    signal_table["lam-alef-transposition"] = {
        "direction": "higher-is-worse", "clean": _stats(lam_clean),
        "broken": {"n": len(lam_cal), "min": min(max(v.values(), default=0) for v in lam_cal.values()),
                   "median": st.median([max(v.values(), default=0) for v in lam_cal.values()]),
                   "max": max(max(v.values(), default=0) for v in lam_cal.values())},
        "threshold": "not shipped as a file-level signal", "separation": None,
        "required_separation": None, "passes": None, "source": "arafix detector inside lexical.validity",
        "note": "reader counts are recorded; the clean maximum is the measured floor; the Python file "
                "has 21 in three readers and 0 in PDFKit, PDFMiner reads reversed. A candidate signal, "
                "not a threshold change.",
        "readers": lam_cal}

    # no text layer — deterministic; clean min Arabic vs planted, no threshold
    signal_table["no-text-layer"] = {
        "direction": "presence", "clean": _stats([r["arabic"] + r["forms"] for r in clean_rows]),
        "broken": {"n": 1, "min": planted_rows["planted-no-tounicode"]["arabic"],
                   "median": planted_rows["planted-no-tounicode"]["arabic"],
                   "max": planted_rows["planted-no-tounicode"]["arabic"]},
        "threshold": f"< {base['values']['min_arabic_chars']['value']} Arabic characters", "separation": None,
        "required_separation": None, "passes": None, "source": "planted-no-tounicode / min_arabic_chars",
        "note": "not a distance metric; the signal is a presence rule"}

    payload = {"schema_version": "signal-separation/1", "generated_at": _now(), **_git(),
               "population": {"clean": len(clean_rows), "planted": len(planted_rows),
                              "calibration": len(cal_rows), "readers": clean_rows[0]["readers"]},
               "thresholds_sha256": __import__("hashlib").sha256(
                   open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"), "rb").read()).hexdigest(),
               "signals": signal_table,
               "calibration": {name: {"defect_type": _cal_defect_type(name, calibration),
                                      "defect_types": next(row["defect_types"] for row in calibration["files"]
                                                           if row["name"] == name),
                                      "lam_alef": lam_cal[name],
                                      "lexical_by_reader": row["lexical_by_reader"]}
                               for name, row in cal_rows.items()},
               "note": "The clean population is the same 70 files; no owner text or ordinary owner name "
                       "is stored. The three calibration names are the assignment's explicit exception."}
    path = os.path.join(a.out, "signal-separation.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    print(f"clean={len(clean_rows)} planted={len(planted_rows)} calibration={len(cal_rows)}")
    for sid in SIGNALS:
        row = signal_table[sid]
        print(f"{sid:26} clean={row['clean']} broken={row['broken']} sep={row['separation']} "
              f"passes={row['passes']}")
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
