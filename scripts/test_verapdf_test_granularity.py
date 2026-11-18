#!/usr/bin/env python3
"""Prove the veraPDF gate sees a NEW failing test inside a clause that already fails.

With clause-level keys, a clause listed in the baseline absorbed every failing test inside it: a new test
appearing under 6.6.4 produced the same set entry and the gate passed. The baseline is now clause-testNumber
(B5), so the same report must be reported as NEW.

A shim `verapdf` answers --version with the baseline's version and --format json with a report carrying
6.6.4 test 2 next to the baseline's 6.6.4 test 1.

Run: python3 scripts/test_verapdf_test_granularity.py
"""
import json
import os
import subprocess
import sys
import tempfile

import fitz

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIM = '''#!/usr/bin/env python3
import os, sys
if "--version" in sys.argv:
    print("veraPDF 1.30.0")
    raise SystemExit(0)
print(open(os.environ["FAKE_REPORT"], encoding="utf-8").read())
'''


def report(tests: list[str]) -> dict:
    return {"report": {"jobs": [{"itemDetails": {"fileName": "x.pdf"},
                                 "validationResult": [{"profileName": "PDF/A-3b validation profile",
                                                       "compliant": False, "details": {"ruleSummaries": [
                                     {"clause": "6.6.4", "testNumber": t, "ruleStatus": "FAILED",
                                      "description": "identification"} for t in tests]}}]}]}}


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="verapdf-granularity-")
    pdf = os.path.join(tmp, "one.pdf")
    d = fitz.open()
    d.new_page()
    d.save(pdf)
    d.close()

    bindir = os.path.join(tmp, "bin")
    os.makedirs(bindir)
    shim = os.path.join(bindir, "verapdf")
    with open(shim, "w", encoding="utf-8") as f:
        f.write(SHIM)
    os.chmod(shim, 0o755)

    failures = 0
    for name, tests, want in (("new-test-in-known-clause", ["1", "2"], "NEW ['6.6.4-2'] exit 1"),
                              ("control-baseline-only", ["1"], "baseline holds, exit 0")):
        path = os.path.join(tmp, name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report(tests), f)
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ.get("PATH", ""),
                   FAKE_REPORT=path, PDF_SPEC="nav_spec")
        r = subprocess.run([sys.executable, "scripts/verapdf_gate.py", pdf, "3b"],
                           cwd=PROJ, env=env, capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        if name == "new-test-in-known-clause":
            ok = r.returncode == 1 and "NEW ['6.6.4-2']" in out
        else:
            ok = r.returncode == 0 and "HELD" in out
        print(f"{'PASS' if ok else 'FAIL'} {name:24s} -> {out.splitlines()[-1][:110] if out else '(no output)'}"
              f"   (want: {want})")
        failures += 0 if ok else 1

    if failures:
        print(f"\nGRANULARITY TEST FAILED — {failures} case(s)")
        return 1
    print("\nGRANULARITY TEST PASSED — a new test in a listed clause is NEW, the baseline itself still holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
