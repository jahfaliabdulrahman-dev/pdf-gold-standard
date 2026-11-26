#!/usr/bin/env python3
"""PR-3's producer: the ZATCA PDF/A-3 forensic table, as one re-runnable command.

The audit of 2026-11-25 (item 5) found the artifact deposited without its producer: the JSON was real, but
nothing in the repository could reproduce it, and it carried no `head` or `dirty` — so «re-run and identical»
was a sentence, not a fact. This script is that producer. It is deliberately the same measurement the
checker's blind mode makes (one scan for the layer, one reading per reader, arafix for orientation), and it
records what the artifact needs to be auditable:

  · `head` + `dirty` from `certificate.pipeline_commit()` — the tree the numbers belong to;
  · `reader_versions` and `environment` — a second machine's numbers are only comparable with these;
  · `sdk` with the sample directory and one sha256 per sample — the population is a vendor SDK, not ours;
  · `runs` — every run appends its timestamp and a digest of the MEASUREMENTS (no timestamps), so two runs
    agreeing is a machine-checked fact rather than a claim in prose.

No sample is copied and no text beyond the bounded first lines the report already publishes is stored.

Usage:
  python3 scripts/zatca_forensics.py --samples <dir> --out <json>          # first run
  python3 scripts/zatca_forensics.py --samples <dir> --out <json>          # again: appends a run
  python3 scripts/zatca_forensics.py --samples <dir> --verify <json>       # refuses if the runs disagree
"""
import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, REPO)

from conformance import certificate as cert_mod                                   # noqa: E402
from conformance.checks import mcid_text, metrics, visual_order                    # noqa: E402
from conformance.hashing import sha256_file                                        # noqa: E402
from conformance.readers import available, text_many, MATRIX                       # noqa: E402

SAMPLES = 16                     # the SDK's PDF-A3 population, declared: a partial directory measures nothing
SAMPLE_LINES = 3


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def checker_thresholds() -> dict:
    """The shipped manifest's arafix keys — the producer must judge orientation with the checker's numbers.

    Calling `visual_order.inspect` without them uses arafix's published defaults, which happen to be equal
    today; a second measurement path that only *happens* to agree is the drift this repository forbids.
    """
    with open(os.path.join(REPO, "arabic_pdf_check", "thresholds.json"), encoding="utf-8") as fh:
        th = json.load(fh)["values"]
    return {"visual_order": th["visual_order"]["value"],
            "presentation_forms": th["presentation_forms"]["value"],
            "min_arabic_chars": th["min_arabic_chars"]["value"]}


