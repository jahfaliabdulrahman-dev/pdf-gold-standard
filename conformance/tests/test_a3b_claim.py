#!/usr/bin/env python3
"""A PDF/A-3b claim may name a second file in a BAKE-OFF — never in a CERTIFICATE.

The bakeoff found WeasyPrint writing `<id>.pdf` (UA-1) and `<id>.a3b.pdf` (A-3b), and our gate judging the UA-1
file against A-3b: 60/60 "failures" on files `verapdf --flavour 3b` passes. The fix lets a producer name the
file that claims the flavour — and that is precisely the door a certificate must not walk through, because a
certificate names ONE document. This test holds both sides of the line, with no veraPDF and no engine:

  accepted: a producer that declares the second file by name, whose path exists and matches
  refused : a path with no declaration · a declaration naming a different file · a missing second file
  refused : the certificate path (`honour_second_file=False`) ignores the claim even when it is well-formed
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from conformance.checks import structure          # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


def refused(fn) -> tuple[bool, str]:
    try:
        fn()
    except ValueError as exc:
        return True, str(exc)
    return False, "no refusal"


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="a3b-claim-")
    main_pdf = os.path.join(tmp, "case.pdf")
    second = os.path.join(tmp, "case.a3b.pdf")
    for path in (main_pdf, second):
        with open(path, "wb") as fh:
            fh.write(b"%PDF-1.7\n")                      # existence is all this rule needs

    good = {"engine": "weasyprint", "engine_version": "70.0", "postprocess": False,
            "second_file": "case.a3b.pdf", "variants": {"also": "pdf/a-3b", "measured": "pdf/ua-1"},
            "a3b_path": second}
    check("declared-second-file-accepted", structure.a3b_target(good, main_pdf) == second,
          structure.a3b_target(good, main_pdf))

    ok, why = refused(lambda: structure.a3b_target({"a3b_path": second}, main_pdf))
    check("path-without-declaration-refused", ok and "did not name" in why, why)

    wrong_name = dict(good, second_file="other.a3b.pdf")
    ok, why = refused(lambda: structure.a3b_target(wrong_name, main_pdf))
    check("declaration-naming-another-file-refused", ok and "did not name" in why, why)

    missing = dict(good, a3b_path=os.path.join(tmp, "absent.a3b.pdf"), second_file="absent.a3b.pdf")
    ok, why = refused(lambda: structure.a3b_target(missing, main_pdf))
    check("missing-second-file-refused", ok and "does not exist" in why, why)

    check("no-claim-returns-the-file-itself", structure.a3b_target({}, main_pdf) == main_pdf)

    # The certificate side: even a perfectly declared claim is ignored — the certified file is judged as itself.
    seen = []
    real = structure.verapdf_mod.failing

    def spy(path, flavour, cache=True):
        seen.append((os.path.basename(path), flavour))
        return []

    structure.verapdf_mod.failing = spy
    try:
        _minimal_pdf(main_pdf)                                  # a real page: veraPDF is stubbed, the reader is not
        structure.evaluate(main_pdf, _case(main_pdf), good, run_verapdf=True, honour_second_file=False)
    finally:
        structure.verapdf_mod.failing = real
    a3b_calls = [p for p, f in seen if f == "3b"]
    check("certificate-path-ignores-the-claim",
          bool(a3b_calls) and all(p == "case.pdf" for p in a3b_calls), f"verapdf saw {seen}")

    print()
    if FAILS:
        print(f"A3B CLAIM GUARD FAILED — {len(FAILS)}: {', '.join(FAILS)}")
        return 1
    print("A3B CLAIM GUARD PASSED — a bakeoff may name a second file, a certificate may not")
    return 0


def _minimal_pdf(path: str) -> None:
    """One tagged page, `/Lang ar`, one heading — enough for `evaluate` to reach the veraPDF calls."""
    import pikepdf
    pdf = pikepdf.Pdf.new()
    stream = pdf.make_stream(b"/H1 << /MCID 0 >> BDC\nBT\nET\nEMC\n")
    page = pikepdf.Dictionary({"/Type": pikepdf.Name("/Page"), "/MediaBox": [0, 0, 595, 842],
                               "/Contents": stream, "/Resources": pikepdf.Dictionary()})
    pages = pdf.make_indirect(pikepdf.Dictionary({
        "/Type": pikepdf.Name("/Pages"), "/Kids": pdf.make_indirect(pikepdf.Array([page])), "/Count": 1}))
    page["/Parent"] = pages
    pdf.Root["/Pages"] = pages
    pdf.Root["/Lang"] = pikepdf.String("ar")
    pdf.Root["/MarkInfo"] = pikepdf.Dictionary({"/Marked": True})
    pdf.save(path)


def _case(pdf_path: str) -> dict:
    """The smallest case that lets `evaluate` run: no headings, one paragraph."""
    return {"id": "a3b-claim", "font": "plex", "blocks": [{"type": "paragraph", "text": "نص"}]}


if __name__ == "__main__":
    sys.exit(main())
