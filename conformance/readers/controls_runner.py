"""The one control runner — a declaration without a live control is an exemption, not a fact.

Both registries use it:
  · `limitations.json` — a limit excuses a measured deficit (a reversed digit run, a bidi decoration);
  · `declared.json`    — a behaviour changes how a reader's output reads and excuses no metric (PDFium's
    RTL row order).

The two registries stay separate because their `usable()` returns mean different things (`apply()` has no
meaning for a behaviour), but the proof machinery is one: same subprocess, same `reproduces: true` rule.

**The check path reads a stored control; it never launches Chrome or Swift.** A control result is stored under
`$ARABIC_PDF_CHECK_CACHE` (or `$XDG_CACHE_HOME/arabic-pdf-check`, default `~/.cache/arabic-pdf-check`) and is
keyed by the reader, its live version, the control script's SHA-256, a fingerprint of the repository code and
fonts the control imports, the platform, and this schema. `arabic-pdf-check controls --refresh` is the only
command that runs them; a missing or stale key is a named refusal, never a silent exemption.

The certificate/reference path passes `mode="live"`: a certificate is a claim about this run, so it may pay
for the control. `blind.check` passes `mode="cached"`: a customer's file must not wait for a GUI tool.
"""
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

from ..hashing import sha256_file

SCHEMA = "arabic-pdf-check-control/1"


class ControlRefused(RuntimeError):
    """A declaration whose control cannot prove it is refused by name."""


def _one_line(text, limit: int = 300) -> str:
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").split())[:limit]


def cache_root() -> str:
    root = os.environ.get("ARABIC_PDF_CHECK_CACHE")
    if not root:
        base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        root = os.path.join(base, "arabic-pdf-check")
    return os.path.join(root, "controls")


def repo_root(controls_dir: str) -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(controls_dir))))


_FINGERPRINT: dict[str, str] = {}


def repo_fingerprint(controls_dir: str) -> str:
    """A hash of every repo file a control imports, its Chrome pin, and the fonts it renders with.

    The reader version alone is not enough: PR-1 changes `normalize`, the control scripts import it, and a
    cache keyed only by (reader, version, script) would serve a result proved against the old code. The
    fingerprint is computed once per process; the controls are a handful of files, and the fonts are a few
    megabytes read once, not per check.
    """
    root = os.path.dirname(os.path.abspath(controls_dir))
    key = root
    if key in _FINGERPRINT:
        return _FINGERPRINT[key]
    repo = repo_root(controls_dir)
    h = hashlib.sha256()
    files = []

    def walk(directory: str):
        for name in sorted(os.listdir(directory)):
            path = os.path.join(directory, name)
            if name == "__pycache__":
                continue
            if os.path.isdir(path):
                walk(path)
            elif name.endswith((".py", ".json")):
                files.append(path)
    walk(os.path.join(repo, "conformance"))
    for extra in ("chrome_pin.py",):
        path = os.path.join(repo, extra)
        if os.path.exists(path):
            files.append(path)
    fonts = os.path.join(repo, "fonts")
    if os.path.isdir(fonts):
        for name in sorted(os.listdir(fonts)):
            if name.endswith((".woff2", ".ttf", ".otf")):
                files.append(os.path.join(fonts, name))
    for path in sorted(set(files)):
        h.update(os.path.relpath(path, repo).encode("utf-8"))
        h.update(b"\0")
        h.update(sha256_file(path).encode("ascii"))
    _FINGERPRINT[key] = h.hexdigest()
    return _FINGERPRINT[key]


