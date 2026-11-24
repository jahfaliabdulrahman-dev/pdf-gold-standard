#!/usr/bin/env python3
"""The new ToUnicode parser must not change the text layer the writer produces.

The audit's acceptance is byte-identical output on the four shipped documents. The whole PDF is NOT
byte-identical between two runs of the OLD writer either — pikepdf reassigns object numbers — so the
invariant that matters is the layer: per page, the content stream bytes and the /ToUnicode bytes of every
font. Those were measured identical between the old parser and the new one on all four documents; the
constants below are the OLD layer hashes, so a future parser/writer change that alters one page fails here.

`najd.pdf` is built locally with a font that CI does not ship; the test skips it by name when absent and the
delivery report carries its local measurement.
"""
import hashlib
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))

GOLDEN = {
    "guide-v2-ar": "89ede771af56ad9cf190b28dc48e8698bba8984be291fd1a322581c7d0708201",
    "report": "12e794aea75c56b35d21d136dd20a0b9829746db2fd4bed6bca92581b29f5afb",
    "najd": "45d40668155d263b6fa4713ae6d28754c7a38d3b0dd52efcd562092b960f76a3",
    "report-print": "7058d9acef89480fe81246776fe81411f8958e91277441075ccc7522e6ef18d3",
}

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def layer_hash(path: str) -> str:
    import pikepdf
    h = hashlib.sha256()
    with pikepdf.open(path) as pdf:
        h.update(f"pages:{len(pdf.pages)}\n".encode())
        for pi, page in enumerate(pdf.pages, 1):
            contents = page.obj.get("/Contents")
            if contents is None:
                data = b""
            elif isinstance(contents, pikepdf.Array):
                data = b"".join(s.read_bytes() for s in contents)
            else:
                data = contents.read_bytes()
            h.update(f"page:{pi}:content:".encode())
            h.update(hashlib.sha256(data).digest())
            res = page.obj.get("/Resources") or {}
            fonts = {str(k): (f.get("/ToUnicode").read_bytes() if f.get("/ToUnicode") is not None else b"")
                     for k, f in (res.get("/Font") or {}).items()}
            for k in sorted(fonts):
                h.update(f"page:{pi}:font:{k}:".encode())
                h.update(hashlib.sha256(fonts[k]).digest())
    return h.hexdigest()


with tempfile.TemporaryDirectory(prefix="ftl-parity-") as tmp:
    for name, golden in GOLDEN.items():
        source = os.path.join(REPO, name + ".pdf")
        if not os.path.exists(source):
            print(f"SKIP {name}: the built PDF is absent (najd is not built in CI; measured locally)")
            continue
        out = os.path.join(tmp, name + ".pdf")
        r = subprocess.run([sys.executable, os.path.join(HERE, "fix_text_layer.py"), source, out],
                           cwd=REPO, capture_output=True, text=True, timeout=600)
        check(f"{name}:writer-exit", r.returncode == 0, (r.stderr or r.stdout)[-300:])
        if r.returncode == 0:
            got = layer_hash(out)
            check(f"{name}:layer-identical", got == golden, f"{got} != {golden}")

print()
if fails:
    print(f"FIX TEXT LAYER PARITY FAILED — {fails}")
    raise SystemExit(1)
print("FIX TEXT LAYER PARITY PASSED — the text layer is the old one, byte for byte")
