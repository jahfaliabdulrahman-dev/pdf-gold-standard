#!/usr/bin/env python3
"""C5 guard: a certificate is valid only when its file, its schema and its verdict all agree.

Controls:
  1. A freshly issued certificate validates.
  2. A wrong file sha256 is refused by name.
  3. A verdict flipped to PASS is refused, and the refusal names the recomputed verdict.
  4. A missing required field is refused by the schema.
  5. `validate` does not run a control script (a certificate must be checkable without producing facts).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)

from conformance import certificate
from conformance.adapters import chrome
from conformance.corpus import cases as corpus_cases

fails = []


def check(name, ok, detail):
    print(("PASS " if ok else "FAIL ") + name + " - " + detail)
    if not ok:
        fails.append(name)


tmp = tempfile.mkdtemp(prefix="conf-cert-")
pdf = os.path.join(tmp, "head-h1-h3.pdf")
case = corpus_cases.by_id(["head-h1-h3"])[0]
chrome.render_case(case, pdf, "chrome")
cert = certificate.certify(pdf, "head-h1-h3", engine="chrome")
good = os.path.join(tmp, "good.cert.json")
json.dump(cert, open(good, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

problems = certificate.validate(good, pdf)
check("valid-certificate", not problems, "; ".join(problems[:3]) or f"verdict {cert['verdict']} accepted")
# The verdict must FOLLOW from the readings, not from the machine's luck: PDFKit is tier-1 and its behaviour
# differs across macOS versions (measured: exact 1.0 on 27.2, 0.0 on the CI image's 15.8.2 for the same file),
# so demanding PASS here would assert the runner's PDFKit instead of the rule. The rule itself stays pinned by
# `flipped-verdict-refused` and by the failing certificate below.
tier1 = [cert["readers"][r]["exact"] for r in ("pdfium", "pdfkit") if r in cert["readers"]]
failed_checks = [c["id"] for c in cert["checks"] if c["status"] == "fail"]
expected = "PASS" if tier1 and min(tier1) == 1.0 and not failed_checks else "FAIL"
check("verdict-follows-readings", cert["verdict"] == expected,
      f"{cert['verdict']} with tier-1 exact {tier1} and failed checks {failed_checks}")

# --- 2 · wrong sha ----------------------------------------------------------
bad = json.loads(json.dumps(cert))
bad["file"]["sha256"] = "0" * 64
path = os.path.join(tmp, "bad-sha.json")
json.dump(bad, open(path, "w"), ensure_ascii=False)
problems = certificate.validate(path, pdf)
check("wrong-sha-refused", any("sha256" in p for p in problems), "; ".join(problems[:2]))

# --- 3 · verdict flipped ----------------------------------------------------
bad = json.loads(json.dumps(cert))
bad["verdict"] = "FAIL" if cert["verdict"] == "PASS" else "PASS"
path = os.path.join(tmp, "bad-verdict.json")
json.dump(bad, open(path, "w"), ensure_ascii=False)
problems = certificate.validate(path, pdf)
check("flipped-verdict-refused", any("recomputed" in p for p in problems), "; ".join(problems[:2]))

# --- 4 · missing field ------------------------------------------------------
bad = json.loads(json.dumps(cert))
del bad["not_checked"]
path = os.path.join(tmp, "missing.json")
json.dump(bad, open(path, "w"), ensure_ascii=False)
problems = certificate.validate(path, pdf)
check("missing-field-refused", any(p.startswith("schema:") for p in problems), "; ".join(problems[:2]))

# --- 5 · no control runs at validate time ----------------------------------
site = os.path.join(tmp, "sitecustomize.py")
open(site, "w").write(
    "import builtins, pathlib\n"
    "def _hook(event, args):\n"
    "    if event == 'subprocess.Popen' and args and 'controls' in str(args[0]):\n"
    "        raise RuntimeError('a control script ran inside validate')\n"
    "import sys\n"
    "sys.addaudithook(_hook)\n")
env = {**os.environ, "PYTHONPATH": tmp + os.pathsep + os.environ.get("PYTHONPATH", "")}
r = subprocess.run([sys.executable, "-m", "conformance", "validate", good, pdf],
                   capture_output=True, text=True, env=env, timeout=300, cwd=REPO)
check("no-control-in-validate", r.returncode == 0 and "control script ran" not in (r.stderr + r.stdout),
      (r.stdout + r.stderr).strip().splitlines()[-1][:120])

# --- 6 · a FAILING certificate, issued for a case whose text layer fails
fail_pdf = os.path.join(tmp, "voc-full.pdf")
chrome.render_case(corpus_cases.by_id(["voc-full"])[0], fail_pdf, "chrome")
fail_cert = certificate.certify(fail_pdf, "voc-full", engine="chrome")
fail_path = os.path.join(tmp, "fail.cert.json")
with open(fail_path, "w", encoding="utf-8") as fh:
    json.dump(fail_cert, fh, ensure_ascii=False, indent=1)
problems = certificate.validate(fail_path, fail_pdf)
check("failing-certificate-valid", not problems, "; ".join(problems[:2]) or
      f"verdict {fail_cert['verdict']}: {fail_cert['verdict_detail'][:70]}")
check("failing-verdict", fail_cert["verdict"] == "FAIL"
      and ("failed checks" in fail_cert["verdict_detail"] or "pdfium exact 0" in fail_cert["verdict_detail"]),
      fail_cert["verdict_detail"][:90])

shutil.rmtree(tmp, ignore_errors=True)
print(f"\nCHECKS IN CERTIFICATE: {len(cert['checks'])} · READERS: {len(cert['readers'])} · "
      f"TIER-1 UNAVAILABLE: {len(cert['tier1_unavailable'])}")
if fails:
    print(f"TEST FAILED — {fails}")
    raise SystemExit(1)
print("CERTIFICATE GUARD PASSED")
