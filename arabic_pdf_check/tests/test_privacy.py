#!/usr/bin/env python3
"""Privacy as a test, not a sentence.

The checker processes in memory: it opens the file (read-only), and writes nothing — no copy, no temp file,
no log. The report carries the file's hash and size, never its path; the only document text it may carry is
the bounded examples (≤5 per reader, ≤80 characters each). A long line of the document must appear nowhere
in the report, and a write attempt during `check` fails the run.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from arabic_pdf_check import blind                          # noqa: E402
from conformance.readers import available, text_many        # noqa: E402

PDF = os.path.join(REPO, "tests", "vocalised_raw.pdf")
FAILS = []
WRITES = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def _audit(event, args):
    if event == "open":
        path, mode = args[0], args[1]
        if isinstance(mode, str) and any(c in mode for c in "wax+"):
            WRITES.append((str(path), mode))
        elif isinstance(mode, int) and (mode & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND
                                                | os.O_TRUNC)):
            WRITES.append((str(path), f"flags={mode}"))


sys.addaudithook(_audit)
report = blind.check(PDF, json.load(open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"))))
blob = json.dumps(report, ensure_ascii=False)

check("no-write-during-check", not WRITES, str(WRITES[:4]))
check("no-path-in-report", PDF not in blob and os.path.basename(PDF) not in blob, "the report names the file")
check("report-keys-exact", set(report) == {"schema_version", "mode", "file", "tool", "readers",
                                           "missing_readers", "failed_readers", "majority", "fonts",
                                           "signals", "risk", "known_limits", "not_judged"},
      str(sorted(report)))
check("file-block-is-hash-only", set(report["file"]) == {"sha256", "bytes", "pages"}, str(report["file"]))

examples = [e for r in report["readers"].values() for e in r["examples"]]
check("examples-bounded", all(len(e["text"]) <= 80 for e in examples) and
      all(len(r["examples"]) <= 5 for r in report["readers"].values()), f"{len(examples)} example(s)")

# a line longer than the example budget must not appear anywhere in the report
ok, _missing = available()
texts = [text_many(name, [PDF])[0] for name in ok]
candidate = next((ln.strip() for t in texts for ln in t.splitlines() if len(ln.strip()) > 90), None)
if candidate:
    check("long-document-line-not-in-report", candidate not in blob, f"{len(candidate)} chars leaked")
else:
    check("long-document-line-not-in-report", True, "no line over 90 chars in this sample")

print()
if FAILS:
    print(f"PRIVACY FAILED — {FAILS}")
    raise SystemExit(1)
print("PRIVACY PASSED — read-only, hash-only, bounded excerpts")
