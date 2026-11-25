#!/usr/bin/env python3
"""Measure the checker: the planted set, the clean set, and the owner's real corpus.

The one command that produces every number in `docs/checker-v0/measurements/` and every threshold in
`arabic_pdf_check/thresholds.json`. Thresholds are DERIVED here, never typed by hand:

  · presentation forms (higher is worse):  value = max(declared floor, clean-set maximum)
  · ToUnicode gap share (higher is worse): value = max(declared floor, clean-set maximum)
  · orientation majority is STRUCTURAL (`len(MATRIX)//2 + 1`), not a measured threshold: a machine without
    one reader must not change a file's verdict. This script only proves the planted file crosses it.

A signal that does not separate (planted value not at least 0.20 away from the clean value) is REFUSED here
and the script fails: the assignment's rule is that a signal which cannot separate is not shipped.

Two rules the audit of 2026-11-25 put in code, because both were silent:

  · a missing `DOCS` file is a REFUSAL that names it, not a smaller clean set. `--allow-missing doc=<reason>`
    is the only way past it, it is recorded in the artifact, and a key that is not a document is refused too.
  · `--tolerance` is PER KEY. `lexical_validity` carries the one measured drift (CI's PDFKit on macos-15 reads
    `doc:guide` at 0.8369 vs 0.8797 locally → derived 0.64 vs shipped 0.67, −0.03; run 45490733095). Every
    other key must match exactly: an absolute 0.05 over keys whose scales differ hid a 6× inflation in
    `presentation_forms`/`tounicode_gap_ratio` and was the audit's finding.

The owner's corpus is measured aggregate-only: no file names, no per-file rows, no text, no excerpts. Its
input directory is read, never written.
"""
import argparse
import json
import os
import shlex
import sys
import tempfile
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

import itertools                                    # noqa: E402

from arabic_pdf_check import blind                  # noqa: E402
from conformance import reference                    # noqa: E402
from conformance.checks import lexical, mcid_text, metrics, structure, visual_order   # noqa: E402
from conformance.checks import segment_order                                        # noqa: E402
from conformance.readers import MATRIX, available, pages_many, text_many   # noqa: E402
from conformance.corpus import cases as corpus_cases                          # noqa: E402
import checker_fixtures                                                       # noqa: E402

DOCS = {"guide": "guide-v2-ar.pdf", "report": "report.pdf", "najd": "najd.pdf", "print": "report-print.pdf"}
# The owner's corpus is private and lives outside the repository; its location is the machine's business,
# not the code's, so it comes from the environment and is never committed.
OWNER_DIR = os.path.expanduser(os.environ.get("OWNER_CORPUS_DIR", ""))
THRESHOLDS = os.path.join(REPO, "arabic_pdf_check", "thresholds.json")


