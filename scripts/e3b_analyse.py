#!/usr/bin/env python3
"""E3b — the six preregistered conditions, applied to the candidate as measured. No hand-typed verdict.

Usage:  python3 scripts/e3b_analyse.py /tmp/e3b [--incumbent /tmp/e3/chrome-r1/results.json]

The preregistration is `docs/engine-bakeoff/03-e3b-preregistration.md`; it was committed before the first build
of `weasyprint+pp`. This script only reads the runs. It prints the six values, compares each to the threshold
the preregistration fixed, and derives PASS/REJECT for the candidate. A missing file is `NOT MEASURED`, never a
pass and never a zero.
"""
import argparse
import json
import os
import statistics
import sys

THRESHOLDS = {
    "P": 35,           # cases at PDFium exact == 1.0
    "S1": 37,          # cases Preview reads exactly
    "clean": 27,       # structure-clean cases
    "cert": 18,        # certificate PASS cases
}


def load(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def exact_count(doc: dict, reader: str) -> int:
    return sum(1 for c in doc["cases"] if c["per_reader"][reader]["metrics"]["exact"] == 1.0)


def clean_count(doc: dict) -> int | None:
    per = doc.get("checks", {}).get("per_check")
    if not per:
        return None
    return sum(1 for c in doc["cases"]
               if all(x["status"] in ("pass", "na") for x in c.get("checks", [])))


def cert_pass(doc: dict, floors: dict) -> int:
    """The same rule `certificate.decide` applies, over a finished run (no floors known -> floors skipped)."""
    n = 0
    for case in doc["cases"]:
        failed = [x for x in case.get("checks", []) if x["status"] == "fail"]
        readers = {k: v["metrics"] for k, v in case["per_reader"].items()}
        if failed or "pdfium" not in readers or readers["pdfium"]["exact"] != 1.0:
            continue
        if "pdfkit" in readers and readers["pdfkit"]["exact"] != 1.0:
            continue
        n += 1
    return n


def failing_rules(doc: dict, flavour: str) -> set[str]:
    out = set()
    for case in doc["cases"]:
        for x in case.get("checks", []):
            if x["id"] == f"verapdf-{flavour}" and x["status"] == "fail":
                out |= {t.strip() for t in x["reason"].split(":", 1)[-1].split(",") if t.strip()[:1].isdigit()}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="/tmp/e3b")
    ap.add_argument("--incumbent", default="/tmp/e3/chrome-r1/results.json")
    args = ap.parse_args()

    cand_r1 = load(os.path.join(args.root, "weasyprint-pp-r1", "results.json"))
    cand_r2 = load(os.path.join(args.root, "weasyprint-pp-r2", "results.json"))
    if cand_r1 is None:
        print(f"NOT MEASURED — {args.root}/weasyprint-pp-r1/results.json does not exist")
        return 2
    n = len(cand_r1["cases"])
    floor_path = os.path.join(args.root, "refusal.json")
    refusal = load(floor_path)

    values = {
        "P": exact_count(cand_r1, "pdfium"),
        "S1": exact_count(cand_r1, "pdfkit"),
        "clean": clean_count(cand_r1),
        "cert": cert_pass(cand_r1, {}),
    }
    rules = {"ua1": failing_rules(cand_r1, "ua1"), "3b": failing_rules(cand_r1, "pdfa3b")}

    det = "NOT MEASURED (no second run)"
    det_ok = False
    if cand_r2 is not None:
        same = sum(1 for a, b in zip(cand_r1["cases"], cand_r2["cases"]) if a["text_sha256"] == b["text_sha256"])
        det = f"text layer {same}/{n}"
        det_ok = same == n

    inc = load(args.incumbent)
    print("candidate: weasyprint+pp · runs:", "r1 only" if cand_r2 is None else "r1 + r2")
    print(f"{'condition':22s} {'measured':>18s}  {'threshold':>10s}  verdict")
    rows = [
        ("1 P (pdfium exact)", f"{values['P']}/{n}", f">= {THRESHOLDS['P']}", values["P"] >= THRESHOLDS["P"]),
        ("2 S1 (preview exact)", f"{values['S1']}/{n}", f">= {THRESHOLDS['S1']}", values["S1"] >= THRESHOLDS["S1"]),
        ("3 structure clean", f"{values['clean']}/{n}", f">= {THRESHOLDS['clean']}",
         values["clean"] is not None and values["clean"] >= THRESHOLDS["clean"]),
        ("4 certificate PASS", f"{values['cert']}/{n}", f">= {THRESHOLDS['cert']}", values["cert"] >= THRESHOLDS["cert"]),
        ("5 veraPDF UA-1 rules", f"{len(rules['ua1'])}: {sorted(rules['ua1'])[:4]}", "== 0", not rules["ua1"]),
        ("5 veraPDF A-3b rules", f"{len(rules['3b'])}: {sorted(rules['3b'])[:4]}", "== 0", not rules["3b"]),
        ("6 determinism", det, "60/60", det_ok),
    ]
    for name, measured, threshold, ok in rows:
        print(f"{name:22s} {measured:>18s}  {threshold:>10s}  {'OK' if ok else 'MISS'}")
    decision = all(ok for *_rest, ok in rows)
    print()
    if refusal:
        print(f"REFUSAL RECORDED: {refusal.get('type')}: {refusal.get('message')}")
        print("→ the layer refused the file; per the preregistration this IS the result and the incumbent stays")
    else:
        print("→ DECISION:", "SWITCH to weasyprint+pp" if decision else "KEEP chrome+pp (at least one condition missed)")
    if inc:
        print(f"incumbent reference: P {exact_count(inc, 'pdfium')}/{len(inc['cases'])} · "
              f"S1 {exact_count(inc, 'pdfkit')}/{len(inc['cases'])} · clean {clean_count(inc)} · "
              f"cert {cert_pass(inc, {})} · rules ua1 {len(failing_rules(inc, 'ua1'))}")
    return 0 if decision else 1


if __name__ == "__main__":
    sys.exit(main())
