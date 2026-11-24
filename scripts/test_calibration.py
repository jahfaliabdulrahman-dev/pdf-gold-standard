#!/usr/bin/env python3
"""The calibration manifest must tag every file's defect type — a name alone is not a classification.

The three files are the assignment's named cases; the 52 ordinary owner files never appear here.
This guard is structural (no text, no owner paths): it proves every calibration row has a declared
type from the taxonomy, a measured evidence block, and a sha256; and that the Python item's defect is
the measured lam-alef transposition, not a claim that the lexical floor caught it.
"""
import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CAL = os.path.join(REPO, "docs", "checker-v0", "measurements", "calibration.json")
HEX = re.compile(r"^[0-9a-f]{64}$")
EXPECTED = {
    "نظام الشركات 1439 سعد الخنفري.pdf": "numerals-mixed",
    "٣ - درس - البايثون.pdf": "lam-alef-transposition",
    "7  - درس - مهارات التواصل.pdf": "lexical-validity",
}
passed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if not condition:
        print(f"FAIL {name} — {detail}")
        raise SystemExit(1)
    passed += 1
    print(f"PASS {name}")


def _walk_no_text(value, path="") -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            check(f"no-text-key:{path}.{k}" if k in ("text", "snippet", "excerpt") else f"key-ok:{path}.{k}",
                  k not in ("text", "snippet", "excerpt"), f"the calibration manifest carries {k}")
            _walk_no_text(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _walk_no_text(v, f"{path}[{i}]")


def main() -> int:
    data = json.load(open(CAL, encoding="utf-8"))
    check("schema-version", data.get("schema_version") == "calibration/2", str(data.get("schema_version")))
    check("taxonomy", isinstance(data.get("defect_types"), dict) and data["defect_types"], "missing defect_types")
    files = data.get("files")
    check("three-files", isinstance(files, list) and len(files) == 3, f"files={len(files or [])}")
    names = {f.get("name"): f for f in files}
    check("exact-names", set(names) == set(EXPECTED), str(sorted(names)))
    for name, expected in EXPECTED.items():
        f = names[name]
        check(f"type:{name}", f.get("defect_type") == expected, str(f.get("defect_type")))
        check(f"types:{name}", isinstance(f.get("defect_types"), list) and expected in f["defect_types"],
              str(f.get("defect_types")))
        check(f"type-first:{name}", f["defect_types"][0] == expected, str(f.get("defect_types")))
        check(f"taxonomy-member:{name}", all(t in data["defect_types"] for t in f["defect_types"]),
              str(f.get("defect_types")))
        check(f"sha:{name}", bool(HEX.match(f.get("sha256", ""))), str(f.get("sha256")))
        ev = f.get("defect_evidence")
        check(f"evidence:{name}", bool(isinstance(ev, dict) and ev.get("note")), "missing measured evidence")
        check(f"readers:{name}", isinstance(ev.get("lam_alef"), dict) and
              set(ev["lam_alef"]) == {"pdfium", "pdfkit", "mupdf", "poppler", "pdfminer"}, "reader set")
    py = names["٣ - درس - البايثون.pdf"]
    check("python:lam-alef-21", py["defect_evidence"]["lam_alef"] ==
          {"pdfium": 21, "pdfkit": 0, "mupdf": 21, "poppler": 21, "pdfminer": 0},
          str(py["defect_evidence"]["lam_alef"]))
    check("python:file-low", py["defect_evidence"]["file_level"] == "low", str(py["defect_evidence"]["file_level"]))
    check("python:no-threshold-claim", "not lowered" in py["defect_evidence"]["note"].lower()
          or "not lowered" in py["defect"].lower() or "لا" in py["defect_evidence"]["note"],
          "the note must state the floor is not lowered")
    _walk_no_text(data)
    print(f"\nCALIBRATION PASSED — 3 named files, {len(data['defect_types'])} defect types, no text")
    return 0


if __name__ == "__main__":
    sys.exit(main())
