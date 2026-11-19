#!/usr/bin/env python3
"""C1 guard: the corpus derives its manifest, meets its floors, and `truth()` is the case file alone.

Four controls, each of which can fail:
  1. `truth()` matches a hand-written answer for five cases written **inside this test**. This is the only
     place a truth is typed by hand — to test the function, never to fill a case.
  2. Deleting one case from a category at its floor makes coverage fail (the corpus floor bites).
  3. A case file that violates the schema is refused by name (unknown block, ragged table, bad level).
  4. MANIFEST.json is exactly what the case files derive (both directions).
"""
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)

from conformance.corpus import cases as C
from conformance.corpus import coverage, manifest
from conformance.corpus.truth import arabic_indic, truth

fails = []


def check(name, ok, detail):
    print(("PASS " if ok else "FAIL ") + name + " - " + detail)
    if not ok:
        fails.append(name)


# --- 1 · truth() on five hand-written cases ---------------------------------
HAND = [
    ({"id": "t1", "category": "shaping", "lang": "ar", "font": "plex", "note": "hand",
      "blocks": [{"type": "heading", "level": 1, "text": "عنوان"},
                 {"type": "paragraph", "text": "فقرة."}]},
     "عنوان\nفقرة."),
    ({"id": "t2", "category": "tables", "lang": "ar", "font": "plex", "note": "hand",
      "blocks": [{"type": "table", "header": ["البند", "المبلغ"], "rows": [["رسوم", "-6,006.965"]]}]},
     "البند\nالمبلغ\nرسوم\n-6,006.965"),
    ({"id": "t3", "category": "tables", "lang": "ar", "font": "plex", "note": "hand",
      "blocks": [{"type": "table", "header": [["المجموع", "التفاصيل"], ["البند", "المبلغ"]],
                  "rows": [["رسوم", "١٠٠"]]}]},
     "المجموع\nالتفاصيل\nالبند\nالمبلغ\nرسوم\n١٠٠"),
    ({"id": "t4", "category": "lists", "lang": "ar", "font": "plex", "note": "hand",
      "blocks": [{"type": "list", "ordered": True, "items": ["أولًا", "ثانيًا"]},
                 {"type": "list", "ordered": False, "items": ["نقطة"]}]},
     "١. أولًا\n٢. ثانيًا\nنقطة"),
    ({"id": "t5", "category": "vocalisation", "lang": "ar", "font": "amiri", "note": "hand",
      "blocks": [{"type": "paragraph", "text": "الْحَمْدُ"}]},
     "الْحَمْدُ"),
]
for case, want in HAND:
    C.validate(case, case["id"])
    got = truth(case)
    check(f"truth:{case['id']}", got == want, repr(got) if got != want else "matches the hand-written answer")
check("arabic_indic", [arabic_indic(n) for n in (1, 10, 25, 99)] == ["١", "١٠", "٢٥", "٩٩"],
      "1,10,25,99 → ١,١٠,٢٥,٩٩")

# --- 2 · the floor bites ----------------------------------------------------
real = C.load_all()
check("coverage-ok", not coverage.problems(real), coverage.summary(real))
at_floor = [c for c in real if c["category"] == "lists"]
cut = [c for c in real if c["id"] != at_floor[0]["id"]]
cut_names = [p.split(":")[0] for p in coverage.problems(cut)]
check("floor-bites", any("lists" in p for p in coverage.problems(cut)), "; ".join(coverage.problems(cut)[:1]))

# --- 3 · the schema refuses by name ----------------------------------------
bad = [
    ("unknown block", {"blocks": [{"type": "figure", "text": "x"}]}),
    ("ragged row", {"blocks": [{"type": "table", "header": ["a", "b"], "rows": [["1"]]}]}),
    ("bad level", {"blocks": [{"type": "heading", "level": 7, "text": "x"}]}),
    ("empty blocks", {"blocks": []}),
]
for label, patch in bad:
    case = copy.deepcopy(HAND[0][0])
    case.update(patch)
    try:
        C.validate(case, label)
        check(f"schema:{label}", False, "accepted a case it should refuse")
    except C.CaseError as exc:
        check(f"schema:{label}", True, f"refused: {str(exc)[:70]}")

# --- 4 · the manifest is derived in both directions -------------------------
check("manifest-derived", not manifest.problems(), "; ".join(manifest.problems()[:2]) or "MANIFEST.json == the cases")
m = manifest.derive()
check("manifest-counts", m["total"] == len(real) and sum(m["counts"].values()) == m["total"],
      f"{m['total']} cases · {m['counts']}")

print(f"\nDERIVED: {coverage.summary(real)}")
if fails:
    print(f"TEST FAILED — {fails}")
    raise SystemExit(1)
print("CORPUS GUARD PASSED")