def control_key(entry: dict, controls_dir: str, reader_name: str, reader_version: str) -> str:
    script = entry.get("control_script") or ""
    path = os.path.join(controls_dir, os.path.basename(script))
    script_sha = sha256_file(path) if script and os.path.exists(path) else "-"
    parts = [SCHEMA, reader_name or entry.get("reader", ""), reader_version, script_sha,
             repo_fingerprint(controls_dir), platform.platform(),
             f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def run_control(entry: dict, controls_dir: str) -> dict:
    """Run the control in a fresh process; it prints one JSON object on stdout."""
    script = entry.get("control_script") or ""
    path = os.path.join(controls_dir, os.path.basename(script))
    if not script or not os.path.exists(path):
        raise ControlRefused(f"{entry['id']}: control script {script!r} does not exist")
    repo = repo_root(controls_dir)
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=600,
                           cwd=repo)
    except subprocess.TimeoutExpired:
        raise ControlRefused(f"{entry['id']}: control timed out (600 s)") from None
    except OSError as exc:
        raise ControlRefused(f"{entry['id']}: control could not start — {type(exc).__name__}") from None
    if r.returncode != 0:
        raise ControlRefused(f"{entry['id']}: control failed — {_one_line(r.stderr or r.stdout)}")
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise ControlRefused(f"{entry['id']}: control printed no JSON ({_one_line(exc)})") from None
    if not isinstance(out, dict) or not isinstance(out.get("reproduces"), bool):
        raise ControlRefused(f"{entry['id']}: control printed no `reproduces` boolean")
    out.setdefault("detail", {})
    if not out["reproduces"]:
        raise ControlRefused(f"{entry['id']}: the control no longer reproduces the behaviour on this reader "
                             f"({_one_line(out.get('detail'))}) — the declaration is stale and must not be applied")
    return out


def _write(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="control-", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _read(path: str, entry: dict, key: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlRefused(f"{entry['id']}: stored control is unreadable ({_one_line(exc)}) — "
                             "run `arabic-pdf-check controls --refresh`") from None
    if (not isinstance(payload, dict) or payload.get("schema") != SCHEMA
            or payload.get("key") != key or not isinstance(payload.get("reproduces"), bool)):
        raise ControlRefused(f"{entry['id']}: stored control is stale or malformed — "
                             "run `arabic-pdf-check controls --refresh`")
    if not payload["reproduces"]:
        raise ControlRefused(f"{entry['id']}: the stored control does not reproduce "
                             f"({_one_line(payload.get('detail'))}) — run `arabic-pdf-check controls --refresh`")
    control = payload.get("control")
    if not isinstance(control, dict) or control.get("reproduces") is not True:
        raise ControlRefused(f"{entry['id']}: stored control carries no measurement — "
                             "run `arabic-pdf-check controls --refresh`")
    return control


_MEM: dict[tuple[str, str], dict] = {}


def control_data(entry: dict, controls_dir: str, reader_name: str = "", reader_version: str = "",
                 mode: str = "live") -> dict:
    """The control's measurement.

    `mode="live"`    — run it now (the certificate/reference path).
    `mode="cached"`  — read the stored result, or refuse by name; never launch the tool (the check path).
    `mode="refresh"` — run it now, store it (the `controls --refresh` command), even a non-reproducing result.
    """
    if mode not in ("live", "cached", "refresh"):
        raise ControlRefused(f"{entry['id']}: unknown control mode {mode!r}")
    reader = reader_name or entry.get("reader", "")
    version = reader_version or entry.get("reader_version_measured", "")
    key = control_key(entry, controls_dir, reader, version)
    if mode == "live":
        return run_control(entry, controls_dir)
    path = os.path.join(cache_root(), key + ".json")
    if mode == "cached":
        mem = _MEM.get((entry["id"], key))
        if mem is None:
            mem = _read(path, entry, key)
            _MEM[(entry["id"], key)] = mem
        return mem
    # refresh
    script = entry.get("control_script") or ""
    script_path = os.path.join(controls_dir, os.path.basename(script))
    written = {
        "schema": SCHEMA, "key": key, "reader": reader, "reader_version": version,
        "script_sha256": sha256_file(script_path) if script and os.path.exists(script_path) else "-",
        "repo_fingerprint": repo_fingerprint(controls_dir),
        "platform": platform.platform(),
        "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        control = run_control(entry, controls_dir)
    except ControlRefused as exc:
        written.update({"reproduces": False, "detail": {"error": _one_line(exc)}})
        _write(path, written)
        _MEM.pop((entry["id"], key), None)
        raise
    written.update({"reproduces": True, "detail": control.get("detail", {}), "control": control})
    _write(path, written)
    _MEM[(entry["id"], key)] = control
    return control
