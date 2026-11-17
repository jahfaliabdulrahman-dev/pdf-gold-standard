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

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.environ.get("VERAPDF_BASELINE") or os.path.join(PROJ, "verapdf-baseline.toml")


def failing_rules(path: str, flavour: str) -> set[str]:
    r = subprocess.run(["verapdf", "--flavour", flavour, "--format", "json", path],
                       capture_output=True, text=True, timeout=900)
    # A crash is not a clean file: exit 1 is "violations found", anything else is the tool failing.
    if r.returncode not in (0, 1):
        raise SystemExit(f"verapdf {flavour}: exit {r.returncode} — the tool failed, not the document: {r.stderr[-300:]}")
    if not r.stdout.strip():
        raise SystemExit(f"verapdf {flavour}: empty JSON output (exit {r.returncode}): {r.stderr[-300:]}")
    data = json.loads(r.stdout)
    out = set()

    def walk(o):
        if isinstance(o, dict):
            if o.get("ruleStatus") == "FAILED":
                rid = o.get("ruleId") or o.get("clause")
                if rid:   # keep bare ids too: PDF/UA identification is clause "5"
                    out.add(str(rid))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return out


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"
    base = tomllib.load(open(BASELINE, "rb"))
    flavours = sys.argv[2:] or base["flavours"]
    ver = subprocess.run(["verapdf", "--version"], capture_output=True, text=True).stdout.splitlines()
    if not ver:
        print("FAIL verapdf-version — `verapdf --version` printed nothing; the tool is not usable")
        raise SystemExit(1)
    ver = ver[0]
    if base["version"] not in ver:
        print(f"FAIL verapdf-version - installed «{ver}», baseline measured on {base['version']}")
        raise SystemExit(1)
    bad = 0
    for f in flavours:
        want = set(base[f]["failing"])
        known = set(base.get("regressions", {}).get(f, {}).get("open", []))
        allowed_dead = set(base.get("fixed", {}).get(f, {}).get("rules", []))
        both = want & allowed_dead
        if both:
            # A rule listed as a known failure AND as fixed is a hole: when it returns, the diff below
            # finds it in neither set and the gate passes. Refuse the table instead of trusting it.
            print(f"FAIL verapdf-{f} — the baseline lists {sorted(both)} as failing and as fixed; "
                  "a rule has one state per flavour")
            bad += 1
            continue
        got = failing_rules(pdf, f)
        want -= allowed_dead
        new, dead = got - want - known, want - got
        returned = got & allowed_dead          # a rule recorded as fixed is failing again
        open_reg = got & known
        ok = not new and not dead and not returned and not open_reg
        print(("PASS " if ok else "FAIL ") + f"verapdf-{f} - {len(got)} failing rules "
              f"(baseline {len(want)}, as in {os.path.basename(BASELINE)})" + (f" · NEW {sorted(new)}" if new else "")
              + (f" · DEAD {sorted(dead)}" if dead else "") + (f" · FIXED-RETURNED {sorted(returned)}" if returned else "")
              + (f" · OPEN REGRESSION {sorted(open_reg)}" if open_reg else ""))
        bad += 0 if ok else 1
    if bad:
        raise SystemExit(1)
    print(f"VERAPDF BASELINE HELD — {len(flavours)} flavours, no new rule, no dead exception")
