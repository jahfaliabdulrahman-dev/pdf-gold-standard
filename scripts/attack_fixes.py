#!/usr/bin/env python3
"""Prove the review fixes BITE — every case below must be REFUSED by the gate.

Run with PDF_SPEC=report_spec, from the repo root, after a green build:
    PDF_SPEC=report_spec .venv/bin/python scripts/attack_fixes.py report.pdf

Each case mutates a COPY in a temp dir; the original is never touched. A case that PASSES is a failure of
this script (the fix does not hold).
"""
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import pikepdf  # noqa: E402

import spec_loader  # noqa: E402
import verify_pdf as G  # noqa: E402

NS = spec_loader.load()
SRC = sys.argv[1] if len(sys.argv) > 1 else "report.pdf"


def run(path: str) -> list[str]:
    doc = G.open_for_gate(path)
    return G.gate(doc)


def mutate(name: str, fn) -> tuple[str, list[str]]:
    tmp = os.path.join(WORK, name + ".pdf")
    with pikepdf.open(SRC) as pdf:
        fn(pdf)
        pdf.save(tmp)
    return name, run(tmp)


def drop_widget_k(pdf):
    for page in pdf.pages:
        for a in page.obj.get("/Annots", []):
            if str(a.get("/Subtype")) == "/Widget":
                st = pdf.Root.StructTreeRoot
                for e in st["/K"] if isinstance(st["/K"], pikepdf.Array) else [st["/K"]]:
                    if getattr(e, "get", lambda k, d=None: None)("/S") == pikepdf.Name.Form:
                        del e["/K"]
                        return
    raise SystemExit("fixture: no /Form element found")


def rename_field(pdf):
    f = pdf.Root.AcroForm.Fields[0]
    f["/T"] = pikepdf.String("wrong_name")


def drop_tabs(pdf):
    for page in pdf.pages:
        if any(str(a.get("/Subtype")) == "/Widget" for a in page.obj.get("/Annots", [])):
            if "/Tabs" in page.obj:
                del page.obj["/Tabs"]
            return
    raise SystemExit("fixture: no page with a widget")


def break_link_structparent(pdf):
    for page in pdf.pages:
        for a in page.obj.get("/Annots", []):
            if str(a.get("/Subtype")) == "/Link":
                a["/StructParent"] = 9999
                return
    raise SystemExit("fixture: no link")


def retitle(pdf):
    with pdf.open_metadata() as m:
        m["dc:title"] = "معيار إنتاج ملفات PDF — دليل المعيار · الإصدار ١٫٠"


def claim_ua(pdf):
    with pdf.open_metadata() as m:
        m["pdfuaid:part"] = "1"


def subset_font_in_dr(pdf):
    """The old bug: the field borrows a page font, which is a subset of that page's words."""
    page_fonts = pdf.pages[0].obj["/Resources"]["/Font"]
    dr = pdf.Root.AcroForm["/DR"]["/Font"]
    dr[next(iter(dr.keys()))] = page_fonts[next(iter(page_fonts.keys()))]


CASES = [("acroform/OBJR removed", drop_widget_k, "acroform"), ("acroform/subset font in /DR", subset_font_in_dr, "acroform"),
         ("acroform/field renamed", rename_field, "acroform"),
         ("acroform/no /Tabs", drop_tabs, "acroform"), ("link/StructParent dangling", break_link_structparent, "link-tagging"),
         ("metadata/wrong title", retitle, "title")]


def main() -> None:
    global WORK
    WORK = tempfile.mkdtemp(prefix="attack-")
    failed = []
    clean = run(SRC)
    if clean:                     # the reference must be green, else «CAUGHT» means nothing
        raise SystemExit(f"attack_fixes: the build under test already fails: {clean}")
    for name, fn, expect in CASES:
        case, fails = mutate(name.replace("/", "_").replace(" ", "_"), fn)
        # Any failure is not a catch: the named check must be the one that failed.
        caught = expect in fails
        print(("CAUGHT   " if caught else "MISSED   ") + case + " -> " + ", ".join(fails)
              + ("" if caught else f"  [expected {expect}]"))
        if not caught:
            failed.append(case)

    # a PDF/UA claim must be judged against the ua1 baseline, not against 3b
    NS.CONFORMANCE = {"pdfuaid:part": "1"}
    case, fails = mutate("ua_claim", claim_ua)
    caught = "pdfua" in fails
    print(("CAUGHT   " if caught else "MISSED   ") + "claim/PDF-UA vs ua1 baseline -> " + "; ".join(fails))
    if not caught:
        failed.append("claim/PDF-UA")

    # the printed link total is parsed, not decorative
    doc = G.open_for_gate(SRC)
    counts = G.printed_counts(doc[NS.PRINTED_COUNTS_PAGE])
    ok = counts.get("links") == NS.EXPECTED_LINKS
    print(("CAUGHT   " if ok else "MISSED   ") + f"printed/links -> {counts}")
    if not ok:
        failed.append("printed/links")

    # calibrate refuses a build whose structure is broken (a lost link is a defect, not a new baseline)
    broken = os.path.join(WORK, "no_link.pdf")
    with pikepdf.open(SRC) as pdf:
        for page in pdf.pages:
            for a in list(page.obj.get("/Annots", [])):
                if str(a.get("/Subtype")) == "/Link":
                    page.obj["/Annots"].remove(a)
                    break
            else:
                continue
            break
        pdf.save(broken)
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(HERE, "calibrate.py"), broken], capture_output=True, text=True)
    refused = r.returncode != 0 and "refusing to calibrate" in (r.stdout + r.stderr)
    print(("CAUGHT   " if refused else "MISSED   ") + "calibrate/a lost link -> " + (r.stdout + r.stderr).strip().splitlines()[-1][:90])
    if not refused:
        failed.append("calibrate/lost-link")

    shutil.rmtree(WORK, ignore_errors=True)
    print("\n" + ("ALL ATTACKS CAUGHT" if not failed else f"MISSED: {failed}"))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
