"""One measurement path for "a file against a text", shared by the corpus certificate and the checker.

`certificate.certify` judges a file against a **corpus case**. `arabic-pdf-check verify` judges a file
against a **free text** the customer supplies. Both need the same block per reader: its version, the five
metrics, the defect counters, the limits that were applied and the ones refused. Writing that loop twice
would let the two disagree about the same file — the same reason `checks/metrics.py` is one module, and the
reason the assignment forbids the checker from carrying its own metrics.

`runner.run` (the corpus floors) consumes the SAME loop through `measure_readings`: it batches the readers'
texts for speed and then calls this module per case, so a new counter or a new limit is added here once.

What this module deliberately does NOT decide: which checks run on the file's structure. Those need a case
(headings, tables, block order), so they stay in `checks/structure.evaluate`; the checker's reference mode
reports the metrics and the file-level text facts only.
"""
from .checks import metrics


def file_block(scan: dict) -> dict:
    """The file-level numbers read from the content stream — defined once, next to the scan that gives them."""
    text = "\n".join(scan["text"].values())
    return {"bidi": metrics.bidi_count(text), "zero_width": metrics.zero_width_count(text),
            "notdef": scan["notdef"], "codes": scan["codes"],
            "missing_unicode": scan["missing_unicode"], "pua": scan["pua"],
            "replacement": scan["replacement"],
            "untagged_chars": len("".join(v for k, v in scan["text"].items() if k[1] < 0))}


def measure_readings(scan: dict, readings: dict, truth_text: str) -> dict:
    """The single per-reader loop: metrics, limits applied, limits refused.

    `readings` is `{reader_name: extracted_text}` for ONE file — batched by the caller when it measures many
    files. `truth_text` is REQUIRED: a measurement without a truth is `exact 0` by construction, and a
    function that silently produced that would be a trap for the next caller.
    """
    if not isinstance(truth_text, str):
        raise TypeError("measure_readings needs the truth text (str); measuring without it is not a comparison")
    from .readers import limitations, load

    block = {}
    for name, reading in readings.items():
        mod = load(name)
        version = mod.version()
        limits, refused, controls = limitations.usable(name, version)
        result = metrics.measure(reading, truth_text,
                                 metrics.bidi_count("\n".join(scan["text"].values())))
        applied = [limitations.apply(lim, truth_text, reading, result, control)
                   for lim, control in zip(limits, controls)]
        block[name] = {
            "version": version,
            **result["metrics"],
            "defects": result["defects"],
            "limitations_applied": [a for a in applied if a["excused"]],
            "limitations_refused": refused,
        }
    return block


def as_results(block: dict) -> dict:
    """The corpus results shape (`per_reader[name].metrics.*`), from the one flat block.

    `results.json` and `ratchet.json` were written with the metrics nested under `metrics`; a certificate
    stores them flat. The NUMBERS are computed once (`measure_readings`); this adapter only changes the shape
    the corpus contract already published, so the floors keep reading the file they know.
    """
    return {name: {"version": b["version"],
                   "metrics": {m: b[m] for m in metrics.METRICS},
                   "defects": b["defects"],
                   "limitations_applied": b["limitations_applied"],
                   "limitations_refused": b.get("limitations_refused", [])}
            for name, b in block.items()}


def mismatch_examples(truth_text: str, reading: str, limit: int = 5) -> list[dict]:
    """Up to `limit` lines of the reader's text that carry a word the truth does not.

    The free truth has no page structure, so `page` is null by construction — never a guessed number. The
    line is cut to 80 characters, not skipped: a long broken line is exactly the case a reader must see.
    """
    want = set(metrics.N(truth_text).split())
    out = []
    for raw in (reading or "").splitlines():
        # Normalize THE LINE, not the whole reading: N also folds newlines into spaces, and a reading
        # normalized whole would collapse every line into one 80-character excerpt.
        line = " ".join(metrics.N(raw).split())
        if not line:
            continue
        if [w for w in line.split() if w not in want]:
            out.append({"page": None, "text": line[:80]})
        if len(out) >= limit:
            break
    return out


def measure_text(pdf_path: str, truth_text: str, reader_names=None) -> dict:
    """Measure every available reader on one file against one truth text.

    Returns `{"readers": {...}, "readings": {...}, "missing": {...}, "file": {...}, "scan": {...}}`.
    `readings` carries the extracted text per reader for the caller's examples (never serialized as-is);
    `scan` is returned so a certificate can run its structure checks on the SAME parse instead of opening
    the file a second time.

    A reader that fails on the file raises (poppler's own behaviour): a tool that could not read a file is
    not a reader that read zero characters, and an exact 0 attributed to it would enter a floor as that
    reader's number.
    """
    from .checks import mcid_text
    from .readers import available, text_many

    ok, missing = available()
    if reader_names:
        ok = {k: v for k, v in ok.items() if k in reader_names}

    scan = mcid_text.scan(pdf_path)
    readings = {name: text_many(name, [pdf_path])[0] for name in ok}
    return {"readers": measure_readings(scan, readings, truth_text),
            "readings": readings, "missing": missing, "file": file_block(scan), "scan": scan}


def page_count(pdf_path: str) -> int:
    """Pages in the file, from the file's own page tree (one parser: pikepdf)."""
    import pikepdf
    with pikepdf.open(pdf_path) as pdf:
        return len(pdf.pages)
