#!/usr/bin/env python3
"""C2 guard: each metric has an example that breaks it, and `N` is the one documented normalization.

A metric that has never been seen failing measures nothing. Each control below is a real defect of the kind
the corpus contains, and the assertion is that the metric moves while the others stay put where they should.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from conformance.checks import metrics as M

fails = []


def check(name, ok, detail):
    print(("PASS " if ok else "FAIL ") + name + " - " + detail)
    if not ok:
        fails.append(name)


TRUTH = "كشف الحساب\nرسوم -6,006.965\nالتاريخ ٢٠٢٦/١١/١٩"

# exact / skeleton: one diacritic removed must leave skeleton_exact at 0 with the marks in the truth, and
# exact at 0 — the pair is what separates a mark defect from a letter defect.
v = {"metrics": {}, "defects": {}}
t_marked = "الْحَمْدُ لِلَّهِ"
check("exact:identical", M.exact(TRUTH, TRUTH) == 1.0, "1.0")
check("exact:reversed-word", M.exact("الحساب كشف\nرسوم -6,006.965\nالتاريخ ٢٠٢٦/١١/١٩", TRUTH) == 0.0,
      "word order matters")
check("skeleton:mark-removed", M.skeleton_exact("الحمد لله", t_marked) == 1.0 and M.exact("الحمد لله", t_marked) == 0.0,
      "skeleton 1.0 while exact 0.0")
check("skeleton:letter-changed", M.skeleton_exact("الحمد للة", t_marked) == 0.0, "a letter change survives mark removal")

# word_f1: a missing word is penalised, but not zeroed
check("word_f1:one-of-three", 0.79 < M.word_f1("أ ب", "أ ب ج") < 0.81, f"{M.word_f1('أ ب', 'أ ب ج'):.3f} — 2 of 3 with perfect precision")

# order: LCS — a swap of adjacent words lowers it without zeroing it
o = M.order("ب أ ج", "أ ب ج")
check("order:swap", 0.66 < o < 0.67, f"{o:.3f} for one adjacent swap")

# digit_runs: the incident (sign moved) must fail, an exact run must pass, and a reversed run is a miss
check("digit_runs:intact", M.digit_runs_ratio("المبلغ -6,006.965 ريال", "المبلغ -6,006.965 ريال") == 1.0, "1.0")
check("digit_runs:sign-moved", M.digit_runs_ratio("المبلغ 6,006.965- ريال", "المبلغ -6,006.965 ريال") == 0.0,
      "the run is signed; moving the sign loses it")
check("digit_runs:reversed-digits", M.digit_runs_ratio("التاريخ ٦٢٠٢/١١/١٩", "التاريخ ٢٠٢٦/١١/١٩") == 2 / 3,
      "a date is three runs («/» is not a separator): the reversed year is lost, ١١ and ١٩ survive")
check("digit_runs:one-of-two", M.digit_runs_ratio("المبلغ -6,006.965 والتاريخ ٦٢٠٢/١١/١٩",
                                                "المبلغ -6,006.965 والتاريخ ٢٠٢٦/١١/١٩") == 0.75, "0.75 — one run of four lost")

# N: bidi controls and whitespace collapse, but digits, tatweel and marks are untouched
check("N:bidi+ws", M.N("أ\u200f\nب\t\tج") == "أ ب ج", repr(M.N("أ\u200f\nب\t\tج")))
check("N:keeps-tatweel", M.N("مـــال") == "مـــال", "U+0640 survives the normalization")
check("N:keeps-marks", M.N("الْحَمْدُ") == "الْحَمْدُ", "harakat survive")
check("N:keeps-digit-script", M.N("٢٠٢٦") != M.N("2026"), "no digit mapping")
# The assignment's `N` removes direction controls and nothing else. The joiners `fix_text_layer`
# inserts stay: they are in the file, a copy-paste carries them, and dropping them in `N` was measured
# to flatter the pipeline (review S6). `zero_width` counts them; `invisible-format` fails the file.
check("N:keeps-zero-width", M.N("تطوي\u2060ل\u200b") == "تطوي\u2060ل\u200b",
      "the producer's joiners stay in N — the count is the metric, not a silent removal")
check("zero_width:counts", M.zero_width_count("أ\u200bب\u2060ج") == 2, "two joiners, two counted")

# defects: each counter has an input that trips it
d = M.defects("\uFB50", "")                      # presentation form
check("defects:presentation", d["presentation_forms"] == 1, str(d))
check("defects:pua", M.defects("\uE000", "")["pua"] == 1, "private use")
check("defects:replacement", M.defects("\uFFFD", "")["replacement"] == 1, "U+FFFD")
check("defects:bidi-excess", M.defects("أ\u200f", "أ")["bidi"] == 1, "one bidi control beyond the truth")
check("defects:bidi-truth-allowed", M.defects("أ\u200f", "أ\u200f")["bidi"] == 0, "the truth's own marks are not a defect")
check("defects:tatweel", M.defects("مـــال", "مال")["tatweel_excess"] == 3, "three tatweel beyond the truth")
check("defects:zero-width", M.defects("أ\u2060ب", "أب")["zero_width"] == 1, "the producer's own joiners are counted")
check("defects:bidi-floor-is-file", M.defects("أ\u200f", "أ", floor_bidi=1)["bidi"] == 0, "the file's own mark is not the reader's defect")

print(f"\nDERIVED: {len(M.METRICS)} metrics · 5 defect counters")
if fails:
    print(f"TEST FAILED — {fails}")
    raise SystemExit(1)
print("METRICS GUARD PASSED")
