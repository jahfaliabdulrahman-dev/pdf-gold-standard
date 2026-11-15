"""The filled variant of «الحرف المقلوب»: same document, values typeset into the page.

Why a separate spec: a filled copy is not the published template. It carries the reader's name, address
and note as PAGE TEXT — shaped once by Chrome at build time, so every reader (phone, Windows, Chrome,
Acrobat, print) shows the same connected Arabic. It therefore has no form fields and no widgets, and its
ink/word counts legitimately differ from the measured template.

`FILL_ALLOWED_FAILURES` is the only gate exception in the project, it is declared here, and it is narrow:
the build still stops on every other check.
"""
import json
import os

import report_spec
from report_spec import *          # noqa: F401,F403 — one document, one set of numbers

_name = os.environ.get("FILL_JSON", "")
FILL_VALUES = json.load(open(_name, encoding="utf-8")) if _name else {}
ACROFORM_FIELDS = []               # nothing is left for the reader's text engine to lay out
FILL_MODE = True
FILL_ALLOWED_FAILURES = {"page-ink", "page-words"}
DOC_TITLE = report_spec.DOC_TITLE + " · نسخة مُعبّأة"
XMP_TITLE = f"{DOC_TITLE} · الإصدار {GUIDE_VERSION_AR}"
