#!/usr/bin/env python3
"""The lam-alef file rule: a density, judged by a majority of the readers that have enough runs to be rate-able.

The population this rule was derived from is the owner's private lesson (21 transpositions in 473–488 runs =
43 per 1000) against a clean maximum of 0.88 per 1000 (report.pdf quoting the defect itself once). These
checks drive `blind.lam_alef_majority` — the function the report calls — with those numbers, and with the
cases that must NOT fire: a single quoted example, a short reading, a two-two split.
"""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, REPO)

from arabic_pdf_check import blind                                              # noqa: E402

RATE = 6.2          # the shipped value; test_lam_alef_separation re-derives it from the artifact
MIN_RUNS = 200

passed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if not condition:
        print(f"FAIL {name} — {detail}")
        raise SystemExit(1)
    passed += 1
    print(f"PASS {name}")


def readers(**kw) -> dict:
    """{reader: (lam_alef, runs)} -> the shape `lexical.validity` returns, which is what `check` passes in."""
    return {name: {"lam_alef": lam, "runs": runs} for name, (lam, runs) in kw.items()}


def main() -> int:
    # the measured clean reading: one quoted example in 1140 runs — the report itself
    clean = readers(pdfium=(1, 1140), pdfkit=(1, 1140), mupdf=(1, 1140), poppler=(1, 1137), pdfminer=(0, 1121))
    rates, over, need = blind.lam_alef_majority(clean, RATE, MIN_RUNS)
    check("clean: a single quoted example is below the density", over == {} and need == 3 and len(rates) == 5,
          f"{over} {need} {len(rates)}")

    # the measured broken reading: 21 in ~480 runs, three readers; PDFKit 0, PDFMiner reads reversed
    broken = readers(pdfium=(21, 481), pdfkit=(0, 485), mupdf=(21, 487), poppler=(21, 488), pdfminer=(0, 473))
    rates, over, need = blind.lam_alef_majority(broken, RATE, MIN_RUNS)
    check("broken: 3 of 5 readers at 43 per 1000 is a majority", set(over) == {"pdfium", "mupdf", "poppler"}
          and need == 3 and len(rates) == 5, f"{over} {need} {len(rates)}")

    # the same file on a Linux runner: PDFKit absent, still 3 of 4
    linux = {k: v for k, v in broken.items() if k != "pdfkit"}
    rates, over, need = blind.lam_alef_majority(linux, RATE, MIN_RUNS)
    check("linux: 3 of 4 without PDFKit is still a majority", set(over) == {"pdfium", "mupdf", "poppler"}
          and need == 3, f"{over} {need}")

    # a short reading is not judged: one example in 50 runs would be 20 per 1000 by arithmetic alone
    short = readers(pdfium=(1, 50), pdfkit=(1, 50))
    rates, over, need = blind.lam_alef_majority(short, RATE, MIN_RUNS)
    check("short: below min_runs nothing is judged and no majority exists", over == {} and need is None and rates == {},
          f"{over} {need}")

    # a two-two split raises nothing
    split = readers(a=(21, 500), b=(21, 500), c=(0, 500), d=(0, 500))
    rates, over, need = blind.lam_alef_majority(split, RATE, MIN_RUNS)
    check("split: 2 of 4 is not a majority", len(over) == 2 and need == 3, f"{over} {need}")

    # the boundary is inclusive on the density, and min_runs itself is judged
    at_rate = readers(a=(31, 5000), b=(0, 5000), c=(0, 5000))       # 31/5000 = exactly 6.2 per 1000
    rates, over, need = blind.lam_alef_majority(at_rate, RATE, MIN_RUNS)
    check("boundary: exactly the density counts as at-or-above", "a" in over and need == 2, f"{over} {need}")
    at_runs = readers(a=(2, MIN_RUNS))                              # 10 per 1000, but only one voter
    rates, over, need = blind.lam_alef_majority(at_runs, RATE, MIN_RUNS)
    check("boundary: exactly min_runs is judged, and one voter withholds a verdict",
          "a" in over and need is None, f"{over} {need}")

    print(f"\nLAM-ALEF RULE PASSED — {passed} check(s); a density, a majority, and a floor that makes 1/n not a rate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
