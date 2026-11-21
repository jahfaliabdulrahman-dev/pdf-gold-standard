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

import pikepdf

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
SCHEMA_V2 = os.path.join(HERE, "schema", "certificate.v2.json")
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


def certify(pdf_path: str, case_id: str | None = None, engine: str = "unknown",
            truth_text: str | None = None, truth_name: str | None = None) -> dict:
    """Issue a certificate for a corpus case OR for a free text — one rule, one measurement path.

    The second form is the generalization the checker needs: the same certificate, with `source` naming the
    truth text instead of a corpus case. The checks that need a case (headings, tables, block order, outline,
    the case's font family) cannot run against free text and are ABSENT from `checks` there — a reader of the
    certificate sees exactly what ran, and `not_checked` says what a machine cannot claim at all.
    """
    from . import ratchet, reference
    from .checks import structure
    from .corpus import cases as corpus_cases, manifest
    from .readers import TIER1

    if (case_id is None) == (truth_text is None):
        raise CertError("certify takes exactly one of a corpus case and a truth text — "
                        "neither a guess nor both")

    case = None
    if case_id is not None:
        drift = manifest.problems()
        if drift:
            raise CertError("the corpus manifest is not what the cases derive — refusing to certify against an "
                            "unknown corpus: " + "; ".join(drift[:3]))
        case = corpus_cases.by_id([case_id])[0]
        truth = structure._truth_text(case)
        source = {"kind": "case", "case": case_id, "category": case["category"],
                  "manifest_sha256": _sha256(manifest.MANIFEST), "cases": manifest.derive()["total"]}
    else:
        assert truth_text is not None                     # guaranteed by the exactly-one rule above
        truth = truth_text
        source = {"kind": "truth", "sha256": hashlib.sha256(truth_text.encode("utf-8")).hexdigest(),
                  "chars": len(truth_text), "name": truth_name}
    # Provenance is DECLARED, never guessed: the file's own /Producer key is a claim, not a measurement, and
    # a certificate that invented an engine would be certifying its own assumption. `unknown` is a value.
    declared = {"chrome": ("conformance chrome adapter", True), "chrome-raw": ("Chrome for Testing (raw)", False)}
    engine_name, postprocessed = declared.get(engine, ("unknown", False))
    producer = {"engine": engine_name, "engine_version": version_of_engine(engine),
                "postprocess": postprocessed}
    commit, dirty = pipeline_commit()
    # One measurement path (`conformance/reference.py`): the checker measures a free text with the same
    # function, so a corpus case and a customer's file cannot be scored by two different loops.
    measured = reference.measure_text(pdf_path, truth)
    readers = measured["readers"]
    unavailable = [{"reader": name, "reason": reason}
                   for name, reason in measured["missing"].items() if name in TIER1]

    floors = ratchet.load()
    for name, block in readers.items():
        floor = (((floors.get(name) or {}).get("floors") or {}).get(block["version"]) or {}).get(
            "cases", {}).get(case_id)
        block["ratcheted"] = floor is not None
        block.pop("limitations_refused", None)   # a refused limit never reaches the certificate; the run prints it

    # honour_second_file=False: a certificate names ONE file and judges that file. An engine that writes a
    # separate PDF/A-3b file can be measured in a bakeoff (`a3b_path`), but never certified through it.
    if case is not None:
        checks = structure.evaluate(pdf_path, case, producer, run_verapdf=True, honour_second_file=False)
        claims = {"pdfua": "1", "pdfa": "3b"}
    else:
        # A free text declares no PDF/UA or PDF/A claim, so veraPDF is not run and `claims` is null: a
        # machine verdict that invented a claim would be judging a document nobody made.
        with pikepdf.open(pdf_path) as pdf:
            checks, _tree = structure.file_checks(pdf, pdf_path, measured["scan"], producer)
        claims = None
    verdict, detail = decide(checks, readers, unavailable, floors, case_id)
    cert = {
        "schema_version": "certificate/2",
        "file": {"sha256": _sha256(pdf_path), "bytes": os.path.getsize(pdf_path), "pages": _pages(pdf_path)},
        "producer": {"engine": producer["engine"], "engine_version": str(producer["engine_version"]),
                     "pipeline_commit": commit, "postprocess": bool(producer["postprocess"])},
        "source": source,
        # The floors in force when this certificate was issued: a later --accept makes the record visible
        # instead of silently re-judging an old certificate against new floors.
        "ratchet_sha256": _sha256(ratchet.FILE) if os.path.exists(ratchet.FILE) else None,
        "tools": {"verapdf": _verapdf_version(),
                  **{n: (readers[n]["version"] if n in readers else None)
                     for n in ("pdfium", "mupdf", "poppler", "pdfminer", "pdfkit")}},
        "claims": claims,
        "checks": checks,
        "readers": readers,
        "tier1_unavailable": unavailable,
        "not_checked": MATTERHORN,
        "verdict": verdict,
        "verdict_detail": detail + (" · pipeline tree dirty" if dirty else "")
                          + ("" if case is not None else
                             " · free text: the case-only checks (headings, tables, block order, outline, "
                             "font family) did not run, and no PDF/UA or PDF/A claim is judged"),
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


def decide(checks: list[dict], readers: dict, unavailable: list[dict], floors: dict,
           case_id: str | None) -> tuple[str, str]:
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


def recheck(pdf_path: str, cert: dict, truth_text: str | None = None) -> list[str]:
    """Re-measure the file and compare with what the certificate claims. A forged reading has no place to hide.

    Works for both sources: a corpus case (its truth is derived here) and a free text (the caller must pass
    the same text — a certificate cannot re-measure a truth it does not carry, and inventing one would be the
    defect this function exists to catch).
    """
    from . import ratchet, reference
    from .checks import metrics as metrics_mod
    from .checks import structure
    from .corpus import cases as corpus_cases
    from .readers import available

    problems = []
    source = cert.get("source") or {"kind": "case", "case": cert["corpus"]["case"]}
    case = None
    if source["kind"] == "truth":
        if truth_text is None:
            return ["this certificate judges a free text: pass the same text (--truth FILE) to re-measure it"]
        got = hashlib.sha256(truth_text.encode("utf-8")).hexdigest()
        if got != source["sha256"]:
            return [f"the truth text hashes to {got[:12]}, the certificate names {source['sha256'][:12]}"]
        truth, case_id = truth_text, None
    else:
        case_id = source["case"]
        case = next((c for c in corpus_cases.load_all() if c["id"] == case_id), None)
        if case is None:
            return [f"the case {case_id!r} named in the certificate is not in this corpus"]
        truth = structure._truth_text(case)

    ok, _missing = available()
    names = [n for n in ("pdfium", "pdfkit") if n in ok]
    measured = reference.measure_text(pdf_path, truth, reader_names=names)
    for name, live in measured["readers"].items():
        stored = cert["readers"].get(name)
        if stored is None:
            problems.append(f"{name}: the file was re-read but the certificate has no block for it")
            continue
        for metric in metrics_mod.METRICS:
            if abs(float(live[metric]) - float(stored[metric])) > 1e-9:
                problems.append(f"{name}.{metric}: re-read {live[metric]:.4f} but the certificate "
                                f"says {stored[metric]:.4f}")
        for kind, n in live["defects"].items():
            if int(n) != int(stored.get("defects", {}).get(kind, 0)):
                problems.append(f"{name}.defect {kind}: re-read {n}, certificate says "
                                f"{stored.get('defects', {}).get(kind, 0)}")
        if live["version"] and stored.get("version") != live["version"]:
            problems.append(f"{name}: the installed reader is {live['version']}, the certificate names "
                            f"{stored.get('version')} — re-issue it")
    producer = {"postprocess": cert["producer"].get("postprocess")}
    if case is not None:
        live_checks = structure.evaluate(pdf_path, case, producer, run_verapdf=True)
    else:
        with pikepdf.open(pdf_path) as pdf:
            live_checks, _tree = structure.file_checks(pdf, pdf_path, measured["scan"], producer)
    stored_checks = {c["id"]: c["status"] for c in cert["checks"]}
    live_ids = {c["id"] for c in live_checks}
    for chk in live_checks:
        if stored_checks.get(chk["id"]) != chk["status"]:
            problems.append(f"check {chk['id']}: re-ran {chk['status']}, certificate says "
                            f"{stored_checks.get(chk['id'])}")
    # Both directions: a check the certificate names but the gate no longer runs is a stale claim, not a
    # match. (A renamed/removed id would otherwise keep its stored `pass` forever.)
    for cid in sorted(set(stored_checks) - live_ids):
        problems.append(f"check {cid}: the certificate names it and the gate no longer runs it — re-issue")
    if problems:
        return problems
    verdict, detail = decide(live_checks, {k: cert["readers"][k] for k in measured["readers"]},
                             cert["tier1_unavailable"], ratchet.load(), case_id)
    if verdict != cert["verdict"]:
        problems.append(f"verdict {cert['verdict']} does not follow from the re-measured file "
                        f"(recomputed {verdict}: {detail})")
    return problems


def validate(cert_path: str, pdf_path: str, do_recheck: bool = False,
             truth_path: str | None = None) -> list[str]:
    """[] means valid. Every refusal names its reason — schema, file hash, verdict, or a limit's evidence.

    `certificate/1` (corpus only) and `certificate/2` (case or free text) are both accepted: an issued
    certificate keeps the schema it was issued with, and re-writing old files to fit a new shape would erase
    the history of what was claimed.
    """
    import jsonschema
    try:
        cert = json.load(open(cert_path, encoding="utf-8"))
    except Exception as exc:
        return [f"{os.path.basename(cert_path)} is not JSON: {exc}"]
    version = cert.get("schema_version")
    schema_path = {"certificate/1": SCHEMA, "certificate/2": SCHEMA_V2}.get(version)
    if schema_path is None:
        return [f"unknown schema_version {version!r} — a certificate names its own shape"]
    schema = json.load(open(schema_path, encoding="utf-8"))
    problems: list[str] = []
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
    source = cert.get("source") or cert.get("corpus") or {}
    case_id = source.get("case")                      # None for a free text: no floors apply
    verdict, detail = decide(cert["checks"], cert["readers"], cert["tier1_unavailable"], floors, case_id)
    if verdict != cert["verdict"]:
        problems.append(f"verdict {cert['verdict']} does not follow from the checks and readers (recomputed "
                        f"{verdict}: {detail})")
    if do_recheck:
        truth_text = None
        if truth_path:
            if not os.path.exists(truth_path):
                return problems + [f"the truth file is missing: {truth_path}"]
            truth_text = open(truth_path, encoding="utf-8").read()
        problems.extend(recheck(pdf_path, cert, truth_text))
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
    source = cert.get("source") or {}
    if source.get("kind") == "truth":
        src = f"truth: sha256 {source['sha256'][:12]} · {source['chars']} chars"
    else:
        src = (f"corpus: {source.get('case', (cert.get('corpus') or {}).get('case'))} "
               f"({source.get('category', (cert.get('corpus') or {}).get('category'))}) · "
               f"MANIFEST {str(source.get('manifest_sha256', ''))[:12]}")
    lines = [f"verdict: {cert['verdict']} — {cert['verdict_detail']}",
             f"file: {cert['file']['sha256'][:12]} · {cert['file']['bytes']} B · {cert['file']['pages']} page(s)",
             src,
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
