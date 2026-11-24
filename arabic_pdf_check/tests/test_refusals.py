#!/usr/bin/env python3
"""Refusals are named, one line, and never a traceback.

The old CLI printed whatever exception it caught (`PDFium: Success` for a corrupt file). This test builds the
three shapes with pikepdf and drives the COMMAND, not the function: the wording a user sees is the contract.
An owner-password-only PDF opens without a password and must NOT be refused; only a user password is
`encrypted (password required)`.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

import pikepdf                                             # noqa: E402
from arabic_pdf_check import blind                         # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def refused(path: str) -> str:
    try:
        blind._preflight(path)
        return ""
    except blind.Refused as exc:
        return str(exc)


source = os.path.join(REPO, "report.pdf")
if not os.path.exists(source):
    print("SKIP refusals: report.pdf is absent (CI builds it before this test)")
    raise SystemExit(0)

with tempfile.TemporaryDirectory(prefix="refusals-") as tmp:
    enc = os.path.join(tmp, "enc.pdf")
    zero = os.path.join(tmp, "zero.pdf")
    corrupt = os.path.join(tmp, "corrupt.pdf")
    owner = os.path.join(tmp, "owner.pdf")
    with pikepdf.open(source) as pdf:
        pdf.save(enc, encryption=pikepdf.Encryption(owner="o", user="u", R=6))
        pdf.save(owner, encryption=pikepdf.Encryption(owner="o", user="", R=6))
    pikepdf.new().save(zero)
    with open(corrupt, "wb") as fh:
        fh.write(b"this is not a PDF\n")

    check("encrypted:message", refused(enc) == "encrypted (password required)", refused(enc))
    check("zero:message", refused(zero) == "no pages", refused(zero))
    check("corrupt:message", refused(corrupt) == "unreadable PDF", refused(corrupt))
    check("owner-only:not-refused", refused(owner) == "", refused(owner))

    env = {**os.environ, "PYTHONPATH": REPO, "ARABIC_PDF_CHECK_CACHE": os.path.join(tmp, "cache")}
    for name, path, expected in (("encrypted", enc, "REFUSED — encrypted (password required)"),
                                 ("zero", zero, "REFUSED — no pages"),
                                 ("corrupt", corrupt, "REFUSED — unreadable PDF")):
        r = subprocess.run([sys.executable, "-m", "arabic_pdf_check", "check", path],
                           cwd=REPO, capture_output=True, text=True, timeout=120, env=env)
        lines = (r.stdout + r.stderr).strip().splitlines()
        check(f"cli:{name}:exit", r.returncode == 2, str(r.returncode))
        check(f"cli:{name}:line", lines and lines[0] == expected, str(lines[:2]))
        check(f"cli:{name}:no-traceback", "Traceback" not in (r.stdout + r.stderr), (r.stdout + r.stderr)[-300:])

print()
if fails:
    print(f"REFUSALS FAILED — {fails}")
    raise SystemExit(1)
print("REFUSALS PASSED — three named refusals, one line each, no traceback")
