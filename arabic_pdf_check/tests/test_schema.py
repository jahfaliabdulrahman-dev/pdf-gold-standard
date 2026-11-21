#!/usr/bin/env python3
"""Every report has the shape it declares — the blind report against `report.v1.json`, a free-text
certificate against `certificate.v2.json`."""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

import jsonschema                                          # noqa: E402

from arabic_pdf_check import blind, markdown               # noqa: E402
from conformance import certificate                        # noqa: E402

FAILS = []
PDF = os.path.join(REPO, "tests", "vocalised_raw.pdf")
TRUTH = "الحمدُ لله رب العالمين.\nهذا اختبار للنص المشكول: الْحَمْدُ، شَدَّة، تَنْوِين."


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


report = blind.check(PDF, json.load(open(os.path.join(REPO, "arabic_pdf_check/thresholds.json"))))
schema = json.load(open(os.path.join(REPO, "arabic_pdf_check/schema/report.v1.json")))
try:
    jsonschema.validate(report, schema)
    check("blind-report-schema", True)
except jsonschema.ValidationError as exc:
    check("blind-report-schema", False, f"{exc.message} at {list(exc.absolute_path)}")
check("blind-mode-is-blind", report["mode"] == "blind" and "verdict" not in report, str(report.get("mode")))
check("blind-no-percentage-key", not any(k in report for k in ("score", "ratio", "percentage", "pass")), "")

cert = certificate.certify(PDF, truth_text=TRUTH, truth_name="vocalised.txt")
cert_schema = json.load(open(os.path.join(REPO, "conformance", "schema", "certificate.v2.json")))
try:
    jsonschema.validate(cert, cert_schema)
    check("certificate-v2-schema", True)
except jsonschema.ValidationError as exc:
    check("certificate-v2-schema", False, f"{exc.message} at {list(exc.absolute_path)}")
check("certificate-truth-source", cert["source"]["kind"] == "truth" and cert["claims"] is None,
      json.dumps(cert.get("source"))[:120])
check("certificate-free-text-checks", {c["id"] for c in cert["checks"]} >=
      {"tounicode-coverage", "presentation-forms", "numerals-persian", "numerals-mixed", "private-keys"},
      str(sorted(c["id"] for c in cert["checks"])))
tmp = tempfile.mkdtemp(prefix="cert-v2-")
path = os.path.join(tmp, "cert.json")
json.dump(cert, open(path, "w", encoding="utf-8"), ensure_ascii=False)
truth_path = os.path.join(tmp, "truth.txt")
with open(truth_path, "w", encoding="utf-8") as fh:
    fh.write(TRUTH)
problems = certificate.validate(path, PDF, do_recheck=True, truth_path=truth_path)
check("certificate-v2-validates-and-rechecks", not problems, "; ".join(problems[:3]))
no_truth = certificate.validate(path, PDF, do_recheck=True)
check("certificate-v2-recheck-needs-truth", any("--truth" in p for p in no_truth), "; ".join(no_truth[:3]))

md = markdown.render_blind(report)
check("markdown-no-pass", "PASS" not in md and "pass" not in md.lower(), "")
check("markdown-no-percent", "%" not in md, "")
check("markdown-lists-missing-readers", (not report["missing_readers"]) or "لم يعمل" in md, "")
check("markdown-names-every-reader", all(name in md for name in report["readers"]), "")

print()
if FAILS:
    print(f"CHECKER SCHEMA FAILED — {FAILS}")
    raise SystemExit(1)
print("CHECKER SCHEMA PASSED — report.v1 and certificate/2 both validate")
