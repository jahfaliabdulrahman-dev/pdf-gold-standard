#!/usr/bin/env python3
"""Blind mode acceptance: the four planted files are high with their named signal; the clean file is not.

The planted files are built by `scripts/checker_fixtures.py` with the pinned engine — no PDF is committed,
and the fixture cannot drift from its generator. Expectation per file:

  · planted-mupdf-logical        → visual-order   (4 of 5 readers return the opposite order — measured)
  · planted-chrome-raw           → presentation-forms (the raw layer carries the forms)
  · planted-presentation-forms   → presentation-forms
  · planted-no-tounicode         → tounicode-gaps (every drawn code lost its Unicode value)

A clean file may have a READER at high risk (pdfminer returns the stored order on our files — a true
finding about that reader); its `risk.file.level` must never be high. That is the assignment's
«تُعلَن ولا تُحسب على الملف» as a test.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import checker_fixtures                                    # noqa: E402
from arabic_pdf_check import blind                         # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


if not os.environ.get("CHROME_PATH"):
    print("REFUSED — CHROME_PATH is unset: the fixtures are built with the pinned engine, and a fixture "
          "built by another engine would measure a different pipeline")
    raise SystemExit(1)

built = checker_fixtures.build_all(tempfile.mkdtemp(prefix="blind-accept-"))
thresholds = json.load(open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"), encoding="utf-8"))

for name, path in built["planted"].items():
    report = blind.check(path, thresholds)
    ids = [s["id"] for s in report["signals"]]
    expected = checker_fixtures.PLANTED[name]
    check(f"planted:{name}:file-high", report["risk"]["file"]["level"] == "high",
          f"file={report['risk']['file']['level']} signals={ids}")
    check(f"planted:{name}:named-signal", expected in ids, f"expected {expected}, got {ids}")

clean = blind.check(built["clean"], thresholds)
check("clean:file-not-high", clean["risk"]["file"]["level"] != "high",
      f"file={clean['risk']['file']['level']} signals={[s['id'] for s in clean['signals']]}")
reader_high = {n: r["risk"] for n, r in clean["readers"].items() if r["risk"] == "high"}
check("clean:reader-highs-are-reader-caused",
      all(s["cause"] == "reader" for r in clean["readers"].values()
          for s in r["signals"] if s["level"] == "high"),
      json.dumps(reader_high))

for name, r in clean["readers"].items():
    check(f"examples:{name}:bounded",
          len(r["examples"]) <= 5 and all(len(e["text"]) <= 80 for e in r["examples"]),
          f"{len(r['examples'])} example(s)")

# Thresholds are CONSUMED, not printed: raise the presentation-forms threshold above the fixture's share and
# its signal must disappear. (A string-search test could pass on a commented-out line; this cannot.)
raised = json.loads(json.dumps(thresholds))
raised["values"]["presentation_forms"]["value"] = 1.0
rep = blind.check(built["planted"]["planted-presentation-forms"], raised)
check("thresholds-consumed", "presentation-forms" not in [s["id"] for s in rep["signals"]],
      str([s["id"] for s in rep["signals"]]))

# A reader that reads but cannot name its pages is DECLARED, never reported as a reading of zero characters.
real_pages_many = blind.pages_many
blind.pages_many = lambda name, paths: None
try:
    unsupported = blind.check(built["clean"], thresholds)
finally:
    blind.pages_many = real_pages_many
check("pages-unsupported-declared", all(r["pages"] == "unsupported" for r in unsupported["readers"].values()),
      str({n: r["pages"] for n, r in unsupported["readers"].items()}))
check("pages-unsupported-still-reads", all(r["chars"] > 0 for r in unsupported["readers"].values()),
      str({n: r["chars"] for n, r in unsupported["readers"].items()}))

print()
if FAILS:
    print(f"BLIND ACCEPTANCE FAILED — {FAILS}")
    raise SystemExit(1)
print("BLIND ACCEPTANCE PASSED — 4/4 planted high with their named signal; the clean file is not high")
