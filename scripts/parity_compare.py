#!/usr/bin/env python3
"""Parity: a gate fix must not move the incumbent's own numbers. Prints the counts that must be identical."""
import json
import sys

OLD = "docs/conformance/results/2026-11-19-chrome.json"
NEW = "/tmp/parity-chrome/results.json"


def total(doc, key):
    return sum(1 for c in doc["cases"] if c["per_reader"][key]["metrics"]["exact"] == 1.0)


def main() -> int:
    with open(OLD, encoding="utf-8") as fh:
        old = json.load(fh)
    with open(NEW, encoding="utf-8") as fh:
        new = json.load(fh)
    rows = [("clean cases", old["checks"]["clean_cases"], new["checks"]["clean_cases"])]
    for reader in ("pdfium", "pdfkit"):
        rows.append((f"{reader} exact", total(old, reader), total(new, reader)))
    diff = [k for k in old["checks"]["per_check"] if old["checks"]["per_check"][k] != new["checks"]["per_check"][k]]
    bad = 0
    for name, a, b in rows:
        ok = a == b
        bad += 0 if ok else 1
        print(f"{'SAME' if ok else 'MOVED'} {name}: {a} -> {b}")
    print(f"{'SAME' if not diff else 'MOVED'} per-check counts: {diff or 'none'}")
    if bad or diff:
        print("PARITY FAILED — the gate fix moved the incumbent's numbers")
        return 1
    print("PARITY HELD — the reader fix changes what the gate says about OTHER producers, not about ours")
    return 0


if __name__ == "__main__":
    sys.exit(main())
