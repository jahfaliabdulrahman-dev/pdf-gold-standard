#!/usr/bin/env python3
"""PR-5b: does the shipped Linux install (pdfium + poppler + pdfminer + pdfjs) reach the same FILE verdicts as
the five shipped readers, on every group we have?

Two sides, one program:

- `all`  — the five readers shipped today (on this host: pdfium, pdfkit, mupdf, poppler, pdfminer).
- `ship` — the four that the bare Linux wheel would have: pdfium, poppler, pdfminer, **pdfjs**.

Phases (each writes a JSON artifact outside the repository; the document, not this comment, carries the result):

  verdicts    per file, both sides: `risk.file.level`, signal ids, voter counts. Owner-corpus files are
              identified by `owner-NN` only — **no owner name, no owner text**, only levels and signal ids.
              Excerpts (a short sample of what each reader returned) are collected ONLY for non-owner groups.
  separation  per shipped signal: max over the clean group vs min over the broken side (planted where it is the
              negative case, calibration for lam-alef), computed for both sides. A signal whose separation
              shrinks is a refusal, not a note.
  timing      `check` on one file, ten runs per side, median reported (the owner asked for the number, so the
              number is produced here and sliced into the document).

The candidate is measured through the same boundary as everything else: `blind.check` and `conformance.readers.
available` are narrowed for the side, but every reader still runs in its own process through `isolate`.
"""
import argparse
import glob
import hashlib
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import checker_fixtures                                                      # noqa: E402
import checker_measure as cm                                                 # noqa: E402
from arabic_pdf_check import blind                                           # noqa: E402
from conformance import readers as readers_mod                                # noqa: E402

SIDES = {
    "all": ("pdfium", "pdfkit", "mupdf", "poppler", "pdfminer"),
    "ship": ("pdfium", "poppler", "pdfminer", "pdfjs"),
}
OWNER_DIR = os.path.expanduser(os.environ.get("OWNER_CORPUS_DIR", ""))
ZATCA_GLOB = os.path.expanduser("~/.cache/zatca-sdk/**/Data/Samples/PDF-A3/*.pdf")


def side_patch(names: tuple[str, ...]):
    """Narrow the two `available()` entry points to one side. Returns a restore callable."""
    ok_all, missing = readers_mod.available()
    ok = {n: m for n, m in ok_all.items() if n in names}
    for n in names:
        if n not in ok:
            mod = readers_mod.load(n)
            mod.version()
            ok[n] = mod
    dropped = {n: f"NotInSide: {why}" for n, why in missing.items() if n not in names}
    dropped.update({n: "NotInSide" for n in ok_all if n not in names})
    real_available = readers_mod.available
    blind_available = blind.available
    readers_mod.available = lambda: (ok, dropped)
    blind.available = lambda: (ok, dropped)
    # `checker_measure` did `from conformance.readers import available` at import time, so patching the module
    # attribute alone would leave the separation phase measuring the FULL matrix while labelling it «ship» — a
    # number that claims a reader set it did not use. Patch the bound name and the denominator too.
    cm.available = lambda: (ok, dropped)
    cm.MATRIX = names

    real_cm_available, real_cm_matrix = cm.available, cm.MATRIX

    def restore():
        readers_mod.available = real_available
        blind.available = blind_available
        cm.available = real_cm_available
        cm.MATRIX = real_cm_matrix
    return restore


def thresholds() -> dict:
    with open(cm.THRESHOLDS, encoding="utf-8") as fh:
        return json.load(fh)


def verdict(path: str, th: dict) -> dict:
    rep = blind.check(path, th)
    file_claim = rep["risk"]["file"]
    return {
        "level": file_claim["level"],
        "withheld": file_claim.get("withheld"),
        "voters": file_claim.get("voters"),
        "signals": sorted(s["id"] for s in rep["signals"]),
        "signal_levels": {s["id"]: s["level"] for s in rep["signals"]},
        "readers": sorted(rep["readers"]),
        "failed": rep.get("failed_readers") or {},
    }


