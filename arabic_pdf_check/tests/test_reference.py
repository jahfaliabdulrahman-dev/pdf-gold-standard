#!/usr/bin/env python3
"""Reference mode: `verify` and `certify` are the same measurement, not two.

Builds one corpus case with the pinned engine, then issues two certificates for the SAME file and the SAME
truth: one naming the case, one naming a free text. Every per-reader number and every defect count must be
identical — if they differ, there is a second measurement path and this test is what catches it.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

from conformance import certificate                        # noqa: E402
from conformance.adapters import chrome                    # noqa: E402
from conformance.checks import structure                   # noqa: E402
from conformance.corpus import cases as corpus_cases       # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


CASE_ID = "head-h1-h3"
case = corpus_cases.by_id([CASE_ID])[0]
truth = structure._truth_text(case)
tmp = tempfile.mkdtemp(prefix="ref-accept-")
pdf = os.path.join(tmp, "case.pdf")
chrome.render_case(case, pdf, "chrome")

by_case = certificate.certify(pdf, case_id=CASE_ID, engine="chrome")
by_truth = certificate.certify(pdf, truth_text=truth, truth_name="case.txt")

check("same-file", by_case["file"]["sha256"] == by_truth["file"]["sha256"], "")
check("schema-v2", by_case["schema_version"] == "certificate/2" == by_truth["schema_version"], "")
check("source-kinds", by_case["source"]["kind"] == "case" and by_truth["source"]["kind"] == "truth", "")
check("truth-hash", by_truth["source"]["sha256"] == __import__("hashlib").sha256(truth.encode()).hexdigest(), "")
check("same-readers", set(by_case["readers"]) == set(by_truth["readers"]), "")

diffs = []
for name in by_case["readers"]:
    a, b = by_case["readers"][name], by_truth["readers"][name]
    for metric in ("version", "exact", "word_f1", "order", "digit_runs", "skeleton_exact", "defects",
                   "limitations_applied"):
        if a.get(metric) != b.get(metric):
            diffs.append(f"{name}.{metric}: {a.get(metric)!r} != {b.get(metric)!r}")
check("same-numbers-per-reader", not diffs, "; ".join(diffs[:4]))

case_ids = {c["id"] for c in by_case["checks"]}
truth_ids = {c["id"] for c in by_truth["checks"]}
check("case-checks-are-a-superset", truth_ids < case_ids and len(truth_ids) > 5,
      f"case={len(case_ids)} truth={len(truth_ids)}")
check("truth-cert-declares-what-did-not-run", "free text" in by_truth["verdict_detail"], by_truth["verdict_detail"])
check("case-cert-claims-are-declared", by_case["claims"] == {"pdfua": "1", "pdfa": "3b"}, "")
check("truth-cert-claims-null", by_truth["claims"] is None, "")

path = os.path.join(tmp, "case.cert.json")
import json                                                # noqa: E402
json.dump(by_case, open(path, "w", encoding="utf-8"), ensure_ascii=False)
problems = certificate.validate(path, pdf)
check("case-certificate-valid", not problems, "; ".join(problems[:3]))

print()
if FAILS:
    print(f"REFERENCE ACCEPTANCE FAILED — {FAILS}")
    raise SystemExit(1)
print("REFERENCE ACCEPTANCE PASSED — one measurement path, two sources")
