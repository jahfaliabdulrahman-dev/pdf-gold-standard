"""One SHA-256 file digest, read in chunks — never the whole file in memory.

Three tools used to carry their own one-line `open(...).read()` hash (`certificate`, `runner`,
`arabic_pdf_check.blind`). The copies are gone: a 200 MB customer PDF is not read into RAM to be hashed, and a
new caller cannot reintroduce the whole-file form without failing `test_hashing.py`.
"""
import hashlib

CHUNK = 1 << 20


def sha256_file(path: str) -> str:
    """The file's SHA-256, read in bounded chunks (`hashlib.file_digest`, Python 3.11+)."""
    with open(path, "rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()
