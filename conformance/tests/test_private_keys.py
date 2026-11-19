#!/usr/bin/env python3
"""`private_keys` must read every place a key can live — the rule is "any object", not "any indirect dictionary".

The check ships inside `structure.evaluate`, and its claim is the sentence above, so every clause needs a
positive control:

  1. an indirect dictionary (the incident's shape: a key on a font dictionary);
  2. a STREAM dictionary — pikepdf reports a stream as `Object`, not `Dictionary`; its keys live in
     `stream_dict`, so the old `isinstance(obj, pikepdf.Dictionary)` filter read an empty list and said "clean";
  3. a DIRECT dictionary nested in an indirect one — `pdf.objects` never lists direct objects;
  4. a dictionary inside an array;
  5. the trailer, which is not in `pdf.objects` at all.

Negatives: a clean file, and a private-looking key that does not start with the reserved prefix (`/XY…`) is
not ours. The last one is the contract: the rule is `/PL`, not "looks private".

No engine, no corpus: a page built by hand, saved and reopened so the walk sees the on-disk shapes.
"""
import os
import sys
import tempfile

import pikepdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

import pdfops  # noqa: E402

FAILS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def make_poisoned(path: str) -> None:
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(300, 300))
    pdf.pages[0].Contents = pdf.make_stream(b"")                       # a stream to carry a key
    pdf.Root["/PLIndirect"] = pikepdf.String("indirect")               # 1 · on the catalog (indirect)
    pdf.pages[0].Contents.stream_dict["/PLStream"] = pikepdf.String("stream")   # 2 · stream dictionary
    pdf.Root["/Holder"] = pikepdf.Dictionary({"/PLDirect": 1})         # 3 · direct dictionary
    pdf.Root["/Arr"] = pikepdf.Array([pikepdf.Dictionary({"/PLInArray": 2})])   # 4 · dictionary in an array
    pdf.trailer["/PLTrailer"] = pikepdf.String("trailer")              # 5 · the trailer itself
    pdf.Root["/XYNotOurs"] = pikepdf.String("not the reserved prefix")  # negative
    pdf.save(path)


def make_clean(path: str) -> None:
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page(page_size=(300, 300))
    pdf.save(path)


tmp = tempfile.mkdtemp(prefix="private-keys-")
try:
    poisoned = os.path.join(tmp, "poisoned.pdf")
    make_poisoned(poisoned)
    with pikepdf.open(poisoned) as pdf:
        found = pdfops.private_keys(pdf)
        # The test must exercise the DIRECT path, not an indirect copy of it: assert the shape it needs.
        check("direct-is-direct", pdf.Root["/Holder"].is_indirect is False,
              f"is_indirect={pdf.Root['/Holder'].is_indirect}")
        check("stream-is-not-dictionary", not isinstance(pdf.pages[0].Contents, pikepdf.Dictionary),
              f"type={type(pdf.pages[0].Contents).__name__}")
    expected = ["/PLDirect", "/PLInArray", "/PLIndirect", "/PLStream", "/PLTrailer"]
    check("every-site-found", found == expected, f"found {found}")

    clean = os.path.join(tmp, "clean.pdf")
    make_clean(clean)
    with pikepdf.open(clean) as pdf:
        check("clean-file", pdfops.private_keys(pdf) == [], f"found {pdfops.private_keys(pdf)}")

    with pikepdf.open(poisoned) as pdf:
        keys = pdfops.private_keys(pdf)
        check("prefix-is-the-contract", "/XYNotOurs" not in keys, f"found {keys}")
        check("direct-and-array-are-found", {"/PLDirect", "/PLInArray"} <= set(keys), f"found {keys}")
finally:
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{len(FAILS)} failure(s)")
if FAILS:
    print(f"PRIVATE-KEY READER FAILED — {FAILS}")
    raise SystemExit(1)
print("PRIVATE-KEY READER PASSED — every site a key can live is read, and the prefix is the contract")