def content_f1(a: str, b: str) -> float:
    """F1 of the two word multisets under the gate's attribution token — order- and digit-blind.

    Measurement only (it is the number that refused the metric form of reader disagreement); it is not a
    gate, not a report field, and it lives in the measurement script so the gate keeps no unused surface.
    """
    ca, cb = structure.words_multi(a), structure.words_multi(b)
    if not ca and not cb:
        return 1.0
    overlap = sum((ca & cb).values())
    if not overlap:
        return 0.0
    precision, recall = overlap / sum(ca.values()), overlap / sum(cb.values())
    return 2 * precision * recall / (precision + recall)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def raw(path: str) -> dict:
    """Everything the thresholds are derived from, measured once per file."""
    ok, _missing = available()
    pages, texts = {}, {}
    for name in ok:
        got = pages_many(name, [path])
        if got is None or got[0] is None:      # the reader reads but cannot name its pages
            pages[name] = []
            texts[name] = text_many(name, [path])[0]
        else:
            pages[name] = got[0]
            texts[name] = "\n".join(pages[name])
    scan = mcid_text.scan(path)
    file_text = "\n".join(scan["text"].values())
    arabic = metrics.arabic_count(file_text)
    forms = metrics.pf_count(file_text)
    values = json.load(open(THRESHOLDS, encoding="utf-8"))["values"]
    orders = blind.visual_orders(texts, values)
    lex = {n: lexical.validity(t) for n, t in texts.items()}
    judged = {n: v for n, v in lex.items() if v["runs"] >= values["lexical_min_runs"]["value"]}
    pairs = [content_f1(texts[a], texts[b]) for a, b in itertools.combinations(sorted(texts), 2)]
    # Only fonts that HAVE a /ToUnicode map can have a gap in it: a simple font with no map is allowed by
    # Matterhorn 31-027 and `font_verdicts` gives it level None — counting its gap_ratio (1.0) would derive
    # a threshold from a non-defect.
    gap_max = max((v["gap_ratio"] for v in structure.font_verdicts(scan, 1.0) if v["tounicode"]), default=0.0)
    empty_pages = {n: v for n, v in blind.empty_pages_for(pages, list(ok)).items() if v}
    seg = segment_order.findings(texts, lexical.lexicon())
    return {
        "pf_ratio": metrics.pf_share(file_text),
        "gap_ratio_max": gap_max,
        "forms": forms,
        "arabic": arabic,
        "visual_share": len([n for n, o in orders.items() if o["visual"]]) / len(MATRIX),
        "visual_readers": [n for n, o in orders.items() if o["visual"]],
        "lexical_min": min((v["ratio"] for v in judged.values()), default=None),
        "lexical_max": max((v["ratio"] for v in judged.values()), default=None),
        "lexical_judged": len(judged),
        "lexical_by_reader": {n: {"runs": v["runs"], "known": v["known"], "ratio": v["ratio"],
                                  "reversed": v["reversed"], "lam_alef": v["lam_alef"]}
                              for n, v in lex.items()},
        "lam_alef_max": max((v["lam_alef"] for v in lex.values()), default=0),
        "pair_min": min(pairs) if pairs else 1.0,
        "empty_pages": {n: v for n, v in empty_pages.items() if v},
        "missing_unicode": scan["missing_unicode"],
        "notdef": scan["notdef"],
        "pua": scan["pua"],
        "mixed_numbers": len(structure.mixed_numbers(file_text)),
        "segment_order": {n: len(seg.get(n, [])) for n in texts},
        "readers": list(ok),
    }


def clean_files(cases_dir: str, reuse: bool = False,
                allow_missing: dict[str, str] | None = None) -> tuple[list[tuple[str, str]], dict[str, str]]:
    """(rows, missing) — the four documents (built by CI) and the whole corpus, built here with the pinned engine.

    `reuse=True` accepts case PDFs that already exist in `cases_dir` (the same case ids); it is for a
    re-measurement after Chrome has become flaky, not a different fixture.

    A missing document is a REFUSAL that names it: silently dropping `najd` moved the clean set from 70 to 69
    on the CI runner and the thresholds were then derived from a population nobody had measured. The only way
    past it is `--allow-missing doc=<reason>`, and the gap is carried into the artifact.
    """
    allowed = dict(allow_missing or {})
    unknown = sorted(set(allowed) - set(DOCS))
    if unknown:
        raise SystemExit(f"REFUSED — --allow-missing names {unknown}; a document key is one of {sorted(DOCS)}")
    out, missing = [], {}
    for label, rel in DOCS.items():
        path = os.path.join(REPO, rel)
        if os.path.exists(path):
            out.append((f"doc:{label}", path))
        elif label in allowed:
            missing[label] = allowed[label]
        else:
            raise SystemExit(
                f"REFUSED — clean document {label!r} is missing ({rel}); the clean set would silently shrink. "
                f"Build it, or declare it with --allow-missing {label}=<reason> (recorded in the artifact).")
    from conformance.adapters import chrome
    for case in corpus_cases.load_all():
        path = os.path.join(cases_dir, f"{case['id']}.pdf")
        if not (reuse and os.path.exists(path)):
            chrome.render_case(case, path, "chrome")
        out.append((f"case:{case['id']}", path))
    return out, missing


