#!/usr/bin/env python3
"""A reader crash or hang is contained: the wrapper kills the process GROUP, not the direct child only.

The audit's item 5 asks for a report that survives a reader exception. A Python exception is the easy half;
a segfault or a `pdftotext` that never returns is the half that kills the process. This test proves the
timeout path kills a grandchild too, and that a missing reader is a named `ReaderFailed`, not a traceback.
"""
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from conformance.readers import isolate                    # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


with tempfile.TemporaryDirectory(prefix="iso-") as tmp:
    pid_file = os.path.join(tmp, "grandchild.pid")
    grandchild = (
        "import os,sys,subprocess,time\n"
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])\n"
        f"open({pid_file!r},'w').write(str(p.pid))\n"
        "p.wait()\n"
    )
    try:
        isolate._run_child([sys.executable, "-c", grandchild], timeout=0.6)
        check("timeout-raises", False, "returned normally")
    except isolate.ReaderFailed as exc:
        check("timeout-raises", "timed out" in str(exc), str(exc))
    time.sleep(0.3)
    pid = int(open(pid_file).read()) if os.path.exists(pid_file) else 0
    alive = False
    if pid:
        try:
            os.kill(pid, 0)
            alive = True
        except ProcessLookupError:
            alive = False
    check("timeout-kills-grandchild", pid > 0 and not alive, f"pid={pid} alive={alive}")

    # A reader that does not exist exits non-zero, and the parent names it instead of raising ImportError.
    try:
        isolate.read("no_such_reader", os.path.join(REPO, "report.pdf"), timeout=30)
        check("missing-reader-refused", False, "returned normally")
    except isolate.ReaderFailed as exc:
        check("missing-reader-refused", "ModuleNotFoundError" in str(exc) or "no_such_reader" in str(exc), str(exc))

print()
if fails:
    print(f"READER ISOLATION FAILED — {fails}")
    raise SystemExit(1)
print("READER ISOLATION PASSED — a timeout kills the group, a missing reader is a named refusal")
