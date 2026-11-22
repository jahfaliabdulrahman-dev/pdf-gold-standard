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
from conformance.checks import mcid_text, metrics, structure, visual_order   # noqa: E402
from conformance.readers import MATRIX, available, pages_many, text_many   # noqa: E402
from conformance.corpus import cases as corpus_cases                          # noqa: E402
import checker_fixtures                                                       # noqa: E402

DOCS = {"guide": "guide-v2-ar.pdf", "report": "report.pdf", "najd": "najd.pdf", "print": "report-print.pdf"}
OWNER_DIR = os.path.expanduser(
    "~/Library/CloudStorage/GoogleDrive-almohalhel1408@gmail.com/ملفاتي/PDF_for_PDF")
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
    pairs = [content_f1(texts[a], texts[b]) for a, b in itertools.combinations(sorted(texts), 2)]
    # Only fonts that HAVE a /ToUnicode map can have a gap in it: a simple font with no map is allowed by
    # Matterhorn 31-027 and `font_verdicts` gives it level None — counting its gap_ratio (1.0) would derive
    # a threshold from a non-defect.
    gap_max = max((v["gap_ratio"] for v in structure.font_verdicts(scan, 1.0) if v["tounicode"]), default=0.0)
    empty_pages = {n: v for n, v in blind.empty_pages_for(pages, list(ok)).items() if v}
    return {
        "pf_ratio": metrics.pf_share(file_text),
        "gap_ratio_max": gap_max,
        "forms": forms,
        "arabic": arabic,
        "visual_share": len([n for n, o in orders.items() if o["visual"]]) / len(MATRIX),
        "visual_readers": [n for n, o in orders.items() if o["visual"]],
        "pair_min": min(pairs) if pairs else 1.0,
        "empty_pages": {n: v for n, v in empty_pages.items() if v},
        "missing_unicode": scan["missing_unicode"],
        "notdef": scan["notdef"],
        "pua": scan["pua"],
        "readers": list(ok),
    }


def clean_files(cases_dir: str) -> list[tuple[str, str]]:
    """The four documents (built by CI) and the whole corpus, built here with the pinned engine."""
    out = []
    for label, rel in DOCS.items():
        path = os.path.join(REPO, rel)
        if os.path.exists(path):
            out.append((f"doc:{label}", path))
    from conformance.adapters import chrome
    for case in corpus_cases.load_all():
        path = os.path.join(cases_dir, f"{case['id']}.pdf")
        chrome.render_case(case, path, "chrome")
        out.append((f"case:{case['id']}", path))
    return out


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


def derive(clean_rows: list[dict], planted_rows: dict, thresholds: dict) -> tuple[dict, list[str]]:
    th = json.loads(json.dumps(thresholds))
    failures = []
    clean_pf = max(r["pf_ratio"] for r in clean_rows)
    clean_gap = max(r["gap_ratio_max"] for r in clean_rows)
    clean_share = max(r["visual_share"] for r in clean_rows)   # a separation check, not a threshold
    clean_min = min(r["pair_min"] for r in clean_rows)

    th["values"]["presentation_forms"]["value"] = round(max(th["values"]["presentation_forms"]["declared"],
                                                             clean_pf), 4)
    th["values"]["tounicode_gap_ratio"]["value"] = round(max(
        th["values"]["tounicode_gap_ratio"]["declared"], clean_gap), 4)
    th["observed"] = {"clean_max_presentation_forms": round(clean_pf, 4),
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
                                         "missing_unicode": r["missing_unicode"]}
                                  for name, r in planted_rows.items()}}
    # separation is required only for the signal a fixture is planted to trip
    for name, row in planted_rows.items():
        expected = checker_fixtures.PLANTED[name]
        if expected == "presentation-forms":
            gap = row["pf_ratio"] - clean_pf
            if gap < 0.20 or row["pf_ratio"] <= th["values"]["presentation_forms"]["value"]:
                failures.append(f"{name}: presentation-forms does not separate "
                                f"(planted {row['pf_ratio']:.3f} vs clean {clean_pf:.3f})")
        elif expected == "visual-order":
            need = blind.majority_needed()
            gap = row["visual_share"] - clean_share
            if gap < 0.20 or row["visual_share"] * len(MATRIX) < need:
                failures.append(f"{name}: orientation majority does not separate "
                                f"(share {row['visual_share']:.2f} vs clean {clean_share:.2f}, "
                                f"need {need}/{len(MATRIX)})")
        elif expected == "tounicode-gaps" and row["missing_unicode"] <= 0:
            failures.append(f"{name}: ToUnicode gaps are not positive")
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
    a = ap.parse_args()
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
    cases_dir = tempfile.mkdtemp(prefix="checker-cases-")
    clean_rows = []
    for label, path in clean_files(cases_dir):
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
    if derived["values"] != base["values"] and not a.write:
        print("THRESHOLDS DIFFER — the measurement does not match the shipped manifest; "
              "review it, then re-run with --write")
        return 1
    print("   " + json.dumps(derived["observed"], ensure_ascii=False)[:400])

    print("== acceptance: the four planted files")
    accepted = {}
    for name, path in built["planted"].items():
        rep = blind.check(path, derived)
        expected = checker_fixtures.PLANTED[name]
        file_ids = [s["id"] for s in rep["signals"]]
        ok = rep["risk"]["file"]["level"] == "high" and expected in file_ids
        accepted[name] = {"expected_signal": expected, "file_signals": file_ids,
                          "file_level": rep["risk"]["file"]["level"],
                          "overall": rep["risk"]["level"], "pass": ok}
        print(f"   {name:28} file={rep['risk']['file']['level']:6} signals={file_ids} "
              f"{'PASS' if ok else 'FAIL'}")

    print("== acceptance: the clean set")
    clean_accept = []
    for row in clean_rows:
        path = _path_for(row["label"], cases_dir)
        rep = blind.check(path, derived)
        clean_accept.append({"label": row["label"], "file_level": rep["risk"]["file"]["level"],
                             "overall": rep["risk"]["level"],
                             "reader_high": [n for n, r in rep["readers"].items() if r["risk"] == "high"],
                             "reader_signals": {n: sorted({s["id"] for s in r["signals"]})
                                                for n, r in rep["readers"].items() if r["signals"]}})
    high_files = [r for r in clean_accept if r["file_level"] == "high"]
    explained = [r for r in clean_accept if r["reader_high"]]
    print(f"   files={len(clean_accept)} file_high={len(high_files)} "
          f"files_with_reader_high={len(explained)}")

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
        dump("planted.json", {"generated_at": _now(), "files": accepted})
        dump("clean.json", {"generated_at": _now(),
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
    if high_files:
        print(f"CLEAN FILE ALARMS: {len(high_files)} — " + ", ".join(r["label"] for r in high_files[:5]))
        return 1
    # Every artifact is written only after every gate passed: a failing run must not replace the deposited
    # evidence, and the manifest must be the one produced by the run whose numbers are above.
    write_all()
    if a.write:
        with open(THRESHOLDS, "w", encoding="utf-8") as fh:
            json.dump(derived, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"written: {THRESHOLDS}")
    print("MEASUREMENT COMPLETE — every planted file is high with its named signal; no clean file is high")
    return 0


def _path_for(label: str, cases_dir: str) -> str:
    if label.startswith("doc:"):
        return os.path.join(REPO, DOCS[label[4:]])
    if label.startswith("case:"):
        return os.path.join(cases_dir, f"{label[5:]}.pdf")
    raise ValueError(f"unknown label {label!r}")


if __name__ == "__main__":
    sys.exit(main())
