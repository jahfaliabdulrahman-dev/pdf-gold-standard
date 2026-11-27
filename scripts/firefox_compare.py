#!/usr/bin/env python3
"""Firefox gate (PR-5c §2): does the text a person copies out of Firefox agree with what our pdf.js reader returns?

Three criteria, declared before the measurement and not re-interpreted afterwards:

  1. the ORDER agrees on every file — both reversed, or both logical;
  2. the lam-alef transposition appears in both or in neither;
  3. word agreement on the compared passage >= 0.90 (multiset F1, digits and order blind).

The comparison is made on THE SAME PAGES on both sides. A copy covers a contiguous run of pages
(the page in front of the person, or several); the reader's text is cut to the contiguous run of pages i..j that
best matches the copy, and i..j is recorded; inside those pages the reader's words are cut to the contiguous run
that best matches the copied passage (a hand selection rarely spans a whole page). Comparing a copied page against the whole document's
reader text fails a perfect copy (a passage identical to the reader's own text scored F1 0.347 against the whole
document), and a lam-alef present elsewhere in the document would be counted against a passage that has none.

Input: one copied-text file per PDF (the owner pastes the selection from Firefox into a text file). The three
targets are the SDK invoice, the guide, and the owner's calibration file — for the last one NOTHING but the
numbers and the verdicts is written out: no excerpt, no name, no sha.

Usage:
  python3 scripts/firefox_compare.py --copies /tmp/ff/copies.json --out docs/checker-v0/measurements/pr5c/firefox-compare.json
    copies.json = {"firefox_version": "161.0", "files": [{"label": "...", "pdf": "<path>", "copy": "<path>",
                                                          "public": true|false}, ...]}
"""
import argparse
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

from conformance.checks import lexical, structure, visual_order      # noqa: E402
from conformance.readers import pdfjs                                # noqa: E402

THRESHOLD = 0.90


def direction(text: str) -> dict:
    """The same arAFix order check the checker uses; `visual` means the copy keeps the opposite order."""
    got = visual_order.inspect(text)
    return {"visual": bool(got["visual"]), "score": round(got["score"], 3) if got.get("score") is not None else None}


def lam_alef(text: str) -> int:
    return int(lexical.validity(text)["lam_alef"])


def f1(a: str, b: str) -> float:
    ca, cb = structure.words_multi(a), structure.words_multi(b)
    if not ca and not cb:
        return 1.0
    overlap = sum((ca & cb).values())
    if not overlap:
        return 0.0
    p, r = overlap / sum(ca.values()), overlap / sum(cb.values())
    return 2 * p * r / (p + r)


def matched_window(copy: str, pages: list[str]) -> tuple[str, tuple[int, int], float]:
    """The contiguous run of pages i..j (1-based) whose words best match the copy: (text, (i, j), F1).

    A person copies the page in front of them, not necessarily page 1, so every contiguous run is tried; ties
    keep the shorter run."""
    best = ("", (0, 0), -1.0)
    for i in range(len(pages)):
        for j in range(i + 1, len(pages) + 1):
            window = "\n".join(pages[i:j])
            score = f1(copy, window)
            if score > best[2] + 1e-9 or (abs(score - best[2]) <= 1e-9 and (j - i) < (best[1][1] - best[1][0] + 1)):
                best = (window, (i + 1, j), score)
    return best


def matched_span(copy: str, window: str) -> tuple[str, float]:
    """Inside the matched pages, the contiguous run of the reader's words that best matches the copy: (text, F1).

    A selection made by hand rarely starts on the page's first word or ends on its last; the criterion is
    agreement on THE COPIED PASSAGE, so the reader's side is cut to the same passage. Every word the copy
    holds still has to be found, in the reader's order, for the F1 to stay high — the cut only removes words
    the person did not select."""
    from collections import Counter
    from conformance.checks.structure import _token, metrics
    raw = metrics.N(window).split()
    toks = [_token(t) for t in raw]
    want = structure.words_multi(copy)
    total_want = sum(want.values())
    best = (window, f1(copy, window))
    if not toks or not total_want:
        return best
    for i in range(len(toks)):
        have, overlap = Counter(), 0
        for j in range(i, len(toks)):
            t = toks[j]
            have[t] += 1
            if have[t] <= want.get(t, 0):
                overlap += 1
            if overlap:
                p, r = overlap / (j - i + 1), overlap / total_want
                score = 2 * p * r / (p + r)
                if score > best[1] + 1e-9:
                    best = (" ".join(raw[i:j + 1]), score)
    return best


