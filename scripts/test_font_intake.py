#!/usr/bin/env python3
"""A licence URL is not a licence grant: nameID 14 must not make a commercial face redistributable.

The old rule counted ANY nameID 14 URL as a grant (`or bool(n.get(14))`), so a commercial EULA link made the
font look open. The rule is now: only text in nameID 0/13 can grant; nameID 14 is a URL kept for the report.
The pure cases pin the rule; the integration case edits a real font's name table and runs `check()`.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import font_intake                                      # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


# --- pure rule ---------------------------------------------------------------------------------
cases = {
    "eula-url-only": ({0: "Copyright Example", 14: "https://example.com/eula"}, True),
    "eula-text-and-url": ({0: "Copyright Example", 13: "Commercial licence. All rights reserved.",
                          14: "https://example.com/eula"}, True),
    "eula-name13-no-phrase": ({0: "Copyright Example", 13: "Acme End User License Agreement. See the URL.",
                              14: "https://example.com/eula"}, True),
    "ofl-text": ({0: "Copyright Example", 13: "SIL Open Font License, Version 1.1",
                  14: "https://openfontlicense.org"}, False),
    "apache-text": ({0: "Copyright Example", 13: "Licensed under the Apache License, Version 2.0"}, False),
    "no-names": ({}, True),
}
for name, (names, want_unclear) in cases.items():
    _text, granted, unclear = font_intake.licence_state(names)
    check(name, unclear is want_unclear and granted is (not want_unclear),
          f"granted={granted} unclear={unclear}")

# --- integration: a real font whose name table is edited -------------------------------------------------
candidates = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
source = next((p for p in candidates if os.path.exists(p)), None)
if source:
    from fontTools.ttLib import TTFont
    for label, name13, name14, want in (
            ("commercial", "Commercial licence. All rights reserved.", "https://example.com/eula", True),
            ("ofl", "SIL Open Font License, Version 1.1", "https://openfontlicense.org", False)):
        font = TTFont(source)
        names = font["name"]
        names.names = [n for n in names.names if n.nameID not in (0, 13, 14)]
        for nid, text in ((0, "Copyright Example"), (13, name13), (14, name14)):
            names.setName(text, nid, 3, 1, 0x409)
        with tempfile.NamedTemporaryFile(suffix=".ttf", delete=False) as fh:
            path = fh.name
        try:
            font.save(path)
            report = font_intake.check(path, [])
            check(f"real-font:{label}", report["redistribution_unclear"] is want,
                  f"unclear={report['redistribution_unclear']} licence={report['licence']!r}")
            check(f"real-font:{label}:url-kept", report.get("licence_url", "") == name14,
                  str(report.get("licence_url")))
        finally:
            os.unlink(path)
else:
    print("SKIP real-font: no system font found — the pure rule above is the measured one")

print()
if fails:
    print(f"FONT INTAKE FAILED — {fails}")
    raise SystemExit(1)
print("FONT INTAKE PASSED — nameID 14 is a link, not a licence")
