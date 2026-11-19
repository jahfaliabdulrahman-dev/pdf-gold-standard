"""Run the corpus through one engine and measure every declared reader.

The order is deliberate: **refuse the corpus before building anything.** A manifest that no longer matches its
cases, or a category below its floor, stops the run before a single PDF exists — a measurement of the wrong
corpus is worse than no measurement. Then build, then extract, then measure, then (optionally) ratchet.

Every number carries its producer: the engine and its version, the reader and its version, and the corpus
manifest's own sha256. There is no aggregate "score" — a single number is what lets a bad reader hide behind a
good one.
"""
import hashlib
import json
import os
import statistics
import time

from .adapters import chrome
from .checks import metrics
from .corpus import cases as corpus_cases
from .corpus import coverage, manifest
from .corpus.truth import truth

ENGINES = {"chrome": "chrome", "chrome-raw": "chrome-raw"}


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def preflight(ids=None) -> tuple[list[dict], list[str]]:
    """Refusals that must stop the run before any build."""
    problems = manifest.problems() + coverage.problems(corpus_cases.load_all())
    if ids and ids != ["all"]:
        try:
            chosen = corpus_cases.by_id(ids)
        except corpus_cases.CaseError as exc:
            problems.append(str(exc))
            chosen = []
        # a subset run cannot certify the corpus floors, so the coverage check above is the whole corpus's
        return chosen, problems
    return corpus_cases.load_all(), problems


def run(engine: str, ids=None, outdir: str = "/tmp/conformance", reader_names=None,
        time_repeats: int = 1, progress=print, run_structure: bool = True) -> dict:
    if engine not in ENGINES:
        raise SystemExit(f"engine {engine!r} is not built yet (this cycle: {sorted(ENGINES)})")
    chosen, problems = preflight(ids)
    if problems:
        raise SystemExit("CORPUS REFUSED:\n  " + "\n  ".join(problems))
    os.makedirs(outdir, exist_ok=True)
    manifest_sha = _sha256(manifest.MANIFEST)

    builds = []
    for case in chosen:
        pdf = os.path.join(outdir, f"{case['id']}.pdf")
        t0 = time.perf_counter()
        producer = chrome.render_case(case, pdf, ENGINES[engine])
        elapsed = time.perf_counter() - t0
        timings = [elapsed]
        for _ in range(max(0, time_repeats - 1)):
            t0 = time.perf_counter()
            chrome.render_case(case, pdf, ENGINES[engine])
            timings.append(time.perf_counter() - t0)
        builds.append({"case": case, "pdf": pdf, "producer": producer, "elapsed": elapsed,
                       "median": statistics.median(timings), "bytes": os.path.getsize(pdf),
                       "sha256": _sha256(pdf), "text_sha256": chrome.text_layer_sha256(pdf)})
        progress(f"built {case['id']:<28} {elapsed:5.2f}s {os.path.getsize(pdf):>7} B")

    VP = {}
    if run_structure:
        from .checks import verapdf as verapdf_mod
        paths_all = [b["pdf"] for b in builds]
        progress("veraPDF: one batch per flavour over the corpus…")
        for flavour in ("ua1", "3b"):
            VP[flavour] = verapdf_mod.batch(paths_all, flavour)
    from .readers import available, text_many
    readers, missing = available()
    if reader_names:
        readers = {k: v for k, v in readers.items() if k in reader_names}
    paths = [b["pdf"] for b in builds]
    texts = {name: text_many(name, paths) for name in readers}

    out_cases = []
    for i, build in enumerate(builds):
        case = build["case"]
        t = truth(case)
        from .checks import mcid_text
        scan = mcid_text.scan(build["pdf"])
        file_text = "\n".join(scan["text"].values())
        floor_bidi = metrics.bidi_count(file_text)
        per_reader = {}
        for name in readers:
            from .readers import limitations
            version = readers[name].version()
            limits, refused, controls = limitations.usable(name, version)
            result = metrics.measure(texts[name][i], t, floor_bidi)
            applied = [limitations.apply(lim, t, texts[name][i], result, control)
                       for lim, control in zip(limits, controls)]
            result["limitations_applied"] = [a for a in applied if a["excused"]]
            result["limitations_refused"] = refused
            per_reader[name] = result
        entry = {
            "id": case["id"], "category": case["category"], "font": case["font"],
            "pdf": os.path.basename(build["pdf"]), "bytes": build["bytes"], "sha256": build["sha256"],
            "text_sha256": build["text_sha256"], "median_seconds": build["median"],
            "producer": build["producer"], "per_reader": per_reader,
            "file": {"bidi": floor_bidi, "zero_width": metrics.zero_width_count(file_text),
                     "notdef": scan["notdef"], "codes": scan["codes"],
                     "untagged_chars": len("".join(v for k, v in scan["text"].items() if k[1] < 0))},
        }
        if run_structure:
            from .checks import structure
            checks = structure.evaluate(build["pdf"], case, build["producer"], run_verapdf=False)
            for flavour, cid in (("ua1", "verapdf-ua1"), ("3b", "verapdf-pdfa3b")):
                fails = VP.get(flavour, {}).get(os.path.realpath(build["pdf"]))
                checks.append({"id": cid, "status": "fail" if fails else "pass",
                               "reason": (f"{len(fails)} failing rule(s): " + ", ".join(k for k, _ in fails[:5]))
                               if fails else "no failing rule"})
            entry["checks"] = checks
            entry["structural_ok"] = all(c["status"] != "fail" for c in checks)
        out_cases.append(entry)

    results = {
        "schema": "conformance-run/1",
        "engine": engine,
        "engine_version": builds[0]["producer"]["engine_version"] if builds else None,
        "corpus": {"manifest_sha256": manifest_sha, "cases": len(out_cases),
                   "counts": manifest.derive()["counts"]},
        "readers": {name: {"version": readers[name].version() if name in readers else None,
                           "available": name in readers,
                           "reason": missing.get(name)} for name in (reader_names or list(readers) + list(missing))},
        "cases": out_cases,
        "summary": summarize(out_cases, readers),
        "checks": summarize_checks(out_cases),
    }
    return results