def self_test() -> int:
    """The harness must pass the reader against itself on one page, and must not judge a page against a document."""
    import tempfile
    probe = os.environ.get("FIREFOX_COMPARE_PROBE")
    if not probe or not os.path.isfile(probe):
        print("self-test needs FIREFOX_COMPARE_PROBE=<a multi-page Arabic PDF>")
        return 2
    pages = pdfjs.pages_many([probe])[0]
    window, k, score = matched_window(pages[0], pages)
    ok_same = k == (1, 1) and score == 1.0
    _, k_last, score_last = matched_window(pages[-1], pages)
    ok_same = ok_same and k_last == (len(pages), len(pages)) and score_last == 1.0
    print(f"last page vs its own window: pages={k_last} F1={score_last:.3f}")
    whole = f1(pages[0], "\n".join(pages)) if len(pages) > 1 else 1.0
    print(f"page 1 vs its own window: pages={k} F1={score:.3f} -> {'ok' if ok_same else 'FAIL'}")
    print(f"page 1 vs whole document (the old comparison): F1={whole:.3f} (pages={len(pages)})")
    return 0 if ok_same else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--copies")
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not (args.copies and args.out):
        ap.error("--copies and --out are required")
    spec = json.load(open(args.copies, encoding="utf-8"))
    out = {"generated_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
           "firefox_version": spec.get("firefox_version"), "criteria": {"word_agreement": THRESHOLD},
           "files": []}
    failures = []
    for entry in spec["files"]:
        label, public = entry["label"], bool(entry.get("public"))
        firefox_text = open(entry["copy"], encoding="utf-8", errors="replace").read()
        pages = pdfjs.pages_many([entry["pdf"]])[0]
        page_text, k, _ = matched_window(firefox_text, pages)
        ours, _ = matched_span(firefox_text, page_text)
        row = {
            "label": label,
            "public": public,
            "firefox": {**direction(firefox_text), "lam_alef": lam_alef(firefox_text),
                        "chars": len(firefox_text), "runs": lexical.validity(firefox_text)["runs"]},
            "pdfjs": {**direction(ours), "lam_alef": lam_alef(ours),
                      "chars": len(ours), "runs": lexical.validity(ours)["runs"]},
            "word_agreement": round(f1(firefox_text, ours), 3),
            "pages_compared": list(k),
            "pages_in_document": len(pages),
        }
        row["order_agrees"] = row["firefox"]["visual"] == row["pdfjs"]["visual"]
        row["lam_alef_agrees"] = (row["firefox"]["lam_alef"] > 0) == (row["pdfjs"]["lam_alef"] > 0)
        row["words_agree"] = row["word_agreement"] >= THRESHOLD
        row["passes"] = row["order_agrees"] and row["lam_alef_agrees"] and row["words_agree"]
        if public:
            row["excerpt"] = {"firefox": " ".join(firefox_text.split())[:160],
                              "pdfjs": " ".join(ours.split())[:160]}
        if not row["passes"]:
            failures.append(label)
        out["files"].append(row)
        print(f"{label:28} order={row['order_agrees']} lam-alef={row['lam_alef_agrees']} "
              f"words={row['word_agreement']} -> {'PASS' if row['passes'] else 'FAIL'}")
    out["failures"] = failures
    out["verdict"] = "pass" if not failures else "fail"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"\nFIREFOX GATE {out['verdict'].upper()} — {len(out['files']) - len(failures)}/{len(out['files'])} file(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