def groups(built: dict, foreign_dir: str | None) -> list[tuple[str, str, str]]:
    """(group, label, path). Owner files are `owner-NN`, in a stable order, mapped outside the repository."""
    out = []
    for label, path in cm.clean_files(os.environ.get("CASES_DIR", "/tmp/cases-a"), reuse=True)[0]:
        out.append(("clean", label, path))
    for name, path in built["planted"].items():
        out.append(("planted", name, path))
    if os.path.isdir(OWNER_DIR):
        files = sorted(glob.glob(os.path.join(OWNER_DIR, "*.pdf")), key=lambda p: os.path.basename(p))
        with open(os.path.join(REPO, "docs", "checker-v0", "measurements", "calibration.json"),
                  encoding="utf-8") as fh:
            cal_sha = {f["sha256"] for f in json.load(fh)["files"]}
        for i, path in enumerate(files, start=1):
            sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
            group = "calibration" if sha in cal_sha else "owner"
            out.append((group, f"owner-{i:02d}" if group == "owner" else f"calibration-{i:02d}", path))
    else:
        out.append(("owner", "MISSING", ""))
    if foreign_dir:
        for path in sorted(glob.glob(os.path.join(foreign_dir, "*.pdf"))):
            out.append(("foreign", os.path.basename(path), path))
    for path in sorted(glob.glob(ZATCA_GLOB, recursive=True)):
        out.append(("zatca", os.path.basename(path), path))
    return out


EXCERPT_GROUPS = {"clean", "planted", "foreign", "zatca"}   # never the owner's text


def excerpt(name: str, path: str, want: int = 90) -> str:
    try:
        text = readers_mod.text_many(name, [path])[0] or ""
    except Exception as exc:                              # noqa: BLE001 — a failed reader is data too
        return f"<{type(exc).__name__}>"
    return " ".join(text.split())[:want]


def phase_verdicts(args, built, foreign_dir) -> int:
    th = thresholds()
    rows, changed = [], []
    # Append-only progress: a long run that is interrupted must not lose the files it already measured.
    partial = args.out + "l"                            # `verdicts.jsonl`
    done = set()
    if os.path.exists(partial):
        with open(partial, encoding="utf-8") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["label"])
                except Exception:                        # noqa: BLE001 — a torn last line is not progress
                    pass
        print(f"resuming: {len(done)} file(s) already measured")
    for group, label, path in groups(built, foreign_dir):
        if not path:
            rows.append({"group": group, "label": label, "missing": True})
            continue
        if label in done:
            continue
        row: dict = {"group": group, "label": label}
        per_side = {}
        for side, names in SIDES.items():
            restore = side_patch(names)
            try:
                per_side[side] = verdict(path, th)
            finally:
                restore()
        row.update({"all": per_side["all"], "ship": per_side["ship"]})
        moved = per_side["all"]["level"] != per_side["ship"]["level"]
        added = sorted(set(per_side["ship"]["signals"]) - set(per_side["all"]["signals"]))
        dropped = sorted(set(per_side["all"]["signals"]) - set(per_side["ship"]["signals"]))
        row["level_moved"] = moved
        row["signals_added"] = added
        row["signals_dropped"] = dropped
        if group in EXCERPT_GROUPS and (moved or added or dropped):
            row["excerpts"] = {}
            for side, names in SIDES.items():
                row["excerpts"][side] = {n: excerpt(n, path) for n in names if n in per_side[side]["readers"]}
        rows.append(row)
        with open(partial, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        flag = "  MOVED" if moved else ("  +" + ",".join(added) if added else "")
        print(f"{group:12} {label:28} all={per_side['all']['level']!s:6} ship={per_side['ship']['level']!s:6}{flag}")
        if moved:
            changed.append(label)
    payload = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "sides": {k: list(v) for k, v in SIDES.items()},
               "files": rows,
               "level_moved": changed,
               "groups": sorted({r["group"] for r in rows})}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"\n{len(changed)} file(s) moved level of {len(rows)}")
    return 0


def _lam_rate(row: dict, floor: int) -> float | None:
    """The highest per-reader lam-alef density (per 1000 runs) in a raw() row — the side that must clear the
    threshold. `runs` is the denominator, so a quoted example (1/n) never masquerades as a rate."""
    rates = [v["lam_alef"] / v["runs"] * 1000.0 for v in (row.get("lexical_by_reader") or {}).values()
             if v["runs"] >= floor]
    return round(max(rates), 3) if rates else None


