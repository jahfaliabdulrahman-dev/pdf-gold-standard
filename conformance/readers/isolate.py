"""Run one reader in its own process, with a timeout, so a crash cannot take the report down.

`blind.check` reads an untrusted file with five C-extension readers. A Python exception is caught by a
`try/except`; a segfault, an abort or a hang is not. This wrapper runs the reader's own `pages_many` /
`text_many` in a fresh interpreter (`conformance.readers._isolated_reader`), starts it in a new process group,
and kills the whole group on timeout — which also kills a `pdftotext` or a Swift child the reader spawned.

It is used by `blind.check` only. The certificate/reference path runs on the trusted corpus and reads in
process; that boundary is declared in `docs/` and enforced by the checker's tests.
"""
import json
import os
import signal
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHILD = "conformance.readers._isolated_reader"
TIMEOUT = 120


class ReaderFailed(RuntimeError):
    """A reader that exited non-zero, crashed, or timed out — named, with a one-line reason."""


def _run_child(command: list[str], timeout: float) -> subprocess.CompletedProcess:
    proc = subprocess.Popen(command, cwd=REPO, env={**os.environ, "PYTHONPATH": REPO},
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise ReaderFailed(f"timed out after {timeout:g}s") from None
    return subprocess.CompletedProcess(command, proc.returncode, out, err)


def read(name: str, path: str, timeout: float = TIMEOUT) -> tuple[list[str] | None, str]:
    """(pages or None, text) from a fresh process. Raises `ReaderFailed` with a one-line reason."""
    with tempfile.TemporaryDirectory(prefix="reader-run-") as tmp:
        out_path = os.path.join(tmp, "out.json")
        r = _run_child([sys.executable, "-m", CHILD, name, path, out_path], timeout)
        if r.returncode != 0:
            reason = (r.stderr or r.stdout or "").strip().splitlines()
            raise ReaderFailed(f"exited {r.returncode}" + (f": {reason[-1][:200]}" if reason else ""))
        try:
            with open(out_path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise ReaderFailed(f"no result ({type(exc).__name__})") from None
    if not payload.get("ok"):
        raise ReaderFailed(" ".join(str(payload.get("error") or "unknown reader error").split())[:200])
    return payload.get("pages"), payload.get("text", "")
