#!/usr/bin/env python3
"""G's blast radius: which corpus cases moved, and in which direction. A fix may not hide a regression.

Compares a fresh run against the committed baseline per case, for both tier-1 readers, and prints:
  · cases whose exact value ROSE (improved) — expected for the money family
  · cases whose exact value FELL   (regressions) — each must be explained or the change is not shipped
  · the clean-case count and every per-check count that changed
"""
import json
import sys

BASE = "docs/conformance/results/2026-11-19-chrome.json"
NEW = sys.argv[1] if len(sys.argv) > 1 else "/tmp/g60/results.json"


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    base, new = load(BASE), load(NEW)
    b = {c["id"]: c for c in base["cases"]}
    n = {c["id"]: c for c in new["cases"]}
    rose, fell, same = [], [], 0
    for cid in b:
        for reader in ("pdfium", "pdfkit"):
            old = b[cid]["per_reader"][reader]["metrics"]["exact"]
            cur = n[cid]["per_reader"][reader]["metrics"]["exact"]
            if cur > old:
                rose.append((cid, reader, old, cur))
            elif cur < old:
                fell.append((cid, reader, old, cur))
            else:
                same += 1
    print(f"cases {len(b)} · reader-values unchanged {same} · rose {len(rose)} · fell {len(fell)}")
    for cid, reader, old, cur in rose:
        print(f"  ROSE {cid:28s} {reader:7s} {old:.3f} -> {cur:.3f}")
    for cid, reader, old, cur in fell:
        print(f"  FELL {cid:28s} {reader:7s} {old:.3f} -> {cur:.3f}")
    print(f"clean cases {base['checks']['clean_cases']} -> {new['checks']['clean_cases']}")
    diff = {k: (base["checks"]["per_check"][k], new["checks"]["per_check"][k])
            for k in base["checks"]["per_check"] if base["checks"]["per_check"][k] != new["checks"]["per_check"][k]}
    print("per-check moves:", diff or "none")
    return 1 if fell else 0


if __name__ == "__main__":
    sys.exit(main())