def owner_files(directory: str) -> list[str]:
    return sorted(os.path.join(directory, f) for f in os.listdir(directory)
                  if f.lower().endswith(".pdf")) if os.path.isdir(directory) else []


def _measure_owner(directory: str, thresholds: dict) -> dict:
    """Aggregate only: signal ids × file count and reader × risk. No names, no rows, no excerpts."""
    files = owner_files(directory)
    print(f"== owner corpus: {len(files)} file(s) in the declared directory")
    by_signal, by_reader_risk, by_file_level, errors = {}, {}, {}, []
    for i, path in enumerate(files, 1):
        try:
            rep = blind.check(path, thresholds)
        except Exception as exc:                     # a file that cannot be measured is a count, not a skip
            errors.append(type(exc).__name__)
            continue
        lvl = rep["risk"]["file"]["level"]
        by_file_level[lvl] = by_file_level.get(lvl, 0) + 1
        for s in rep["signals"]:
            by_signal[s["id"]] = by_signal.get(s["id"], 0) + 1
        for name, r in rep["readers"].items():
            by_reader_risk.setdefault(name, {}).setdefault(r["risk"], 0)
            by_reader_risk[name][r["risk"]] += 1
        if i % 10 == 0:
            print(f"   … {i}/{len(files)}")
    return {"files": len(files), "measured": len(files) - len(errors), "errors": len(errors),
            "by_file_level": by_file_level, "by_signal": by_signal, "by_reader_risk": by_reader_risk}


def derive_lexical_threshold(clean_min: float) -> float:
    """The one formula for the lexical floor: a clean reading must sit 0.20 above the floor.

    `checker_measure --write` and the PR-2 comparison both call this function; a second copy of the
    arithmetic would certify a threshold that is not shipped.
    """
    return round(clean_min - 0.20, 2)


def _pairs(items, what: str) -> dict[str, str]:
    """`KEY=VALUE` items -> a dict; a bare token is refused, never read as a silent skip."""
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"REFUSED — {what} expects KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        if not key.strip() or not value.strip():
            raise SystemExit(f"REFUSED — {what} got an empty key or value: {item!r}")
        out[key.strip()] = value.strip()
    return out


def _tolerances(items) -> dict[str, float]:
    """The per-key tolerance map. An unknown key is refused: a tolerance on nothing is a hole on everything."""
    out = {}
    for key, raw in _pairs(items, "--tolerance").items():
        try:
            out[key] = abs(float(raw))
        except ValueError:
            raise SystemExit(f"REFUSED — --tolerance {key}={raw!r} is not a number") from None
    return out


def unknown_tolerance_keys(tolerance: dict[str, float], values: dict) -> list[str]:
    """Tolerance keys that name no threshold — a tolerance on nothing is a hole on everything."""
    return sorted(set(tolerance) - set(values))


def unexplained_deltas(derived: dict, base: dict, tolerance: dict[str, float]) -> dict[str, float]:
    """{key: delta} for every key whose drift exceeds ITS OWN tolerance (absent tolerance = 0.0).

    One absolute tolerance over keys whose scales differ (0.01 … 0.67) is how a 6× inflation in a ratio walks
    through a green gate. `checker_measure --tolerance` and its test read this function; a second copy of the
    rule would certify a gate that is not the one that ran.
    """
    deltas = {k: round(derived[k]["value"] - base[k]["value"], 4)
              for k in base if k in derived}
    return {k: d for k, d in deltas.items() if abs(d) > tolerance.get(k, 0.0)}


