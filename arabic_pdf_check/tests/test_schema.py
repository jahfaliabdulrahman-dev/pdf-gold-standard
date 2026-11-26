#!/usr/bin/env python3
"""Every report has the shape it declares — the blind report against `report.v1.json`, a free-text
certificate against `certificate.v2.json`."""
import ast
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
# Every id the checker can EMIT must be in the schema's enum. The blind report built above exercises one file and
# never trips the newer signals, so it cannot see this drift: a shipped report carrying `segment-order` failed
# validation while the suite stayed green (2026-11-25). The ids are read from the SOURCE, not from a list here —
# a list would be a second registry, free to drift with the first.
def emitted_ids(path: str) -> set[str]:
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_finding"
                and node.args):
            for sub in ast.walk(node.args[0]):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and "-" in sub.value:
                    out.add(sub.value)
    return out


emitted = emitted_ids(os.path.join(REPO, "arabic_pdf_check", "blind.py"))
declared = set(schema["$defs"]["signal"]["properties"]["id"]["enum"])
check("every-emitted-signal-id-is-declared", emitted <= declared, f"undeclared: {sorted(emitted - declared)}")
check("signal-ids-are-read-from-source", len(emitted) >= 10, f"{sorted(emitted)}")

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

# ---- the v2 contract: one source, a text hash that says it is a text hash, per-reader evidence, no v1 corpus
bad = json.loads(json.dumps(cert))
bad["corpus"] = {"case": "x", "category": "y", "manifest_sha256": "0" * 64, "cases": 1}
try:
    jsonschema.validate(bad, cert_schema)
    check("v2-rejects-corpus", False, "a certificate carried both `source` and the v1 `corpus` block")
except jsonschema.ValidationError:
    check("v2-rejects-corpus", True)
legacy = json.loads(json.dumps(cert))
legacy["source"].pop("text_sha256")
legacy["source"]["sha256"] = "0" * 64
try:
    jsonschema.validate(legacy, cert_schema)
    check("v2-accepts-old-truth-hash", True)
except jsonschema.ValidationError as exc:
    check("v2-accepts-old-truth-hash", False, exc.message)
without = json.loads(json.dumps(cert))
without["source"].pop("text_sha256")
try:
    jsonschema.validate(without, cert_schema)
    check("v2-requires-a-truth-hash", False, "a truth source with no hash validated")
except jsonschema.ValidationError:
    check("v2-requires-a-truth-hash", True)
check("v2-readers-carry-evidence",
      all({"confidence", "examples"} <= set(r) for r in cert["readers"].values()),
      str({n: sorted(set(r) - {"confidence", "examples"}) for n, r in cert["readers"].items()}))

# A NEW-shape certificate (text_sha256) without per-reader evidence is refused by `validate`, although the
# schema alone would accept it (old certificates must keep validating; new ones must carry the evidence).
doctored = json.loads(json.dumps(cert))
first = next(iter(doctored["readers"]))
doctored["readers"][first].pop("confidence")
doctored_path = os.path.join(tmp, "no-evidence.json")
with open(doctored_path, "w", encoding="utf-8") as fh:
    json.dump(doctored, fh, ensure_ascii=False)
problems = certificate.validate(doctored_path, PDF)
check("v2-validate-requires-evidence", any("confidence" in p for p in problems), "; ".join(problems[:3]))

# A malformed certificate is a NAMED refusal, never a traceback: `source`/`readers` of the wrong JSON type
# reach the new-shape guard before the schema runs, so the guard must check them.
for field, bad in (("source", "x"), ("readers", ["pdfium"])):
    broken = json.loads(json.dumps(cert))
    broken[field] = bad
    bpath = os.path.join(tmp, f"bad-{field}.json")
    with open(bpath, "w", encoding="utf-8") as fh:
        json.dump(broken, fh, ensure_ascii=False)
    try:
        out = certificate.validate(bpath, PDF)
        check(f"v2-bad-{field}-is-named", any("JSON objects" in p for p in out), "; ".join(out[:2]))
    except Exception as exc:                                     # noqa: BLE001 - the point is the absence
        check(f"v2-bad-{field}-is-named", False, f"{type(exc).__name__}: {exc}")

# ---- a BOM in the customer's truth file is a byte-order mark, not the first character of the text
bom_truth = os.path.join(tmp, "bom.txt")
with open(bom_truth, "w", encoding="utf-8-sig") as fh:
    fh.write(TRUTH)
bom_out = os.path.join(tmp, "bom.json")
bom_md = os.path.join(tmp, "bom.md")
r = __import__("subprocess").run(
    [sys.executable, "-m", "arabic_pdf_check", "verify", PDF, "--truth", bom_truth, "-o", bom_out, "--md", bom_md],
    capture_output=True, text=True, timeout=900, cwd=REPO)
ok = os.path.exists(bom_out)
bom = json.load(open(bom_out, encoding="utf-8")) if ok else {}
check("bom-cli-runs", ok, (r.stderr or r.stdout).strip()[-200:])
check("bom-not-a-character", bom.get("source", {}).get("chars") == len(TRUTH),
      f"chars {bom.get('source', {}).get('chars')} vs {len(TRUTH)}")

print()
if FAILS:
    print(f"CHECKER SCHEMA FAILED — {FAILS}")
    raise SystemExit(1)
print("CHECKER SCHEMA PASSED — report.v1 and certificate/2 both validate")
