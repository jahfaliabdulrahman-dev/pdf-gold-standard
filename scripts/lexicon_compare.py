#!/usr/bin/env python3
"""PR-2: measure the current lexicon and the Wikipedia candidate on the SAME texts, five readers.

The assignment's sets: 70 clean (4 documents + 66 corpus cases), the planted fixtures, LibreOffice's
two files, the owner's 55 (read-only), and ZATCA's 16 SDK samples. The owner's per-file rows are NOT
written: the 51 ordinary files are aggregated; the three calibration files keep their names (the
assignment names them); the known-bad file is a label, not a name. No text/excerpt is stored.

Separation is reported two ways, because a reader can move the number:
  · literal (the assignment's): min clean file minimum - max ratio among the 3 calibration files + the
    known-bad file. This includes `نظام الشركات` (a numerals defect, lexically valid), so it is negative.
  · lexical-only: the same, but only the files whose defect is lexical (`7 - درس - مهارات التواصل`
    and the known-bad file). `٣ - درس - البايثون` is disclosed, not silently dropped: its ratio is above
    the shipped floor.

The decision rule is the assignment's: the candidate is accepted only if its literal separation is not
lower than the current lexicon's. The lexical-only number is reported beside it, never used to replace it.
This script does NOT write the threshold; `checker_measure.py --write` does, after the decision.

    python3 scripts/lexicon_compare.py --out /tmp/pr2
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import statistics as st
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

from arabic_pdf_check import blind                                      # noqa: E402
from conformance.checks import lexical                                  # noqa: E402
from conformance.readers import available, text_many                    # noqa: E402
import checker_fixtures                                                 # noqa: E402
import checker_measure                                                  # noqa: E402

OWNER_DIR = os.path.expanduser(os.environ.get("OWNER_CORPUS_DIR", ""))
ZATCA_GLOB = os.path.expanduser("~/.cache/zatca-sdk/238-R3.4.8/*/Data/Samples/PDF-A3")
BASELINE_THRESHOLDS = os.path.join(REPO, "docs", "checker-v0", "measurements", "thresholds.json")
CALIBRATION = ["نظام الشركات 1439 سعد الخنفري.pdf", "٣ - درس - البايثون.pdf", "7  - درس - مهارات التواصل.pdf"]
# The known-bad file's NAME is the machine's business, not the code's: the repository is public and the owner
# decided (2026-11-25) that no owner filename enters it. The comparison is refused when the variable is unset,
# because a silent empty name would measure the wrong file.
KNOWN_BAD = os.environ.get("OWNER_KNOWN_BAD", "")
LEXICAL_BROKEN = {CALIBRATION[2]}          # the known-bad row arrives through `known` below


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_info() -> dict:
    head = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "-C", REPO, "status", "--porcelain", "--untracked-files=no"],
                                capture_output=True, text=True, check=True).stdout.strip())
    script = hashlib.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()
    return {"head": head, "dirty": dirty, "script_sha256": script}


def measure(path: str, readers: list[str], vocab: dict[str, frozenset[str]]) -> dict:
    texts = {}
    for name in readers:
        try:
            texts[name] = text_many(name, [path])[0] or ""
        except Exception:                            # a reader failure is a missing score, not a zero
            texts[name] = None
    scores = {}
    for key, words in vocab.items():
        scores[key] = {}
        for name in readers:
            if texts[name] is None:
                scores[key][name] = {"runs": 0, "known": 0, "ratio": None, "error": "ReaderFailed"}
                continue
            scores[key][name] = lexical.validity(texts[name], words)
    return scores


def build_foreign(foreign_dir: str) -> list[tuple[str, str]]:
    htmls = sorted(glob.glob(os.path.join(foreign_dir, "*.html")))
    if not htmls:
        raise SystemExit(f"REFUSED — no LibreOffice HTML sources in {foreign_dir}")
    out = tempfile.mkdtemp(prefix="pr2-foreign-")
    profile = os.path.join(out, "lo-profile")
    proc = subprocess.run(["soffice", "--headless", f"-env:UserInstallation=file://{profile}",
                           "--convert-to", "pdf", "--outdir", out, *htmls],
                          capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise SystemExit(f"REFUSED — LibreOffice conversion failed: {proc.stderr.strip() or proc.stdout.strip()}")
    pdfs = sorted(glob.glob(os.path.join(out, "*.pdf")))
    if len(pdfs) != len(htmls):
        raise SystemExit(f"REFUSED — LibreOffice produced {len(pdfs)} of {len(htmls)} PDFs")
    return [(os.path.basename(p), p) for p in pdfs]


def summarize(records: list[dict], key: str, min_runs: int) -> dict:
    clean = [r for r in records if r["set"] == "clean"]
    cal = [r for r in records if r["set"] == "calibration"]
    known = [r for r in records if r["set"] == "known-bad"]
    lexical_broken = [r for r in cal if r.get("name") in LEXICAL_BROKEN] + known

    def judged(row: dict, name: str) -> bool:
        v = row["scores"][key][name]
        return v["runs"] >= min_runs and v["ratio"] is not None

    readers = sorted({name for r in records for name in r["scores"][key]})
    clean_min_r, clean_med_r = {}, {}
    for name in readers:
        vals = [r["scores"][key][name]["ratio"] for r in clean if judged(r, name)]
        clean_min_r[name] = min(vals) if vals else None
        clean_med_r[name] = st.median(vals) if vals else None
    file_mins = []
    doc_mins = []
    for r in clean:
        vals = [r["scores"][key][n]["ratio"] for n in readers if judged(r, n)]
        if vals:
            file_mins.append(min(vals))
            if r["label"].startswith("doc:"):
                doc_mins.append(min(vals))
    clean_file_min = min(file_mins) if file_mins else None
    clean_docs_min = min(doc_mins) if doc_mins else None

    def max_by_reader(rows: list[dict]) -> dict:
        out = {}
        for name in readers:
            vals = [r["scores"][key][name]["ratio"] for r in rows if judged(r, name)]
            out[name] = max(vals) if vals else None
        return out

    broken_max_r = max_by_reader(cal + known)
    lexical_max_r = max_by_reader(lexical_broken)
    sep_r = {n: (None if clean_min_r[n] is None or broken_max_r[n] is None
                 else round(clean_min_r[n] - broken_max_r[n], 4)) for n in readers}
    lex_sep_r = {n: (None if clean_min_r[n] is None or lexical_max_r[n] is None
                     else round(clean_min_r[n] - lexical_max_r[n], 4)) for n in readers}
    broken_vals = [r["scores"][key][n]["ratio"] for r in cal + known for n in readers if judged(r, n)]
    lexical_vals = [r["scores"][key][n]["ratio"] for r in lexical_broken for n in readers if judged(r, n)]
    broken_max = max(broken_vals) if broken_vals else None
    lexical_max = max(lexical_vals) if lexical_vals else None
    sep_all = None if clean_file_min is None or broken_max is None else round(clean_file_min - broken_max, 4)
    sep_lex = None if clean_file_min is None or lexical_max is None else round(clean_file_min - lexical_max, 4)
    sep_reader_min = min((v for v in sep_r.values() if v is not None), default=None)
    sep_reader_med = st.median([v for v in sep_r.values() if v is not None]) if any(
        v is not None for v in sep_r.values()) else None

    rows = {}
    for r in cal:
        rows[r["name"]] = {n: r["scores"][key][n]["ratio"] for n in readers if judged(r, n)}
    for r in known:
        rows["known-bad"] = {n: r["scores"][key][n]["ratio"] for n in readers if judged(r, n)}
    return {
        "readers": readers,
        "clean_min_by_reader": clean_min_r,
        "clean_median_by_reader": clean_med_r,
        "clean_file_min": clean_file_min,
        "clean_docs_min": clean_docs_min,
        "broken_max_by_reader": broken_max_r,
        "broken_max": broken_max,
        "lexical_broken_max_by_reader": lexical_max_r,
        "lexical_broken_max": lexical_max,
        "calibration": rows,
        "separation_by_reader": sep_r,
        "separation_reader_min": sep_reader_min,
        "separation_reader_median": sep_reader_med,
        "separation_all": sep_all,
        "separation_lexical_only": sep_lex,
        "separation_lexical_only_by_reader": lex_sep_r,
        "clean_judged": sum(1 for r in clean if any(judged(r, n) for n in readers)),
        "calibration_judged": sum(1 for r in cal if any(judged(r, n) for n in readers)),
    }


def owner_summary(records: list[dict], key: str, min_runs: int) -> dict:
    rows = [r for r in records if r["set"] == "owner"]
    readers = sorted({name for r in rows for name in r["scores"][key]})
    out = {}
    for name in readers:
        vals = [r["scores"][key][name]["ratio"] for r in rows
                if r["scores"][key][name]["runs"] >= min_runs and r["scores"][key][name]["ratio"] is not None]
        out[name] = {"judged": len(vals), "min": min(vals) if vals else None,
                     "median": st.median(vals) if vals else None}
    return {"files": len(rows), "by_reader": out}


def check_high(paths: list[tuple[str, str]], key: str, threshold: float, base: dict) -> dict:
    """Run the real checker with one lexicon and one threshold; count lexical-validity highs."""
    lexicon_path = lexical.SHIPPED_DATA if key == "wiki" else lexical.BASELINE_DATA
    th = json.loads(json.dumps(base))
    th["values"]["lexical_validity"]["value"] = threshold
    rows, errors = [], []
    for label, p in paths:
        try:
            rep = blind.check(p, th, lexicon_path=lexicon_path)
        except Exception as exc:
            errors.append({"label": label, "error": type(exc).__name__})
            continue
        high = [s for s in rep["signals"] if s["id"] == "lexical-validity" and s["level"] == "high"]
        rows.append({"label": label, "file_level": rep["risk"]["file"]["level"],
                     "lexical_high": bool(high), "reader_high": [n for n, r in rep["readers"].items()
                                                                 if r["risk"] == "high"]})
    return {"lexicon": os.path.basename(lexicon_path), "threshold": threshold,
            "files": len(rows), "lexical_high": sum(1 for r in rows if r["lexical_high"]),
            "high": sum(1 for r in rows if r["file_level"] == "high"), "rows": rows, "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=tempfile.mkdtemp(prefix="pr2-compare-"))
    ap.add_argument("--owner-dir", default=OWNER_DIR)
    ap.add_argument("--zatca-dir", default=None)
    ap.add_argument("--foreign-dir", default=os.path.join(REPO, "docs", "checker-v0", "foreign"))
    ap.add_argument("--clean-dir", default=None,
                    help="reuse rendered case PDFs already in this directory (no Chrome; same case ids)")
    a = ap.parse_args()
    if not a.owner_dir or not os.path.isdir(a.owner_dir):
        ap.error("the owner corpus is private: set OWNER_CORPUS_DIR to a directory")
    os.makedirs(a.out, exist_ok=True)

    info = git_info()
    readers = list(available()[0])
    if len(readers) != 5:
        raise SystemExit(f"REFUSED — {len(readers)} reader(s) available, expected 5: {readers}")
    base = json.load(open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"), encoding="utf-8"))
    min_runs = base["values"]["lexical_min_runs"]["value"]
    baseline_threshold = json.load(open(BASELINE_THRESHOLDS, encoding="utf-8"))["values"]["lexical_validity"]["value"]
    vocab = {"current": lexical.lexicon(lexical.BASELINE_DATA), "wiki": lexical.lexicon(lexical.SHIPPED_DATA)}
    print(f"head {info['head']} dirty={info['dirty']} · readers {readers} · "
          f"current words {len(vocab['current'])} · wiki words {len(vocab['wiki'])}")

    print("== clean: 4 documents + 66 corpus cases")
    clean = checker_measure.clean_files(a.clean_dir or tempfile.mkdtemp(prefix="pr2-cases-"),
                                        reuse=bool(a.clean_dir))
    if len(clean) != 70:
        raise SystemExit(f"REFUSED — clean set is {len(clean)}, expected 70")
    print("== planted fixtures")
    planted = list(checker_fixtures.build_all(tempfile.mkdtemp(prefix="pr2-planted-"))["planted"].items())
    print("== LibreOffice")
    foreign = build_foreign(a.foreign_dir)
    print(f"   {len(foreign)} file(s)")
    owner = sorted(os.path.join(a.owner_dir, f) for f in os.listdir(a.owner_dir) if f.lower().endswith(".pdf"))
    if len(owner) != 55:
        raise SystemExit(f"REFUSED — owner corpus has {len(owner)} PDFs, expected 55")
    print(f"== owner: {len(owner)} file(s)")
    zatca_dir = a.zatca_dir or (glob.glob(ZATCA_GLOB)[0] if glob.glob(ZATCA_GLOB) else "")
    zatca = sorted(glob.glob(os.path.join(zatca_dir, "*.pdf"))) if zatca_dir else []
    if len(zatca) != 16:
        raise SystemExit(f"REFUSED — ZATCA set has {len(zatca)} PDFs, expected 16")
    print(f"== ZATCA: {len(zatca)} file(s)")

    records = []
    for label, path in clean:
        records.append({"set": "clean", "label": label, "scores": measure(path, readers, vocab)})
    for label, path in planted:
        records.append({"set": "planted", "label": label, "scores": measure(path, readers, vocab)})
    for label, path in foreign:
        records.append({"set": "foreign", "label": label, "scores": measure(path, readers, vocab)})
    calibration_paths = {}
    for name in CALIBRATION:
        path = os.path.join(a.owner_dir, name)
        if not os.path.exists(path):
            matches = glob.glob(os.path.join(a.owner_dir, name.replace("7  ", "7*").replace(" - ", "*")))
            if len(matches) == 1:
                path = matches[0]
            else:
                raise SystemExit(f"REFUSED — calibration file not found: {name}")
        calibration_paths[path] = name
    known_path = os.path.join(a.owner_dir, KNOWN_BAD)
    if not KNOWN_BAD:
        raise SystemExit("REFUSED — set OWNER_KNOWN_BAD to the known-bad file's name; the name is the "
                         "machine's business, not the code's (and the repository is public)")
    if not os.path.exists(known_path) or not os.path.isfile(known_path):
        raise SystemExit(f"REFUSED — known bad file not found: {KNOWN_BAD}")
    calibration_paths[known_path] = KNOWN_BAD
    for i, path in enumerate(owner, 1):
        if path in calibration_paths:
            s = "known-bad" if path == known_path else "calibration"
            rec = {"set": s, "label": f"{s}-{i:02}", "scores": measure(path, readers, vocab)}
            if s == "calibration":
                rec["name"] = calibration_paths[path]
            records.append(rec)
        else:
            records.append({"set": "owner", "label": f"owner-{i:02}", "scores": measure(path, readers, vocab)})
        if i % 10 == 0:
            print(f"   owner {i}/{len(owner)}", flush=True)
    for i, path in enumerate(zatca, 1):
        records.append({"set": "zatca", "label": f"zatca-{i:02}", "scores": measure(path, readers, vocab)})

    summary = {k: summarize(records, k, min_runs) for k in ("current", "wiki")}
    owner_agg = {k: owner_summary(records, k, min_runs) for k in ("current", "wiki")}
    candidate_threshold = checker_measure.derive_lexical_threshold(summary["wiki"]["clean_docs_min"])
    shipped_threshold = base["values"]["lexical_validity"]["value"]
    decision = {
        "rule": "candidate is accepted only when its literal separation is not lower than the current lexicon's",
        "primary": "separation_all = min clean file minimum - max ratio among 3 calibration files + known-bad",
        "secondary": "separation_lexical_only = same, only the 7-file and the known-bad file",
        "population_all": "3 calibration + known-bad",
        "population_lexical": ["7  - درس - مهارات التواصل.pdf", "known-bad"],
        "current_separation_all": summary["current"]["separation_all"],
        "wiki_separation_all": summary["wiki"]["separation_all"],
        "current_separation_lexical_only": summary["current"]["separation_lexical_only"],
        "wiki_separation_lexical_only": summary["wiki"]["separation_lexical_only"],
        "current_separation_reader_min": summary["current"]["separation_reader_min"],
        "wiki_separation_reader_min": summary["wiki"]["separation_reader_min"],
        "accept": bool(summary["wiki"]["separation_all"] is not None
                       and summary["current"]["separation_all"] is not None
                       and summary["wiki"]["separation_all"] >= summary["current"]["separation_all"]),
        "accept_lexical_only": bool(summary["wiki"]["separation_lexical_only"] is not None
                                    and summary["current"]["separation_lexical_only"] is not None
                                    and summary["wiki"]["separation_lexical_only"]
                                    >= summary["current"]["separation_lexical_only"]),
        "reader_min_accept": bool(summary["wiki"]["separation_reader_min"] is not None
                                  and summary["current"]["separation_reader_min"] is not None
                                  and summary["wiki"]["separation_reader_min"]
                                  >= summary["current"]["separation_reader_min"]),
        "threshold_matches_manifest": candidate_threshold == shipped_threshold,
    }
    zatca_current = check_high([(f"zatca-{i:02}", p) for i, p in enumerate(zatca, 1)], "current",
                               baseline_threshold, base)
    zatca_wiki = check_high([(f"zatca-{i:02}", p) for i, p in enumerate(zatca, 1)], "wiki",
                            candidate_threshold, base)
    planted_swap = [(label, path) for label, path in planted if label == "planted-letter-swap"]
    swap_current = check_high(planted_swap, "current", baseline_threshold, base)
    swap_wiki = check_high(planted_swap, "wiki", candidate_threshold, base)

    payload = {
        "generated_at": now(), **info,
        "lexicons": {k: {"path": os.path.basename(p), "sha256": hashlib.sha256(
                            open(p, "rb").read()).hexdigest(), "words": len(vocab[k])}
                     for k, p in (("current", lexical.BASELINE_DATA), ("wiki", lexical.SHIPPED_DATA))},
        "minimum_runs": min_runs,
        "thresholds": {"baseline": baseline_threshold, "candidate": candidate_threshold,
                       "shipped": shipped_threshold, "baseline_source": os.path.relpath(BASELINE_THRESHOLDS, REPO)},
        "counts": {s: sum(1 for r in records if r["set"] == s) for s in
                   ("clean", "planted", "foreign", "owner", "calibration", "known-bad", "zatca")},
        "owner": owner_agg,
        "summary": summary,
        "decision": decision,
        "zatca": {"current": zatca_current, "wiki": zatca_wiki},
        "planted_letter_swap": {"current": swap_current, "wiki": swap_wiki},
        # The owner's ordinary rows are aggregate-only. The three calibration names are the assignment's
        # explicit exception; the known-bad row is a label, never a name.
        "records": [r for r in records if r["set"] != "owner"],
    }
    path = os.path.join(a.out, "lexicon-compare.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    print("\n== decision")
    for k in ("current", "wiki"):
        s = summary[k]
        print(f"{k:8} clean_min={s['clean_file_min']} broken_max={s['broken_max']} "
              f"sep_all={s['separation_all']} sep_lex={s['separation_lexical_only']} "
              f"sep_reader_min={s['separation_reader_min']}")
    print(f"thresholds baseline={baseline_threshold} candidate={candidate_threshold} shipped={shipped_threshold} "
          f"match={decision['threshold_matches_manifest']}")
    print(f"ZATCA lexical-validity high: current {zatca_current['lexical_high']}/{zatca_current['files']} · "
          f"wiki {zatca_wiki['lexical_high']}/{zatca_wiki['files']}")
    print(f"planted-letter-swap high: current {swap_current['high']}/{swap_current['files']} · "
          f"wiki {swap_wiki['high']}/{swap_wiki['files']}")
    print(f"ACCEPT literal: {decision['accept']} · lexical-only: {decision['accept_lexical_only']} · "
          f"reader-min: {decision['reader_min_accept']}")
    print(f"written: {path}")
    return 0 if decision["accept"] else 1


if __name__ == "__main__":
    sys.exit(main())
