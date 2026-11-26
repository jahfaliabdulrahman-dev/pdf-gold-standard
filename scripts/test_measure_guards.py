#!/usr/bin/env python3
"""The two guards the audit of 2026-11-25 asked for, each with the case that must fail.

  1. `--tolerance` is PER KEY: a drift inside its own key's tolerance passes, a drift outside it fails, and a
     key with no tolerance is exactly zero. The audit's finding was one absolute 0.05 over keys whose scales
     run from 0.01 to 0.67.
  2. a missing clean document is a REFUSAL that names it. `--allow-missing doc=<reason>` is the only way past
     it, and the gap is carried into the artifact.

Every check below drives the function the script actually uses; none of them re-implements the rule.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

import checker_measure as cm                                                     # noqa: E402

passed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if not condition:
        print(f"FAIL {name} — {detail}")
        raise SystemExit(1)
    passed += 1
    print(f"PASS {name}")


def values(**kw) -> dict:
    return {k: {"value": v} for k, v in kw.items()}


def main() -> int:
    base = values(lexical_validity=0.67, presentation_forms=0.02, tounicode_gap_ratio=0.01)

    # ---- the per-key tolerance -----------------------------------------------------------------
    within = values(lexical_validity=0.64, presentation_forms=0.02, tounicode_gap_ratio=0.01)
    check("tolerance: -0.03 on lexical passes at its own 0.03",
          cm.unexplained_deltas(within, base, {"lexical_validity": 0.03}) == {},
          str(cm.unexplained_deltas(within, base, {"lexical_validity": 0.03})))
    check("tolerance: -0.031 on lexical fails at 0.03",
          cm.unexplained_deltas(values(lexical_validity=0.639), base, {"lexical_validity": 0.03})
          == {"lexical_validity": -0.031})
    inflated = values(lexical_validity=0.67, presentation_forms=0.08, tounicode_gap_ratio=0.07)
    caught = cm.unexplained_deltas(inflated, base, {"lexical_validity": 0.03})
    check("tolerance: presentation_forms +0.06 and gap +0.06 fail WITHOUT their own tolerance",
          caught == {"presentation_forms": 0.06, "tounicode_gap_ratio": 0.06}, str(caught))
    check("tolerance: the same drift passes only when its own key is given one",
          cm.unexplained_deltas(inflated, base, {"lexical_validity": 0.03, "presentation_forms": 0.06,
                                                 "tounicode_gap_ratio": 0.06}) == {})
    check("tolerance: identical manifests are empty", cm.unexplained_deltas(base, base, {}) == {})
    check("tolerance: an unknown key is refused",
          cm.unknown_tolerance_keys({"lexical_validty": 0.03}, base) == ["lexical_validty"])
    check("tolerance: a known key is not",
          cm.unknown_tolerance_keys({"lexical_validity": 0.03}, base) == [])
    check("tolerance: a bare token is refused", _raises(lambda: cm._tolerances(["0.05"])))
    check("tolerance: a non-number is refused", _raises(lambda: cm._tolerances(["lexical_validity=abc"])))

    # ---- the missing document ------------------------------------------------------------------
    missing_doc = os.path.join(tempfile.mkdtemp(prefix="docs-"), "absent.pdf")
    check("missing doc: the file really is absent (the control can produce the defect)",
          not os.path.exists(missing_doc))

    real_repo, real_docs, real_load = cm.REPO, cm.DOCS, cm.corpus_cases.load_all
    cm.REPO = os.path.dirname(missing_doc)
    cm.DOCS = {"absent": os.path.basename(missing_doc)}
    cm.corpus_cases.load_all = lambda: []
    try:
        try:
            cm.clean_files(tempfile.mkdtemp(prefix="cases-"))
            check("missing doc: undeclared is refused", False, "clean_files returned instead of refusing")
        except SystemExit as exc:
            check("missing doc: undeclared is refused by name", "absent" in str(exc), str(exc))
        rows, missing = cm.clean_files(tempfile.mkdtemp(prefix="cases-"), allow_missing={"absent": "not built here"})
        check("missing doc: declared is recorded, not silent",
              rows == [] and missing == {"absent": "not built here"}, f"{rows} {missing}")
        check("missing doc: a key that is not a document is refused",
              _raises(lambda: cm.clean_files(tempfile.mkdtemp(prefix="cases-"), allow_missing={"nope": "x"})))
    finally:
        cm.REPO, cm.DOCS, cm.corpus_cases.load_all = real_repo, real_docs, real_load

    print(f"\nMEASURE GUARDS PASSED — {passed} check(s); the tolerance is per key and a missing document is a refusal")
    return 0


def _raises(fn) -> bool:
    try:
        fn()
    except SystemExit:
        return True
    return False


if __name__ == "__main__":
    sys.exit(main())
