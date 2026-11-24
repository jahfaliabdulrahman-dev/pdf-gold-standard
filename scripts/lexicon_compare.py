#!/usr/bin/env python3
"""PR-2: measure the current lexicon and the Wikipedia candidate on the SAME texts, five readers.

The assignment's sets: 70 clean (4 documents + 66 corpus cases), the planted fixtures, LibreOffice's
two files, the owner's 55 (read-only), and ZATCA's 16 SDK samples. The owner's names are not written:
each owner file is `owner-NN`; the three calibration files and the known bad file keep their names
(the assignment names them), and no text/excerpt is stored.

Separation is reported two ways, because a reader can move the number:
  · per reader: min(clean ratio) - max(real-broken ratio), and the minimum across readers;
  · whole set: min(file's minimum across judged readers) - max(real-broken ratio across judged readers).

The decision rule is the assignment's: the candidate is accepted only if its separation is not lower
than the current lexicon's. This script does NOT write the threshold; `checker_measure.py --write`
does, after the decision. It does not touch the owner's directory.

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
from conformance.adapters import chrome                                 # noqa: E402
from conformance.checks import lexical                                  # noqa: E402
from conformance.corpus import cases as corpus_cases                    # noqa: E402
from conformance.readers import available, text_many                    # noqa: E402
import checker_fixtures                                                 # noqa: E402

DOCS = {"guide": "guide-v2-ar.pdf", "report": "report.pdf", "najd": "najd.pdf", "print": "report-print.pdf"}
OWNER_DIR = os.path.expanduser(os.environ.get("OWNER_CORPUS_DIR", ""))
ZATCA_GLOB = os.path.expanduser("~/.cache/zatca-sdk/238-R3.4.8/*/Data/Samples/PDF-A3")
CALIBRATION = ["نظام الشركات 1439 سعد الخنفري.pdf", "٣ - درس - البايثون.pdf", "7  - درس - مهارات التواصل.pdf"]
KNOWN_BAD = "اللائحة-التنفيذية-وملحقاتها.pdf"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def head() -> str:
    return subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def build_clean(cases_dir: str) -> list[tuple[str, str]]:
    out = []
    for label, rel in DOCS.items():
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            raise SystemExit(f"REFUSED — clean document missing: {rel}")
        out.append((f"doc:{label}", path))
    cases = corpus_cases.load_all()
    for i, case in enumerate(cases, 1):
        path = os.path.join(cases_dir, f"{case['id']}.pdf")
        chrome.render_case(case, path, "chrome")
        out.append((f"case:{case['id']}", path))
        if i % 10 == 0:
            print(f"   clean cases built: {i}/{len(cases)}")
    if len(out) != 70:
        raise SystemExit(f"REFUSED — clean set is {len(out)}, expected 70 (4 documents + 66 cases)")
    return out


def build_planted() -> dict[str, str]:
    return checker_fixtures.build_all(tempfile.mkdtemp(prefix="pr2-planted-"))["planted"]


def build_foreign(foreign_dir: str) -> list[tuple[str, str]]:
    htmls = sorted(glob.glob(os.path.join(foreign_dir, "*.html")))
    if not htmls:
        raise SystemExit(f"REFUSED — no LibreOffice HTML sources in {foreign_dir}")
    out = tempfile.mkdtemp(prefix="pr2-foreign-")
    profile = os.path.join(out, "lo-profile")
    cmd = ["soffice", "--headless", f"-env:UserInstallation=file://{profile}",
           "--convert-to", "pdf", "--outdir", out, *htmls]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise SystemExit(f"REFUSED — LibreOffice conversion failed: {proc.stderr.strip() or proc.stdout.strip()}")
    pdfs = sorted(glob.glob(os.path.join(out, "*.pdf")))
    if len(pdfs) != len(htmls):
        raise SystemExit(f"REFUSED — LibreOffice produced {len(pdfs)} of {len(htmls)} PDFs")
    return [(os.path.basename(p), p) for p in pdfs]


def measure(path: str, readers: list[str], vocab: dict[str, frozenset[str]]) -> dict:
    texts = {}
    for name in readers:
        try:
            texts[name] = text_many(name, [path])[0] or ""
        except Exception as exc:                     # a reader failure is a missing score, not a zero
            texts[name] = None
    scores = {}
    for key, words in vocab.items():
        scores[key] = {}
        for name in readers:
            if texts[name] is None:
                scores[key][name] = {"runs": 0, "known": 0, "ratio": None, "error": "ReaderFailed"}
                continue
            v = lexical.validity(texts[name], words)
            scores[key][name] = v
    return scores


def summarize(records: list[dict], key: str, min_runs: int) -> dict:
    clean = [r for r in records if r["set"] == "clean"]
    cal = [r for r in records if r["set"] == "calibration"]
    known = [r for r in records if r["set"] == "known-bad"]

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
    for r in clean:
        vals = [r["scores"][key][n]["ratio"] for n in readers if judged(r, n)]
        if vals:
            file_mins.append(min(vals))
    clean_file_min = min(file_mins) if file_mins else None

    broken_max_r = {}
    for name in readers:
        vals = [r["scores"][key][name]["ratio"] for r in cal + known if judged(r, name)]
        broken_max_r[name] = max(vals) if vals else None
    sep_r = {n: (None if clean_min_r[n] is None or broken_max_r[n] is None
                 else round(clean_min_r[n] - broken_max_r[n], 4)) for n in readers}
    broken_vals = [r["scores"][key][n]["ratio"] for r in cal + known for n in readers if judged(r, n)]
    broken_max = max(broken_vals) if broken_vals else None
    sep_all = None if clean_file_min is None or broken_max is None else round(clean_file_min - broken_max, 4)
    sep_reader_min = min((v for v in sep_r.values() if v is not None), default=None)
    sep_reader_med = st.median([v for v in sep_r.values() if v is not None]) if any(
        v is not None for v in sep_r.values()) else None

    rows = {}
    for r in cal + known:
        rows[r.get("name", r["label"])] = {
            n: r["scores"][key][n]["ratio"] for n in readers if judged(r, n)}
    return {
        "readers": readers,
        "clean_min_by_reader": clean_min_r,
        "clean_median_by_reader": clean_med_r,
        "clean_file_min": clean_file_min,
        "broken_max_by_reader": broken_max_r,
        "broken_max": broken_max,
        "calibration": rows,
        "separation_by_reader": sep_r,
        "separation_reader_min": sep_reader_min,
        "separation_reader_median": sep_reader_med,
        "separation_all": sep_all,
        "clean_judged": sum(1 for r in clean if any(judged(r, n) for n in readers)),
        "calibration_judged": sum(1 for r in cal if any(judged(r, n) for n in readers)),
    }


def check_high(paths: list[tuple[str, str]], key: str, threshold: float, base: dict) -> dict:
    """Run the real checker with one lexicon and one threshold; count lexical-validity highs."""
    path = lexical.DATA if key == "wiki" else lexical.CURRENT_DATA
    lexical.set_default(path)
    th = json.loads(json.dumps(base))
    th["values"]["lexical_validity"]["value"] = threshold
    rows, errors = [], []
    try:
        for label, p in paths:
            try:
                rep = blind.check(p, th)
            except Exception as exc:
                errors.append({"label": label, "error": type(exc).__name__})
                continue
            high = [s for s in rep["signals"] if s["id"] == "lexical-validity" and s["level"] == "high"]
            rows.append({"label": label, "file_level": rep["risk"]["file"]["level"],
                         "lexical_high": bool(high), "reader_high": [n for n, r in rep["readers"].items()
                                                                     if r["risk"] == "high"]})
    finally:
        lexical.set_default(lexical.DATA)
    return {"lexicon": os.path.basename(path), "threshold": threshold,
            "files": len(rows), "lexical_high": sum(1 for r in rows if r["lexical_high"]),
            "high": sum(1 for r in rows if r["file_level"] == "high"), "rows": rows, "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=tempfile.mkdtemp(prefix="pr2-compare-"))
    ap.add_argument("--owner-dir", default=OWNER_DIR)
    ap.add_argument("--zatca-dir", default=None)
    ap.add_argument("--foreign-dir", default=os.path.join(REPO, "docs", "checker-v0", "foreign"))
    a = ap.parse_args()
    if not a.owner_dir:
        ap.error("the owner corpus is private: set OWNER_CORPUS_DIR or pass --owner-dir")
    if not os.path.isdir(a.owner_dir):
        ap.error(f"owner directory not found: {a.owner_dir}")
    os.makedirs(a.out, exist_ok=True)

    readers = list(available()[0])
    if len(readers) != 5:
        raise SystemExit(f"REFUSED — {len(readers)} reader(s) available, expected 5: {readers}")
    base = json.load(open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"), encoding="utf-8"))
    min_runs = base["values"]["lexical_min_runs"]["value"]
    vocab = {"current": lexical.lexicon(lexical.CURRENT_DATA), "wiki": lexical.lexicon(lexical.DATA)}
    print(f"readers: {readers} · current words {len(vocab['current'])} · wiki words {len(vocab['wiki'])}")

    print("== clean: 4 documents + 66 corpus cases")
    clean = build_clean(tempfile.mkdtemp(prefix="pr2-cases-"))
    print("== planted fixtures")
    planted = list(build_planted().items())
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
        print(f"   {label:28}", flush=True)
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
    if not os.path.exists(known_path):
        raise SystemExit(f"REFUSED — known bad file not found: {KNOWN_BAD}")
    calibration_paths[known_path] = KNOWN_BAD
    for i, path in enumerate(owner, 1):
        name = os.path.basename(path)
        if path in calibration_paths:
            s = "known-bad" if path == known_path else "calibration"
            records.append({"set": s, "label": f"{s}-{i:02}", "name": calibration_paths[path],
                            "scores": measure(path, readers, vocab)})
        else:
            records.append({"set": "owner", "label": f"owner-{i:02}", "scores": measure(path, readers, vocab)})
        if i % 10 == 0:
            print(f"   owner {i}/{len(owner)}", flush=True)
    for i, path in enumerate(zatca, 1):
        records.append({"set": "zatca", "label": f"zatca-{i:02}", "scores": measure(path, readers, vocab)})

    summary = {k: summarize(records, k, min_runs) for k in ("current", "wiki")}
    current_sep = summary["current"]["separation_all"]
    wiki_sep = summary["wiki"]["separation_all"]
    current_sep_min = summary["current"]["separation_reader_min"]
    wiki_sep_min = summary["wiki"]["separation_reader_min"]
    decision = {
        "rule": "candidate is accepted only when its separation is not lower than the current lexicon's",
        "primary": "separation_all (min clean file minimum - max real-broken ratio), same population for both",
        "current_separation_all": current_sep,
        "wiki_separation_all": wiki_sep,
        "current_separation_reader_min": current_sep_min,
        "wiki_separation_reader_min": wiki_sep_min,
        "accept": bool(wiki_sep is not None and current_sep is not None and wiki_sep >= current_sep),
        "reader_min_accept": bool(wiki_sep_min is not None and current_sep_min is not None
                                  and wiki_sep_min >= current_sep_min),
    }
    candidate_threshold = None if summary["wiki"]["clean_file_min"] is None else round(
        summary["wiki"]["clean_file_min"] - 0.20, 2)
    current_threshold = base["values"]["lexical_validity"]["value"]
    zatca_current = check_high([(f"zatca-{i:02}", p) for i, p in enumerate(zatca, 1)], "current",
                               current_threshold, base)
    zatca_wiki = check_high([(f"zatca-{i:02}", p) for i, p in enumerate(zatca, 1)], "wiki",
                            candidate_threshold if candidate_threshold is not None else current_threshold, base)
    planted_swap = [(label, path) for label, path in planted if label == "planted-letter-swap"]
    swap_current = check_high(planted_swap, "current", current_threshold, base)
    swap_wiki = check_high(planted_swap, "wiki", candidate_threshold if candidate_threshold is not None else current_threshold, base)

    payload = {
        "generated_at": now(), "head": head(),
        "lexicons": {k: {"path": os.path.basename(p), "sha256": hashlib.sha256(
                            open(p, "rb").read()).hexdigest(), "words": len(vocab[k])}
                     for k, p in (("current", lexical.CURRENT_DATA), ("wiki", lexical.DATA))},
        "minimum_runs": min_runs,
        "counts": {s: sum(1 for r in records if r["set"] == s) for s in
                   ("clean", "planted", "foreign", "owner", "calibration", "known-bad", "zatca")},
        "summary": summary,
        "decision": decision,
        "candidate_threshold": candidate_threshold,
        "zatca": {"current": zatca_current, "wiki": zatca_wiki},
        "planted_letter_swap": {"current": swap_current, "wiki": swap_wiki},
        "records": records,
    }
    path = os.path.join(a.out, "lexicon-compare.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")

    print("\n== decision")
    for k in ("current", "wiki"):
        s = summary[k]
        print(f"{k:8} clean_min={s['clean_file_min']} broken_max={s['broken_max']} "
              f"sep_all={s['separation_all']} sep_reader_min={s['separation_reader_min']} "
              f"sep_reader_med={s['separation_reader_median']}")
        print("         clean_min_by_reader:", s["clean_min_by_reader"])
        print("         broken_max_by_reader:", s["broken_max_by_reader"])
    print(f"candidate threshold (derived): {candidate_threshold}")
    print(f"ZATCA lexical-validity high: current {zatca_current['lexical_high']}/{zatca_current['files']} · "
          f"wiki {zatca_wiki['lexical_high']}/{zatca_wiki['files']}")
    print(f"planted-letter-swap high: current {swap_current['high']}/{swap_current['files']} · "
          f"wiki {swap_wiki['high']}/{swap_wiki['files']}")
    print(f"ACCEPT: {decision['accept']} (reader-min: {decision['reader_min_accept']})")
    print(f"written: {path}")
    return 0 if decision["accept"] else 1


if __name__ == "__main__":
    sys.exit(main())
