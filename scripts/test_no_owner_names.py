#!/usr/bin/env python3
"""No owner filename may enter this PUBLIC repository — the guard, not the intention.

The owner decided on 2026-11-25: the repository is public, the only filenames it may carry are the three
calibration files (an explicit exemption, already published in `measurements/calibration.json`) and the names
this project builds itself.

The rule, and its two halves:

  · a NON-ASCII `*.pdf` name is allowed only if it is one of the declared exemptions below. The three exempt
    names contain spaces, so the scan also produces their space-delimited tails («البايثون.pdf», …); those
    tails are accepted as fragments OF the exemption, never as new names.
  · an ASCII `*.pdf` name is accepted: the corpus cases, the built documents and the fixtures are ASCII by
    convention. **Declared limit:** an owner file whose name is plain ASCII and shaped like a fixture
    (`scan1.pdf`) would pass this guard; the owner-named set it was written for is Arabic or space-bearing.

A guard that cannot fail is theatre, so `--self-test` plants a name the exemption list does not cover and
requires the scan to catch it.
"""
import os
import re
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# The three calibration files are the owner's exemption; the two guides are this project's own deliverables.
EXEMPT_NAMES = (
    "نظام الشركات 1439 سعد الخنفري.pdf",
    "٣ - درس - البايثون.pdf",
    "7  - درس - مهارات التواصل.pdf",
    "دليل-معيار-إنتاج-PDF.pdf",
    "دليل-معيار-إنتاج-PDF-v2.pdf",
)

BINARY = (".pdf", ".png", ".jpg", ".jpeg", ".gz", ".zip", ".woff", ".woff2", ".ttf", ".otf", ".xcassets")
TOKEN = re.compile(r"[^\s\"'`«»،:()\[\]<>|*]+\.pdf")


def fragments(names):
    """Every space-delimited tail of an exempt name that still ends in `.pdf` — its fragments, not new names."""
    out = set()
    for name in names:
        parts = name.split(" ")
        for i in range(len(parts)):
            tail = " ".join(parts[i:])
            if tail.endswith(".pdf"):
                out.add(tail)
                out.add(tail.split(" ")[-1])
    return out


ALLOWED_NON_ASCII = set(EXEMPT_NAMES) | fragments(EXEMPT_NAMES)


def scanned_files(root: str) -> list[str]:
    """Tracked text files only: a generated PDF's bytes are not a claim about the source tree."""
    listed = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True, check=True).stdout
    return [p for p in listed.split() if not p.lower().endswith(BINARY)]


def scan_text(rel: str, text: str) -> list[tuple[str, int, str]]:
    bad = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for token in TOKEN.findall(line):
            if not token.isascii() and token not in ALLOWED_NON_ASCII:
                bad.append((rel, lineno, token))
    return bad


def violations(root: str) -> list[tuple[str, int, str]]:
    bad = []
    for rel in scanned_files(root):
        path = os.path.join(root, rel)
        try:
            with open(path, encoding="utf-8") as fh:
                bad.extend(scan_text(rel, fh.read()))
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    return bad


def main() -> int:
    if "--self-test" in sys.argv:
        # The control goes through the SAME scan, in both directions: an unlisted Arabic name must bite, and an
        # exempt name (and its fragment) must not. A control that only asserts membership proves nothing.
        # Built at run time: a literal control name would be a violation of this very guard (the file is
        # scanned like every other tracked file).
        control = "ملف-المالك-الخاص" + ".pdf"
        caught = scan_text("fabricated.md", f"a table row: `{control}` and a bare {control}.")
        if [t for _rel, _n, t in caught] != [control, control]:
            print(f"GUARD FAILED — the scan did not catch its own control: {caught}")
            return 1
        spared = scan_text("fabricated.md", "the exempt `٣ - درس - البايثون.pdf` and its tail `البايثون.pdf`")
        if spared:
            print(f"GUARD FAILED — the scan flagged a declared exemption: {spared}")
            return 1
        print("PASS self-test — an unlisted Arabic name is caught twice, an exempt name and its fragment are spared")
    bad = violations(REPO)
    for rel, lineno, token in bad[:40]:
        print(f"  owner-name leak: {rel}:{lineno}: {token}")
    print(f"  {len(scanned_files(REPO))} tracked text file(s) scanned · {len(bad)} unlisted non-ASCII name(s)")
    if bad:
        print("OWNER-NAME GUARD FAILED — a filename outside the exemption list is in the tree")
        return 1
    print("OWNER-NAME GUARD PASSED — every non-ASCII PDF name in the tree is a declared exemption")
    return 0


if __name__ == "__main__":
    sys.exit(main())
