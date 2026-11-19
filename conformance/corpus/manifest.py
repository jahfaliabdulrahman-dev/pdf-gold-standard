"""MANIFEST.json — derived from the case files, never hand-written.

Every count in the certificate and in the docs comes from here: the number of cases, the count per
category, and each case's sha256. `--write` is the only writer; `problems()` compares the stored file to a
fresh derivation in both directions, so a case added without regenerating the manifest, or a manifest row
with no case behind it, is a refusal rather than a stale number.
"""
import json
import os
from collections import Counter

from . import cases as C

MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MANIFEST.json")


def derive() -> dict:
    entries = []
    for path in C.case_paths():
        case = C.load(path)
        entries.append({
            "id": case["id"],
            "category": case["category"],
            "file": os.path.basename(path),
            "bytes": os.path.getsize(path),
            "sha256": C.sha256_of(path),
        })
    counts = Counter(e["category"] for e in entries)
    return {
        "schema": "conformance-corpus/1",
        "total": len(entries),
        "counts": {k: counts[k] for k in sorted(counts)},
        "cases": sorted(entries, key=lambda e: e["id"]),
    }


def write(path: str = MANIFEST) -> dict:
    manifest = derive()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    return manifest


def load(path: str = MANIFEST) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def problems(path: str = MANIFEST) -> list[str]:
    """[] means the manifest is exactly what the case files derive. Names every difference."""
    if not os.path.exists(path):
        return [f"{os.path.basename(path)} is missing — run `python -m conformance manifest --write`"]
    stale, fresh = load(path), derive()
    out = []
    if stale.get("total") != fresh["total"]:
        out.append(f"total {stale.get('total')} in the file, {fresh['total']} derived")
    if stale.get("counts") != fresh["counts"]:
        out.append(f"counts {stale.get('counts')} in the file, {fresh['counts']} derived")
    have = {e["id"]: e for e in stale.get("cases", [])}
    want = {e["id"]: e for e in fresh["cases"]}
    for missing in sorted(set(want) - set(have)):
        out.append(f"case {missing} exists but is not in the manifest")
    for extra in sorted(set(have) - set(want)):
        out.append(f"manifest lists {extra} but no case file has that id")
    for name in sorted(set(have) & set(want)):
        if have[name]["sha256"] != want[name]["sha256"]:
            out.append(f"case {name}: sha256 {have[name]['sha256'][:12]} in the file, "
                       f"{want[name]['sha256'][:12]} derived (the case changed)")
        if have[name]["category"] != want[name]["category"]:
            out.append(f"case {name}: category {have[name]['category']} in the file, "
                       f"{want[name]['category']} derived")
    return out
