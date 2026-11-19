"""The four commands behind `python -m conformance`, wired to the modules that do the work."""
import json
import os
import sys


def run_command(a) -> int:
    from . import ratchet, runner
    try:
        results = runner.run(a.engine, a.cases, a.out, a.readers, getattr(a, "time_repeats", 1))
    except SystemExit as exc:
        print(exc)
        return 2
    js, md = runner.write(results, a.out)
    print("\n" + runner.results_table(results))
    print(f"\nwritten: {js}\n         {md}")
    if getattr(a, "accept", False):
        ratchet.accept(results)
        print("RATCHET ACCEPTED — floors rewritten from this run")
        return 0
    if a.ratchet:
        bad, notes = ratchet.check(results)
        for n in notes:
            print(f"note: {n}")
        if bad:
            print("RATCHET FAILED:\n  " + "\n  ".join(bad))
            return 1
        print("RATCHET HELD — no reader, case or metric below its floor")
    return 0


def certify_command(a) -> int:
    from . import certificate
    try:
        cert = certificate.certify(a.pdf, a.case, a.engine)
    except certificate.CertError as exc:
        print(f"REFUSED — {exc}")
        return 2
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(cert, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print(certificate.human_summary(cert))
    print(f"\nwritten: {a.out}")
    return 0 if cert["verdict"] == "PASS" else 1


def validate_command(a) -> int:
    from . import certificate
    problems = certificate.validate(a.cert, a.pdf)
    if problems:
        print("INVALID CERTIFICATE:\n  " + "\n  ".join(problems))
        return 1
    print("CERTIFICATE VALID — schema, file sha256 and a recomputed verdict that agrees")
    return 0


def selftest_command(a) -> int:
    from . import selftest
    missed = selftest.run(a.engine)
    return 0 if not missed else 1
