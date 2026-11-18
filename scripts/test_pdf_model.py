#!/usr/bin/env python3
"""The model boundary, on synthetic files: every refusal the gate promises must actually happen.

The boundary is a promise — «Do deeper than 1 is refused», «text inside a form is refused», «an unresolved
Do is a hole» — and a promise is only kept if it is seen refusing. The mutation suite proves it on a real
document; these cases prove the EDGES the real document does not contain (an unresolved name, a form that
carries its own resources), in twenty lines each, without a browser.

Run: python3 scripts/test_pdf_model.py
"""
import io
import os
import sys

import pikepdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pdfops import model_boundary  # noqa: E402


def _pdf(content: bytes, forms=None, page_forms=None):
    """A one-page PDF. `forms` are (name, content, resources) added to the page's /XObject."""
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(595, 842))
    xo = pikepdf.Dictionary()
    for name, body, res in (forms or []):
        f = pdf.make_stream(body)
        f["/Type"] = pikepdf.Name("/XObject")
        f["/Subtype"] = pikepdf.Name("/Form")
        f["/BBox"] = pikepdf.Array([0, 0, 595, 842])
        f["/Resources"] = res if res is not None else pikepdf.Dictionary({})
        xo[name] = f
    page.Resources = pikepdf.Dictionary({"/XObject": xo}) if forms else pikepdf.Dictionary({})
    page.Contents = pdf.make_stream(content)
    return pdf


def _names(violations):
    return " | ".join(violations)


CASES = []


def case(name, want=None):
    def wrap(fn):
        CASES.append((name, fn, want))
        return fn
    return wrap


@case("clean-page")
def clean():
    return _pdf(b"BT /F1 12 Tf 1 0 0 1 100 400 Tm (x) Tj ET")


@case("text-inside-a-form", "text inside a Form XObject")
def text_in_form():
    return _pdf(b"q /Fx Do Q", forms=[("/Fx", b"BT /F1 12 Tf 1 0 0 1 100 400 Tm (x) Tj ET", None)])


@case("form-inside-a-form", "inside a form's /Resources")
def nested():
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(595, 842))

    def form(body, res=None):
        f = pdf.make_stream(body)
        f["/Type"] = pikepdf.Name("/XObject")
        f["/Subtype"] = pikepdf.Name("/Form")
        f["/BBox"] = pikepdf.Array([0, 0, 10, 10])
        f["/Resources"] = res if res is not None else pikepdf.Dictionary({})
        return f

    inner = form(b"")
    outer = form(b"", pikepdf.Dictionary({"/XObject": pikepdf.Dictionary({"/Inner": inner})}))
    page.Resources = pikepdf.Dictionary({"/XObject": pikepdf.Dictionary({"/Fx": outer})})
    page.Contents = pdf.make_stream(b"q /Fx Do Q")
    return pdf


@case("text-rise", "text rise")
def rise():
    return _pdf(b"BT /F1 12 Tf 4 Ts 1 0 0 1 100 400 Tm (x) Tj ET")


@case("rotated-artifact-text", "non-axis-aligned")
def rotated():
    return _pdf(b"/Artifact BMC q 0 1 -1 0 200 200 cm BT /F1 12 Tf (x) Tj ET Q EMC")


@case("unresolved-do-on-page", "unresolved Do")
def unresolved_page():
    return _pdf(b"q /Nowhere Do Q")


@case("unresolved-do-inside-a-form", "Do inside a Form XObject")
def unresolved_in_form():
    # J4: the chain hides because the name is not in the form's own resources
    return _pdf(b"q /Fx Do Q", forms=[("/Fx", b"q /Missing Do Q", None)])


def main() -> int:
    bad = 0
    for name, fn, want in CASES:
        pdf = fn()
        buf = io.BytesIO()
        pdf.save(buf)
        buf.seek(0)
        with pikepdf.open(buf) as reopened:
            got = model_boundary(reopened)
        ok = (not got) if want is None else any(want in g for g in got)
        print(f"{'PASS' if ok else 'FAIL'} {name:28s} -> {_names(got) or 'no violation'}")
        bad += 0 if ok else 1
    if bad:
        print(f"\nMODEL TESTS FAILED — {bad} case(s)")
        return 1
    print(f"\nMODEL TESTS PASSED — {len(CASES)} cases: the boundary refuses what it promises, and a clean page passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
