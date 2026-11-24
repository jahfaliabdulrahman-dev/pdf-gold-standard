#!/usr/bin/env python3
"""veraPDF baseline gate: no NEW failing rule, and no DEAD exception.

Usage: python3 scripts/verapdf_gate.py out.pdf [3b ua1 4]
Reads verapdf-baseline.toml, runs veraPDF per flavour, compares the failing-rule SETS exactly.
Exit 1 when a rule fails that is not named, or a named rule stopped failing (the reason went stale).
"""
import json
import os
import re
import subprocess
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verapdf_json import guard, failing_rules  # noqa: E402  (one reader; a report that judged nothing is not a clean file)

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def baseline_path() -> str:
    """The document's own baseline, as its spec declares it — and nowhere else.

    An environment variable used to override it here while verify_pdf.py read the spec's, so one run could be
    judged against a baseline the other half of the gate had never been told about (B8). Each spec now names
    its file; there is no second source to disagree with.
    """
    sys.path.insert(0, os.path.join(PROJ, "scripts"))
    sys.path.insert(0, PROJ)
    import spec_loader
    return os.path.join(PROJ, spec_loader.load().VERAPDF_BASELINE)


BASELINE = baseline_path()


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"
    base = tomllib.load(open(BASELINE, "rb"))
    flavours = sys.argv[2:] or base["flavours"]
    ver = subprocess.run(["verapdf", "--version"], capture_output=True, text=True).stdout.splitlines()
    if not ver:
        print("FAIL verapdf-version — `verapdf --version` printed nothing; the tool is not usable")
        raise SystemExit(1)
    ver = ver[0]
    accepted = {str(v) for v in (base.get("version"), base.get("revalidated_on")) if v}
    if not any(label in ver for label in accepted):
        print(f"FAIL verapdf-version - installed «{ver}», baseline measured on {sorted(accepted)}")
        raise SystemExit(1)
    bad = 0
    for f in flavours:
        if f not in base:
            raise SystemExit(f"verapdf: flavour «{f}» is not declared in {os.path.basename(BASELINE)} — "
                             f"declared: {sorted(k for k in base if k in ('3b', '4', '4f', 'ua1'))}")
        want = set(base[f]["failing"])
        known = set(base.get("regressions", {}).get(f, {}).get("open", []))
        allowed_dead = set(base.get("fixed", {}).get(f, {}).get("rules", []))
        # `failing` is clause-testNumber (measured). `fixed.rules` and `regressions.open` stay at clause
        # level: a rule that stopped failing cannot be re-measured to recover its test number, so those
        # historical lists are compared by clause and say so in the baseline header.
        clause = lambda k: k.split("-")[0]  # noqa: E731
        both = {w for w in want if clause(w) in allowed_dead}
        if both:
            # A rule listed as a known failure AND as fixed is a hole: when it returns, the diff below
            # finds it in neither set and the gate passes. Refuse the table instead of trusting it.
            print(f"FAIL verapdf-{f} — the baseline lists {sorted(both)} as failing and as fixed; "
                  "a rule has one state per flavour")
            bad += 1
            continue
        got = failing_rules(pdf, f)
        want -= {w for w in want if clause(w) in allowed_dead}
        open_reg = {g for g in got if clause(g) in known}
        new = {g for g in got if g not in want and clause(g) not in known
               and clause(g) not in allowed_dead}
        dead = want - got
        returned = {g for g in got if clause(g) in allowed_dead and g not in want}  # a fixed clause failing again
        ok = not new and not dead and not returned and not open_reg
        print(("PASS " if ok else "FAIL ") + f"verapdf-{f} - {len(got)} failing rules "
              f"(baseline {len(want)}, as in {os.path.basename(BASELINE)})" + (f" · NEW {sorted(new)}" if new else "")
              + (f" · DEAD {sorted(dead)}" if dead else "") + (f" · FIXED-RETURNED {sorted(returned)}" if returned else "")
              + (f" · OPEN REGRESSION {sorted(open_reg)}" if open_reg else ""))
        bad += 0 if ok else 1
    if bad:
        raise SystemExit(1)
    print(f"VERAPDF BASELINE HELD — {len(flavours)} flavours, no new rule, no dead exception")
