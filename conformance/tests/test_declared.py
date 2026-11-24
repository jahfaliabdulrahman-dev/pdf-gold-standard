#!/usr/bin/env python3
"""A declared reader behaviour without a working control is an anecdote — refused by name.

Two controls:
  1. an entry whose control script does not exist is refused (`DeclaredRefused`), never applied;
  2. the real entry (PDFium's RTL row order) holds only when its control reproduces on THIS install — the
     control builds the row with the pinned engine, reads it with PDFium and must see value-before-label.
A stale behaviour (control says false) is refused by the same path; the message names the reason.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from conformance.readers import declared, pdfium            # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


try:
    declared.run_control({"id": "no-control", "control_script": "does_not_exist.py"})
    check("missing-control-refused", False, "no exception")
except declared.DeclaredRefused as exc:
    check("missing-control-refused", "does not exist" in str(exc), str(exc))

try:
    declared.run_control({"id": "no-script", "control_script": ""})
    check("empty-control-refused", False, "no exception")
except declared.DeclaredRefused as exc:
    check("empty-control-refused", "does not exist" in str(exc), str(exc))

held, refused, controls = declared.usable("pdfium", pdfium.version(), mode="live")
check("pdfium-row-order-holds", any(e["id"] == "pdfium-rtl-row-order" for e in held),
      "; ".join(refused) or "the control did not reproduce")
if held:
    detail = controls[0].get("detail") or {}
    check("control-sees-value-first", detail.get("value_before_label") is True, str(detail))
    check("control-version-matches", held[0]["reader_version_measured"] == pdfium.version(),
          f"{held[0]['reader_version_measured']} vs {pdfium.version()}")
    # The report prints the LIVE version and the version the behaviour was measured on; a declaration from an
    # older install must not be printed as if it were measured now.
    check("live-version-recorded", held[0].get("reader_version_now") == pdfium.version(),
          f"{held[0].get('reader_version_now')} vs {pdfium.version()}")
    check("version-mismatch-flag", held[0].get("version_mismatch") is False,
          str(held[0].get("version_mismatch")))

print()
if fails:
    print(f"DECLARED BEHAVIOUR FAILED — {fails}")
    raise SystemExit(1)
print("DECLARED BEHAVIOUR PASSED — the control decides, the file never asserts")
