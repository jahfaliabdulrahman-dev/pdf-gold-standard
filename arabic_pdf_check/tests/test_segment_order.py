#!/usr/bin/env python3
"""The segment-order rule: a reader is an outlier only against a strict reader majority, never by itself.

The real population is deposited in `docs/checker-v0/measurements/segment-order.json`; this file quotes NO
number from it — the counts, the range and the file total are read there by the tests that need them, so a
regenerated artifact cannot leave a stale figure in a docstring. These are the
synthetic controls the rule needs on every run, one per branch: a majority and an outlier, an agreement, a
split, too few voters, a palindrome, and a letter-reversed reading that must not vote at all.
"""
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, REPO)

from conformance.checks import lexical, segment_order                          # noqa: E402

A, B, C = "كتاب", "مدرسة", "قلم"
# The tokenizer normalises (ة→ه …): the vocabulary and the expectations are the same normalisation.
NA, NB, NC = (lexical.normalize(w) for w in (A, B, C))
VOCAB = frozenset({NA, NB, NC})
ARTIFACT = os.path.join(REPO, "docs", "checker-v0", "measurements", "segment-order.json")

passed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if not condition:
        print(f"FAIL {name} — {detail}")
        raise SystemExit(1)
    passed += 1
    print(f"PASS {name}")


def line(*words: str) -> str:
    return " ".join(words)


def main() -> int:
    # 1. a majority and an outlier: three readers on one order, one on its reverse
    texts = {"a": line(A, B), "b": line(A, B), "c": line(A, B), "d": line(B, A)}
    found = segment_order.findings(texts, VOCAB)
    check("outlier: the one reversed reader is flagged", set(found) == {"d"}, str(found))
    check("outlier: the evidence names both orders", found["d"][0]["words"] == [NB, NA]
          and found["d"][0]["reversed_of"] == [NA, NB], str(found["d"]))
    check("outlier: display is the reader's word, not the normalised comparison key",
          found["d"][0]["display"] == [B, A], str(found["d"][0]["display"]))
    check("outlier: agree counts the readers that hold the majority (3 of 4), not the voters (4)",
          (found["d"][0]["agree"], found["d"][0]["voters"]) == (3, 4), str(found["d"][0]))
    check("outlier: no page is claimed when the caller passed none", found["d"][0]["page"] is None)

    # 2. agreement raises nothing
    check("agreement: identical orders raise nothing",
          segment_order.findings({"a": line(A, B), "b": line(A, B), "c": line(A, B)}, VOCAB) == {})

    # 3. a split has no ground truth
    check("split: 2-2 raises nothing",
          segment_order.findings({"a": line(A, B), "b": line(A, B), "c": line(B, A), "d": line(B, A)},
                                 VOCAB) == {})

    # 4. two voters are not a majority of anything
    check("too few voters: two readers raise nothing",
          segment_order.findings({"a": line(A, B), "b": line(B, A)}, VOCAB) == {})

    # 5. a palindrome cannot be told apart from its reverse
    check("palindrome: a segment equal to its reverse raises nothing",
          segment_order.findings({"a": line(A, A), "b": line(A, A), "c": line(A, A)}, VOCAB) == {})

    # 6. a letter-reversed reading is visual-order's finding and does not vote (its words are canonicalised)
    reversed_reader = " ".join(w[::-1] for w in (A, B))
    found = segment_order.findings({"a": line(A, B), "b": line(A, B), "c": line(A, B), "v": reversed_reader},
                                   VOCAB)
    check("letter-reversed reading is not a voter and not an outlier", found == {}, str(found))

    # 7. a line with one Arabic word is not a segment
    check("single word: one word is not a segment",
          segment_order.findings({"a": A, "b": A, "c": A}, VOCAB) == {})

    # 8. the deposited population: the clean side is a reader finding, not a file defect, and the broken side is
    #    PDFium's — the range is READ here, never typed (a typed range went stale once: «3–7» vs 2–6).
    art = json.load(open(ARTIFACT, encoding="utf-8"))
    sets = art["sets"]
    must = json.load(open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"), encoding="utf-8"))
    clean_all = [f["readers"] for name in ("clean-documents", "clean-corpus-cases") for f in sets[name]["files"]]
    worst_clean = max([n for readers in clean_all for n in readers.values()] or [0])
    check("artifact: the clean maximum is below the shipped value", worst_clean < must["values"]["segment_order_min"]["value"],
          f"{worst_clean} vs {must['values']['segment_order_min']['value']}")
    broken = [f["readers"]["pdfium"] for f in sets["zatca"]["files"] if f["readers"]["pdfium"]]
    check("artifact: PDFium carries the ZATCA reversal and no other reader does",
          sum(broken) > 0
          and all(v == 0 for f in sets["zatca"]["files"] for k, v in f["readers"].items() if k != "pdfium"),
          str(sets["zatca"]["totals"]))
    value = must["values"]["segment_order_min"]["value"]
    check("threshold: the value is the clean maximum + 1 (the one derivation rule)",
          value == max(must["values"]["segment_order_min"]["declared"], worst_clean + 1),
          f"{value} vs clean {worst_clean}")
    # blind.py fires at `count >= value`, so the separation is clean_max < value <= smallest broken count
    check("separation: the clean maximum is below the value and every broken file reaches it",
          min(broken) >= value > worst_clean, f"clean {worst_clean}, value {value}, min broken {min(broken)}")
    art_range = f"{min(broken)}-{max(broken)}"
    shipped = must["values"]["segment_order_min"]["source"]
    check("the shipped sentence quotes this artifact's range", f"{min(broken)}-{max(broken)} per affected" in shipped,
          f"artifact {art_range} vs source: {shipped[:120]}")
    check("the shipped sentence quotes this artifact's total", f"{sum(broken)} reversed segment(s)" in shipped,
          f"total {sum(broken)}")

    print(f"\nSEGMENT-ORDER RULE PASSED — {passed} check(s); a majority of voters, one outlier, and no vote from "
          f"a visual reading")
    return 0


if __name__ == "__main__":
    sys.exit(main())
