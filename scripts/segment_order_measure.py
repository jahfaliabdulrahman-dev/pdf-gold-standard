#!/usr/bin/env python3
"""Measure the segment-order signal on a directory of PDFs — the producer of measurements/segment-order.json.

The signal is a READER one, so the artifact records one count per reader per file: how many Arabic segments
that reader returns in the exact reverse order of a strict majority of the other readers. No text is
deposited — only counts and the file's sha256 — so the artifact can hold vendor samples and the owner's
documents without publishing either's content.

Every set carries its own provenance (the command, the tree's `head`, `dirty`), because a measurement whose
population cannot be traced is the gap the 2026-11-25 audit named for PR-3 — it should not be reproduced here.

Usage:
  python3 scripts/segment_order_measure.py --dir ~/.cache/zatca-sdk/238-R3.4.8/*/Data/Samples/PDF-A3 \
      --set zatca --out docs/checker-v0/measurements/segment-order.json
"""
import argparse
import json
import os
import shlex
import sys
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

from conformance import certificate as cert_mod                                  # noqa: E402
from conformance.checks import lexical, segment_order                            # noqa: E402
from conformance.hashing import sha256_file                                      # noqa: E402
from conformance.readers import available, text_many                             # noqa: E402


def measure(path: str, vocab) -> dict:
    ok, missing = available()
    texts = {}
    for name in ok:
        texts[name] = text_many(name, [path])[0]      # a string; joining it again would insert \n between characters
    found = segment_order.findings(texts, vocab)
    return {"sha256": sha256_file(path), "bytes": os.path.getsize(path),
            "readers": {n: len(found.get(n, [])) for n in texts},
            "voters": len(texts), "missing_readers": sorted(missing)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--set", default="set", help="the population's name in the artifact (zatca, clean, owner…)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = sorted(os.path.join(a.dir, f) for f in os.listdir(a.dir) if f.lower().endswith(".pdf"))
    if not files:
        raise SystemExit(f"REFUSED — no PDF in {a.dir}: an empty population measures nothing")
    vocab = lexical.lexicon()
    rows, totals = [], {}
    for path in files:
        row = {"label": f"{a.set}-{len(rows) + 1:02}", **measure(path, vocab)}
        rows.append(row)
        for name, n in row["readers"].items():
            totals[name] = totals.get(name, 0) + n
        print(f"   {row['label']}  " + "  ".join(f"{k}={v}" for k, v in row["readers"].items()))
    try:
        commit, dirty = cert_mod.pipeline_commit()
    except cert_mod.CertError:
        commit, dirty = "unknown", None
    payload = {"schema": "segment-order/2", "generated_at": _now(), "sets": {}}
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as fh:
            payload = json.load(fh)
        # Rebuild from `sets` only: an earlier schema kept `set`/`files`/`totals` at the top level, and a merge
        # that leaves them beside `sets` publishes two copies of one measurement, only one of which is fresh.
        payload = {"schema": "segment-order/2", "generated_at": _now(),
                   "sets": payload.get("sets") or {}}
    payload["sets"][a.set] = {
        "dir": os.path.basename(os.path.normpath(a.dir)),
        "command": shlex.join(["python3", os.path.relpath(__file__, REPO)] + sys.argv[1:]),
        "head": commit, "dirty": dirty, "measured_at": _now(),
        "files": rows, "totals": totals,
        "rule": "a reader is counted when a line's Arabic segment (>=2 words) is the exact reverse of a strict "
                "majority of the readers' order; one vote per reader per multiset; letter-reversed readings do "
                "not vote"}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("totals:", json.dumps(totals))
    print(f"written: {a.out}")
    return 0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


if __name__ == "__main__":
    sys.exit(main())
