"""The certificate: what was measured on one file, by which tools, and a verdict that is recomputed.

Three properties make it worth more than a JSON dump:

  · **Every claim is a named check with a status.** `PASS` never stands alone; it names the tier-1 readers it
    was measured with, and `tier1_unavailable[]` records a missing one with its reason, so a PDFium-only
    certificate cannot pass for a two-reader one.
  · **The verdict is derived, not stored and believed.** `validate` re-derives PASS/FAIL from `checks`,
    `readers` and `ratchet.json`, and refuses a certificate whose stored verdict disagrees — the same lesson
    as the pipeline's veraPDF guard.
  · **The claim is bounded in the document itself.** `not_checked` carries the published totals of the
    Matterhorn Protocol (136 conditions; 87 machine-determinable, 47 requiring human judgment, 2 with no
    specific test) and says in one sentence what this certificate does *not* do: it does not claim all 87,
    it claims the ids in `checks`. PDF/UA conformance also needs the human half; a machine verdict that
    forgot that would be the most expensive kind of wrong.

`validate` never runs a control script: a certificate must be checkable without producing new facts. The
controls run in `run` and `certify`, and a limit whose control stopped reproducing is refused there.
"""
import hashlib
import json
import os
import subprocess

MATTERHORN = {
    "source": "Matterhorn Protocol 1.1 (PDF Association, CC BY 4.0, 2021), «Matterhorn Protocol Checkpoints»",
    "conditions_total": 136,
    "machine_determinable": 87,
    "human_judgment": 47,
    "no_specific_test": ["23-001", "27-001"],
    "note": "This certificate claims only the ids listed in `checks`. The 87 machine-determinable conditions "
            "are conditions software CAN determine, not conditions this tool checks; the 47 that need human "
            "judgment are outside it by construction.",
}

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "schema", "certificate.v1.json")
REPO = os.path.abspath(os.path.join(HERE, ".."))


class CertError(RuntimeError):
    """The certificate cannot be issued or is not valid — refused by name."""


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _git(*args) -> str:
    r = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True, timeout=60)
    return r.stdout.strip() if r.returncode == 0 else ""


def pipeline_commit() -> tuple[str, bool]:
    commit = _git("rev-parse", "HEAD")
    if not commit:
        raise CertError("the pipeline commit cannot be read (git rev-parse HEAD) — a certificate must name its code")
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no"))
    return commit, dirty


def _pages(path: str) -> int:
    import pymupdf
    doc = pymupdf.open(path)
    try:
        return doc.page_count
    finally:
        doc.close()


