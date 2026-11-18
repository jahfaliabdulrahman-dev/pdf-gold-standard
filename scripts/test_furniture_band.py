"""The producer's furniture guard, seen failing: the build stops by name, not by silence.

B1 closed the gate side with a mutation (a pagination block in the body is refused). This is the other
half — the producer path: a run Chrome left unmarked in the body must not be swept into /Pagination.
The same rule, exercised where it runs at build time.

    PDF_SPEC=report_spec python3 scripts/test_furniture_band.py out.pdf
"""
import os
import sys

import pikepdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import postprocess  # noqa: E402


def instr(op, *operands):
    return pikepdf.ContentStreamInstruction(list(operands), pikepdf.Operator(op))


def run(y):
    return [instr("BMC", pikepdf.Name("/ReversedChars")),
            instr("Tf", pikepdf.Name("/F1"), 12),
            instr("Tm", 1, 0, 0, 1, 100, y),
            instr("Tj", pikepdf.String("x")),
            instr("EMC")]


def main() -> int:
    pdf = pikepdf.open(sys.argv[1])
    page = pdf.pages[1]                       # a content page: it carries /StructParents and a ParentTree entry
    try:
        postprocess._tag_orphan_runs(pdf, page, run(400), [(0, 60)], 2)
    except ValueError as exc:
        print(f"PASS body run refused by name: {str(exc)[:96]}")
    else:
        print("FAIL body run at y=400 was accepted with a [(0, 60)] band")
        return 1
    out = postprocess._tag_orphan_runs(pdf, page, run(36), [(0, 60)], 2)
    if not any(str(i.operator) == "BDC" and str(i.operands[0]) == "/Artifact" for i in out):
        print("FAIL footer run at y=36 was not wrapped as an artifact")
        return 1
    print("PASS footer run at y=36 wrapped as /Artifact /Pagination")
    # a show that follows the closed block is not inside it: stale state would report a false stray
    after = run(36) + [instr("BT", ), instr("Tm", 1, 0, 0, 1, 100, 400), instr("Tj", pikepdf.String("x")), instr("ET")]
    if postprocess.outside_bands(after, [(0, 60)]):
        print("FAIL a show after EMC was still counted as pagination")
        return 1
    print("PASS a show after EMC is not pagination")
    return 0


if __name__ == "__main__":
    sys.exit(main())
