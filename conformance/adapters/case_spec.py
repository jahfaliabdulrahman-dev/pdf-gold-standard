"""The case spec handed to `postprocess.apply` — the only document constants a case build carries.

`postprocess` was written for documents with a spec module. A conformance case has no spec: its document
is the case file. This module builds a module-like object with exactly what postprocess reads, and nothing
that belongs to a calibrated document (no title, no version, no ink table, no furniture band, no conformance
identifier). `tests` assert that `nav_spec` is never loaded during a conformance run — the leak this shim
closes was real: `feature_pdfua` and `feature_xmp` fall back to `spec_loader.load()` when no override is
given, and `spec_loader` defaults to the guide.

FURNITURE_BANDS is empty on purpose: a case has no running header or footer, so any artifact text is
outside every band and the producer's band rule refuses it. That is the correct answer for a case.
"""
import types


def make(case: dict) -> types.ModuleType:
    spec = types.ModuleType("conformance_case_spec")
    constants = {
        "PDFUA": True,
        "FURNITURE_BANDS": [],
        "XMP_TITLE": f"conformance case {case['id']}",
        "XMP_DESCRIPTION": "conformance corpus case — a test file, not a deliverable document",
        "XMP_CREATOR": "PDF Gold Standard conformance gate",
        # The case DECLARES the two claims it is certified against. A file that does not identify itself as
        # PDF/UA-1 fails veraPDF clause 5-1 before any content rule is reached (measured), and a certificate
        # that measured an undeclared file would be checking a claim nobody made. The claims are in the file;
        # the certificate says whether they hold.
        "CONFORMANCE": {"pdfaid:part": 3, "pdfaid:conformance": "B", "pdfuaid:part": 1},
    }
    for key, value in constants.items():
        setattr(spec, key, value)          # a module object, not a dict: postprocess checks isinstance(ModuleType)
    return spec