def certify(pdf_path: str, case_id: str, engine: str = "unknown") -> dict:
    from . import ratchet
    from .checks import structure
    from .corpus import cases as corpus_cases, manifest
    from .readers import available, limitations, text_many
    from .checks import metrics

    drift = manifest.problems()
    if drift:
        raise CertError("the corpus manifest is not what the cases derive — refusing to certify against an "
                        "unknown corpus: " + "; ".join(drift[:3]))
    case = corpus_cases.by_id([case_id])[0]
    # Provenance is DECLARED, never guessed: the file's own /Producer key is a claim, not a measurement, and
    # a certificate that invented an engine would be certifying its own assumption. `unknown` is a value.
    declared = {"chrome": ("conformance chrome adapter", True), "chrome-raw": ("Chrome for Testing (raw)", False)}
    engine_name, postprocessed = declared.get(engine, ("unknown", False))
    producer = {"engine": engine_name, "engine_version": version_of_engine(engine),
                "postprocess": postprocessed}
    commit, dirty = pipeline_commit()
    readings, readers, unavailable = {}, {}, []
    readers_ok, missing = available()
    for name, mod in readers_ok.items():
        readings[name] = text_many(name, [pdf_path])[0]
    for name, reason in missing.items():
        from .readers import TIER1
        if name in TIER1:
            unavailable.append({"reader": name, "reason": reason})

    from .checks import mcid_text
    scan = mcid_text.scan(pdf_path)
    file_bidi = metrics.bidi_count("\n".join(scan["text"].values()))

    floors = ratchet.load()
    for name in readings:
        version = readers_ok[name].version()
        limits, refused, controls = limitations.usable(name, version)
        result = metrics.measure(readings[name], structure._truth_text(case), file_bidi)
        applied = [limitations.apply(lim, structure._truth_text(case), readings[name], result, control)
                   for lim, control in zip(limits, controls)]
        floor = (((floors.get(name) or {}).get("floors") or {}).get(version) or {}).get(
            "cases", {}).get(case_id)
        readers[name] = {
            "version": version,
            **result["metrics"],
            "defects": result["defects"],
            "limitations_applied": [a for a in applied if a["excused"]],
            "ratcheted": floor is not None,
        }
        _ = refused          # a refused limit never reaches the certificate; the run prints it

    # honour_second_file=False: a certificate names ONE file and judges that file. An engine that writes a
    # separate PDF/A-3b file can be measured in a bakeoff (`a3b_path`), but never certified through it.
    checks = structure.evaluate(pdf_path, case, producer, run_verapdf=True, honour_second_file=False)
    verdict, detail = decide(checks, readers, unavailable, floors, case_id)
    cert = {
        "schema_version": "certificate/1",
        "file": {"sha256": _sha256(pdf_path), "bytes": os.path.getsize(pdf_path), "pages": _pages(pdf_path)},
        "producer": {"engine": producer["engine"], "engine_version": str(producer["engine_version"]),
                     "pipeline_commit": commit, "postprocess": bool(producer["postprocess"])},
        "corpus": {"case": case_id, "category": case["category"],
                   "manifest_sha256": _sha256(manifest.MANIFEST), "cases": manifest.derive()["total"]},
        # The floors in force when this certificate was issued: a later --accept makes the record visible
        # instead of silently re-judging an old certificate against new floors.
        "ratchet_sha256": _sha256(ratchet.FILE) if os.path.exists(ratchet.FILE) else None,
        "tools": {"verapdf": _verapdf_version(), **{n: (readers_ok[n].version() if n in readers_ok else None)
                                                    for n in ("pdfium", "mupdf", "poppler", "pdfminer", "pdfkit")}},
        "claims": {"pdfua": "1", "pdfa": "3b"},
        "checks": checks,
        "readers": readers,
        "tier1_unavailable": unavailable,
        "not_checked": MATTERHORN,
        "verdict": verdict,
        "verdict_detail": detail + (" · pipeline tree dirty" if dirty else ""),
    }
    return cert


def version_of_engine(engine: str) -> str:
    """The engine's own version when we can ask it; «unknown» otherwise (never a guess)."""
    if engine in ("chrome", "chrome-raw"):
        try:
            from .adapters import chrome
            return chrome.chrome_bin()[1]
        except Exception as exc:
            return f"unavailable ({type(exc).__name__})"
    return "unknown"


def _verapdf_version() -> str:
    from .checks import verapdf as v
    try:
        return v.version()
    except Exception as exc:
        return f"unavailable ({type(exc).__name__})"


