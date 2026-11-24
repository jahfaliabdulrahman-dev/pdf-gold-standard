#!/usr/bin/env python3
"""Measure a set of PDFs from OTHER producers — the second calibration set, never the pipeline's own output.

The owner's rule: a threshold calibrated only on our own Chrome output is not calibrated. This script reads a
directory of files a different producer wrote (LibreOffice, Word, a scanner's exporter) and reports what the
checker would say, WITHOUT touching the shipped thresholds. Its output is the evidence a human uses to say
which files really lost text; only after that verdict can a threshold be re-derived.

    python3 scripts/checker_foreign.py docs/checker-v0/foreign --out docs/checker-v0/measurements/foreign.json

Exit 1 if any file is `high`: a foreign CLEAN set that alarms is a calibration failure, not a file failure —
the human verdict decides which side is wrong, and nothing is written to the manifest here.
"""
import argparse
import glob
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)

from arabic_pdf_check import blind                                      # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    thresholds_path = os.path.join(REPO, "arabic_pdf_check", "thresholds.json")
    with open(thresholds_path, encoding="utf-8") as fh:
        thresholds = json.load(fh)
    rows, high = [], []
    for path in sorted(glob.glob(os.path.join(a.directory, "*.pdf"))):
        report = blind.check(path, thresholds)
        level = report["risk"]["file"]["level"]
        rows.append({"file": os.path.basename(path), "sha256": report["file"]["sha256"], "level": level,
                     "signals": [{"id": s["id"], "level": s["level"]} for s in report["signals"]]})
        if level == "high":
            high.append(os.path.basename(path))
    payload = {"directory": os.path.basename(os.path.abspath(a.directory)), "files": len(rows),
               "high": len(high), "generated_at": _now(),
               "thresholds_sha256": hashlib.sha256(open(thresholds_path, "rb").read()).hexdigest(),
               "command": " ".join(sys.argv), "rows": rows}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"foreign set: {len(rows)} file(s), {len(high)} high — {a.out}")
    for r in rows:
        print(f"  {r['level']:6} {r['file']}: {', '.join(s['id'] + '/' + s['level'] for s in r['signals']) or '—'}")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
