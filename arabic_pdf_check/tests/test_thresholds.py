#!/usr/bin/env python3
"""The thresholds in the package are the ones the measurement derived — and nothing else is shipped.

  · presentation forms: value == max(declared, clean maximum)
  · ToUnicode gap share: value == max(declared, clean maximum)
  · orientation: arafix's published 0.30, and it is PASSED to the detector (a value in the manifest that no
    code reads is a sentence, not a threshold)
  · every key in `values` is consumed by the code — a key nobody reads is a lie in the report's manifest
  · the metric form of reader disagreement is REFUSED: its clean minimum is recorded in `observed.refused`,
    no threshold key exists for it, and the blind report only uses the deterministic page-empty form.
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
THRESHOLDS = os.path.join(REPO, "arabic_pdf_check", "thresholds.json")
MEASUREMENTS = os.path.join(REPO, "docs", "checker-v0", "measurements", "pr2", "thresholds.json")
sys.path.insert(0, REPO)

fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        fails.append(name)


th = json.load(open(THRESHOLDS, encoding="utf-8"))
observed = th.get("observed") or {}
check("measured-at", bool(th.get("measured_at")), str(th.get("measured_at")))
check("command-recorded", "checker_measure.py" in (th.get("command") or ""), str(th.get("command")))
check("clean-set-size", int(observed.get("clean_files", 0)) >= 70, str(observed.get("clean_files")))

pf = th["values"]["presentation_forms"]
check("presentation-forms-derived",
      abs(pf["value"] - round(max(pf["declared"], observed["clean_max_presentation_forms"]), 4)) < 1e-9,
      f"value {pf['value']} declared {pf['declared']} clean {observed.get('clean_max_presentation_forms')}")
gap = th["values"]["tounicode_gap_ratio"]
check("gap-ratio-derived",
      abs(gap["value"] - round(max(gap["declared"], observed["clean_max_gap_ratio"]), 4)) < 1e-9,
      f"value {gap['value']} declared {gap['declared']} clean {observed.get('clean_max_gap_ratio')}")
lex = th["values"]["lexical_validity"]
check("lexical-validity-derived",
      abs(lex["value"] - round(observed["clean_min_lexical_validity"] - 0.20, 2)) < 1e-9,
      f"value {lex['value']} clean minimum {observed.get('clean_min_lexical_validity')}")

# The orientation threshold is arafix's published default; the checker must PASS it, not merely store it.
import conformance.checks.visual_order as vo                        # noqa: E402
check("visual-order-matches-arafix",
      abs(float(th["values"]["visual_order"]["value"]) - vo.THRESHOLD) < 1e-9,
      f"manifest {th['values']['visual_order']['value']} arafix {vo.THRESHOLD}")

blind_src = open(os.path.join(REPO, "arabic_pdf_check", "blind.py"), encoding="utf-8").read()
import ast                                                            # noqa: E402
tree = ast.parse(blind_src)
subscripts = {node.slice.value for node in ast.walk(tree)
              if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
              and node.value.id == "th" and isinstance(node.slice, ast.Constant)}
unread = [k for k in th["values"] if k not in subscripts]
check("every-threshold-is-read", not unread,
      f"never subscripted as th['<key>'] in blind.py: {unread}")

check("no-disagreement-threshold", not any(k.startswith("disagreement") for k in th["values"]),
      str(sorted(th["values"])))
check("refusal-recorded", "reader-disagreement-metric" in (observed.get("refused") or {}),
      str(observed.get("refused")))
check("clean-min-pair-recorded", "clean_min_pair_f1" in observed, "")

measured = json.load(open(MEASUREMENTS, encoding="utf-8")) if os.path.exists(MEASUREMENTS) else None
check("committed-measurement-matches", measured is not None and
      measured["values"] == th["values"] and measured["observed"] == observed,
      "docs/checker-v0/measurements/pr2/thresholds.json is stale — re-run scripts/checker_measure.py")
for p in glob.glob(os.path.join(REPO, "docs", "checker-v0", "measurements", "**", "thresholds.json"),
                   recursive=True):
    d = json.load(open(p, encoding="utf-8"))
    if d.get("superseded_by"):
        continue
    check(f"unmarked-measurement-{os.path.relpath(p, REPO)}", d["values"] == th["values"],
          f"{p} is neither the shipped values nor marked superseded_by")

print()
if fails:
    print(f"THRESHOLDS FAILED — {fails}")
    raise SystemExit(1)
print("THRESHOLDS PASSED — the shipped values are the measured ones")