def summarize(out_cases: list[dict], readers: dict) -> dict:
    """Per reader: mean of each metric, how many cases are exact, and per-category exact rates."""
    summary = {}
    for name in readers:
        rows = [c["per_reader"][name] for c in out_cases if name in c["per_reader"]]
        if not rows:
            continue
        entry = {"cases": len(rows),
                 "exact_cases": sum(1 for r in rows if r["metrics"]["exact"] == 1.0),
                 "mean": {m: round(statistics.fmean(r["metrics"][m] for r in rows), 4) for m in metrics.METRICS},
                 "defects": {k: sum(r["defects"][k] for r in rows) for k in rows[0]["defects"]},
                 "categories": {}}
        for cat in sorted({c["category"] for c in out_cases}):
            cat_rows = [c["per_reader"][name] for c in out_cases
                        if c["category"] == cat and name in c["per_reader"]]
            if cat_rows:
                entry["categories"][cat] = {
                    "cases": len(cat_rows),
                    "exact": sum(1 for r in cat_rows if r["metrics"]["exact"] == 1.0),
                    "order_mean": round(statistics.fmean(r["metrics"]["order"] for r in cat_rows), 4),
                }
        summary[name] = entry
    return summary


def summarize_checks(out_cases: list[dict]) -> dict:
    """Per check id: pass/fail/na across the corpus, and the cases whose structure is not clean.

    This is the number E's baseline needs: how many cases this engine cannot certify at all, and by which
    named check — not a blended «quality» score.
    """
    rows = [c for c in out_cases if "checks" in c]
    if not rows:
        return {}
    ids = []
    for c in rows:
        for chk in c["checks"]:
            if chk["id"] not in ids:
                ids.append(chk["id"])
    out = {"per_check": {}, "structural_failures": [c["id"] for c in rows if not c["structural_ok"]],
           "clean_cases": sum(1 for c in rows if c["structural_ok"]), "cases": len(rows)}
    for cid in ids:
        got = [chk for c in rows for chk in c["checks"] if chk["id"] == cid]
        out["per_check"][cid] = {"pass": sum(1 for g in got if g["status"] == "pass"),
                                 "fail": sum(1 for g in got if g["status"] == "fail"),
                                 "na": sum(1 for g in got if g["status"] == "na")}
    return out


def results_table(results: dict) -> str:
    """A markdown table of (reader × metric) plus the per-category exact counts — the report's raw shape."""
    lines = ["| reader | version | exact cases | exact | word_f1 | order | digit_runs | skeleton | bidi | pres.forms |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name, s in results["summary"].items():
        d = s["defects"]
        lines.append(f"| {name} | {results['readers'][name]['version']} | {s['exact_cases']}/{s['cases']} | "
                     f"{s['mean']['exact']:.3f} | {s['mean']['word_f1']:.3f} | {s['mean']['order']:.3f} | "
                     f"{s['mean']['digit_runs']:.3f} | {s['mean']['skeleton_exact']:.3f} | {d['bidi']} | "
                     f"{d['presentation_forms']} |")
    cats = sorted({c for s in results["summary"].values() for c in s["categories"]})
    lines += ["", "| category | " + " | ".join(results["summary"]) + " |",
              "|---" * (len(results["summary"]) + 1) + "|"]
    for cat in cats:
        cells = []
        for name, s in results["summary"].items():
            e = s["categories"].get(cat)
            cells.append(f"{e['exact']}/{e['cases']}" if e else "—")
        lines.append(f"| {cat} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write(results: dict, outdir: str) -> tuple[str, str]:
    js = os.path.join(outdir, "results.json")
    md = os.path.join(outdir, "results.md")
    with open(js, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    with open(md, "w", encoding="utf-8") as fh:
        fh.write(f"# conformance run — {results['engine']} {results['engine_version']}\n\n")
        fh.write(f"corpus {results['corpus']['cases']} cases · MANIFEST sha256 `{results['corpus']['manifest_sha256']}`\n\n")
        fh.write(results_table(results) + "\n\n")
        if results.get("checks"):
            c = results["checks"]
            fh.write(f"## structural checks\n\n{c['clean_cases']}/{c['cases']} cases clean; "
                     f"not clean: {', '.join(c['structural_failures']) or 'none'}\n\n")
            fh.write("| check | pass | fail | na |\n|---|---|---|---|\n")
            for cid, v in c["per_check"].items():
                fh.write(f"| {cid} | {v['pass']} | {v['fail']} | {v['na']} |\n")
            fh.write("\n")
        misses = [(c["id"], n) for c in results["cases"] for n, r in c["per_reader"].items()
                  if r["metrics"]["exact"] != 1.0]
        fh.write("## not exact, by case\n\n")
        by_case = {}
        for cid, reader in misses:
            by_case.setdefault(cid, []).append(reader)
        for cid in sorted(by_case):
            fh.write(f"- `{cid}`: {', '.join(by_case[cid])}\n")
    return js, md
