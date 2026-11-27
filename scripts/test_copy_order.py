#!/usr/bin/env python3
"""PR-6 condition د: `copy_order` must equal a fresh per-reader orientation measurement, reader by reader.

The report builds the table from one call to `blind.visual_orders()`; this test does NOT read that code path's
output — it re-extracts each reader's text with `isolate.read` and re-runs `visual_order.inspect`, then compares
the two tables row by row. A table that agrees with itself proves nothing; a table that agrees with an
independent re-measurement on the SAME texts is the claim.

Two files, as the assignment asks: the Arabic guide (a clean document) and a ZATCA invoice (a production file
whose order splits the readers). Nothing of the owner's corpus is touched.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REPO)

from arabic_pdf_check import blind                                    # noqa: E402
from conformance.checks import visual_order                           # noqa: E402
from conformance.readers import isolate                               # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def zatca_invoice() -> str | None:
    found = sorted(glob.glob(os.path.expanduser(
        "~/.cache/zatca-sdk/**/Data/Samples/PDF-A3/Standard_Invoice.pdf"), recursive=True))
    return found[0] if found else None


def compare(path: str, label: str) -> None:
    thresholds = json.load(open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"), encoding="utf-8"))
    report = blind.check(path, thresholds)
    th = thresholds["values"]
    decl = {"visual_order": th["visual_order"]["value"],
            "presentation_forms": th["presentation_forms"]["value"],
            "min_arabic_chars": th["min_arabic_chars"]["value"]}
    fresh = {}
    for name in report["readers"]:
        _pages, text = isolate.read(name, os.path.abspath(path))
        fresh[name] = visual_order.inspect(text, decl)

    rows = {r["reader"]: r for r in report["copy_order"]["rows"]}
    check(f"{label}:one-row-per-reader", set(rows) == set(fresh), f"{sorted(rows)} vs {sorted(fresh)}")
    for name, got in fresh.items():
        row = rows.get(name) or {}
        expected = ("reversed" if got["visual"] else
                    "logical" if got["score"] is not None and got["score"] <= -decl["visual_order"]
                    else "inconclusive")
        check(f"{label}:{name}:order", row.get("order") == expected,
              f"table={row.get('order')} fresh={expected} score={got['score']}")
        check(f"{label}:{name}:score", row.get("score") == got["score"],
              f"table={row.get('score')} fresh={got['score']}")
    check(f"{label}:lists-match-rows",
          report["copy_order"]["reversed"] == [n for n in fresh if fresh[n]["visual"]]
          or set(report["copy_order"]["reversed"]) == {n for n in fresh if fresh[n]["visual"]},
          str(report["copy_order"]["reversed"]))
    check(f"{label}:no-file-level-visual-signal",
          not any(s["id"] == "visual-order" and s["cause"] == "file" for s in report["signals"]),
          str([(s["id"], s["cause"]) for s in report["signals"]]))


compare(os.path.join(REPO, "guide-v2-ar.pdf"), "guide")
invoice = zatca_invoice()
if invoice:
    compare(invoice, "zatca-invoice")
else:
    print("SKIP zatca-invoice - the SDK sample is not cached on this machine")

print()
if FAILS:
    print(f"COPY ORDER FAILED — {len(FAILS)}: {', '.join(FAILS)}")
    raise SystemExit(1)
print("COPY ORDER PASSED — the table equals an independent re-measurement, reader by reader")
