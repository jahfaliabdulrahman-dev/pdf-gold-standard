"""The four commands behind `python -m conformance`, wired to the modules that do the work."""
import json
import os
import sys


def run_command(a) -> int:
    from . import ratchet, runner
    try:
        results = runner.run(a.engine, a.cases, a.out, a.readers, getattr(a, "time_repeats", 1),
                             run_structure=not getattr(a, "no_structure", False))
    except SystemExit as exc:
        print(exc)
        return 2
    js, md = runner.write(results, a.out)
    print("\n" + runner.results_table(results))
    print(f"\nwritten: {js}\n         {md}")
    if getattr(a, "accept", False):
        ratchet.accept(results, allow_lower=getattr(a, "force", False))
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


def ratchet_command(a) -> int:
    """`accept --from results.json` / `check --from results.json` — the CI loop, on a saved run."""
    import json

    from . import ratchet
    with open(a.source, encoding="utf-8") as fh:
        results = json.load(fh)
    path = a.path or ratchet.FILE
    if a.action == "accept":
        ratchet.accept(results, path, allow_lower=getattr(a, "force", False))
        print(f"RATCHET ACCEPTED — {path}")
        return 0
    bad, notes = ratchet.check(results, path)
    for note in notes:
        print(f"note: {note}")
    if bad:
        print("RATCHET FAILED:")
        for b in bad:
            print(f"  {b}")
        return 1
    print("RATCHET HELD — no reader, case or metric below the floor of its version")
    return 0


def certify_command(a) -> int:
    from . import certificate
    from .corpus.cases import CaseError
    from .readers.limitations import LimitRefused
    truth_text = None
    if getattr(a, "truth", None):
        try:
            # utf-8-sig: a BOM is a byte-order mark, not a character of the customer's text. Keeping it
            # turns a clean file into `exact 0` — the first character of the truth is one nobody typed.
            truth_text = open(a.truth, encoding="utf-8-sig").read()
        except OSError as exc:
            print(f"REFUSED — the truth file cannot be read: {exc}")
            return 2
    try:
        cert = certificate.certify(a.pdf, getattr(a, "case", None), a.engine,
                                   truth_text=truth_text,
                                   truth_name=(getattr(a, "truth_name", None)
                                               or (os.path.basename(a.truth) if truth_text is not None else None)))
    except (certificate.CertError, CaseError, LimitRefused) as exc:
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
    # `--recheck` re-measures the file (tier-1 readers + every structural check); without it, a certificate
    # is checked against itself. The flag existed in the parser but was never passed here — a command that
    # re-validates without re-measuring is not the control its name promises.
    problems = certificate.validate(a.cert, a.pdf, do_recheck=getattr(a, "recheck", False),
                                    truth_path=getattr(a, "truth", None))
    if problems:
        print("INVALID CERTIFICATE:\n  " + "\n  ".join(problems))
        return 1
    print("CERTIFICATE VALID — schema, file sha256 and a recomputed verdict that agrees"
          + (" — and the file re-measured" if getattr(a, "recheck", False) else ""))
    return 0


def selftest_command(a) -> int:
    from . import selftest
    missed = selftest.run(a.engine)
    return 0 if not missed else 1
