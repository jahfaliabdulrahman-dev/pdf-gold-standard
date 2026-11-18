"""Where MuPDF's word order leaves the markup's order — per divergent run, with the PDF line it lands on.

B9: the floor is calibrated per document from what the layer can do, so the runs that lower the
sequence ratio must be named before any threshold is written. This prints them: each non-equal run
of words between the derived markup and MuPDF's extraction, the page/block/line it closest lands on,
and a per-page count — the input to fixing the layer rather than lowering the floor.

    python3 scripts/line_order_report.py out.pdf [--min-run 2] [--top 40]
"""
import argparse
import collections
import difflib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_pdf as V          # noqa: E402  (the gate's own tokenisation, so numbers agree)
import spec_loader              # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--min-run", type=int, default=2, help="ignore runs shorter than this many words")
    ap.add_argument("--top", type=int, default=40, help="print at most this many runs (largest first)")
    args = ap.parse_args()

    spec_loader.load()                     # PDF_SPEC decides which document the truth is read from
    truth = V.truth_words()

    import fitz
    doc = fitz.open(args.pdf)
    got, where = [], []
    for pno, page in enumerate(doc, 1):
        # The gate reads `p.get_text()`; its words come from lines, so rebuild the same stream line by
        # line (`get_text("words")` splits a word across a line break and would shift every index).
        for bno, block in enumerate(page.get_text("dict")["blocks"]):
            for lno, line in enumerate(block.get("lines", [])):
                text = "".join(s["text"] for s in line["spans"])
                for w in V.source_words(text):
                    got.append(w)
                    where.append((pno, bno, lno))

    ratio = V.sequence_ratio(truth, got)
    sm = difflib.SequenceMatcher(None, truth, got, autojunk=False)   # the runs behind that ratio
    gate_stream = V.source_words("\n".join(p.get_text() for p in doc))
    if gate_stream != got:
        print(f"WARNING: line-rebuild stream differs from get_text() ({len(got)} vs {len(gate_stream)} tokens)")
    print(f"{os.path.basename(args.pdf)}: sequence {ratio:.3f} · "
          f"{len(truth)} source words · {len(got)} extracted · {len(doc)} pages")

    runs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        size = max(i2 - i1, j2 - j1)
        if size < args.min_run:
            continue
        at = where[j1] if j1 < len(where) else (where[-1] if where else (0, 0, 0))
        runs.append((size, tag, i1, i2, j1, j2, at))

    by_page = collections.Counter()
    for size, tag, i1, i2, j1, j2, at in runs:
        by_page[at[0]] += size

    print("\nper page (runs of ≥%d words):" % args.min_run)
    for pno in sorted(by_page):
        print(f"  p{pno:>2}: {by_page[pno]:>4} words")

    print(f"\nlargest {min(args.top, len(runs))} of {len(runs)} runs:")
    for size, tag, i1, i2, j1, j2, at in sorted(runs, reverse=True)[: args.top]:
        t = " ".join(truth[i1:i2])[:110]
        g = " ".join(got[j1:j2])[:110]
        print(f"\n[{tag} {size}] p{at[0]} b{at[1]} l{at[2]}")
        print(f"  markup: {t}")
        print(f"  mupdf : {g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
