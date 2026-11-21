#!/usr/bin/env python3
"""Declared reader BEHAVIOURS — facts a reader exhibits that excuse no metric and must still be named.

`limitations.json` holds limits: predicates that excuse a measured deficit (a reversed digit run, a bidi
decoration). This file holds the other kind: a reader's known behaviour that changes how its output reads
but does not make any metric wrong — PDFium's row order in an RTL key/value table whose value starts with
a Latin letter. A report that hid it would blame the file for the reader's order.

Every entry names the version it was measured on and a control script that reproduces it. The rules are the
same as for limits (and stricter where it matters):
  · no control script, or no file for it → refused by name, never assumed;
  · the control runs HERE, in a fresh process, and must print `reproduces: true`;
  · a different installed reader version re-runs the control; a control that no longer reproduces refuses
    the declaration ("stale declaration") — the truth is the measurement, not this file.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DECLARED = os.path.join(HERE, "declared.json")
CONTROLS = os.path.join(HERE, "controls")


class DeclaredRefused(RuntimeError):
    """A behaviour without a working control is an anecdote — refused by name."""


def load() -> list[dict]:
    with open(DECLARED, encoding="utf-8") as fh:
        return json.load(fh)


def run_control(entry: dict) -> dict:
    script = entry.get("control_script") or ""
    path = os.path.join(CONTROLS, os.path.basename(script))
    if not script or not os.path.exists(path):
        raise DeclaredRefused(f"{entry['id']}: control script {script!r} does not exist")
    r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=600,
                       cwd=os.path.dirname(HERE))
    if r.returncode != 0:
        raise DeclaredRefused(f"{entry['id']}: control failed — {(r.stderr or r.stdout).strip()[:300]}")
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise DeclaredRefused(f"{entry['id']}: control printed no JSON ({exc}): {r.stdout[:200]!r}") from None
    if not out.get("reproduces"):
        raise DeclaredRefused(f"{entry['id']}: the control no longer reproduces the behaviour on this reader "
                              f"({out.get('detail')}) — the declaration is stale and must not be printed")
    out.setdefault("detail", {})
    return out


_CACHE: dict[str, dict] = {}


def control_data(entry: dict) -> dict:
    if entry["id"] not in _CACHE:
        _CACHE[entry["id"]] = run_control(entry)
    return _CACHE[entry["id"]]


def usable(reader_name: str, reader_version: str) -> tuple[list[dict], list[str], list[dict]]:
    """(declarations that hold, named refusals, the control measurements they rest on)."""
    ok, refused, controls = [], [], []
    for entry in load():
        if entry.get("reader") != reader_name:
            continue
        try:
            control = control_data(entry)
            ok.append(entry)
            controls.append(control)
        except DeclaredRefused as exc:
            refused.append(str(exc))
    return ok, refused, controls
