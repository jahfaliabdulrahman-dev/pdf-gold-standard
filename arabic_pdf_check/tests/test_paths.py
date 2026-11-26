#!/usr/bin/env python3
"""A relative path is the first thing a customer types; it must mean the file they are looking at.

Every reader runs in a child process started with `cwd=REPO` (`conformance/readers/isolate.py`). An unresolved
`invoice.pdf` was therefore opened as `REPO/invoice.pdf` by four of five readers: they failed, the one that
survives (`pdfkit`, in-process) voted alone, and a clean file was reported **high** — a false accusation produced
by the product's own wrapper, on the first command anyone types.

The control is the same file by absolute path: same readers, same file verdict, same file-level signals. A
one-sided assertion would pass on a build where both paths are broken in the same way.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FIXTURE = os.path.join(REPO, "tests", "vocalised_raw.pdf")

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def run(path: str, cwd: str) -> dict:
    out = os.path.join(cwd, "report.json")
    env = {**os.environ, "PYTHONPATH": REPO}
    r = subprocess.run([sys.executable, "-m", "arabic_pdf_check", "check", path, "-o", out],
                       cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit(f"check failed on {path!r}: {r.returncode}\n{(r.stderr or r.stdout)[-800:]}")
    with open(out, encoding="utf-8") as fh:
        return json.load(fh)


def shape(report: dict) -> dict:
    """Only what a customer acts on: who read, the FILE verdict, and the file-level signals."""
    return {
        "readers": sorted(report.get("readers") or []),
        "file_level": ((report.get("risk") or {}).get("file") or {}).get("level"),
        "file_signals": sorted(s["id"] for s in (report.get("signals") or [])
                               if s.get("cause") == "file" and s.get("level") in ("high", "medium")),
        "failed": {k: str(v)[:80] for k, v in (report.get("failed_readers") or {}).items()},
    }


work = tempfile.mkdtemp(prefix="relative-path-")
try:
    shutil.copy(FIXTURE, os.path.join(work, "invoice.pdf"))
    absolute = shape(run(os.path.join(work, "invoice.pdf"), work))
    relative = shape(run("invoice.pdf", work))

    check("every-available-reader-reads-a-relative-path", relative["readers"] == absolute["readers"],
          f"relative {relative['readers']} vs absolute {absolute['readers']}")
    check("the-file-verdict-is-the-same", relative["file_level"] == absolute["file_level"],
          f"relative {relative['file_level']} vs absolute {absolute['file_level']}")
    check("the-file-level-signals-are-the-same", relative["file_signals"] == absolute["file_signals"],
          f"relative {relative['file_signals']} vs absolute {absolute['file_signals']}")
    # The failure this test exists for: a reader that could not find the file the customer named.
    check("no-reader-failed-to-find-the-file",
          not any(("FileNotFoundError" in why or "No such file" in why) for why in relative["failed"].values()),
          str(relative["failed"]))
finally:
    shutil.rmtree(work, ignore_errors=True)

print()
if fails:
    print(f"RELATIVE PATH FAILED — {len(fails)}: {', '.join(fails)}")
    raise SystemExit(1)
print("RELATIVE PATH PASSED — the file a customer names is the file every reader opens")