def decide(checks: list[dict], readers: dict, unavailable: list[dict], floors: dict, case_id: str) -> tuple[str, str]:
    """The one rule. Re-derived by `validate`; never taken from the file being checked."""
    failed = [c["id"] for c in checks if c["status"] == "fail"]
    if failed:
        return "FAIL", "failed checks: " + ", ".join(failed)
    if "pdfium" not in readers:
        return "FAIL", "pdfium (tier-1) is unavailable — the primary metric was not measured"
    if readers["pdfium"]["exact"] != 1:
        return "FAIL", "pdfium exact 0 (the primary metric P)"
    if "pdfkit" in readers and readers["pdfkit"]["exact"] != 1:
        return "FAIL", "pdfkit exact 0 (tier-1)"
    low = []
    for name, block in readers.items():
        # The floor of THIS reader's version: a certificate is judged against the floors its own tools imply.
        floor = ((((floors.get(name) or {}).get("floors") or {}).get(block.get("version")) or {})
                 .get("cases", {}).get(case_id))
        if floor is None:
            continue
        for metric in ("exact", "word_f1", "order", "digit_runs", "skeleton_exact"):
            if float(block[metric]) + 1e-9 < float(floor.get(metric, 0.0)):
                low.append(f"{name}.{metric} {block[metric]:.4f} < {floor.get(metric):.4f}")
    if low:
        return "FAIL", "below the recorded floor: " + "; ".join(low[:4])
    if unavailable:
        return "PASS", "PASS (tier-1 incomplete: " + ", ".join(u["reader"] for u in unavailable) + " n/a)"
    return "PASS", "PASS (both tier-1 readers exact, every check passed)"


def recheck(pdf_path: str, cert: dict) -> list[str]:
    """Re-measure the file and compare with what the certificate claims. A forged reading has no place to hide.

    This is the answer to the one hole the review would not let stand as a declared limit: a certificate is
    unsigned JSON, so `readers` could be edited. Re-extracting with the tier-1 readers and re-running the
    structural checks costs seconds for one file and needs no trust in the file being checked. What it cannot
    do is prove the *producer* — that is what the pipeline commit and the markup hash are for.
    """
    from .checks import metrics, structure
    from .corpus import cases as corpus_cases
    from .readers import available, text_many, version_of
    problems = []
    case_id = cert["corpus"]["case"]
    case = next((c for c in corpus_cases.load_all() if c["id"] == case_id), None)
    if case is None:
        return [f"the case {case_id!r} named in the certificate is not in this corpus"]
    ok, _missing = available()
    names = [n for n in ("pdfium", "pdfkit") if n in ok]
    readings = {n: text_many(n, [pdf_path])[0] for n in names}
    versions = {n: version_of(n) for n in names}
    file_bidi = metrics.bidi_count("\n".join(structure.mcid_text.scan(pdf_path)["text"].values()))
    for name, reading in readings.items():
        live = metrics.measure(reading, structure._truth_text(case), file_bidi)
        stored = cert["readers"].get(name)
        if stored is None:
            problems.append(f"{name}: the file was re-read but the certificate has no block for it")
            continue
        for metric in ("exact", "word_f1", "order", "digit_runs", "skeleton_exact"):
            if abs(float(live["metrics"][metric]) - float(stored[metric])) > 1e-9:
                problems.append(f"{name}.{metric}: re-read {live['metrics'][metric]:.4f} but the certificate "
                                f"says {stored[metric]:.4f}")
        for kind, n in live["defects"].items():
            if int(n) != int(stored.get("defects", {}).get(kind, 0)):
                problems.append(f"{name}.defect {kind}: re-read {n}, certificate says "
                                f"{stored.get('defects', {}).get(kind, 0)}")
        if versions.get(name) and stored.get("version") != versions[name]:
            problems.append(f"{name}: the installed reader is {versions[name]}, the certificate names "
                            f"{stored.get('version')} — re-issue it")
    live_checks = structure.evaluate(pdf_path, case, {"postprocess": cert["producer"].get("postprocess")},
                                     run_verapdf=True)
    stored_checks = {c["id"]: c["status"] for c in cert["checks"]}
    for chk in live_checks:
        if stored_checks.get(chk["id"]) != chk["status"]:
            problems.append(f"check {chk['id']}: re-ran {chk['status']}, certificate says "
                            f"{stored_checks.get(chk['id'])}")
    if problems:
        return problems
    from . import ratchet
    verdict, detail = decide(live_checks, {k: cert["readers"][k] for k in readings},
                             cert["tier1_unavailable"], ratchet.load(), case_id)
    if verdict != cert["verdict"]:
        problems.append(f"verdict {cert['verdict']} does not follow from the re-measured file "
                        f"(recomputed {verdict}: {detail})")
    return problems


