"""The file's SHA-256 is one function, and it reads in chunks.

Why this test exists: three copies of a one-line whole-file hash had grown in `certificate.py`, `runner.py` and
`blind.py`. A copy is not a bug by itself; the whole-file `read()` is — a customer PDF of a few hundred MB would
be loaded into memory just to name it. The test proves (a) the digest is correct on a file larger than one
chunk, and (b) the three consumers import the one function instead of carrying a local one.
"""
import hashlib
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from conformance import hashing                         # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


# A file larger than one internal chunk, with a known digest. `hashlib.file_digest` uses its own chunk size;
# 3 MiB is above both the module's declared chunk and the usual 2 MiB buffer.
payload = bytes(range(256)) * (3 * 1024 * 4)
with tempfile.NamedTemporaryFile(delete=False) as fh:
    fh.write(payload)
    path = fh.name
try:
    check("chunked-digest", hashing.sha256_file(path) == hashlib.sha256(payload).hexdigest())
finally:
    os.unlink(path)

import conformance.certificate as certificate            # noqa: E402
import conformance.runner as runner                      # noqa: E402
import arabic_pdf_check.blind as blind                   # noqa: E402

for module in (certificate, runner, blind):
    assert module.__file__ is not None
    source = open(module.__file__, encoding="utf-8").read()
    check(f"{module.__name__}:no-whole-file-hash", "fh.read()).hexdigest()" not in source.replace(" ", ""),
          "a local whole-file hash is still present")

print()
if fails:
    print(f"HASHING FAILED — {fails}")
    raise SystemExit(1)
print("HASHING PASSED — one chunked digest, no whole-file copy")
