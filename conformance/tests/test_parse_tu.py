#!/usr/bin/env python3
"""The one ToUnicode parser: five audit cases, the range bomb, and the real CMaps of the four documents.

The audit (2026-11-24) measured four defects in the old regex reader: a multi-line array, a `%` comment, a
ligature destination and two ranges on one line. The old reader raised on three and silently dropped half of
the fourth. This test holds the grammar (ISO 32000-1 §9.10.3 / Adobe TN #5014) and the two out-of-spec shapes
the assignment sends: a 65,536-code range and a four-byte range bomb.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

from fix_text_layer import CMapError, parse_tu, parse_tu_report   # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def wrap(body: str, kind: str = "bfrange", count: int = 1) -> str:
    head = ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo\n"
            "<< /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n")
    return head + f"{count} begin{kind}\n{body}\nend{kind}\nendcmap\nend\nend\n"


cases = {
    "single-line-array": ("<0001> <0002> [<0627> <0628>]", {1: "ا", 2: "ب"}),
    "multi-line-array": ("<0001> <0002> [\n<0627>\n<0628>\n]", {1: "ا", 2: "ب"}),
    "comment-in-range": ("% a comment\n<0001> <0002> <0627>", {1: "ا", 2: "ب"}),
    "ligature-destination": ("<0001> <0002> <06440627>", {1: "لا", 2: "لب"}),
    "two-ranges-one-line": ("<0001> <0002> <0627> <0010> <0011> <0628>",
                            {1: "ا", 2: "ب", 0x10: "ب", 0x11: "ة"}),
}
for name, (body, expected) in cases.items():
    try:
        report = parse_tu_report(wrap(body))
        got = report["map"]
        check(f"{name}:no-exception", True)
        check(f"{name}:complete", got == expected, f"{got} != {expected}")
        check(f"{name}:not-unparsable", report["unparsable"] is False, str(report["problems"]))
        check(f"{name}:strict-equal", parse_tu(wrap(body)) == expected)
    except Exception as exc:
        check(f"{name}:no-exception", False, f"{type(exc).__name__}: {exc}")

# The 65,536-code range is at the cap, not over it: complete, no exception, no cap flag.
full = wrap("<0000> <FFFF> <0000>")
t = time.time()
report = parse_tu_report(full)
check("range-65536", len(report["map"]) == 65536 and report["capped"] == 0 and not report["unparsable"],
      f"len={len(report['map'])} capped={report['capped']} fatal={report['unparsable']}")
check("range-65536:surrogates-named", any("lone UTF-16 surrogate" in p for p in report["problems"]),
      str(report["problems"])[:200])
check("range-65536:fast", time.time() - t < 10, f"{time.time() - t:.2f}s")

# The four-byte bomb: capped, never an exception, and the map stops honestly at the cap.
bomb = wrap("<00000000> <FFFFFFFF> <0000>")
t = time.time()
report = parse_tu_report(bomb)
check("bomb:no-exception", True)
check("bomb:capped", report["capped"] == 1, str(report["capped"]))
check("bomb:bounded", 0 < len(report["map"]) <= 65536, str(len(report["map"])))
check("bomb:fast", time.time() - t < 10, f"{time.time() - t:.2f}s")

# A wrong count is a named note, not a refusal: readers ignore the count and the entries are complete.
report = parse_tu_report(wrap("<0001> <0627>", kind="bfchar", count=5))
check("count-mismatch:not-fatal", report["unparsable"] is False, str(report["problems"]))
check("count-mismatch:map", report["map"] == {1: "ا"}, str(report["map"]))
check("count-mismatch:named", any("count says 5" in p for p in report["problems"]), str(report["problems"]))

# A source with no destination is fatal, and the strict wrapper refuses instead of returning a partial map.
bad = wrap("<0001>", kind="bfchar", count=1)
report = parse_tu_report(bad)
check("missing-destination:report", report["unparsable"] is True, str(report["problems"]))
try:
    parse_tu(bad)
    check("missing-destination:strict-raises", False, "no exception")
except CMapError as exc:
    check("missing-destination:strict-raises", True, str(exc))

report = parse_tu_report(wrap("1 usecmap", kind="bfchar", count=1))
check("usecmap:unresolved", report["unparsable"] is True and any("usecmap" in p for p in report["problems"]),
      str(report["problems"]))

# Real CMaps: the four shipped PDFs carry Chrome/Skia output, header and all. The parser must read them.
import pikepdf                                            # noqa: E402

real = 0
for name in ("guide-v2-ar", "report", "najd", "report-print"):
    path = os.path.join(REPO, name + ".pdf")
    if not os.path.exists(path):
        continue
    with pikepdf.open(path) as pdf:
        found = 0
        for page in pdf.pages:
            res = page.obj.get("/Resources")
            for _, font in (res or {}).get("/Font", {}).items():
                tu = font.get("/ToUnicode")
                if tu is None:
                    continue
                found += 1
                report = parse_tu_report(tu.read_bytes().decode("latin-1"))
                check(f"real:{name}:{found}:parsed", not report["unparsable"] and not report["capped"],
                      str(report["problems"])[:200])
                check(f"real:{name}:{found}:map", len(report["map"]) > 0, str(len(report["map"])))
                break
            if found:
                break
        real += found
if real:
    check("real:at-least-one", True, str(real))
else:
    # Declared skip, not a pass: the four documents are build artifacts that exist on the macOS job.
    # The Linux checker job still runs the parser cases above; this line says what it did not see.
    print("SKIP real — none of the four built PDFs is present here (the macOS job builds them)")

print()
if fails:
    print(f"PARSE TU FAILED — {fails}")
    raise SystemExit(1)
print(f"PARSE TU PASSED — 5 audit cases, the bomb, the edges and {real} real CMap(s)")
