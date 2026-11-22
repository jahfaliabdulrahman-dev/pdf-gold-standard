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
check("truth-hash", by_truth["source"]["text_sha256"] == __import__("hashlib").sha256(truth.encode()).hexdigest(), "")
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

# `results.json` / `ratchet.json` published the metrics NESTED under `metrics`; a certificate stores them
# flat. The adapter is the only place the shapes meet, and this is the regression the corpus run caught:
# consumers read `per_reader[name].metrics.exact`, not `per_reader[name].exact`.
from conformance import reference                          # noqa: E402
flat = {"pdfium": {"version": "9.9", "exact": 1.0, "word_f1": 1.0, "order": 1.0, "digit_runs": 1.0,
                   "skeleton_exact": 1.0, "defects": {"pua": 0}, "limitations_applied": []}}
shaped = reference.as_results(flat)
check("results-shape", shaped["pdfium"]["metrics"]["exact"] == 1.0
      and "exact" not in shaped["pdfium"], str(shaped)[:160])

# The corpus SUMMARIZER (and the ratchet) read the nested shape; a test that built the nested dict by hand
# stayed green over a broken runner. This passes the adapter's own output through the real summarizer.
from conformance import runner                            # noqa: E402
summary = runner.summarize([{"id": "probe", "category": "shape", "per_reader": shaped}], {"pdfium": None})
check("results-shape-summarize", summary["pdfium"]["exact_cases"] == 1, str(summary)[:200])

# A reading can carry control characters (PDFKit emits U+0000); an evidence excerpt must be printable text.
ex = reference.mismatch_examples("كلمة أخرى", "سطر\u0000خاطئ\nثانٍ\u0000خاطئ")
check("examples-printable", ex and all("\u0000" not in e["text"] for e in ex) and len(ex) == 2, str(ex))

print()
if FAILS:
    print(f"REFERENCE ACCEPTANCE FAILED — {FAILS}")
    raise SystemExit(1)
print("REFERENCE ACCEPTANCE PASSED — one measurement path, two sources")
