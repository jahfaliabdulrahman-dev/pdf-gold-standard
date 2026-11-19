"""conformance CLI — run · certify · validate · selftest · manifest.

  python3 -m conformance manifest --write          # derive corpus/MANIFEST.json from the cases
  python3 -m conformance run --engine chrome [--cases all|<id>…] --out DIR
  python3 -m conformance certify FILE --case ID -o FILE.cert.json
  python3 -m conformance validate FILE.cert.json FILE.pdf
  python3 -m conformance selftest [--engine chrome]
"""
import argparse
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="conformance", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("manifest", help="derive corpus/MANIFEST.json (or check it)")
    m.add_argument("--write", action="store_true", help="rewrite the file; without it, only report drift")
    m.add_argument("--check", action="store_true", help="exit 1 when the stored manifest is not derived")

    r = sub.add_parser("run", help="build the corpus with one engine and measure every declared reader")
    r.add_argument("--engine", default="chrome", choices=["chrome", "chrome-raw", "typst", "weasyprint"])
    r.add_argument("--cases", nargs="*", default=["all"])
    r.add_argument("--out", default="/tmp/conformance")
    r.add_argument("--readers", nargs="*", default=None, help="subset of reader names (default: all)")
    r.add_argument("--ratchet", action="store_true", help="compare the run to ratchet.json (exit 1 on a drop)")
    r.add_argument("--accept", action="store_true", help="record this run as the new floors (manual, per commit)")
    r.add_argument("--time-repeats", type=int, default=1, help="builds per case for the median time (E uses 3)")

    c = sub.add_parser("certify", help="write a certificate for one file against one case")
    c.add_argument("pdf")
    c.add_argument("--case", required=True)
    c.add_argument("--engine", default="unknown", choices=["chrome", "chrome-raw", "unknown"],
                   help="the producer you declare for this file (recorded as a declaration, not a measurement)")
    c.add_argument("-o", "--out", required=True)

    v = sub.add_parser("validate", help="validate a certificate against its file (schema, sha, verdict)")
    v.add_argument("cert")
    v.add_argument("pdf")

    s = sub.add_parser("selftest", help="planted mutations: every check must be seen failing")
    s.add_argument("--engine", default="chrome", choices=["chrome", "chrome-raw", "typst", "weasyprint"])

    a = ap.parse_args(argv)
    if a.cmd == "manifest":
        from .corpus import manifest, coverage, cases
        if a.write:
            man = manifest.write()
            print(f"MANIFEST WRITTEN — {man['total']} cases · {coverage.summary(cases.load_all())}")
            return 0
        drift = manifest.problems()
        print("MANIFEST DRIFT:\n  " + "\n  ".join(drift) if drift else "MANIFEST OK — exactly what the cases derive")
        return 1 if drift else 0
    from .cli import run_command, certify_command, validate_command, selftest_command
    if a.cmd == "run":
        return run_command(a)
    if a.cmd == "certify":
        return certify_command(a)
    if a.cmd == "validate":
        return validate_command(a)
    if a.cmd == "selftest":
        return selftest_command(a)
    return 2


if __name__ == "__main__":
    sys.exit(main())
