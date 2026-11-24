#!/usr/bin/env python3
"""Build the Wikipedia Arabic 50k word list — the PR-2 lexicon candidate.

Source (pinned by commit, not by branch):
  IlyaSemenov/wikipedia-word-frequency
  results/arwiki-2022-08-29.txt @ b49c2ea1554d87094959ba15a41b3f383795434d

The file is a frequency list, one `word count` pair per line. The first 50,000 lines are the
list; the build writes only the word, one per line, gzip with mtime=0 so the output is
byte-for-byte reproducible. Both digests are constants here and are verified on every run:

  source sha256  c98ae500aa256bd36943677f395ae2457ea5c19576354139319db9833f74713c
  output sha256  60ee5e67102248111ef87b6f72a8a1f73753c9d01994a98b233eadf6b321df69

Commands:
  python3 scripts/build_wiki_lexicon.py          # download the pinned source, write the list, verify
  python3 scripts/build_wiki_lexicon.py --check  # verify the committed list only (no network)
  python3 scripts/build_wiki_lexicon.py --source PATH  # offline source; its digest must still match

Licensing: the text is derived from Arabic Wikipedia (CC-BY-SA); the list repository is MIT.
The derived file keeps CC-BY-SA — see `conformance/data/LICENSE-ar_words.txt`. It is not
relicensed by this repository.

Why this list and not the current one: the current FrequencyWords/OpenSubtitles list is a
spoken-subtitle vocabulary; the Wikipedia list is written prose. The measured comparison is in
`docs/checker-v0/08-pr2-evidence-2026-11-24.md`; the choice is not made here.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import sys
import urllib.request

SOURCE_COMMIT = "b49c2ea1554d87094959ba15a41b3f383795434d"
SOURCE_PATH = "results/arwiki-2022-08-29.txt"
SOURCE_URL = f"https://raw.githubusercontent.com/IlyaSemenov/wikipedia-word-frequency/{SOURCE_COMMIT}/{SOURCE_PATH}"
SOURCE_SHA256 = "c98ae500aa256bd36943677f395ae2457ea5c19576354139319db9833f74713c"
OUTPUT_SHA256 = "60ee5e67102248111ef87b6f72a8a1f73753c9d01994a98b233eadf6b321df69"
TOP = 50_000
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUTPUT = os.path.join(REPO, "conformance", "data", "ar_words_wiki50k.txt.gz")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_source(data: bytes, top: int = TOP) -> list[str]:
    """The first `top` lines, word only. A line without a word is a source this script refuses."""
    words = []
    for n, line in enumerate(data.decode("utf-8").splitlines(), 1):
        if len(words) >= top:
            break
        parts = line.split()
        if not parts:
            raise ValueError(f"line {n}: no word")
        words.append(parts[0])
    if len(words) != top:
        raise ValueError(f"source has {len(words)} usable lines, expected {top}")
    if len(set(words)) != top:
        raise ValueError(f"source has {top - len(set(words))} duplicate word(s) in the top {top}")
    return words


def gzip_words(words: list[str]) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        gz.write(("\n".join(words) + "\n").encode("utf-8"))
    return buf.getvalue()


def read_words(path: str) -> list[str]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        words = [w for w in fh.read().splitlines() if w]
    if len(words) != TOP:
        raise ValueError(f"{path}: {len(words)} words, expected {TOP}")
    return words


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=None, help="local source file; its sha256 must be the pinned one")
    ap.add_argument("--output", default=OUTPUT)
    ap.add_argument("--check", action="store_true", help="verify the existing output; do not write")
    ap.add_argument("--verify-source", action="store_true",
                    help="verify the pinned source digest and recompute the output; do not write")
    a = ap.parse_args()

    if a.check:
        if not os.path.exists(a.output):
            print(f"REFUSED — {a.output} is missing", file=sys.stderr)
            return 2
        got = sha256(open(a.output, "rb").read())
        if got != OUTPUT_SHA256:
            print(f"REFUSED — {a.output}: sha256 {got}, expected {OUTPUT_SHA256}", file=sys.stderr)
            return 2
        words = read_words(a.output)
        print(f"VERIFIED — {len(words)} words · sha256 {got}")
        return 0

    if a.source:
        with open(a.source, "rb") as fh:
            data = fh.read()
    else:
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "pdf-gold-standard/1"})
        try:
            with urllib.request.urlopen(req, timeout=120) as fh:
                data = fh.read()
        except OSError as exc:
            print(f"REFUSED — source download failed: {type(exc).__name__}", file=sys.stderr)
            return 2
    got = sha256(data)
    if got != SOURCE_SHA256:
        print(f"REFUSED — source sha256 {got}, expected {SOURCE_SHA256}", file=sys.stderr)
        return 2
    try:
        words = read_source(data)
    except ValueError as exc:
        print(f"REFUSED — {exc}", file=sys.stderr)
        return 2
    out = gzip_words(words)
    got = sha256(out)
    if got != OUTPUT_SHA256:
        print(f"REFUSED — output sha256 {got}, expected {OUTPUT_SHA256}", file=sys.stderr)
        return 2
    if a.verify_source:
        print(f"VERIFIED SOURCE — {len(words)} words · source {SOURCE_SHA256} · output {got}")
        return 0
    os.makedirs(os.path.dirname(a.output), exist_ok=True)
    with open(a.output, "wb") as fh:
        fh.write(out)
    print(f"WROTE — {len(words)} words · sha256 {got} · source @ {SOURCE_COMMIT[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
