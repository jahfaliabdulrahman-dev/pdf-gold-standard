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
import subprocess
import sys

from ..checks import metrics

HERE = os.path.dirname(os.path.abspath(__file__))
LIMITS = os.path.join(HERE, "limitations.json")
CONTROLS = os.path.join(HERE, "controls")


class LimitRefused(RuntimeError):
    """A limit without a working control is not a limit — it is an exemption."""


def load() -> list[dict]:
    with open(LIMITS, encoding="utf-8") as fh:
        return json.load(fh)


def controls_dir() -> str:
    return CONTROLS


def run_control(limit: dict) -> dict:
    """Run the control in a fresh process; it prints one JSON object on stdout."""
    script = limit.get("control_script") or ""
    path = os.path.join(CONTROLS, os.path.basename(script))
    if not script or not os.path.exists(path):
        raise LimitRefused(f"{limit['id']}: control script {script!r} does not exist")
    r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=600,
                       cwd=os.path.dirname(HERE))
    if r.returncode != 0:
        raise LimitRefused(f"{limit['id']}: control failed — {(r.stderr or r.stdout).strip()[:300]}")
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise LimitRefused(f"{limit['id']}: control printed no JSON ({exc}): {r.stdout[:200]!r}") from None
    if not out.get("reproduces"):
        raise LimitRefused(f"{limit['id']}: the control no longer reproduces the defect on this reader "
                           f"({out.get('detail')}) — the limit is stale and must not be applied")
    out.setdefault("detail", {})
    return out


_CONTROL_CACHE: dict[str, dict] = {}


def control_data(limit: dict) -> dict:
    """The control's measurement, run once per process. A control cannot pass silently: it raises."""
    if limit["id"] not in _CONTROL_CACHE:
        _CONTROL_CACHE[limit["id"]] = run_control(limit)
    return _CONTROL_CACHE[limit["id"]]


def usable(reader_name: str, reader_version: str, *, run_controls: bool) -> tuple[list[dict], list[str]]:
    """The limits that may be applied to `reader_name`, and the named refusals."""
    ok, refused = [], []
    for limit in load():
        if limit.get("reader") != reader_name:
            continue
        try:
            if not limit.get("control_script"):
                raise LimitRefused(f"{limit['id']}: no control_script — an unproven limit is an exemption")
            if run_controls and reader_version != limit.get("reader_version_measured"):
                control_data(limit)
            ok.append(limit)
        except LimitRefused as exc:
            refused.append(str(exc))
    return ok, refused


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
