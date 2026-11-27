#!/usr/bin/env python3
"""What the SHIPPED Linux install can say — the same product code, three readers instead of five.

The bare install (`pip install -e .`, no `mupdf` extra, on Linux) has three readers, so a majority is TWO, not
three. The thresholds were measured on five readers. A report is worth what its rule is worth, so this script
runs `blind.check` over the same bytes twice — once with every reader this machine has, once with the
shipped-Linux set — and prints the file-level verdicts side by side. Nothing is lowered and nothing is
recomputed: the checker's own functions decide, and the diff is the finding.

The set is applied by replacing `blind.available`, the boundary `check` itself calls, so everything else in the
report (`readers`, `missing_readers`, `majority`, the dropped-reader sentences) stays the product's own.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from arabic_pdf_check import blind                                    # noqa: E402
from conformance.readers import available as real_available           # noqa: E402
import checker_fixtures                                              # noqa: E402

SHIPPED_LINUX = ("pdfium", "poppler", "pdfminer")


def check_as(pdf_path: str, thresholds: dict, keep: tuple[str, ...] | None):
    """`blind.check` with `available()` narrowed to `keep`; returns the report.

    A name in `keep` that the shipped MATRIX does not declare yet (a CANDIDATE reader, e.g. `pdfjs`) is imported
    directly and added to the voting set — the measurement must be able to ask «what would this reader say?»
    before anybody ships it, and `shipped.available()` is untouched by that.
    """
    if keep is None:
        return blind.check(pdf_path, thresholds)
    ok, missing = real_available()
    for name in keep:
        if name in ok:
            continue
        try:
            from conformance.readers import load
            mod = load(name)
            mod.version()
            ok[name] = mod
        except Exception as exc:
            missing[name] = f"{type(exc).__name__}: {exc}"
    kept = {n: m for n, m in ok.items() if n in keep}
    dropped = {n: why for n, why in missing.items()}
    for n in ok:
        if n not in keep:
            dropped[n] = f"NotInTheShippedSet: {n} is not installed by `pip install -e .` on Linux"
    saved, blind.available = blind.available, (lambda: (kept, dropped))
    try:
        return blind.check(pdf_path, thresholds)
    finally:
        blind.available = saved


def verdict(report: dict) -> tuple[str | None, list[str], int | None, int]:
    """(FILE verdict, the signals that carried it, votes needed, voters) — read from the report, never recomputed.

    `risk.level` is the loudest thing in the report, and a single reader can make it loud (`causes: ['reader']`);
    the claim this script is about is the FILE verdict, so it reads `risk.file` and only `cause == "file"`
    signals. Reading the loudest field instead would compare reader noise between the two reader sets.
    """
    risk = (report.get("risk") or {}).get("file") or {}
    signals = [s["id"] for s in (report.get("signals") or [])
               if s.get("cause") == "file" and s.get("level") in ("high", "medium")]
    readers = ((report.get("majority") or {}).get("readers") or {})
    return risk.get("level"), signals, readers.get("needed"), readers.get("read", 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fixtures-dir", default=None, help="a directory outside the repository")
    ap.add_argument("--zatca-dir", default=os.path.expanduser(
        "~/.cache/zatca-sdk/238-R3.4.8/zatca-einvoicing-sdk-Java-238-R3.4.8/Data/Samples/PDF-A3"))
    ap.add_argument("--keep", default=",".join(SHIPPED_LINUX))
    a = ap.parse_args()

    thresholds = json.load(open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"), encoding="utf-8"))
    keep = tuple(n.strip() for n in a.keep.split(",") if n.strip())

    built = checker_fixtures.build_all(a.fixtures_dir or os.path.join(os.path.dirname(a.out), "fixtures"))
    files: list[tuple[str, str]] = [("base:clean-chrome", built["clean"])]
    files += [(f"planted:{k}", v) for k, v in sorted(built["planted"].items())]
    for doc in ("guide-v2-ar.pdf", "report.pdf", "najd.pdf", "report-print.pdf"):
        p = os.path.join(REPO, doc)
        if os.path.isfile(p):
            files.append((f"doc:{doc}", p))
    if os.path.isdir(a.zatca_dir):
        files += [(f"zatca:{os.path.basename(p)}", os.path.join(a.zatca_dir, p))
                  for p in sorted(os.listdir(a.zatca_dir)) if p.lower().endswith(".pdf")]

    rows, changed = [], 0
    for label, path in files:
        full = check_as(path, thresholds, None)
        bare = check_as(path, thresholds, keep)
        fv, fs, fneed, fvoters = verdict(full)
        bv, bs, bneed, bvoters = verdict(bare)
        diff = (fv != bv) or (set(fs) != set(bs))
        changed += bool(diff)
        rows.append({"file": label, "all": {"level": fv, "signals": fs, "needed": fneed, "voters": fvoters},
                     "shipped": {"level": bv, "signals": bs, "needed": bneed, "voters": bvoters},
                     "changed": diff})
        mark = "  CHANGED" if diff else ""
        print(f"{label:44s} all={fv or '-':5s}({fneed} of {fvoters}) {','.join(fs):26s}"
              f" shipped={bv or '-':5s}({bneed} of {bvoters}) {','.join(bs):26s}{mark}")

    per_signal = {}
    for row in rows:
        for side in ("all", "shipped"):
            for sig in row[side]["signals"]:
                key = (side, sig)
                per_signal[key] = per_signal.get(key, 0) + 1
    print("\nfile-level signal counts (all → shipped):")
    for sig in sorted({s for (_, s) in per_signal}):
        print(f"  {sig:26s} {per_signal.get(('all', sig), 0):3d} → {per_signal.get(('shipped', sig), 0):3d}")
    print(f"\n{changed} of {len(rows)} file(s) change verdict when the readers shrink to {', '.join(keep)}")

    json.dump({"keep": keep, "changed": changed, "files": rows,
               "counts": {f"{s}|{k}": v for (s, k), v in per_signal.items()}},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
