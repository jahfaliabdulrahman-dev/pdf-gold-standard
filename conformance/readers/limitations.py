"""Declared reader limits — narrow, proven, and refused when the proof stops holding.

A limit is never a sentence in a JSON file that excuses whatever it likes. Every entry names a **predicate**
(one of the functions below), a **control script** that produces a file with a producer that is not this
pipeline, and the reader version the defect was measured on. The rules:

  · No control script, or a control that does not exist → the limit is refused by name (never applied).
  · `validate` never runs a control (a certificate must be checkable without producing new facts), but `run`
    and `certify` do: if the installed reader's version differs from `reader_version_measured`, the control is
    re-run, and a control that no longer reproduces the defect refuses the limit ("stale limit").
  · Each predicate is narrow by construction and reports what it excused, so the certificate can print it.

Two predicates, each measured on this machine (2026-11-19):
  reversed_truth_run          MuPDF returns an Arabic-Indic digit run reversed — even on a file MuPDF wrote
  reader_bidi_decorations     pdftotext wraps every RTL line in U+202A…U+202C marks the file does not carry
"""
import json
import os

from ..checks import metrics
from .controls_runner import ControlRefused, control_data as _control_data, run_control as _run_control

HERE = os.path.dirname(os.path.abspath(__file__))
LIMITS = os.path.join(HERE, "limitations.json")
CONTROLS = os.path.join(HERE, "controls")


class LimitRefused(ControlRefused):
    """A limit without a working control is not a limit — it is an exemption."""


def load() -> list[dict]:
    with open(LIMITS, encoding="utf-8") as fh:
        return json.load(fh)


def controls_dir() -> str:
    return CONTROLS


def run_control(limit: dict) -> dict:
    try:
        return _run_control(limit, CONTROLS)
    except ControlRefused as exc:
        raise LimitRefused(str(exc)) from None


def control_data(limit: dict) -> dict:
    try:
        return _control_data(limit, CONTROLS)
    except ControlRefused as exc:
        raise LimitRefused(str(exc)) from None


def usable(reader_name: str, reader_version: str) -> tuple[list[dict], list[str], list[dict]]:
    """(limits to apply, named refusals, the control measurements they rest on).

    The control runs HERE, once per limit, inside the try: a control that stopped reproducing is a named
    refusal (`limitations_refused`), never an exception that escapes as a traceback. The version in the file is
    the version the defect was measured on; when the installed reader differs, the control is re-run and its
    verdict decides — the assignment's «upgrade ⇒ re-run the control» as code, not as a comment.
    """
    ok, refused, controls = [], [], []
    for limit in load():
        if limit.get("reader") != reader_name:
            continue
        try:
            if not limit.get("control_script"):
                raise LimitRefused(f"{limit['id']}: no control_script — an unproven limit is an exemption")
            control = control_data(limit)
            ok.append(limit)
            controls.append(control)
        except LimitRefused as exc:
            refused.append(str(exc))
    return ok, refused, controls


# ---------------------------------------------------------------- predicates
def _reversed_truth_run(truth: str, out: str) -> tuple[int, str]:
    """Excuse only the DEFICIT of a run whose exact reverse is present, and only that deficit."""
    from collections import Counter
    want, have = Counter(metrics.digit_runs(truth)), Counter(metrics.digit_runs(out))
    missing = want - have
    excused = sum(min(n, have.get(r[::-1], 0)) for r, n in missing.items())
    return excused, f"{excused}/{sum(missing.values())} missing run(s) are exact reversals"


def _reader_bidi_decorations(truth: str, out: str, control: dict | None = None) -> tuple[int, str]:
    excess = max(0, metrics.bidi_count(out) - metrics.bidi_count(truth))
    per_line = int((control or {}).get("detail", {}).get("per_line", 0) or 0)
    lines = max(1, len([ln for ln in out.splitlines() if ln.strip()]))
    allowed = min(excess, per_line * lines)
    return allowed, f"{allowed}/{excess} control(s) excused at {per_line}/line over {lines} line(s)"


def apply(limit: dict, truth: str, out: str, result: dict, control: dict | None) -> dict:
    """Excuse the narrow slice this limit names; return a record for `limitations_applied`."""
    pattern = limit["pattern"]
    if pattern == "reversed_truth_run":
        excused, detail = _reversed_truth_run(truth, out)
        from collections import Counter
        want = Counter(metrics.digit_runs(truth))
        if want and excused:
            found = sum((want & Counter(metrics.digit_runs(out))).values())
            result["metrics"]["digit_runs"] = round((found + excused) / sum(want.values()), 6)
    elif pattern == "reader_bidi_decorations":
        excused, detail = _reader_bidi_decorations(truth, out, control)
        if excused:
            result["defects"]["bidi"] = max(0, result["defects"]["bidi"] - excused)
    else:
        raise LimitRefused(f"{limit['id']}: unknown pattern {pattern!r}")
    return {"id": limit["id"], "excused": excused, "detail": detail,
            "reader_version_measured": limit["reader_version_measured"]}
