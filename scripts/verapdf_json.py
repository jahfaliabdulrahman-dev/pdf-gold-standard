"""The shape a veraPDF report must have before its silence counts as «no failing rule».

An empty failing set looks exactly like a clean document, so a report that judged nothing used to pass both
screens: a job that raised a `taskException`, or a job with no `validationResult`, produced zero rules and
the set diff found no new rule. The guard refuses such a report as an INPUT — exit 1 with the reason —
instead of reading «the tool did not judge» as «the tool found nothing».

Shape held here (veraPDF 1.30, measured on a real report):
  report.jobs[*].validationResult[*] has a boolean `compliant`, and no job carries a `taskException`.
"""
import json
import subprocess


def guard(data: dict, flavour: str) -> None:
    jobs = ((data or {}).get("report") or {}).get("jobs")
    if not jobs:
        raise SystemExit(f"verapdf {flavour}: the report has no jobs — nothing was judged, so an empty set "
                         "proves nothing")
    for n, job in enumerate(jobs, 1):
        if job.get("taskException"):
            raise SystemExit(f"verapdf {flavour}: job {n} raised a taskException "
                             f"({str(job['taskException'])[:160]}) — the tool did not judge the file")
        results = job.get("validationResult")
        if not isinstance(results, list) or not results:
            raise SystemExit(f"verapdf {flavour}: job {n} carries no validationResult — the report has no verdict")
        if not any(isinstance(v, dict) and isinstance(v.get("compliant"), bool) for v in results):
            raise SystemExit(f"verapdf {flavour}: job {n} has no validationResult with a boolean «compliant» "
                             "— the report carries a verdict we cannot read")


def failing_rules(path: str, flavour: str) -> set[str]:
    """The rule keys this flavour reports as FAILED, at clause-testNumber level.

    clause+test, not the clause: a new failing test inside a clause that already fails was invisible to a
    clause-level set. A rule without a test number keeps its clause (PDF/UA identification is clause "5").
    """
    r = subprocess.run(["verapdf", "--flavour", flavour, "--format", "json", path],
                       capture_output=True, text=True, timeout=900)
    # A crash is not a clean file: exit 1 is «violations found», anything else is the tool failing.
    if r.returncode not in (0, 1):
        raise SystemExit(f"verapdf {flavour}: exit {r.returncode} — the tool failed, not the document: "
                         f"{r.stderr[-300:]}")
    if not r.stdout.strip():
        raise SystemExit(f"verapdf {flavour}: empty JSON output (exit {r.returncode}): {r.stderr[-300:]}")
    data = json.loads(r.stdout)
    guard(data, flavour)
    out = set()

    def walk(o):
        if isinstance(o, dict):
            if o.get("ruleStatus") == "FAILED":
                clause, test = o.get("clause"), o.get("testNumber")
                rid = f"{clause}-{test}" if clause and test else (o.get("ruleId") or clause)
                if rid:
                    out.add(str(rid))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return out
