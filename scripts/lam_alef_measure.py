#!/usr/bin/env python3
"""The lam-alef separation, measured: counts, Arabic runs and a rate per 1000 runs, per reader.

Why a rate and not a count: a count grows with the document, and the clean population's only occurrence is
`report.pdf` *quoting* the defect's own example («األتمتة» in a quotation) — one hit, 1 of 1140 runs. A count
threshold of 2 would fire on any document that quotes two examples; a rate does not, and it is the quantity a
transposition density actually is. The shipped value is the geometric midpoint between the measured clean
maximum and the measured broken minimum (`docs/checker-v0/measurements/lam-alef-separation.json`), which
`scripts/test_lam_alef_separation.py` re-derives from the artifact rather than trusting the literal.

Aggregate only: no text, no excerpts, no page content — the file's sha256, and one row per reader.

Usage:  python3 scripts/lam_alef_measure.py --pdf <file.pdf> [--label doc:report] [--out artifact.json]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

from conformance.checks import lexical                                            # noqa: E402
from conformance.hashing import sha256_file                                      # noqa: E402
from conformance.readers import available, text_many                             # noqa: E402


def measure(path: str) -> dict:
    """{sha256, readers: {name: {runs, lam_alef, rate_per_1000}}, missing_readers} — aggregate only."""
    ok, missing = available()
    rows = {}
    for name in ok:
        text = text_many(name, [path])[0]          # the matrix's one reading, per reader
        v = lexical.validity(text)
        rate = round(v["lam_alef"] / v["runs"] * 1000.0, 2) if v["runs"] else None
        rows[name] = {"runs": v["runs"], "lam_alef": v["lam_alef"], "rate_per_1000": rate}
    return {"sha256": sha256_file(path), "readers": rows, "missing_readers": sorted(missing)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--label", default=None, help="what this file is in the artifact (e.g. doc:report)")
    ap.add_argument("--out", default=None, help="append to this JSON artifact (a list under `files`)")
    a = ap.parse_args()
    row = {"label": a.label or os.path.basename(a.pdf), **measure(a.pdf)}
    print(json.dumps(row, ensure_ascii=False, indent=1))
    if a.out:
        payload = {"schema": "lam-alef-separation/1", "generated_at": _now(), "files": []}
        if os.path.exists(a.out):
            with open(a.out, encoding="utf-8") as fh:
                payload = json.load(fh)
            payload["generated_at"] = _now()
        payload["files"] = [f for f in payload["files"] if f["label"] != row["label"]] + [row]
        payload["files"].sort(key=lambda f: f["label"])
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        print(f"written: {a.out}")
    return 0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    sys.exit(main())