def measure_file(path: str, ok: dict, thresholds: dict) -> dict:
    scan = mcid_text.scan(path)
    text = "\n".join(scan["text"].values())
    pf = metrics.pf_count(text)
    arabic = metrics.arabic_count(text)
    codes = sum(row.get("codes") or 0 for row in scan["fonts"].values())
    readers = {}
    for name in ok:
        reading = text_many(name, [path])[0]
        order = visual_order.inspect(reading, thresholds)
        # The artifact's sample is the first ARABIC-bearing lines (that is what the report publishes and
        # what the PR-3 reader table compares) — not the first lines, which are often Latin headers.
        ids = [ln.strip() for ln in reading.splitlines() if metrics.ARABIC.search(ln)][:SAMPLE_LINES]
        readers[name] = {
            "chars": len(reading),          # the reading as the reader returned it (the PR-3 artifact's definition)
            "pf": metrics.pf_count(reading),
            "arabic": metrics.arabic_count(reading),
            "visual": bool(order["visual"]),
            "score": order["score"],
            "confidence": order["confidence"],
            "sample": ids,
        }
    import pikepdf
    with pikepdf.open(path) as pdf:
        af = pdf.Root.get("/AF") is not None
        producer = str((pdf.docinfo or {}).get("/Producer") or "")
    return {"pf_file": pf, "arabic_file": arabic, "af_present": bool(af), "producer": producer,
            "type3_fonts": sum(1 for row in scan["fonts"].values() if row.get("subtype") == "/Type3"),
            "pf_share": round(pf / (pf + arabic), 4) if pf + arabic else 0.0,
            "missing_unicode": scan["missing_unicode"], "notdef": scan["notdef"], "pua": scan["pua"],
            "fonts": len(scan["fonts"]), "codes": codes, "readers": readers}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", required=True, help="the PDF-A3 sample directory (16 PDFs)")
    ap.add_argument("--out", default=None, help="the artifact to write or extend")
    ap.add_argument("--sdk", default=None, help="the SDK's name and release, e.g. 'zatca-einvoicing-sdk-Java 238-R3.4.8'")
    ap.add_argument("--expect", default=None,
                    help="a deposite artifact whose per-sample sha256 values pin this population; a mismatch refuses")
    ap.add_argument("--verify", default=None, help="re-measure, then refuse unless the fresh digest is a recorded one")
    a = ap.parse_args()

    if not os.path.isdir(a.samples):
        raise SystemExit(f"REFUSED — no such sample directory: {a.samples}")
    files = sorted(os.path.join(a.samples, f) for f in os.listdir(a.samples) if f.lower().endswith(".pdf"))
    if len(files) != SAMPLES:
        raise SystemExit(f"REFUSED — {len(files)} PDF(s) in {a.samples}; the declared population is {SAMPLES}")
    ok, missing = available()
    if missing:
        raise SystemExit(f"REFUSED — readers missing: {sorted(missing)}; the declared population is five readers")
    if "pdfkit" not in ok:
        raise SystemExit("REFUSED — PDFKit is missing: this measurement is the macOS five-reader population")

    expected = {}
    if a.expect:
        with open(a.expect, encoding="utf-8") as fh:
            expected = {r["name"]: r["sha256"] for r in json.load(fh)["files"]}
    thresholds = checker_thresholds()
    rows, per_file = [], {}
    for i, path in enumerate(files, 1):
        name = os.path.basename(path)
        sha = sha256_file(path)
        if expected and expected.get(name) != sha:
            raise SystemExit(f"REFUSED — {name}: sha256 {sha[:16]}… is not the pinned {str(expected.get(name))[:16]}…; "
                             f"this is not the declared population")
        row = {"index": i, "name": name, "sha256": sha, **measure_file(path, ok, thresholds)}
        rows.append(row)
        per_file[os.path.basename(path)] = row
        print(f"   {i:02}/{len(files)} {os.path.basename(path)[:52]:54} pf={row['pf_share']:.4f}")

    summary = {
        "files": len(rows),
        "pf_file_positive": sum(1 for r in rows if r["pf_file"] > 0),
        "readers_copying_all_forms": {n: sum(1 for r in rows if r["readers"][n]["pf"] == r["pf_file"] > 0)
                                      for n in ok},
        "readers_reading_reversed": {n: sum(1 for r in rows if r["readers"][n]["visual"]) for n in ok},
        "missing_unicode_total": sum(r["missing_unicode"] for r in rows),
        "notdef_total": sum(r["notdef"] for r in rows),
        "pua_total": sum(r["pua"] for r in rows),
        "file_level_high_signal": f"presentation-forms ({sum(1 for r in rows if r['pf_share'] > 0.02)}/{len(rows)})",
        "visual_order_file_level": sum(1 for r in rows
                                       if sum(1 for n in ok if r["readers"][n]["visual"]) > len(ok) // 2),
        "tounicode_gap_signal": sum(1 for r in rows if r["missing_unicode"] > 0),
        "drawn_codes_total": sum(r["codes"] for r in rows),
        "fonts_total": sum(r["fonts"] for r in rows),
        "producer": ", ".join(sorted({r["producer"] for r in rows if r["producer"]})),
        "type3_samples": [r["index"] for r in rows if r["type3_fonts"]],
        "af_absent_samples": [r["index"] for r in rows if not r["af_present"]],
    }
    measurements = {"summary": summary, "files": rows}
    digest = hashlib.sha256(canonical(measurements).encode("utf-8")).hexdigest()

    if a.verify:
        # VERIFY RE-MEASURES. Comparing the artifact to its own hash proves only that someone recomputed a
        # hash of the edited numbers — the fresh `digest` above is the measurement, and it must be a recorded one.
        art = json.load(open(a.verify, encoding="utf-8"))
        digests = {run["measurements_sha256"] for run in art.get("runs", [])}
        if len(digests) != 1:
            print(f"VERIFY FAILED — the artifact records {len(digests)} different measurement digests: {sorted(digests)}")
            return 1
        if digest not in digests:
            print(f"VERIFY FAILED — the fresh measurement {digest[:16]}… is not a recorded run {sorted(digests)}")
            return 1
        print(f"VERIFY PASSED — the fresh re-measurement equals the recorded digest {digest[:16]}…, "
              f"{len(art['runs'])} run(s), head {art['head']}, dirty {art['dirty']}")
        return 0

    payload = {"schema_version": "zatca-forensics/2", "generated_at": _now(), "runs": []}
    if a.out and os.path.exists(a.out):
        payload = json.load(open(a.out, encoding="utf-8"))
        payload["generated_at"] = _now()
        payload.setdefault("runs", [])
    try:
        commit, dirty = cert_mod.pipeline_commit()
    except cert_mod.CertError:
        commit, dirty = "unknown", None
    sdk = (a.sdk or "").strip()
    if not sdk:
        raise SystemExit("REFUSED — --sdk '<name> <release>' is required: per-file sha256 identifies content, not "
                         "the release the content came from")
    payload.update({"head": commit, "dirty": dirty,
                    "sdk": {"declared": sdk, "directory": os.path.basename(os.path.normpath(a.samples)),
                            "parent": os.path.basename(os.path.dirname(os.path.normpath(a.samples)))},
                    "readers": list(ok), "missing_readers": sorted(missing),
                    "reader_versions": {**{n: ok[n].version() for n in ok},
                                        "arafix": visual_order.VERSION},
                    "environment": {"platform": platform.platform(), "machine": platform.machine(),
                                    "python": platform.python_version(), "readers_declared": len(MATRIX)},
                    "summary": summary, "files": rows})
    # Every run is kept: two runs agreeing is the fact the artifact exists to carry, and replacing a run with
    # its own digest would leave exactly one — a claim that the numbers are stable, with nothing behind it.
    payload["runs"] = payload["runs"] + [{"generated_at": payload["generated_at"],
                                          "measurements_sha256": digest, "head": commit, "dirty": dirty,
                                          "out": os.path.abspath(a.out or "")}]
    payload["runs"] = payload["runs"][-5:]
    if not a.out:
        raise SystemExit("REFUSED — --out is required to deposit a run (or use --verify)")
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"digest {digest[:16]}… · head {commit} · dirty {dirty} · {len(payload['runs'])} run(s)")
    print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
