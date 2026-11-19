#!/usr/bin/env python3
"""Every test in the repository must be WIRED: run by CI, or excused by name with a reason.

This defect has now happened three times — `test_check_kinds`, then `test_mcid_text`/`test_a3b_claim`, and again
with `test_bidi_space` — always the same way: a guard is written, passes locally, and no workflow step runs it.
So this is not another wiring commit; it is the check that makes the next wiring impossible to forget.

A test is wired if its file name appears in `.github/workflows/build-pdf.yml`, or if it is in `EXEMPT` below with
a written reason. An exemption for a file that no longer exists is a failure too: a stale excuse is how a suite
quietly shrinks.

The checker is proven by running it against a fabricated repository (a test file nobody wired) and requiring it
to fail — a guard that has never failed is a guard nobody has tested.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, ".."))
WORKFLOW = os.path.join(PROJ, ".github", "workflows", "build-pdf.yml")
SEARCH_DIRS = ("scripts", "conformance/tests", ".")     # where a test file may live

# name -> why CI must not run it. Empty is the goal: every entry here is a test that runs nowhere else.
EXEMPT: dict[str, str] = {}


def discover(root: str) -> list[str]:
    """Every `test_*.py` in the repository's test locations, as POSIX paths relative to the root."""
    found = []
    for d in SEARCH_DIRS:
        base = os.path.normpath(os.path.join(root, d))
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if name.startswith("test_") and name.endswith(".py") and os.path.isfile(os.path.join(base, name)):
                found.append(os.path.normpath(os.path.join(d, name)).replace(os.sep, "/"))
    return found


def unwired(tests: list[str], workflow: str, exempt: dict[str, str]) -> tuple[list[str], list[str]]:
    """(tests nobody runs, exemptions that no longer name a test). Reads the file's NAME in the workflow."""
    names = {os.path.basename(t) for t in tests}
    missing = [t for t in tests if os.path.basename(t) not in workflow and os.path.basename(t) not in exempt]
    stale = [n for n in exempt if n not in names]
    return missing, stale


def main() -> int:
    with open(WORKFLOW, encoding="utf-8") as fh:
        workflow = fh.read()
    tests = discover(PROJ)
    if not tests:
        print("CI-WIRING GUARD FAILED — no test file found; the search is broken, not the repository")
        return 1
    # comments in the workflow do not run anything: a name that appears only after a `#` is not wired
    live = "\n".join(line.split("#", 1)[0] for line in workflow.splitlines())
    missing, stale = unwired(tests, live, EXEMPT)

    for t in missing:
        print(f"  not wired: {t}")
    for n in stale:
        print(f"  stale exemption: {n} (no such test)")
    print(f"  {len(tests)} test file(s) · {len(tests) - len(missing)} wired · {len(EXEMPT)} exempt")

    # the guard must fail on a repository with an unwired test: otherwise it would pass on the defect it exists for
    caught = unwired(tests + ["scripts/test_nobody_runs_this.py"], live, EXEMPT)[0]
    if "scripts/test_nobody_runs_this.py" not in caught:
        print("CI-WIRING GUARD FAILED — the checker did not flag a fabricated unwired test")
        return 1

    if missing or stale:
        print(f"CI-WIRING GUARD FAILED — {len(missing)} unwired, {len(stale)} stale")
        return 1
    print("CI-WIRING GUARD PASSED — every test file is named by the workflow or excused with a reason")
    return 0


if __name__ == "__main__":
    sys.exit(main())
