"""The one reader of a veraPDF report — and the shape a report must have before its verdict is believed.

Two things are checked before any rule set is taken from a report (B6, tightened after review):

  · the report says it JUDGED something — a job, no `taskException`, a `validationResult` with a boolean
    `compliant` for the profile we asked for (a verdict for PDF/A-3b is not a verdict for PDF/UA-1);
  · the verdict and the rules AGREE — `compliant=false` with no failing rule, or `compliant=true` while
    naming failing rules, is a report whose silence would otherwise read as «clean» (an empty set is exactly
    what a clean document looks like).

`failing_rules` is the only place the tool's JSON is turned into a failing set; the gate and the claim probe
both call it (the B5 message promised one reader, and the review found two).
"""
import json
import subprocess

# The profile veraPDF must name for each flavour we ask for. The match is exact, against
# f"{PROFILE[flavour]} validation profile": «PDF/UA-1» must not match «PDF/UA-10…», and «PDF/A-4» must not
# match «PDF/A-4f» — a verdict for another profile is not this one.
PROFILE = {"3b": "PDF/A-3b", "4": "PDF/A-4", "4f": "PDF/A-4f", "ua1": "PDF/UA-1"}


def _run(path: str, flavour: str) -> dict:
    r = subprocess.run(["verapdf", "--flavour", flavour, "--format", "json", path],
                       capture_output=True, text=True, timeout=900)
    # A crash is not a clean file: exit 1 is «violations found», anything else is the tool failing.
    if r.returncode not in (0, 1):
        raise SystemExit(f"verapdf {flavour}: exit {r.returncode} — the tool failed, not the document: "
                         f"{r.stderr[-300:]}")
    if not r.stdout.strip():
        raise SystemExit(f"verapdf {flavour}: empty JSON output (exit {r.returncode}): {r.stderr[-300:]}")
    return json.loads(r.stdout)


def _failed(rule) -> bool:
    return str(rule.get("ruleStatus", "FAILED")) == "FAILED"


def guard(data: dict, flavour: str) -> None:
    jobs = ((data or {}).get("report") or {}).get("jobs")
    if not jobs:
        raise SystemExit(f"verapdf {flavour}: the report has no jobs — nothing was judged, so an empty set "
                         "proves nothing")
    if flavour not in PROFILE:
        raise SystemExit(f"verapdf: flavour «{flavour}» is not declared — declared: {sorted(PROFILE)}")
    want = PROFILE[flavour]
    for n, job in enumerate(jobs, 1):
        if job.get("taskException"):
            raise SystemExit(f"verapdf {flavour}: job {n} raised a taskException "
                             f"({str(job['taskException'])[:160]}) — the tool did not judge the file")
        results = job.get("validationResult")
        if not isinstance(results, list) or not results:
            raise SystemExit(f"verapdf {flavour}: job {n} carries no validationResult — the report has no verdict")
        if not all(isinstance(v, dict) and isinstance(v.get("compliant"), bool) for v in results):
            raise SystemExit(f"verapdf {flavour}: job {n} has a validationResult without a boolean «compliant» "
                             "— the report carries a verdict we cannot read")
        for v in results:
            name = str(v.get("profileName", ""))
            # Exact, not a prefix: «PDF/UA-1» would also match «PDF/UA-10…» (review N7).
            if name != f"{want} validation profile":
                raise SystemExit(f"verapdf {flavour}: job {n} was judged against «{name}», not the {flavour} "
                                 f"profile ({want} validation profile) — a verdict for another profile is not this one")
            failed = [x for x in ((v.get("details") or {}).get("ruleSummaries") or []) if _failed(x)]
            if v["compliant"] is False and not failed:
                raise SystemExit(f"verapdf {flavour}: job {n} says NON-compliant but names no failing rule — "
                                 "the verdict and the rules disagree")
            if v["compliant"] is True and failed:
                raise SystemExit(f"verapdf {flavour}: job {n} says compliant while naming "
                                 f"{len(failed)} failing rule(s) — the verdict and the rules disagree")


def _key(rule) -> str:
    clause, test = rule.get("clause"), rule.get("testNumber")
    return str(f"{clause}-{test}" if clause and test else (rule.get("ruleId") or clause))


def read_report(data: dict, flavour: str) -> list[tuple[str, str]]:
    """(rule, description) from an ALREADY PARSED report — the same guard, no subprocess (a saved report is
    a fixture, and a fixture is what makes the shape testable without veraPDF installed)."""
    guard(data, flavour)
    out = []
    for job in data["report"]["jobs"]:
        for v in job["validationResult"]:
            for rule in ((v.get("details") or {}).get("ruleSummaries") or []):
                if _failed(rule):
                    out.append((_key(rule), str(rule.get("description", ""))[:160]))
    return out


def failing_rules_detail(path: str, flavour: str) -> list[tuple[str, str]]:
    """(clause-testNumber, description) for every failing rule — the one reader, for both screens.

    clause+test, not the clause: a new failing test inside a clause that already fails was invisible to a
    clause-level set. A rule without a test number keeps its clause (PDF/UA identification is clause "5").
    """
    return read_report(_run(path, flavour), flavour)


def failing_rules(path: str, flavour: str) -> set[str]:
    """The rule keys this flavour reports as FAILED, at clause-testNumber level."""
    return {k for k, _ in failing_rules_detail(path, flavour)}
