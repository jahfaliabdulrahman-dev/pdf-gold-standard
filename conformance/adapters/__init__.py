"""One adapter per engine. An adapter turns a case into that engine's source, then into a PDF.

The chrome adapter is the *installed build*: Chrome for Testing (pinned), then `fix_text_layer`, then
`postprocess`, then the outline. `chrome-raw` stops after Chrome. typst/weasyprint are the bakeoff's
competitors and take no post-processing at all.

Nothing here reads a document spec. `case_spec` is the module-like object handed to `postprocess.apply`
in place of the calibrated `nav_spec`, and `test_conformance_isolation.py` proves no `*_spec` module is
loaded by a run.
"""
from . import fonts  # noqa: F401  (re-exported for the adapters and the CLI)
