"""Floors per (reader, version, case, metric) — a regression is a drop below the floor of the version that ran.

Why per case and not a mean: a mean lets one case collapse while another improves and the floor still holds —
the exact failure mode the owner's review named.

Why per version: a reader's numbers move when the reader moves, and pretending otherwise forces one of two
lies. Skipping the comparison when the version differs leaves that reader unguarded (a real regression passes);
comparing across versions reads an upgrade as a regression. So the file holds one block per measured version,
and **a version with no block is a failure that names the version** — an upgrade is accepted deliberately, with
its numbers, in a commit.

    {"pdfium": {"floors": {"5.15.2": {"cases": {"<id>": {"exact": 1.0, "defects": {...}}}}}},
     "pdfkit": {"floors": {"27.2.1": {...}, "15.8.2": {...}}}}

`accept` merges one version's block and leaves every other version's block alone — accepting the CI runner's
PDFKit never erases the owner's.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "ratchet.json")
TOL = 1e-9
METRICS = ("exact", "word_f1", "order", "digit_runs", "skeleton_exact")


def load(path: str = FILE) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    for reader, block in data.items():
        if "floors" not in block:
            raise SystemExit(f"ratchet.json is the pre-version shape at {reader!r} — re-record it with "
                             f"`python3 -m conformance ratchet accept --from <results.json>`")
    return data


def derive(results: dict) -> dict:
    """The floors a run implies: {reader: {version, cases: {case: {metric: value, defects: {...}}}}}"""
    out = {}
    for reader, block in results["readers"].items():
        if not block.get("available"):
            continue
        cases = {}
        for case in results["cases"]:
            r = case["per_reader"].get(reader)
            if not r:
                continue
            cases[case["id"]] = {**{k: v for k, v in r["metrics"].items()}, "defects": r["defects"]}
        out[reader] = {"version": block["version"], "cases": cases}
    return out


def accept(results: dict, path: str = FILE, allow_lower: bool = False) -> dict:
    """Merge this run's floors for every reader version it measured; other versions keep their blocks.

    A floor is a promise: `accept` refuses to lower one. A run that regressed must be fixed, not recorded —
    otherwise the next comparison is against the regression and the gate forgets the defect. `allow_lower=True`
    is the deliberate rebase (a reader whose *definition* changed), and it says so in the caller's flag.

    A pre-version file cannot be merged (its block has no version key) and cannot be compared either, so this
    run replaces it and says so — the file it replaces has never held more than one version per reader.
    """
    try:
        floors = load(path)
    except SystemExit:
        print(f"note: {path} was the pre-version shape — replaced by this run's per-version blocks")
        floors = {}
    lowered = []
    for reader, block in derive(results).items():
        entry = floors.setdefault(reader, {"floors": {}})
        old = entry["floors"].get(block["version"], {}).get("cases", {})
        if not allow_lower:
            for case, values in block["cases"].items():
                want = old.get(case)
                if not want:
                    continue
                for metric in METRICS:
                    if float(values.get(metric, 0.0)) + TOL < float(want.get(metric, 0.0)):
                        lowered.append(f"{reader} {block['version']}/{case}: {metric} "
                                       f"{values.get(metric):.4f} < floor {want.get(metric):.4f}")
                for kind, n in (values.get("defects") or {}).items():
                    if n > (want.get("defects") or {}).get(kind, 0):
                        lowered.append(f"{reader} {block['version']}/{case}: defect {kind} {n} > floor "
                                       f"{want.get('defects', {}).get(kind, 0)}")
        entry["floors"].setdefault(block["version"], {})["cases"] = block["cases"]
    if lowered:
        raise SystemExit(
            f"RATCHET REFUSED — this run lowers {len(lowered)} floor(s); fix the regression or pass --force "
            f"for a deliberate rebase:\n  " + "\n  ".join(lowered[:12]))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(floors, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    return floors


def check(results: dict, path: str = FILE) -> tuple[list[str], list[str]]:
    """(regressions, notes). A regression names the reader, the version, the case and the metric."""
    floors = load(path)
    bad, notes = [], []
    if not floors:
        return ["no ratchet.json — run `conformance ratchet accept --from <results.json>` to record the first "
                "floors"], notes
    measured = derive(results)
    for gone in sorted(set(floors) - set(measured)):
        bad.append(f"{gone}: floors recorded but the reader did not run in this comparison "
                   f"(a reader that disappears is a regression, not a skip)")
    for reader, block in sorted(measured.items()):
        entry = floors.get(reader)
        if entry is None:
            bad.append(f"{reader}: no floors recorded for any version")
            continue
        version = block["version"]
        base = entry["floors"].get(version)
        if base is None:
            known = ", ".join(sorted(entry["floors"])) or "none"
            bad.append(f"{reader} {version}: no floors for this version (recorded: {known}) — a reader that "
                       f"changed is accepted deliberately: `conformance ratchet accept --from <results.json>`")
            continue
        compared = 0
        for case, mine in block["cases"].items():
            if case not in base["cases"]:
                notes.append(f"{reader} {version}/{case}: new case, no floor yet")
                continue
            want = base["cases"][case]
            compared += 1
            for metric, value in mine.items():
                if metric == "defects":
                    for kind, n in value.items():
                        if n > want.get("defects", {}).get(kind, 0):
                            bad.append(f"{reader} {version}/{case}: defect {kind} {n} > floor "
                                       f"{want['defects'].get(kind, 0)}")
                elif float(value) + TOL < float(want.get(metric, 0.0)):
                    bad.append(f"{reader} {version}/{case}: {metric} {value:.4f} < floor "
                               f"{want.get(metric, 0.0):.4f}")
        for gone in sorted(set(base["cases"]) - set(block["cases"])):
            bad.append(f"{reader} {version}/{gone}: floor exists but the case is gone from the run")
        notes.append(f"{reader} {version}: {compared} cases compared")
    return bad, notes
