#!/usr/bin/env python3
"""Prove both veraPDF screens refuse a report that judged nothing.

A shim `verapdf` answers --version with the baseline's version and --format json with a report that either
raises a taskException, carries no validationResult, or carries one without a boolean `compliant` — exit 0
every time, which is the shape that used to pass the failing-rule set diff as «clean».

Run: python3 scripts/test_verapdf_json_guard.py
"""
import json
import os
import subprocess
import sys
import tempfile

import fitz

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import verapdf_json as VJ  # noqa: E402  (the reader under test, called in-process on a REAL report)

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIM = '''#!/usr/bin/env python3
import os, sys
if "--version" in sys.argv:
    print("veraPDF 1.30.0")
    raise SystemExit(0)
print(open(os.environ["BAD_JSON"], encoding="utf-8").read())
'''

PROFILE = "PDF/A-3b validation profile"


def _job(results):
    return {"report": {"jobs": [{"itemDetails": {"fileName": "x.pdf"}, "validationResult": results}]}}


def _result(compliant, rules=None, profile=PROFILE):
    return {"profileName": profile, "compliant": compliant,
            "details": {"ruleSummaries": rules or []}}


CASES = {
    "no-validationResult": ({"report": {"jobs": [{"itemDetails": {"fileName": "x.pdf"}}]}}, "no validationResult"),
    # verdict and rules disagree: a non-compliant report that names nothing is the silence that reads as clean
    "non-compliant-no-rule": (_job([_result(False, [])]), "verdict and the rules disagree"),
    "compliant-with-failing-rule": (_job([_result(True, [{"clause": "6.6.4", "testNumber": "1",
                                                          "ruleStatus": "FAILED"}])]),
                                    "says compliant while naming"),
    # a verdict for another profile is not this flavour's verdict
    "wrong-profile": (_job([_result(False, [{"clause": "6.6.4", "testNumber": "1", "ruleStatus": "FAILED"}],
                                       profile="PDF/UA-1 validation profile")]),
                      "a verdict for another profile"),
    "taskException": ({"report": {"jobs": [{"itemDetails": {}, "taskException": "PDFBox: cannot parse",
                                           "validationResult": []}]}}, "taskException"),
    "no-compliant-key": ({"report": {"jobs": [{"itemDetails": {},
                                              "validationResult": [{"statement": "?"}]}]}},
                         "boolean «compliant»"),
}


FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "verapdf-report-3b.json")


def _fixture_cases():
    """A REAL report (saved from veraPDF 1.30.0), not a hand-written shape: it proves the reader on the
    bytes the tool actually emits, and that a renamed status key cannot pass as «clean»."""
    if not os.path.exists(FIXTURE):
        return []
    data = json.load(open(FIXTURE, encoding="utf-8"))
    got = [k for k, _ in VJ.read_report(data, "3b")]
    want = [f"{r['clause']}-{r['testNumber']}"
            for r in data["report"]["jobs"][0]["validationResult"][0]["details"]["ruleSummaries"]]
    out = []
    if sorted(got) != sorted(want):
        out.append(f"the fixture's failing set is {got}, its rules say {want}")
    renamed = json.loads(json.dumps(data))
    for r in renamed["report"]["jobs"][0]["validationResult"][0]["details"]["ruleSummaries"]:
        r["status"] = r.pop("ruleStatus")          # a renamed key must not read as «no failing rule»
    # A renamed status key must not SHRINK the failing set: the reader treats an absent status as FAILED,
    # which is the conservative direction (a clean report may look dirty; never the reverse).
    try:
        kept = sorted(k for k, _ in VJ.read_report(renamed, "3b"))
    except SystemExit as exc:
        out.append(f"a renamed status crashed the reader instead of defaulting to FAILED: {exc}")
    else:
        if kept != sorted(want):
            out.append(f"a renamed ruleStatus lost rules: {kept} != {sorted(want)}")
    try:
        VJ.guard(data, "ua1")                      # the same bytes, asked for another flavour
    except SystemExit:
        pass
    else:
        out.append("a 3b report was accepted as a ua1 verdict")
    return out


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="verapdf-guard-")
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
    for name, (payload, reason) in CASES.items():
        path = os.path.join(tmp, name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ.get("PATH", ""),
                   BAD_JSON=path, PDF_SPEC="report_spec")
        for label, argv in (("gate", ["scripts/verapdf_gate.py", pdf, "3b"]),
                            ("claim", ["scripts/claim_probe.py", pdf])):
            r = subprocess.run([sys.executable, *argv], cwd=PROJ, env=env,
                               capture_output=True, text=True, timeout=120)
            out = (r.stdout + r.stderr).strip()
            ok = r.returncode == 1 and reason in out
            print(f"{'PASS' if ok else 'FAIL'} {label:5s} {name:20s} -> exit {r.returncode}: "
                  f"{out.splitlines()[-1][:110] if out else '(no output)'}")
            failures += 0 if ok else 1
    fixture_bad = _fixture_cases()
    print(f"{'PASS' if not fixture_bad else 'FAIL'} fixture {'':13s} {'real report (veraPDF 1.30.0)':20s} -> "
          + (", ".join(fixture_bad) if fixture_bad else "the reader returns exactly the rules the report names; "
             "a renamed status cannot shrink them; another flavour is refused"))
    failures += len(fixture_bad)
    if failures:
        print(f"\nVERAPDF JSON GUARD FAILED — {failures} case(s) did not refuse the report")
        return 1
    print(f"\nVERAPDF JSON GUARD PASSED — {len(CASES)} bad shapes refused by both screens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