def phase_separation(args, built, foreign_dir) -> int:
    """Per signal: the clean maximum and the broken minimum, both sides, from the same `raw()` the manifest uses."""
    th = thresholds()
    values = th["values"]
    clean_paths = [(lbl, p) for lbl, p in cm.clean_files(os.environ.get("CASES_DIR", "/tmp/cases-a"),
                                                         reuse=True)[0]]
    planted = dict(built["planted"])
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sides": {}}
    for side, names in SIDES.items():
        restore = side_patch(names)
        try:
            c_rows = {lbl: cm.raw(p) for lbl, p in clean_paths}
            p_rows = {n: cm.raw(p) for n, p in planted.items()}
        finally:
            restore()
        lex_floor = values["lexical_min_runs"]["value"]
        lam_floor = values["lam_alef_min_runs"]["value"]

        def clean_max(key):                                # noqa: ANN001 — one metric, one maximum
            vals = [r[key] for r in c_rows.values() if r.get(key) is not None]
            return max(vals) if vals else None

        lex_clean = [v["ratio"] for r in c_rows.values() for v in (r["lexical_by_reader"] or {}).values()
                     if v["runs"] >= lex_floor]
        lam_clean = [v["lam_alef"] / v["runs"] * 1000.0 for r in c_rows.values()
                     for v in (r["lexical_by_reader"] or {}).values() if v["runs"] >= lam_floor]
        side_out = {
            "readers": list(names),
            "clean_max_presentation_forms": clean_max("pf_ratio"),
            "clean_max_tounicode_gap": clean_max("gap_ratio_max"),
            "clean_max_visual_share": max((len(r["visual_readers"]) / len(names) for r in c_rows.values()),
                                          default=None),
            "clean_min_lexical": min(lex_clean) if lex_clean else None,
            "clean_max_lam_alef_rate": max(lam_clean) if lam_clean else None,
            "clean_max_missing_unicode": clean_max("missing_unicode"),
            "planted": {n: {"visual_readers": r["visual_readers"],
                            "lexical_max": r["lexical_max"],
                            "pf_ratio": r["pf_ratio"],
                            "missing_unicode": r["missing_unicode"],
                            "lam_alef_max": r["lam_alef_max"]} for n, r in p_rows.items()},
        }
        swap = p_rows.get("planted-letter-swap", {}).get("lexical_max")
        lam_broken_rate = _lam_rate(p_rows.get("planted-lam-alef", {}), lam_floor)
        side_out["separation"] = {
            # Lower is better for these three: the broken side must sit above the clean maximum.
            "tounicode-gaps": {"clean_max": side_out["clean_max_tounicode_gap"],
                               "broken_min": p_rows.get("planted-no-tounicode", {}).get("missing_unicode")},
            "presentation-forms": {"clean_max": side_out["clean_max_presentation_forms"],
                                   "broken_min": p_rows.get("planted-presentation-forms", {}).get("pf_ratio")},
            "visual-order": {"clean_max": side_out["clean_max_visual_share"],
                             "broken_min": len(p_rows.get("planted-chrome-raw", {}).get("visual_readers", []))
                             / len(names)},
            # Higher is better for lexical; for lam-alef HIGHER IS WORSE (a density per 1000 runs) and the two
            # bounds must be the same UNIT: clean maximum RATE vs calibration minimum RATE. Mixing a count with
            # a rate is how «30 vs 0.88» read like a 29-point gap.
            "lexical-validity": {"clean_min": side_out["clean_min_lexical"], "broken_max": swap},
            "lam-alef-transposition": {"clean_max_rate": side_out["clean_max_lam_alef_rate"],
                                       "broken_min_rate": lam_broken_rate},
        }
        out["sides"][side] = side_out
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    for side in SIDES:
        print(f"\n== {side}: " + json.dumps(out["sides"][side]["separation"], ensure_ascii=False))
    return 0