def validate(cert_path: str, pdf_path: str, do_recheck: bool = False) -> list[str]:
    """[] means valid. Every refusal names its reason — schema, file hash, verdict, or a limit's evidence."""
    import jsonschema
    try:
        cert = json.load(open(cert_path, encoding="utf-8"))
    except Exception as exc:
        return [f"{os.path.basename(cert_path)} is not JSON: {exc}"]
    schema = json.load(open(SCHEMA, encoding="utf-8"))
    problems = []
    try:
        jsonschema.validate(cert, schema)
    except jsonschema.ValidationError as exc:
        problems.append(f"schema: {exc.message} at {list(exc.absolute_path)}")
        return problems                                  # nothing below is meaningful without the shape
    if not os.path.exists(pdf_path):
        return [f"the file being certified is missing: {pdf_path}"]
    got = _sha256(pdf_path)
    if got != cert["file"]["sha256"]:
        problems.append(f"file sha256 {got[:12]} is not the certified {cert['file']['sha256'][:12]}")
    if os.path.getsize(pdf_path) != cert["file"]["bytes"]:
        problems.append(f"file size {os.path.getsize(pdf_path)} is not the certified {cert['file']['bytes']}")
    from . import ratchet
    floors = ratchet.load()
    case_id = cert["corpus"]["case"]
    verdict, detail = decide(cert["checks"], cert["readers"], cert["tier1_unavailable"], floors, case_id)
    if verdict != cert["verdict"]:
        problems.append(f"verdict {cert['verdict']} does not follow from the checks and readers (recomputed "
                        f"{verdict}: {detail})")
    if do_recheck:
        problems.extend(recheck(pdf_path, cert))
    # A limit must name an evidence-carrying entry for this reader, at the version the control was measured on.
    from .readers import limitations
    known = {lim["id"]: lim for lim in limitations.load()}
    for name, block in cert["readers"].items():
        for applied in block["limitations_applied"]:
            lim = known.get(applied["id"])
            if lim is None:
                problems.append(f"limitation {applied['id']} applied to {name} but not declared in limitations.json")
            elif lim["reader"] != name:
                problems.append(f"limitation {applied['id']} declares reader {lim['reader']}, applied to {name}")
            elif applied["reader_version_measured"] != lim.get("reader_version_measured"):
                problems.append(f"limitation {applied['id']} was measured on "
                                f"{lim.get('reader_version_measured')}, the certificate records "
                                f"{applied['reader_version_measured']}")
            elif not lim.get("control_script"):
                problems.append(f"limitation {applied['id']} has no control script — an exemption, not a limit")
    return problems


def human_summary(cert: dict) -> str:
    lines = [f"verdict: {cert['verdict']} — {cert['verdict_detail']}",
             f"file: {cert['file']['sha256'][:12]} · {cert['file']['bytes']} B · {cert['file']['pages']} page(s)",
             f"corpus: {cert['corpus']['case']} ({cert['corpus']['category']}) · "
             f"MANIFEST {cert['corpus']['manifest_sha256'][:12]}",
             "checks:"]
    for c in cert["checks"]:
        lines.append(f"  [{c['status']:<4}] {c['id']}: {c['reason'][:120]}")
    lines.append("readers:")
    for name, r in cert["readers"].items():
        limits = ", ".join(f"{a['id']}({a['excused']})" for a in r["limitations_applied"]) or "none"
        lines.append(f"  {name:<8} {r['version']:<28} exact {r['exact']} · order {r['order']:.2f} · "
                     f"digit_runs {r['digit_runs']:.2f} · limits {limits}"
                     + ("" if r["ratcheted"] else " · unratcheted"))
    if cert["tier1_unavailable"]:
        lines.append("tier-1 unavailable: " + "; ".join(f"{u['reader']}: {u['reason'][:80]}"
                                                        for u in cert["tier1_unavailable"]))
    return "\n".join(lines)
