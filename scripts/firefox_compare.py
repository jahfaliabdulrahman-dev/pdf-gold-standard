#!/usr/bin/env python3
"""Firefox gate (PR-5c §2): does the text a person copies out of Firefox agree with what our pdf.js reader returns?

Three criteria, declared before the measurement and not re-interpreted afterwards:

  1. the ORDER agrees on every file — both reversed, or both logical;
  2. the lam-alef transposition appears in both or in neither;
  3. word agreement on the compared passage >= 0.90 (multiset F1, digits and order blind).

Input: one copied-text file per PDF (the owner pastes the selection from Firefox into a text file). The three
targets are the SDK invoice, the guide, and the owner's calibration file — for the last one NOTHING but the
numbers and the verdicts is written out: no excerpt, no name, no sha.

Usage:
  python3 scripts/firefox_compare.py --copies /tmp/ff/copies.json --out docs/checker-v0/measurements/pr5c/firefox-compare.json
    copies.json = {"firefox_version": "161.0", "files": [{"label": "...", "pdf": "<path>", "copy": "<path>",
                                                          "public": true|false}, ...]}
"""
import argparse
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

from conformance.checks import lexical, structure, visual_order      # noqa: E402
from conformance.readers import pdfjs                                # noqa: E402

THRESHOLD = 0.90


def direction(text: str) -> dict:
    """The same arAFix order check the checker uses; `visual` means the copy keeps the opposite order."""
    got = visual_order.inspect(text)
    return {"visual": bool(got["visual"]), "score": round(got["score"], 3) if got.get("score") is not None else None}


def lam_alef(text: str) -> int:
    return int(lexical.validity(text)["lam_alef"])


def f1(a: str, b: str) -> float:
    ca, cb = structure.words_multi(a), structure.words_multi(b)
    if not ca and not cb:
        return 1.0
    overlap = sum((ca & cb).values())
    if not overlap:
        return 0.0
    p, r = overlap / sum(ca.values()), overlap / sum(cb.values())
    return 2 * p * r / (p + r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--copies", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    spec = json.load(open(args.copies, encoding="utf-8"))
    out = {"generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
           "firefox_version": spec.get("firefox_version"), "criteria": {"word_agreement": THRESHOLD},
           "files": []}
    failures = []
    for entry in spec["files"]:
        label, public = entry["label"], bool(entry.get("public"))
        firefox_text = open(entry["copy"], encoding="utf-8", errors="replace").read()
        ours = pdfjs.text(entry["pdf"])
        row = {
            "label": label,
            "public": public,
            "firefox": {**direction(firefox_text), "lam_alef": lam_alef(firefox_text),
                        "chars": len(firefox_text), "runs": lexical.validity(firefox_text)["runs"]},
            "pdfjs": {**direction(ours), "lam_alef": lam_alef(ours),
                      "chars": len(ours), "runs": lexical.validity(ours)["runs"]},
            "word_agreement": round(f1(firefox_text, ours), 3),
        }
        row["order_agrees"] = row["firefox"]["visual"] == row["pdfjs"]["visual"]
        row["lam_alef_agrees"] = (row["firefox"]["lam_alef"] > 0) == (row["pdfjs"]["lam_alef"] > 0)
        row["words_agree"] = row["word_agreement"] >= THRESHOLD
        row["passes"] = row["order_agrees"] and row["lam_alef_agrees"] and row["words_agree"]
        if public:
            row["excerpt"] = {"firefox": " ".join(firefox_text.split())[:160],
                              "pdfjs": " ".join(ours.split())[:160]}
        if not row["passes"]:
            failures.append(label)
        out["files"].append(row)
        print(f"{label:28} order={row['order_agrees']} lam-alef={row['lam_alef_agrees']} "
              f"words={row['word_agreement']} -> {'PASS' if row['passes'] else 'FAIL'}")
    out["failures"] = failures
    out["verdict"] = "pass" if not failures else "fail"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"\nFIREFOX GATE {out['verdict'].upper()} — {len(out['files']) - len(failures)}/{len(out['files'])} file(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
