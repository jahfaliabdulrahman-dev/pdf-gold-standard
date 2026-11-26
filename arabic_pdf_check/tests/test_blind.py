#!/usr/bin/env python3
"""Blind mode acceptance: every planted file is high with its named signal; the clean file is not.

The planted files are built by `scripts/checker_fixtures.py` with the pinned engine — no PDF is committed,
and the fixture cannot drift from its generator. Expectation per file:

  · planted-mupdf-logical        → visual-order   (4 of 5 readers return the opposite order — measured)
  · planted-chrome-raw           → presentation-forms (the raw layer carries the forms)
  · planted-presentation-forms   → presentation-forms
  · planted-no-tounicode         → tounicode-gaps (every drawn code lost its Unicode value)
  · planted-letter-swap          → lexical-validity (letters shaped, order correct, words nonexistent)
  · planted-lam-alef             → lam-alef-transposition (a density; declared `medium`, not `high`)

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
from conformance.checks import lexical                     # noqa: E402

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
    declared = checker_fixtures.PLANTED_LEVEL.get(name, "high")
    check(f"planted:{name}:file-level",
          blind.LEVELS[report["risk"]["file"]["level"]] >= blind.LEVELS[declared],
          f"declared {declared} file={report['risk']['file']['level']} signals={ids}")
    check(f"planted:{name}:named-signal", expected in ids, f"expected {expected}, got {ids}")

clean = blind.check(built["clean"], thresholds)
check("clean:file-not-high", clean["risk"]["file"]["level"] != "high",
      f"file={clean['risk']['file']['level']} signals={[s['id'] for s in clean['signals']]}")
check("tool:lexicon-named", clean["tool"]["lexicon"]["file"] == os.path.basename(lexical.SHIPPED_DATA)
      and len(clean["tool"]["lexicon"]["sha256"]) == 64, str(clean["tool"]["lexicon"]))
baseline = blind.check(built["clean"], thresholds, lexicon_path=lexical.BASELINE_DATA)
check("tool:explicit-lexicon-recorded", baseline["tool"]["lexicon"]["file"] == os.path.basename(lexical.BASELINE_DATA),
      str(baseline["tool"]["lexicon"]))
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
real_read = blind.isolate.read
blind.isolate.read = lambda name, path: (None, real_read(name, path)[1])
try:
    unsupported = blind.check(built["clean"], thresholds)
finally:
    blind.isolate.read = real_read
check("pages-unsupported-declared", all(r["pages"] == "unsupported" for r in unsupported["readers"].values()),
      str({n: r["pages"] for n, r in unsupported["readers"].items()}))
check("pages-unsupported-still-reads", all(r["chars"] > 0 for r in unsupported["readers"].values()),
      str({n: r["chars"] for n, r in unsupported["readers"].items()}))

# The assignment's two-reader test: two judged readers, both failing ⇒ the gap stays high; three passing ⇒
# medium. `recovery_state` is the one rule; the report's `majority.recovery` says which branch ran.
def state(*ratios):
    return blind.recovery_state({f"r{i}": {"ratio": r, "runs": 100} for i, r in enumerate(ratios)}, 0.5)


check("recovered:two-fail", state(0.1, 0.2)[0] is False, str(state(0.1, 0.2)))
check("recovered:three-pass", state(0.9, 0.8, 0.7)[0] is True, str(state(0.9, 0.8, 0.7)))
check("recovered:split", state(0.9, 0.1)[0] is None and state(0.9, 0.1)[1] == "split", str(state(0.9, 0.1)))
check("recovered:one-voter", state(0.9)[0] is None and state(0.9)[1] == "no-voters", str(state(0.9)))
check("majority:one-voter-none", blind.majority_needed(1) is None, str(blind.majority_needed(1)))
check("majority:five-readers-three", blind.majority_needed(5) == 3, str(blind.majority_needed(5)))

# A reader that crashes is named, dropped from the majority, and the file is not clean.
real_read = blind.isolate.read
def crash(name, path):
    if name == "pdfium":
        raise blind.isolate.ReaderFailed("exited 1: boom")
    return real_read(name, path)
blind.isolate.read = crash
try:
    crashed = blind.check(built["clean"], thresholds)
finally:
    blind.isolate.read = real_read
check("reader-failure:named", crashed["failed_readers"].get("pdfium", "").startswith("ReaderFailed"),
      str(crashed.get("failed_readers")))
check("reader-failure:reason", "boom" in crashed["failed_readers"].get("pdfium", ""),
      str(crashed.get("failed_readers")))
check("reader-failure:signal", any(s["id"] == "reader-failure" for s in crashed["signals"]),
      str([s["id"] for s in crashed["signals"]]))
check("reader-failure:not-clean", crashed["risk"]["file"]["level"] != "low",
      crashed["risk"]["file"]["level"])
check("reader-failure:majority-dropped", crashed["majority"]["readers"]["read"] == 4,
      str(crashed["majority"]))

# Examples: no bidi override, no ESC, and a code span that survives a backtick.
examples = blind._examples("نص `مكسور` ‮عكس\x1b[31m", [])
check("examples:no-bidi", "\u202e" not in examples[0]["text"], repr(examples[0]["text"]))
check("examples:no-esc", "\x1b" not in examples[0]["text"], repr(examples[0]["text"]))
from arabic_pdf_check import markdown                    # noqa: E402
span = markdown._code(examples[0]["text"])
check("examples:code-span", span.startswith("``") and span.endswith("``"), span)

# A reader's failure reason is a CLASS in the report, never the exception text (which can carry a local path
# into a customer's document).
check("why-class-drops-path", blind.why_class("ImportError: /Users/secret/libpdfkit.dylib") == "ImportError",
      blind.why_class("ImportError: /Users/secret/libpdfkit.dylib"))

print()
if FAILS:
    print(f"BLIND ACCEPTANCE FAILED — {FAILS}")
    raise SystemExit(1)
print(f"BLIND ACCEPTANCE PASSED — {len(built['planted'])}/{len(built['planted'])} planted at their declared "
      f"level with their named signal; the clean file is not high")
