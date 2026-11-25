#!/usr/bin/env python3
"""No owner filename may enter this PUBLIC repository — the guard, not the intention.

The owner decided on 2026-11-25: the repository is public, the only filenames it may carry are the three
calibration files (an explicit exemption, already published in `measurements/calibration.json`) and the names
this project builds itself.

What is scanned, and how a name is read:

  · TRACKED PATHS as well as their contents (`git ls-files -z`, so a non-ASCII path is not mangled by quoting
    and a path with spaces is one entry). A tracked `.pdf` is binary, so its NAME is the only thing there is to
    check — and a name is exactly what this guard is about.
  · a candidate name is taken from the last delimiter on the line to `.pdf`, so a name with SPACES is seen
    whole (a spaced name is not reduced to its last word). A candidate is allowed only when it IS an
    exempt name, or ENDS WITH one (a prose sentence that mentions the exempt file), or is pure ASCII (the
    corpus cases, builds and fixtures are ASCII by convention).
  · a name that is on the FORBIDDEN list is found by HASH, as a run of 1-5 adjacent words, with or without a
    `.pdf` extension — the extension-keyed rule alone missed a bare name that was already in the tree.
  · **Declared limit:** an owner file whose name is plain ASCII and shaped like a fixture (`scan1.pdf`) would
    pass; the population this guard was written for is Arabic or space-bearing. The three calibration names
    themselves are public by the owner's exemption.

A guard that cannot fail is theatre, so `--self-test` plants controls in both directions: an unlisted Arabic
name must bite, a spaced name with an ASCII tail must bite, a spaced name sharing an exempt surname must bite,
an exempt name and a prose mention of it must be spared.
"""
import hashlib
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

# Names the tree has carried and must never carry again. Stored as sha256 of the whitespace-normalised term, so
# the guard can find them without republishing them; each entry is (hash, what it was). They are found in the
# text as a run of 1-5 adjacent words — the owner's names appear with AND without a .pdf extension, so a rule
# keyed on the extension alone missed one of them.
FORBIDDEN_SHA256 = {
    "5f14be50f5328954": "a case file the review quoted as a bare name (no extension)",
    "4b9756a6e9b2853b": "the statute name the lexicon probe used to hide behind an env var",
}

BINARY = (".pdf", ".png", ".jpg", ".jpeg", ".gz", ".zip", ".woff", ".woff2", ".ttf", ".otf", ".xcassets")
# A candidate may contain spaces; it stops at the delimiters this repository's prose and tables use.
CANDIDATE = re.compile(r"[^\n\"'`«»،:|()\[\]<>*]+\.pdf")


def allowed(candidate: str) -> bool:
    """Is this candidate a name the repository may carry? Exact exemption, a prose mention of one, or ASCII."""
    candidate = candidate.strip().rstrip(".,;")
    if candidate.isascii():
        return True
    if candidate in EXEMPT_NAMES:
        return True
    return any(candidate.endswith(" " + name) or candidate.endswith("`" + name) for name in EXEMPT_NAMES)


def forbidden_terms(line: str) -> list[str]:
    """The hashed terms found in this line as 1-5 adjacent words (extension or not)."""
    words = line.split()
    hits = []
    for n in range(1, 6):
        for i in range(len(words) - n + 1):
            term = " ".join(words[i:i + n]).strip("`«»،.:;()[]|\"'")
            if len(term) < 5:
                continue
            if hashlib.sha256(term.encode()).hexdigest()[:16] in FORBIDDEN_SHA256:
                hits.append(term)
    return hits


def scan_text(rel: str, text: str) -> list[tuple[str, int, str]]:
    bad = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for candidate in CANDIDATE.findall(line):
            if not allowed(candidate):
                bad.append((rel, lineno, candidate.strip()))
        for term in forbidden_terms(line):
            bad.append((rel, lineno, f"<forbidden term {len(term)} chars>"))
    return bad


def tracked(root: str) -> list[str]:
    """`git ls-files -z`: one entry per path, unquoted, spaces intact."""
    out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def violations(root: str) -> tuple[list[tuple[str, int, str]], list[str]]:
    """(leaks in text, leaks in path names) — a path is a claim about a name even when its bytes are binary."""
    leaks, paths = [], []
    for rel in tracked(root):
        name = os.path.basename(rel)
        if name.lower().endswith(BINARY) and not name.isascii() and not allowed(name):
            paths.append(rel)
            continue
        if rel.lower().endswith(BINARY):
            continue
        path = os.path.join(root, rel)
        try:
            with open(path, encoding="utf-8") as fh:
                leaks.extend(scan_text(rel, fh.read()))
        except UnicodeDecodeError:
            continue
        except FileNotFoundError:
            # A tracked file that cannot be opened means the scan is incomplete — that is a failure, not a skip.
            leaks.append((rel, 0, "<tracked file is missing on disk>"))
    return leaks, paths


def main() -> int:
    if "--self-test" in sys.argv:
        # Built at run time: a literal control name would be a violation of this very guard (the file is
        # scanned like every other tracked file).
        control = "ملف-المالك-الخاص" + ".pdf"
        spaced = "كشف حساب " + "2025" + ".pdf"
        surname = "عقد " + "الخنفري" + ".pdf"
        cases = {
            "unlisted Arabic name": (control, True),
            "spaced name with an ASCII tail": (spaced, True),
            "spaced name sharing an exempt surname": (surname, True),
            "exempt name": ("٣ - درس - البايثون.pdf", False),
            "prose mention of an exempt name": ("see `٣ - درس - البايثون.pdf` for the case", False),
            "ASCII fixture": ("planted-lam-alef.pdf", False),
        }
        # the hash path is a mechanism of its own, so it gets its own control (a synthetic entry, not a real name)
        probe = "hash path control term"
        FORBIDDEN_SHA256[hashlib.sha256(probe.encode()).hexdigest()[:16]] = "self-test"
        try:
            caught = scan_text("fabricated.md", "prefix " + probe + " suffix")
        finally:
            FORBIDDEN_SHA256.pop(hashlib.sha256(probe.encode()).hexdigest()[:16], None)
        if len(caught) != 1:
            print(f"GUARD FAILED — a hashed term must be found as a word run, got {caught}")
            return 1

        for label, (text, must_bite) in cases.items():
            caught = scan_text("fabricated.md", text)
            if bool(caught) != must_bite:
                print(f"GUARD FAILED — {label}: expected {'a violation' if must_bite else 'a pass'}, got {caught}")
                return 1
        print(f"PASS self-test — {len(cases)} controls and 1 hash-run probe: three unlisted names bite "
              f"(including a spaced name and one sharing an exempt surname), three exempt/ASCII forms are "
              f"spared, and a hashed term is found without a `.pdf` extension")
    leaks, paths = violations(REPO)
    for rel, lineno, token in leaks[:40]:
        print(f"  owner-name leak: {rel}:{lineno}: {token}")
    for rel in paths[:40]:
        print(f"  owner-name path: {rel}")
    n_paths = len(tracked(REPO))
    print(f"  {n_paths} tracked path(s) and their text scanned · {len(leaks)} leak(s) · {len(paths)} named path(s)")
    if leaks or paths:
        print("OWNER-NAME GUARD FAILED — a filename outside the exemption list is in the tree")
        return 1
    print("OWNER-NAME GUARD PASSED — every non-ASCII PDF name in the tree is a declared exemption")
    return 0


if __name__ == "__main__":
    sys.exit(main())
