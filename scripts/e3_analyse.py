#!/usr/bin/env python3
"""E3 analysis — the preregistration's rule applied to four measured runs, with no hand-typed number.

Usage:  python3 scripts/e3_analyse.py /tmp/e3           # dir holding <engine>-r1 / <engine>-r2

Every figure the E3 report prints is computed here from the runs' own `results.json`, and the rule is applied
literally. Nothing is averaged into a score: P is a count of cases, S1 is a mean of per-case readings, S3 is a
count of DISTINCT failing rules, S4 is an identity check between two independent runs.
"""
import json
import os
import statistics
import sys

ENGINES = [("chrome", "chrome+pp"), ("chrome-raw", "chrome-raw"), ("typst", "typst"), ("weasyprint", "weasyprint")]
TIER1 = ("pdfium", "pdfkit")


def load(root: str, engine: str, run: int) -> dict | None:
    path = os.path.join(root, f"{engine}-r{run}", "results.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def rule_ids(reason: str) -> set[str]:
    """`4 failing rule(s): 6.6.2.3.1-1, 6.2.4.3-2` -> {'6.6.2.3.1-1', '6.2.4.3-2'}"""
    out = set()
    for chunk in reason.split(":", 1)[-1].split(","):
        token = chunk.strip()
        if token and token[0].isdigit():
            out.add(token)
    return out


def analyse(root: str) -> int:
    rows = {}
    for engine, label in ENGINES:
        r1, r2 = load(root, engine, 1), load(root, engine, 2)
        if r1 is None:
            print(f"MISSING {engine}-r1 — not measured")
            return 1
        cases = r1["cases"]
        n = len(cases)
        row = {"version": r1["engine_version"], "cases": n}
        # P — the primary metric: cases at exact 1 in pdfium
        row["P"] = sum(1 for c in cases if c["per_reader"]["pdfium"]["metrics"]["exact"] == 1.0)
        row["P_frac"] = row["P"] / n
        # S1 — pdfkit exact, mean
        row["S1"] = statistics.mean(c["per_reader"]["pdfkit"]["metrics"]["exact"] for c in cases)
        # S2 — the worst reader per case (min order), averaged, and the corpus minimum
        worst = [min(c["per_reader"][r]["metrics"]["order"] for r in c["per_reader"]) for c in cases]
        row["S2_mean_worst"] = statistics.mean(worst)
        row["S2_min"] = min(worst)
        # H2 — .notdef, counted from the file itself; U+20C1's own case is exempt by the prereg
        notdef = [(c["id"], c["file"]["notdef"]) for c in cases if c["file"]["notdef"] > 0]
        row["notdef_cases"] = [c for c in notdef if c != "mon-riyal-sign"]
        # H3/H4 — veraPDF and the structural checks, as the gate reports them
        def statuses(cid):
            return {x["id"]: x["status"] for x in case_checks[cid]}
        case_checks = {c["id"]: c.get("checks", []) for c in cases}
        row["H3_a3b_pass"] = sum(1 for c in cases for x in c.get("checks", [])
                                 if x["id"] == "verapdf-pdfa3b" and x["status"] == "pass")
        row["H4_ua1_pass"] = sum(1 for c in cases for x in c.get("checks", [])
                                 if x["id"] == "verapdf-ua1" and x["status"] == "pass")
        row["H4_heading_pass"] = sum(1 for c in cases for x in c.get("checks", [])
                                     if x["id"] == "headings" and x["status"] == "pass")
        row["H4_na"] = sorted({x["id"] for c in cases for x in c.get("checks", []) if x["status"] == "na"})
        # S3 — distinct failing rules across the corpus, both flavours
        failed = set()
        for c in cases:
            for x in c.get("checks", []):
                if x["id"].startswith("verapdf-") and x["status"] == "fail":
                    failed |= rule_ids(x["reason"])
        row["S3_rules"] = sorted(failed)
        # S5 — build time: median of the per-case medians
        row["S5_median_s"] = statistics.median(c["median_seconds"] for c in cases)
        # S4 — determinism r1 vs r2 (file bytes and the text layer)
        if r2 is None:
            row["S4"] = "not measured (no second run)"
        else:
            # The rule's wording is «طبقة نص متطابقة» — the TEXT LAYER, not the bytes: an engine that stamps a
            # creation date or a /ID is still deterministic in what it prints. Both counts are reported.
            text_same = sum(1 for a, b in zip(cases, r2["cases"]) if a["text_sha256"] == b["text_sha256"])
            byte_same = sum(1 for a, b in zip(cases, r2["cases"]) if a["sha256"] == b["sha256"])
            row["S4"] = f"text layer {text_same}/{n} · bytes {byte_same}/{n}"
            row["S4_text"] = text_same
        # provenance: sha256 and /Producer per file, printed before any comparison
        row["producers"] = sorted({c.get("producer_pdf") or (c["producer"] or {}).get("engine", "") for c in cases})
        row["sha_unique"] = len({c["sha256"] for c in cases})
        rows[label] = row

    # ---- the rule, applied literally ---------------------------------------------------------------
    base = rows["chrome+pp"]
    print(f"{'engine':12s} {'version':22s} {'P (pdfium exact)':>17s} {'S1':>6s} {'S2 mean':>8s} {'S3 rules':>9s} "
          f"{'S5 s':>7s} {'A-3b':>6s} {'UA-1':>6s} {'headings':>9s}")
    for label in ("chrome+pp", "chrome-raw", "typst", "weasyprint"):
        r = rows[label]
        print(f"{label:12s} {r['version']:22s} {r['P']:>3d}/{r['cases']:<2d} ({r['P_frac']:.3f}) {r['S1']:6.3f} "
              f"{r['S2_mean_worst']:8.3f} {len(r['S3_rules']):9d} {r['S5_median_s']:7.3f} "
              f"{r['H3_a3b_pass']:>2d}/60 {r['H4_ua1_pass']:>2d}/60 {r['H4_heading_pass']:>2d}/60")
    print()
    for label in ("chrome+pp", "chrome-raw", "typst", "weasyprint"):
        r = rows[label]
        print(f"{label}: notdef cases {r['notdef_cases'] or 'none'} · na checks {r['H4_na'] or 'none'} · "
              f"determinism {r['S4']}")
        print(f"   distinct files {r['sha_unique']}/{r['cases']} · producers {r['producers']}")
        if r["S3_rules"]:
            print(f"   failing rules: {', '.join(r['S3_rules'])}")
    print()
    for label in ("typst", "weasyprint"):
        r = rows[label]
        d = r["P_frac"] - base["P_frac"]
        eligible = r["P_frac"] >= base["P_frac"] + 0.05
        tie = abs(d) < 0.05
        print(f"{label}: dP = {d:+.3f} → transition-eligible: {eligible} · tie: {tie}")
    return 0


if __name__ == "__main__":
    sys.exit(analyse(sys.argv[1] if len(sys.argv) > 1 else "/tmp/e3"))
