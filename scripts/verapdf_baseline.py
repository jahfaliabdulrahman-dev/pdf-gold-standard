#!/usr/bin/env python3
"""Derive each document's `failing` set from a measurement — never from a hand-typed table.

Usage: python3 scripts/verapdf_baseline.py --root <dir-with-built-pdfs> [--write]

`failing` is whatever veraPDF reports as FAILED at clause-testNumber level for this build. The script prints
the baseline → measured set per document and flavour, and rewrites only the `failing = [...]` line of each
flavour section, only with --write — comments, `fixed`, `regressions` and the rest of the file are untouched.

The print copy shares the report's baseline: its measurement must equal the report's, and a difference is
refused rather than picked.
"""
import argparse
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verapdf_json import failing_rules  # noqa: E402  (the one reader of a veraPDF report)

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# document -> (built pdf, its baseline)
DOCS = (
    ("guide", "guide.pdf", "verapdf-baseline.toml"),
    ("report", "report.pdf", "verapdf-baseline-report.toml"),
    ("report-print", "report-print.pdf", "verapdf-baseline-report.toml"),
    ("najd", "najd.pdf", "verapdf-baseline-najd.toml"),
)


def rewrite(path: str, updates: dict[str, list[str]]) -> None:
    lines = open(path, encoding="utf-8").read().split("\n")
    for flavour, keys in updates.items():
        try:
            head = lines.index(f"[{flavour}]")
        except ValueError:
            raise SystemExit(f"{path}: no [{flavour}] section — the baseline does not name this flavour")
        i = head + 1
        while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("#")):
            i += 1
        if i >= len(lines) or not lines[i].startswith("failing = "):
            raise SystemExit(f"{path}: [{flavour}] does not begin with a single-line `failing = [...]` — "
                             "refusing to guess where the set ends")
        comment = ""
        if "#" in lines[i]:
            comment = "   " + lines[i][lines[i].index("#"):]
        body = ", ".join(f'"{k}"' for k in keys)
        lines[i] = f"failing = [{body}]" + comment
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="directory holding the built PDFs")
    ap.add_argument("--write", action="store_true", help="rewrite the baseline files (default: report only)")
    ap.add_argument("--accept-new", action="store_true",
                    help="allow a NEW failing rule into the baseline; without it --write refuses (a new failure "
                         "is a regression to explain, not a table to update)")
    args = ap.parse_args()

    measured: dict[str, dict[str, set[str]]] = {}
    writes: dict[str, dict[str, list[str]]] = {}
    additions: dict[str, list[str]] = {}
    for doc, pdf_name, base_name in DOCS:
        pdf = os.path.join(args.root, pdf_name)
        if not os.path.exists(pdf):
            raise SystemExit(f"{doc}: {pdf} does not exist — build it first; a baseline is measured, not assumed")
        base = tomllib.load(open(os.path.join(PROJ, base_name), "rb"))
        got = {f: failing_rules(pdf, f) for f in base["flavours"]}
        measured[doc] = got
        print(f"{doc:13s} ({base_name})")
        for f in base["flavours"]:
            want = set(base[f]["failing"])
            now = got[f]
            mark = "=" if want == now else "→"
            print(f"  {f:4s} baseline {len(want):2d} {mark} measured {len(now):2d}   {sorted(now)}")
            if want != now:
                added, gone = sorted(now - want), sorted(want - now)
                if added:
                    additions[f"{base_name} {f}"] = added
                    print(f"       + {added}")
                if gone:
                    print(f"       - {gone}")
            writes.setdefault(base_name, {})[f] = sorted(now)

    # The print copy shares the report's baseline: one file cannot hold two measurements.
    if "report" in measured and "report-print" in measured:
        for f in measured["report"]:
            if measured["report"][f] != measured["report-print"].get(f):
                print(f"REFUSED — report and the print copy measure different {f} sets: "
                      f"{sorted(measured['report'][f] ^ measured['report-print'].get(f, set()))}")
                return 1

    if not args.write:
        print("\n(dry run — pass --write to rewrite the failing sets)")
        return 0
    if additions and not args.accept_new:
        for where, added in additions.items():
            print(f"REFUSED — {where} would gain {added}: a NEW failing rule is a regression to explain, "
                  "not a baseline edit (pass --accept-new if it is understood and accepted)")
        return 1
    for base_name, updates in writes.items():
        rewrite(os.path.join(PROJ, base_name), updates)
        print(f"wrote {base_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
