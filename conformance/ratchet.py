"""The ratchet — a floor per (reader × case × metric), never a corpus average.

Why per case and not a mean: a mean lets one case collapse while another improves and the floor still holds —
the exact failure mode the owner's review named. The file records every case's value, so a regression names the
case. Why the reader version and not the corpus hash: binding to the corpus would invalidate every floor the
moment a case is added; binding to the reader version is what makes a *reader upgrade* a decision instead of a
silent drift.

`check()` fails on a value below its floor and on a case that disappeared. A new case with no floor is
reported as `unratcheted` (the run prints it; `--accept` gives it a floor). No comparison is made across
reader versions: a version change refuses the comparison by name.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "ratchet.json")
TOL = 1e-9
# Readers whose version comes from the machine, not from a pin: PDFKit ships with macOS, and poppler ships from
# brew with no version switch (the CI runner had 26.10.0 while the floors were measured on 26.07.0 — measured,
# not assumed). Their floors are not comparable across machines, so the comparison is skipped FOR THAT READER
# and said out loud. What keeps them honest instead: the writer's `limitations.json` control is re-run on every
# `run`, so a limit that stopped reproducing on the installed version is refused by name. Never silent, and
# never for a pip-pinned reader.
# A case whose outcome depends on the MACHINE rather than on the engine: `mon-riyal-sign` draws U+20C1, which
# neither declared font has, so the glyph comes from whatever system fallback the OS offers — a different font
# on macOS 27.2 (pdfium exact 1.0) than on the CI image's 15.x (0.0). Measured, not assumed. The case stays in
# the corpus and its numbers stay in every result; only its floors are withheld, because a floor that is one
# machine's accident is not a floor. Fixing it is a font decision, and that is the owner's.
MACHINE_DEPENDENT_CASES = {
    "mon-riyal-sign": "U+20C1 is in neither declared font, so the fallback that draws it is the OS's — "
                      "measured 1.0 on macOS 27.2 and 0.0 on the CI's 15.x",
}
UNPINNED = {
    "pdfkit": "PDFKit ships with macOS; its version is the runner image, not a pin",
    "poppler": "poppler ships from brew with no version switch; the floors are one machine's",
}


def load(path: str = FILE) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def derive(results: dict) -> dict:
    """The floors a run implies: {reader: {version, cases: {case: {metric: value, defects: {...}}}}}"""
    out = {}
    for reader, block in results["readers"].items():
        if not block.get("available"):
            continue
        cases = {}
        for case in results["cases"]:
            if case["id"] in MACHINE_DEPENDENT_CASES:
                continue                 # a floor that is one machine's accident is not a floor
            r = case["per_reader"].get(reader)
            if not r:
                continue
            cases[case["id"]] = {**{k: v for k, v in r["metrics"].items()}, "defects": r["defects"]}
        out[reader] = {"version": block["version"], "cases": cases}
    return out


def accept(results: dict, path: str = FILE) -> dict:
    floors = derive(results)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(floors, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return floors


def check(results: dict, path: str = FILE) -> tuple[list[str], list[str]]:
    """(regressions, notes). A regression names the reader, the case and the metric."""
    floors = load(path)
    bad, notes = [], []
    if not floors:
        return ["no ratchet.json — run with --accept to record the first floors"], notes
    measured = derive(results)
    for gone in sorted(set(floors) - set(measured)):
        bad.append(f"{gone}: floors recorded but the reader did not run in this comparison "
                   f"(a reader that disappears is a regression, not a skip)")
    for case_id in sorted(MACHINE_DEPENDENT_CASES):
        if case_id in (results.get("cases") and {c["id"] for c in results["cases"]} or set()):
            notes.append(f"{case_id}: floors withheld — {MACHINE_DEPENDENT_CASES[case_id]}")
    for reader, block in measured.items():
        base = floors.get(reader)
        if base is None:
            notes.append(f"{reader}: no floors recorded")
            continue
        if base.get("version") != block["version"]:
            if reader in UNPINNED:
                notes.append(f"{reader}: {block['version']} vs floors on {base.get('version')} — "
                             f"{UNPINNED[reader]}; floors not compared")
                continue
            bad.append(f"{reader}: version {block['version']} measured, floors recorded on {base.get('version')} "
                       f"— re-run with --accept after checking the changelog")
            continue
        for case, mine in block["cases"].items():
            if case in MACHINE_DEPENDENT_CASES:
                continue                     # measured and reported, never floored — see the note above
            if case not in base["cases"]:
                notes.append(f"{reader}/{case}: new case, no floor yet")
                continue
            want = base["cases"][case]
            for metric, value in mine.items():
                if metric == "defects":
                    for kind, n in value.items():
                        if n > want.get("defects", {}).get(kind, 0):
                            bad.append(f"{reader}/{case}: defect {kind} {n} > floor {want['defects'].get(kind, 0)}")
                elif float(value) + TOL < float(want.get(metric, 0.0)):
                    bad.append(f"{reader}/{case}: {metric} {value:.4f} < floor {want.get(metric, 0.0):.4f}")
        for gone in sorted(set(base["cases"]) - set(block["cases"])):
            bad.append(f"{reader}/{gone}: floor exists but the case is gone from the run")
    return bad, notes
