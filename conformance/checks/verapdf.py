"""veraPDF, batched: one JVM for many files, the same guard the pipeline uses.

The reader is `scripts/verapdf_json.guard` — the repository's one reader of a veraPDF report, which refuses a
report that did not judge, judged another profile, or whose verdict disagrees with its rules. Nothing here
re-implements that. What is added is batching: 54 cases × 2 flavours × one JVM each would cost more time than
the builds themselves, so the files go in one call and the report's jobs are mapped back by item name.
"""
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.join(REPO, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "scripts"))

from verapdf_json import PROFILE, _key, guard        # noqa: E402  (one reader, one key format)

FLAVOURS = ("ua1", "3b")
_CACHE: dict = {}


class VerapdfError(RuntimeError):
    """The tool failed, or the report is not a judgement — never «clean»."""


def _failed(rule) -> bool:
    return str(rule.get("ruleStatus", "FAILED")) == "FAILED"


def batch(paths: list[str], flavour: str) -> dict:
    """{abs path: [(rule key, description)]} for one flavour; raises if the tool or the report is unusable."""
    if flavour not in PROFILE:
        raise VerapdfError(f"flavour {flavour!r} is not declared (declared: {sorted(PROFILE)})")
    r = subprocess.run(["verapdf", "--flavour", flavour, "--format", "json", *paths],
                       capture_output=True, text=True, timeout=1800)
    if r.returncode not in (0, 1):
        raise VerapdfError(f"verapdf {flavour}: exit {r.returncode} — the tool failed, not the document: "
                           f"{(r.stderr or '')[-300:]}")
    if not r.stdout.strip():
        raise VerapdfError(f"verapdf {flavour}: empty output (exit {r.returncode})")
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise VerapdfError(f"verapdf {flavour}: output is not JSON ({exc})") from None
    guard(data, flavour)                       # the repository's guard, unchanged
    out = {}
    for job in data["report"]["jobs"]:
        details = job.get("itemDetails") or job.get("item") or {}
        name = os.path.realpath(str(details.get("name", "")))
        failing = []
        for v in job.get("validationResult") or []:
            for rule in ((v.get("details") or {}).get("ruleSummaries") or []):
                if _failed(rule):
                    failing.append((_key(rule), str(rule.get("description", ""))[:160]))
        out[name] = failing
    missing = [p for p in (os.path.realpath(x) for x in paths) if p not in out]
    if missing:
        raise VerapdfError(f"verapdf {flavour}: no job for {len(missing)} file(s), e.g. {missing[0]}")
    return out


def failing(path: str, flavour: str, cache: bool = True) -> list[tuple[str, str]]:
    """The failing rules for one file — cached per process, so a certificate does not run veraPDF twice."""
    key = (os.path.realpath(path), flavour)
    if cache and key in _CACHE:
        return _CACHE[key]
    got = batch([path], flavour)[os.path.realpath(path)]
    _CACHE[key] = got
    return got


def version() -> str:
    r = subprocess.run(["verapdf", "--version"], capture_output=True, text=True, timeout=120)
    out = (r.stdout or r.stderr or "").strip().splitlines()
    return out[0].strip() if out else "unknown"
