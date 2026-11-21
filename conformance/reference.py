"""One measurement path for "a file against a text", shared by the corpus certificate and the checker.

`certificate.certify` judges a file against a **corpus case**. `arabic-pdf-check verify` judges a file
against a **free text** the customer supplies. Both need the same block per reader: its version, the five
metrics, the defect counters, the limits that were applied and the ones refused. Writing that loop twice
would let the two disagree about the same file — the same reason `checks/metrics.py` is one module, and the
reason the assignment forbids the checker from carrying its own metrics.

What this module deliberately does NOT decide: which checks run on the file's structure. Those need a case
(headings, tables, block order), so they stay in `checks/structure.evaluate`; the checker's reference mode
reports the metrics and the file-level text facts only.
"""
from .checks import metrics


def measure_text(pdf_path: str, truth_text: str, reader_names=None) -> dict:
    """Measure every available reader on one file against one truth text.

    Returns `{"readers": {...}, "readings": {...}, "missing": {...}, "file": {...}, "scan": {...}}`:
      · `readers` — the block a certificate stores: version, metrics, defects, limits (no raw text);
      · `readings` — the extracted text per reader, for the caller's examples (never serialized as-is);
      · `missing` — every reader that could not run, with its reason (never a silent skip);
      · `file` — the file-level numbers read from the content stream: bidi floor, zero-width, .notdef,
        codes, untagged characters;
      · `scan` — the whole `mcid_text.scan` result, for the per-font table.

    A reader that fails on the file raises (poppler's own behaviour): a tool that could not read a file is
    not a reader that read zero characters, and an exact 0 attributed to it would enter a floor as that
    reader's number.
    """
    from .checks import mcid_text
    from .readers import available, limitations, text_many

    ok, missing = available()
    if reader_names:
        ok = {k: v for k, v in ok.items() if k in reader_names}

    scan = mcid_text.scan(pdf_path)
    file_text = "\n".join(scan["text"].values())
    floor_bidi = metrics.bidi_count(file_text)

    block, readings = {}, {}
    for name, mod in ok.items():
        version = mod.version()
        limits, refused, controls = limitations.usable(name, version)
        reading = text_many(name, [pdf_path])[0]
        result = metrics.measure(reading, truth_text, floor_bidi)
        applied = [limitations.apply(lim, truth_text, reading, result, control)
                   for lim, control in zip(limits, controls)]
        readings[name] = reading
        block[name] = {
            "version": version,
            **result["metrics"],
            "defects": result["defects"],
            "limitations_applied": [a for a in applied if a["excused"]],
            "limitations_refused": refused,
        }

    return {
        "readers": block,
        "readings": readings,
        "missing": missing,
        "file": {"bidi": floor_bidi, "zero_width": metrics.zero_width_count(file_text),
                 "notdef": scan["notdef"], "codes": scan["codes"],
                 "missing_unicode": scan["missing_unicode"], "pua": scan["pua"],
                 "replacement": scan["replacement"],
                 "untagged_chars": len("".join(v for k, v in scan["text"].items() if k[1] < 0))},
        "scan": scan,
    }


METRIC_NAMES = metrics.METRICS


def page_count(pdf_path: str) -> int:
    """Pages in the file, from the file's own page tree (one parser: pikepdf)."""
    import pikepdf
    with pikepdf.open(pdf_path) as pdf:
        return len(pdf.pages)
