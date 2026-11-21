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

from .controls_runner import ControlRefused, control_data as _control_data, run_control as _run_control

HERE = os.path.dirname(os.path.abspath(__file__))
DECLARED = os.path.join(HERE, "declared.json")
CONTROLS = os.path.join(HERE, "controls")


class DeclaredRefused(ControlRefused):
    """A behaviour without a working control is an anecdote — refused by name."""


def load() -> list[dict]:
    with open(DECLARED, encoding="utf-8") as fh:
        return json.load(fh)


def run_control(entry: dict) -> dict:
    try:
        return _run_control(entry, CONTROLS)
    except ControlRefused as exc:
        raise DeclaredRefused(str(exc)) from None


def control_data(entry: dict) -> dict:
    try:
        return _control_data(entry, CONTROLS)
    except ControlRefused as exc:
        raise DeclaredRefused(str(exc)) from None


def usable(reader_name: str, reader_version: str) -> tuple[list[dict], list[str], list[dict]]:
    """(declarations that hold, named refusals, the control measurements they rest on).

    The version in the file is the version the behaviour was MEASURED on; the installed reader's version is
    attached to every entry as `reader_version_now`, and a mismatch is marked. The control decides whether the
    declaration still holds — printing the old version as if it were measured now is what this field prevents.
    """
    ok, refused, controls = [], [], []
    for entry in load():
        if entry.get("reader") != reader_name:
            continue
        try:
            control = control_data(entry)
            entry = dict(entry)
            entry["reader_version_now"] = reader_version
            entry["version_mismatch"] = entry.get("reader_version_measured") != reader_version
            ok.append(entry)
            controls.append(control)
        except DeclaredRefused as exc:
            refused.append(str(exc))
    return ok, refused, controls
