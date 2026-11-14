"""One document, one spec.

`build.py`, `scripts/verify_pdf.py`, `scripts/gate_selftest.py` and `postprocess.py` all read the document's
numbers from ONE module. This loader makes that module selectable per document (`PDF_SPEC=report_spec`)
instead of hard-wiring `nav_spec`, so a second deliverable reuses the same pipeline, the same gate and the
same self-test — and the first one cannot regress silently.

Default is `nav_spec` (the guide): an unset environment variable must keep the existing build byte-for-byte.
"""
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def load(name: str | None = None):
    """Import the spec module named by the argument, or $PDF_SPEC, or nav_spec."""
    module = name or os.environ.get("PDF_SPEC") or "nav_spec"
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    return importlib.import_module(module)
