"""The one control runner — a declaration without a live control is an exemption, not a fact.

Both registries use it:
  · `limitations.json` — a limit excuses a measured deficit (a reversed digit run, a bidi decoration);
  · `declared.json`    — a behaviour changes how a reader's output reads and excuses no metric (PDFium's
    RTL row order).

The two registries stay separate because their `usable()` returns mean different things (`apply()` has no
meaning for a behaviour), but the proof machinery is one: same subprocess, same `reproduces: true` rule, same
per-process cache. Two copies would drift into one registry that passes and one that does not.
"""
import json
import os
import subprocess
import sys


class ControlRefused(RuntimeError):
    """A declaration whose control cannot prove it is refused by name."""


def run_control(entry: dict, controls_dir: str) -> dict:
    """Run the control in a fresh process; it prints one JSON object on stdout."""
    script = entry.get("control_script") or ""
    path = os.path.join(controls_dir, os.path.basename(script))
    if not script or not os.path.exists(path):
        raise ControlRefused(f"{entry['id']}: control script {script!r} does not exist")
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(controls_dir)))
    r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=600,
                       cwd=repo_root)
    if r.returncode != 0:
        raise ControlRefused(f"{entry['id']}: control failed — {(r.stderr or r.stdout).strip()[:300]}")
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise ControlRefused(f"{entry['id']}: control printed no JSON ({exc}): {r.stdout[:200]!r}") from None
    if not out.get("reproduces"):
        raise ControlRefused(f"{entry['id']}: the control no longer reproduces the behaviour on this reader "
                             f"({out.get('detail')}) — the declaration is stale and must not be applied")
    out.setdefault("detail", {})
    return out


_CACHE: dict[str, dict] = {}


def control_data(entry: dict, controls_dir: str) -> dict:
    """The control's measurement, run once per process. A control cannot pass silently: it raises."""
    if entry["id"] not in _CACHE:
        _CACHE[entry["id"]] = run_control(entry, controls_dir)
    return _CACHE[entry["id"]]