def phase_lamalef(args, built, foreign_dir) -> int:
    """The two bounds the lam-alef threshold is derived from, per side, in rate per 1000 runs.

    clean maximum and calibration minimum are the SAME unit on purpose: the shipped formula is
    `sqrt(clean_max x calibration_min)`, so a count anywhere in it silently changes the threshold's meaning.
    """
    th = thresholds()
    floor = th["values"]["lam_alef_min_runs"]["value"]
    clean = cm.clean_files(os.environ.get("CASES_DIR", "/tmp/cases-a"), reuse=True)[0]
    cal = [(lbl, p) for grp, lbl, p in groups(built, foreign_dir) if grp == "calibration"]
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "min_runs": floor, "sides": {}}
    for side, names in SIDES.items():
        restore = side_patch(names)
        try:
            c_rows = [(lbl, cm.raw(p)) for lbl, p in clean]
            k_rows = [(lbl, cm.raw(p)) for lbl, p in cal]
            planted = cm.raw(built["planted"]["planted-lam-alef"])
        finally:
            restore()

        def worst(row):                                  # noqa: ANN001 — (rate, reader) of the highest density
            pairs = [(v["lam_alef"] / v["runs"] * 1000.0, n) for n, v in (row["lexical_by_reader"] or {}).items()
                     if v["runs"] >= floor]
            return max(pairs) if pairs else (None, None)

        clean_pairs = [(worst(r)[0], worst(r)[1], lbl) for lbl, r in c_rows]
        clean_pairs = [c for c in clean_pairs if c[0] is not None]
        cal_pairs = [(worst(r)[0], worst(r)[1], lbl) for lbl, r in k_rows]
        cal_pairs = [c for c in cal_pairs if c[0] is not None]
        c_max = max(clean_pairs) if clean_pairs else (None, None, None)
        c_min = min(cal_pairs) if cal_pairs else (None, None, None)
        out["sides"][side] = {
            "readers": list(names),
            "clean_max_rate": None if c_max[0] is None else round(c_max[0], 3),
            "clean_max_reader": c_max[1], "clean_max_label": c_max[2],
            "calibration_min_rate": None if c_min[0] is None else round(c_min[0], 3),
            "calibration_min_reader": c_min[1], "calibration_min_label": c_min[2],
            "planted_rate": _lam_rate(planted, floor),
            "calibration": [{"label": r[2], "rate": None if r[0] is None else round(r[0], 3), "reader": r[1]}
                            for r in cal_pairs],
        }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    for side, v in out["sides"].items():
        print(f"{side:5} clean_max={v['clean_max_rate']} ({v['clean_max_reader']} on {v['clean_max_label']}) "
              f"cal_min={v['calibration_min_rate']} ({v['calibration_min_reader']}) planted={v['planted_rate']}")
    return 0


def phase_timing(args, built, foreign_dir) -> int:
    th = thresholds()
    target = args.timing_file or os.path.join(REPO, "guide-v2-ar.pdf")
    if not os.path.exists(target):
        target = built["clean"]
    out = {"file": os.path.basename(target), "runs": args.runs, "sides": {}}
    for side, names in SIDES.items():
        times = []
        for _ in range(args.runs):
            restore = side_patch(names)
            try:
                t0 = time.perf_counter()
                blind.check(target, th)
                times.append(time.perf_counter() - t0)
            finally:
                restore()
        out["sides"][side] = {"median_s": round(statistics.median(times), 3),
                              "min_s": round(min(times), 3), "max_s": round(max(times), 3),
                              "runs_s": [round(t, 3) for t in times]}
        print(f"{side}: median {out['sides'][side]['median_s']}s over {args.runs} run(s)")
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("verdicts", "separation", "timing", "lamalef"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--timing-file", default=None)
    ap.add_argument("--foreign-dir", default=None,
                    help="the directory holding the LibreOffice-converted PDFs (built outside the repository)")
    args = ap.parse_args()
    if not args.foreign_dir:
        args.foreign_dir = os.environ.get("FOREIGN_DIR")
    built = checker_fixtures.build_all(tempfile.mkdtemp(prefix="pdfjs-measure-"))
    return {"verdicts": phase_verdicts, "separation": phase_separation, "timing": phase_timing,
            "lamalef": phase_lamalef}[args.phase](args, built, args.foreign_dir)


if __name__ == "__main__":
    raise SystemExit(main())