def derive(clean_rows: list[dict], planted_rows: dict, thresholds: dict) -> tuple[dict, list[str]]:
    th = json.loads(json.dumps(thresholds))
    failures = []
    clean_pf = max(r["pf_ratio"] for r in clean_rows)
    clean_gap = max(r["gap_ratio_max"] for r in clean_rows)
    clean_share = max(r["visual_share"] for r in clean_rows)   # a separation check, not a threshold
    clean_min = min(r["pair_min"] for r in clean_rows)
    judged_clean = [r for r in clean_rows if r["lexical_min"] is not None]
    # The lexical floor is derived from the four REAL documents, not from a 24-run synthetic edge case:
    # the synthetic cases are clean and must not alarm, but their lexical ratios are short-text artefacts
    # and moved between macOS and the CI (0.8333 vs 0.78). The four documents are the substantive clean
    # population; the 8-run judged set is reported, and the remaining 62 cases are below the 20-run floor.
    threshold_clean = [r for r in judged_clean if r["label"].startswith("doc:")] or judged_clean
    clean_lex = min(r["lexical_min"] for r in threshold_clean)
    clean_min_case = min(threshold_clean, key=lambda r: r["lexical_min"])["label"] if threshold_clean else None
    clean_lex_all = min(r["lexical_min"] for r in judged_clean) if judged_clean else None

    th["values"]["presentation_forms"]["value"] = round(max(th["values"]["presentation_forms"]["declared"],
                                                             clean_pf), 4)
    th["values"]["tounicode_gap_ratio"]["value"] = round(max(
        th["values"]["tounicode_gap_ratio"]["declared"], clean_gap), 4)
    swap = planted_rows.get("planted-letter-swap") or {}
    broken_lex = swap.get("lexical_max")
    if clean_lex is None or broken_lex is None:
        failures.append("lexical-validity: no judgeable reading in the clean set or the letter-swap fixture")
    elif clean_lex - broken_lex < 0.20:
        failures.append(f"lexical-validity does not separate (clean minimum {clean_lex:.3f} vs planted "
                        f"maximum {broken_lex:.3f}; need 0.20)")
    else:
        # Higher is better, so the rule mirrors the other signals: a clean reading must sit at least the
        # declared 0.20 SEPARATION above the floor. The planted letter-swap is the negative side; the
        # PR-2 calibration files are measured separately (docs/checker-v0/08-pr2-evidence-2026-11-24.md).
        th["values"]["lexical_validity"]["value"] = derive_lexical_threshold(clean_lex)
        # Every count in this sentence is computed HERE: a manifest that prints a literal where a measurement
        # belongs reads the same on a runner where the population is 69 files and 3 documents.
        th["values"]["lexical_validity"]["source"] = (
            f"derived: clean_set_minimum - 0.20 (higher = better); clean minimum "
            f"{clean_lex:.4f} (governing {clean_min_case}); {len(threshold_clean)} document(s) of "
            f"{len(judged_clean)} judged clean files (the other {len(clean_rows) - len(judged_clean)} are below "
            f"the {int(th['values']['lexical_min_runs']['value'])}-run floor; all judged minimum "
            f"{clean_lex_all:.4f}). The planted letter-swap is the negative side. The calibration lesson's "
            f"defect is a measured lam-alef transposition, not lexical-only "
            f"(measurements/lam-alef-separation.json); its lexical ratio is above this floor and is NOT "
            f"repaired by lowering the threshold.")
    th["observed"] = {"clean_max_presentation_forms": round(clean_pf, 4),
                      "clean_min_lexical_validity": None if clean_lex is None else round(clean_lex, 4),
                      "clean_min_lexical_all": None if clean_lex_all is None else round(clean_lex_all, 4),
                      "clean_min_lexical_case": clean_min_case,
                      "clean_judged_files": len(judged_clean),
                      "clean_threshold_files": len(threshold_clean),
                      "clean_docs": {r["label"]: r.get("lexical_by_reader") for r in clean_rows
                                     if r["label"].startswith("doc:")},
                      "clean_max_visual_share": round(clean_share, 4),
                      "clean_max_gap_ratio": round(clean_gap, 4),
                      "clean_min_pair_f1": round(clean_min, 4),
                      "clean_files": len(clean_rows),
                      "refused": {"reader-disagreement-metric":
                                  f"content_f1 reaches {clean_min:.3f} between clean readers (single-word and "
                                  f"digit-only cases): any threshold above zero misses, and a threshold at zero "
                                  f"fires on clean files — no value separates, so the metric form is not shipped; "
                                  f"the page-empty form is deterministic and ships"},
                      "planted": {name: {"forms": r["forms"], "arabic": r["arabic"],
                                         "visual_share": round(r["visual_share"], 3),
                                         "pair_min": round(r["pair_min"], 4),
                                         "lexical_max": None if r["lexical_max"] is None else round(r["lexical_max"], 4),
                                         "missing_unicode": r["missing_unicode"]}
                                  for name, r in planted_rows.items()}}
    # The lam-alef density: clean maximum computed from the same rows the report measures, and a separation
    # check. The broken side is not in this population (it is the owner's private calibration file, measured
    # into measurements/lam-alef-separation.json); scripts/test_lam_alef_separation.py re-derives the shipped
    # value from that artifact so the literal cannot drift from its evidence.
    lam_min_runs = th["values"]["lam_alef_min_runs"]["value"]
    lam_rates = [v["lam_alef"] / v["runs"] * 1000.0
                 for r in clean_rows for v in (r.get("lexical_by_reader") or {}).values()
                 if v["runs"] >= lam_min_runs]
    clean_lam = max(lam_rates) if lam_rates else 0.0
    th["observed"]["clean_max_lam_alef_rate"] = round(clean_lam, 2)
    if clean_lam >= th["values"]["lam_alef_rate_per_1000"]["value"]:
        failures.append(f"lam-alef transposition does not separate: clean maximum {clean_lam:.2f} per 1000 runs "
                        f">= threshold {th['values']['lam_alef_rate_per_1000']['value']}")
    # Segment order: a READER signal, so the clean side is a population of reader findings, not of file
    # defects — but the value still follows the repo's one derivation rule (clean maximum + 1), because a single
    # clean hit within a run must not become the floor. The separation is then checked against the measured
    # broken side: every ZATCA sample that carries the defect carries >= 3, so 1 and 2 both separate, and the
    # formula — not a story about «hiding» files — is what picks 2.
    seg_by_file = {r["label"]: r.get("segment_order") or {} for r in clean_rows}
    clean_seg = max([v for rows in seg_by_file.values() for v in rows.values()] or [0])
    seg_floor = th["values"]["segment_order_min"]["declared"]
    th["values"]["segment_order_min"]["value"] = max(seg_floor, clean_seg + 1)
    seg_hits = {k: v for k, v in seg_by_file.items() if any(v.values())}
    seg_total = sum(v for rows in seg_by_file.values() for v in rows.values())
    th["observed"]["clean_max_segment_order"] = clean_seg
    th["observed"]["clean_segment_order_total"] = seg_total
    th["observed"]["clean_segment_order_files"] = seg_hits
    th["values"]["segment_order_min"]["source"] = (
        f"derived: clean maximum + 1 (declared floor {seg_floor}). The clean set ({len(clean_rows)} files) "
        f"measures at most {clean_seg} reversed segment(s) per reader, {seg_total} in {len(seg_hits)} file(s) "
        f"across all readers — reader findings on clean files (a reader that reverses a segment around a "
        f"number or a Latin run), not file defects. Broken side, measured: the ZATCA SDK's 16 PDF/A-3 samples "
        f"give pdfium 2-7 per affected file (measurements/segment-order.json), and the signal fires at "
        f"count >= value, so {clean_seg} < {th['values']['segment_order_min']['value']} separates. A reader "
        f"signal: it never "
        f"raises the file")
    # separation is required only for the signal a fixture is planted to trip
    for name, row in planted_rows.items():
        expected = checker_fixtures.PLANTED[name]
        if expected == "presentation-forms":
            gap = row["pf_ratio"] - clean_pf
            if gap < 0.20 or row["pf_ratio"] <= th["values"]["presentation_forms"]["value"]:
                failures.append(f"{name}: presentation-forms does not separate "
                                f"(planted {row['pf_ratio']:.3f} vs clean {clean_pf:.3f})")
        elif expected == "visual-order":
            need = blind.majority_needed(len(MATRIX))
            gap = row["visual_share"] - clean_share
            if gap < 0.20 or row["visual_share"] * len(MATRIX) < need:
                failures.append(f"{name}: orientation majority does not separate "
                                f"(share {row['visual_share']:.2f} vs clean {clean_share:.2f}, "
                                f"need {need}/{len(MATRIX)})")
        elif expected == "tounicode-gaps" and row["missing_unicode"] <= 0:
            failures.append(f"{name}: ToUnicode gaps are not positive")
        elif expected == "lexical-validity":
            if row["lexical_max"] is None or row["lexical_max"] >= th["values"]["lexical_validity"]["value"]:
                failures.append(f"{name}: lexical validity does not separate "
                                f"(planted maximum {row['lexical_max']} vs threshold "
                                f"{th['values']['lexical_validity']['value']})")
    th["measured_at"] = _now()
    return th, failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None,
                    help="where the measurement artifacts go (default: a fresh directory under /tmp; "
                         "docs/checker-v0/measurements is never written unless named)")
    ap.add_argument("--owner-dir", default=OWNER_DIR)
    ap.add_argument("--skip-owner", action="store_true")
    ap.add_argument("--write", action="store_true",
                    help="write the derived thresholds into arabic_pdf_check/thresholds.json (review first)")
    ap.add_argument("--owner-only", action="store_true",
                    help="measure only the owner's corpus against the committed thresholds")
    ap.add_argument("--clean-dir", default=None,
                    help="reuse rendered case PDFs already in this directory (no Chrome; same case ids)")
    ap.add_argument("--tolerance", action="append", default=None, metavar="KEY=VALUE",
                    help="CI-only: accept a derived manifest within this per-key absolute delta of the shipped "
                         "one (repeatable). A key with no tolerance must match exactly; the shipped value is "
                         "never changed, and every delta is printed")
    ap.add_argument("--allow-missing", action="append", default=None, metavar="DOC=REASON",
                    help="declare a missing clean document by name and reason (repeatable); recorded in the "
                         "artifact. Without it, a missing document is a refusal")
    a = ap.parse_args()
    tolerance = _tolerances(a.tolerance)
    allow_missing = _pairs(a.allow_missing, "--allow-missing")
    if not a.skip_owner and not a.owner_dir:
        ap.error("the owner corpus is private: set OWNER_CORPUS_DIR or pass --owner-dir "
                 "(or --skip-owner)")
    if a.out is None:
        a.out = tempfile.mkdtemp(prefix="checker-measure-")
        print(f"out: {a.out} (pass --out to choose; the repository is not written by default)")
    os.makedirs(a.out, exist_ok=True)

    if a.owner_only:
        with open(THRESHOLDS, encoding="utf-8") as fh:
            thresholds = json.load(fh)
        owner = _measure_owner(a.owner_dir, thresholds)
        with open(os.path.join(a.out, "owner.json"), "w", encoding="utf-8") as fh:
            json.dump({"generated_at": _now(), **owner}, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
        print(f"written: {os.path.join(a.out, 'owner.json')}")
        return 0

    print("== fixtures")
    # Built outside the repository: a generated PDF inside it is a fixture that will drift from its generator
    # (the assignment's rule), and `git add -A` would swallow it.
    built = checker_fixtures.build_all(tempfile.mkdtemp(prefix="checker-fixtures-"))
    planted_raw = {name: raw(path) for name, path in built["planted"].items()}

    print("== clean set (4 documents + the whole corpus, built with the pinned engine)")
    cases_dir = a.clean_dir or tempfile.mkdtemp(prefix="checker-cases-")
    clean_rows = []
    clean_sources, missing_docs = clean_files(cases_dir, reuse=bool(a.clean_dir),
                                              allow_missing=allow_missing)
    if missing_docs:
        print("   DECLARED MISSING: " + json.dumps(missing_docs, ensure_ascii=False))
    for label, path in clean_sources:
        row = raw(path)
        row["label"] = label
        clean_rows.append(row)
        print(f"   {label:40} pair_min={row['pair_min']:.3f} pf={row['pf_ratio']:.3f} "
              f"visual={row['visual_share']:.1f}")

    print("== thresholds")
    with open(THRESHOLDS, encoding="utf-8") as fh:
        base = json.load(fh)
    derived, failures = derive(clean_rows, planted_raw, base)
    derived["command"] = shlex.join(["python3", os.path.relpath(__file__, REPO)] + sys.argv[1:])
    derived["missing_docs"] = missing_docs
    unknown = unknown_tolerance_keys(tolerance, base["values"])
    if unknown:
        print(f"REFUSED — --tolerance names {unknown}, which is not a threshold key "
              f"({sorted(base['values'])})")
        return 1
    print("   values: " + json.dumps({k: v["value"] for k, v in derived["values"].items()}))
    if derived["values"] != base["values"] and not a.write:
        deltas = {k: round(derived["values"][k]["value"] - base["values"][k]["value"], 4)
                  for k in base["values"] if k in derived["values"]}
        unexplained = unexplained_deltas(derived["values"], base["values"], tolerance)
        if unexplained:
            print(f"THRESHOLDS DIFFER outside the declared per-key tolerance {tolerance or '{}'}: "
                  f"{json.dumps(deltas)} — unexplained: {json.dumps(unexplained)}. "
                  f"The measurement does not match the shipped manifest; review it, then re-run with --write")
            return 1
        print(f"THRESHOLDS DIFFER within the declared per-key tolerance {tolerance}: {json.dumps(deltas)} "
              f"— the shipped values stay {json.dumps({k: v['value'] for k, v in base['values'].items()})}")
    print("   " + json.dumps(derived["observed"], ensure_ascii=False)[:400])

    def accept(th: dict, tag: str) -> tuple[dict, list, list]:
        """Run the whole acceptance against ONE manifest: (planted rows, clean rows, clean file-high rows)."""
        rows = {}
        for name, path in built["planted"].items():
            rep = blind.check(path, th)
            expected = checker_fixtures.PLANTED[name]
            want = checker_fixtures.PLANTED_LEVEL.get(name, "high")
            file_ids = [s["id"] for s in rep["signals"]]
            ok = (blind.LEVELS[rep["risk"]["file"]["level"]] >= blind.LEVELS[want]
                  and expected in file_ids)
            rows[name] = {"expected_signal": expected, "expected_level": want, "file_signals": file_ids,
                          "file_level": rep["risk"]["file"]["level"],
                          "overall": rep["risk"]["level"], "thresholds": tag, "pass": ok}
            print(f"   [{tag:7}] {name:28} file={rep['risk']['file']['level']:6} signals={file_ids} "
                  f"{'PASS' if ok else 'FAIL'}")
        clean = []
        for row in clean_rows:
            path = _path_for(row["label"], cases_dir)
            rep = blind.check(path, th)
            clean.append({"label": row["label"], "file_level": rep["risk"]["file"]["level"],
                          "overall": rep["risk"]["level"], "thresholds": tag,
                          "reader_high": [n for n, r in rep["readers"].items() if r["risk"] == "high"],
                          "reader_signals": {n: sorted({s["id"] for s in r["signals"]})
                                             for n, r in rep["readers"].items() if r["signals"]}})
        high = [r for r in clean if r["file_level"] == "high"]
        explained = [r for r in clean if r["reader_high"]]
        print(f"   [{tag:7}] clean: files={len(clean)} file_high={len(high)} "
              f"files_with_reader_high={len(explained)}")
        return rows, clean, high

    print(f"== acceptance: the {len(built['planted'])} planted files and the clean set "
          f"— on the SHIPPED and the DERIVED manifest")
    accepted, clean_accept, high_files = accept(base, "shipped")
    derived_acc, derived_clean, derived_high = accept(derived, "derived")
    planted_fail = [n for n, r in {**accepted, **derived_acc}.items() if not r["pass"]]
    high_all = high_files + [r for r in derived_high if r["label"] not in {h["label"] for h in high_files}]

    owner = None
    if not a.skip_owner:
        owner = _measure_owner(a.owner_dir, derived)

    def dump(name: str, payload) -> None:
        path = os.path.join(a.out, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")
        print(f"written: {path}")

    def write_all() -> None:
        """Every artifact is written here, and this is called only after every gate passed."""
        explained = [r for r in clean_accept if r["reader_high"]]
        dump("planted.json", {"generated_at": _now(), "thresholds": "shipped", "files": accepted,
                              "derived_pass": all(r["pass"] for r in derived_acc.values())})
        dump("clean.json", {"generated_at": _now(), "thresholds": "shipped",
                            "summary": {"files": len(clean_accept),
                                        "file_high": len(high_files),
                                        "files_with_reader_high": len(explained)},
                            "files": clean_accept})
        if owner is not None:
            dump("owner.json", {"generated_at": _now(), **owner})
        dump("thresholds.json", derived)
        with open(os.path.join(a.out, "arafix.md"), "w", encoding="utf-8") as fh:
            fh.write("# arafix — the orientation detector, measured\n\n"
                     f"- version: {visual_order.VERSION} (MIT)\n"
                     f"- threshold: {visual_order.THRESHOLD} (arafix DEFAULT_THRESHOLDS)\n"
                     f"- clean set: maximum orientation share {derived['observed']['clean_max_visual_share']}\n"
                     f"- planted: {json.dumps({k: v['visual_share'] for k, v in derived['observed']['planted'].items()})}\n"
                     "- mechanism: three voted signals (final-only letters, joining forms, definite article) — NOT the\n"
                     "  assignment's «share of words a lexicon reads forward vs reversed»; the difference is declared in\n"
                     "  docs/checker-v0/00-sources.md §3 and the measurements above are what the adoption rests on.\n")

    if failures:
        print("SEPARATION FAILED:\n  " + "\n  ".join(failures))
        return 1
    if planted_fail:
        print(f"PLANTED ACCEPTANCE FAILED: {sorted(planted_fail)}")
        return 1
    if high_all:
        print(f"CLEAN FILE ALARMS: {len(high_all)} — " + ", ".join(r["label"] for r in high_all[:5]))
        return 1
    # Every artifact is written only after every gate passed: a failing run must not replace the deposited
    # evidence, and the manifest must be the one produced by the run whose numbers are above.
    write_all()
    if a.write:
        with open(THRESHOLDS, "w", encoding="utf-8") as fh:
            json.dump(derived, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"written: {THRESHOLDS}")
    print("MEASUREMENT COMPLETE — every planted file is at its declared level with its named signal, on the "
          "shipped and the derived manifest; no clean file is high")
    return 0


def _path_for(label: str, cases_dir: str) -> str:
    if label.startswith("doc:"):
        return os.path.join(REPO, DOCS[label[4:]])
    if label.startswith("case:"):
        return os.path.join(cases_dir, f"{label[5:]}.pdf")
    raise ValueError(f"unknown label {label!r}")


if __name__ == "__main__":
    sys.exit(main())
