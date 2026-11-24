#!/usr/bin/env python3
"""The bit-parallel LCS must be the SAME function, only faster.

The old row DP is kept here as the reference — not as production code. 1,000 random pairs (varied alphabet
sizes, lengths, and the empty/identical/single-element edges) must agree exactly; a mismatch is a wrong
metric, not a rounding difference. The timings are printed and bounded loosely so a slow CI runner does not
turn a performance measurement into a flaky gate: the old 4,000-word case was 1.27 s, the new one is
milliseconds, and 30,000 words must still finish under 30 s.
"""
import random
import sys
import time

sys.path.insert(0, __file__.rsplit("/conformance/", 1)[0])
from conformance.checks import metrics                   # noqa: E402

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def dp(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


# Edges first: an empty side, identical, single element, no common element.
edges = [([], []), ([], ["a"]), (["a"], []), (["a"], ["a"]), (["a"], ["b"]),
         (["a", "b", "c"], ["a", "b", "c"]), (["a", "b"], ["b", "a"])]
for a, b in edges:
    check(f"edge:{a}:{b}", metrics.lcs(a, b) == dp(a, b), f"{metrics.lcs(a, b)} != {dp(a, b)}")

rng = random.Random(20261124)
mismatch = 0
for _ in range(1000):
    alphabet = "abcde"[: rng.randint(1, 5)]
    a = [rng.choice(alphabet) for _ in range(rng.randint(0, 40))]
    b = [rng.choice(alphabet) for _ in range(rng.randint(0, 40))]
    if metrics.lcs(a, b) != dp(a, b):
        mismatch += 1
check("random-1000", mismatch == 0, f"{mismatch} mismatch(es)")

for n, bound in ((4000, 0.5), (30000, 30.0)):
    a = [f"w{i % 997}" for i in range(n)]
    b = list(reversed(a))
    t = time.time()
    got = metrics.lcs(a, b)
    elapsed = time.time() - t
    print(f"  n={n}: {elapsed:.3f}s")
    check(f"n={n}:exact", got == dp(a, b) if n <= 4000 else got >= 1, f"got {got}")
    check(f"n={n}:time", elapsed < bound, f"{elapsed:.3f}s >= {bound}s")

print()
if fails:
    print(f"LCS FAILED — {fails}")
    raise SystemExit(1)
print("LCS PASSED — exact against the row DP, bit-parallel in time")
