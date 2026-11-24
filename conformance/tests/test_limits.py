#!/usr/bin/env python3
"""C3 guard: a limit without a working control is refused by name, and a limit only excuses its narrow slice.

Four controls:
  1. A fabricated limit with no `control_script` is refused by `usable()` — and the refusal names it.
  2. A limit whose control path does not exist is refused.
  3. The two declared limits pass their controls on this machine (the controls really reproduce).
  4. The digit predicate excuses an exact reversal and nothing else; the bidi predicate excuses at most the
     control's per-line count.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))

from conformance.checks import metrics
from conformance.readers import limitations as L

fails = []


def check(name, ok, detail):
    print(("PASS " if ok else "FAIL ") + name + " - " + detail)
    if not ok:
        fails.append(name)


# --- 1/2 · refusals --------------------------------------------------------
original = L.load
L.load = lambda: [{"id": "fake-no-control", "reader": "mupdf", "metric": "digit_runs",
                   "pattern": "reversed_truth_run"}]
ok, refused, _controls = L.usable("mupdf", "2.1", mode="live")
check("no-control-refused", not ok and any("fake-no-control" in r for r in refused), "; ".join(refused))
L.load = lambda: [{"id": "fake-missing-script", "reader": "mupdf", "metric": "digit_runs",
                   "pattern": "reversed_truth_run", "control_script": "controls/nope.py"}]
ok, refused, _controls = L.usable("mupdf", "2.1", mode="live")
check("missing-script-refused", not ok and any("does not exist" in r for r in refused), "; ".join(refused))
L.load = original

# --- 3 · the declared limits really reproduce ------------------------------
for limit in L.load():
    out = L.run_control(limit)
    check(f"control:{limit['id']}", out["reproduces"] is True, str(out["detail"])[:130])

# --- 4 · the predicates are narrow ----------------------------------------
truth = "المبلغ ٢٠٢٦ والتاريخ ٢٠٢٦/١١/١٩"
out_ok = "المبلغ ٢٠٢٦ والتاريخ ٢٠٢٦/١١/١٩"
out_rev = "المبلغ ٦٢٠٢ والتاريخ ٢٠٢٦/١١/١٩"
out_bad = "المبلغ ٦٢٠٣ والتاريخ ٢٠٢٦/١١/١٩"

limit = {"id": "t", "reader": "mupdf", "metric": "digit_runs", "pattern": "reversed_truth_run",
         "reader_version_measured": "2.1"}
res_ok = metrics.measure(out_ok, truth)
res_rev = metrics.measure(out_rev, truth)
res_bad = metrics.measure(out_bad, truth)
a_rev = L.apply(limit, truth, out_rev, dict(res_rev, metrics=dict(res_rev["metrics"])), {})
a_bad = L.apply(limit, truth, out_bad, dict(res_bad, metrics=dict(res_bad["metrics"])), {})
check("digit:reversal-excused", a_rev["excused"] >= 1, f"excused {a_rev['excused']} — {a_rev['detail']}")
check("digit:non-reversal-kept", a_bad["excused"] == 0, f"excused {a_bad['excused']} on a non-reversal")
check("digit:intact-needs-nothing", res_ok["metrics"]["digit_runs"] == 1.0, "1.0 without a limit")

# The real control's own output — a hand-written {"per_line": 2} hid a key-name bug once (review S1): the
# control wrote `pdftotext_per_line`, the predicate read `per_line`, and the limit excused nothing.
bidi_limit = next(l for l in L.load() if l["id"] == "poppler-bidi-decorations")
real = L.run_control(bidi_limit)
per_line = int(real["detail"]["per_line"])
check("bidi:control-key", per_line >= 1, f"the control's detail carries per_line={per_line}")
decorated = "أ\nب\nج" + "\u202b" * (per_line * 3 + 4)
res = {"metrics": {}, "defects": {"bidi": per_line * 3 + 4}}
a = L.apply(bidi_limit, "أ\nب\nج", decorated, res, real)
check("bidi:capped-per-line", a["excused"] == per_line * 3 and res["defects"]["bidi"] == 4,
      f"excused {a['excused']} of {per_line * 3 + 4} at {per_line}/line over 3 lines, {res['defects']['bidi']} left")

print(f"\nDECLARED LIMITS: {len(L.load())}")
if fails:
    print(f"TEST FAILED — {fails}")
    raise SystemExit(1)
print("LIMITS GUARD PASSED")
