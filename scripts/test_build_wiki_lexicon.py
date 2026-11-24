#!/usr/bin/env python3
"""The build is reproducible: the committed list has the pinned digest, and the parser refuses
a source that is short, duplicated, or has a line with no word. No network is used."""
import os
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import build_wiki_lexicon as B  # noqa: E402


def check(name: str, cond: bool, why: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL {name}: {why}")
    print(f"PASS {name}")


# 1. The committed output verifies against the constant, and has TOP words.
rc = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "build_wiki_lexicon.py"), "--check"],
                    capture_output=True, text=True)
check("committed-output-verifies", rc.returncode == 0, rc.stderr or rc.stdout)
check("committed-output-count", "50000 words" in rc.stdout, rc.stdout)

# 2. A three-line source is parsed to three words, in order, counts dropped.
data = "في 9865644\nمن 6224386\nعلى 2534132\n".encode()
check("word-only", B.read_source(data, top=3)[:3] == ["في", "من", "على"], str(B.read_source(data, top=3)[:3]))

# 3. A short source is refused, not silently truncated.
try:
    B.read_source("في 1\n".encode("utf-8"))
except ValueError as exc:
    check("short-refused", "expected 50000" in str(exc), str(exc))
else:
    raise SystemExit("FAIL short-refused: accepted a one-line source")

# 4. A duplicate word is refused (a top-50k list is not a multiset).
try:
    B.read_source(("في 1\n" * B.TOP).encode())
except ValueError as exc:
    check("duplicate-refused", "duplicate" in str(exc), str(exc))
else:
    raise SystemExit("FAIL duplicate-refused: accepted duplicates")

# 5. gzip is deterministic: same words, same bytes, and mtime is zero.
a = B.gzip_words(["في", "من", "على"])
b = B.gzip_words(["في", "من", "على"])
check("gzip-deterministic", a == b, "two calls differ")
check("gzip-mtime-zero", a[4:8] == b"\x00\x00\x00\x00", a[4:8].hex())

# 6. A different word list has a different digest (the constant is not a check on nothing).
check("digest-binds-content", B.sha256(a) != B.sha256(B.gzip_words(["في", "من"])), "same digest for different lists")

# 7. A wrong source digest is refused by the command (offline, with a temp source).
with tempfile.NamedTemporaryFile("wb", suffix=".txt", delete=False) as fh:
    fh.write("في 1\n".encode("utf-8"))
    bad = fh.name
try:
    rc = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "build_wiki_lexicon.py"),
                         "--source", bad], capture_output=True, text=True)
    check("wrong-source-refused", rc.returncode == 2 and "source sha256" in rc.stderr, rc.stderr or rc.stdout)
finally:
    os.unlink(bad)

print("\nWIKI LEXICON BUILD PASSED — the committed list is the pinned source, and the build refuses bad input")
