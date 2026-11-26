"""Run one reader in its own process, with a timeout, so a crash cannot take the report down.

`blind.check` reads an untrusted file with five C-extension readers. A Python exception is caught by a
`try/except`; a segfault, an abort or a hang is not. This wrapper runs the reader's own `pages_many` /
`text_many` in a fresh interpreter (`conformance.readers._isolated_reader`), starts it in a new process group,
and kills the whole group on timeout — which also kills a `pdftotext` or a Swift child the reader spawned.

The result comes back over an inherited pipe descriptor, never a file: the text of an untrusted document must
not be written to disk by the checker. A drain thread reads the pipe while `communicate()` waits, so a large
page list cannot deadlock on the pipe buffer.

It is used by `blind.check` only. The certificate/reference path runs on the trusted corpus and reads in
process; that boundary is declared in `docs/` and enforced by the checker's tests.
"""
import json
import os
import signal
import subprocess
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHILD = "conformance.readers._isolated_reader"
TIMEOUT = 120
TAIL = 200


class ReaderFailed(RuntimeError):
    """A reader that exited non-zero, crashed, or timed out — named, with a one-line reason."""


def _drain(fd: int, sink: list[bytes]) -> None:
    with os.fdopen(fd, "rb") as fh:
        sink.append(fh.read())


def _run_child(command: list[str], timeout: float) -> subprocess.CompletedProcess:
    """Run a command in its own process group; kill the GROUP on timeout. Kept separate from `read` so the
    isolation test can drive the boundary with a synthetic grandchild instead of a real reader."""
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
    """(pages or None, text) from a fresh process. Raises `ReaderFailed` with a one-line reason.

    The path is made absolute HERE, not trusted from the caller: the child starts with `cwd=REPO`, so a
    relative path would be resolved against the repository and the reader would report a file that exists as
    missing — with a message that blames the reader.
    """
    path = os.path.abspath(path)
    r_fd, w_fd = os.pipe()
    try:
        proc = subprocess.Popen([sys.executable, "-m", CHILD, name, path, str(w_fd)], cwd=REPO,
                                env={**os.environ, "PYTHONPATH": REPO}, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, start_new_session=True, pass_fds=(w_fd,))
    finally:
        os.close(w_fd)                               # the child holds its copy; the parent must close its own
    chunks: list[bytes] = []
    drain = threading.Thread(target=_drain, args=(r_fd, chunks), daemon=True)
    drain.start()
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        drain.join(timeout=2)
        raise ReaderFailed(f"timed out after {timeout:g}s") from None
    drain.join(timeout=5)
    if proc.returncode != 0:
        reason = (err or out or "").strip().splitlines()
        raise ReaderFailed(f"exited {proc.returncode}" + (f": {reason[-1][:TAIL]}" if reason else ""))
    raw = b"".join(chunks)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReaderFailed(f"no result ({type(exc).__name__})") from None
    if not payload.get("ok"):
        raise ReaderFailed(" ".join(str(payload.get("error") or "unknown reader error").split())[:TAIL])
    return payload.get("pages"), payload.get("text", "")
