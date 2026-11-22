"""The blind mode: what a file says about itself, with no source text to compare against.

Every number here is either deterministic (a count of characters or of codes drawn without a Unicode
value) or comes from a detector that is measured and cited:
  · ToUnicode coverage  — `conformance.checks.mcid_text.scan`, per font (ISO 32000-1 §14.8.2.4.2;
    Matterhorn 10-001, 31-027…31-030);
  · orientation         — `conformance.checks.visual_order` (arafix, MIT; UAX #9 and W3C alreq §3.2);
  · numeral rules       — the gate's own `structure.persian_digits` / `structure.mixed_numbers`;
  · reader disagreement — the deterministic case only: a page a reader returns empty while two or more
    readers read it. The metric form (`content_f1` with a threshold) was measured on the clean set and
    refused — the clean minimum is 0.0, so no threshold separates (measurements/thresholds.json).

What it does NOT do: no percentage, no PASS, no OCR, no judgement of the drawn glyphs — only of the text
layer and of what the readers make of it. The risk is reported at two levels, and they are different claims:
`risk.file` is about the document, `risk.readers.<name>` is about copying from that tool. A reader's known
limit never raises `risk.file` — that is the assignment's «تُعلَن ولا تُحسب على الملف», as code.
"""
import hashlib
import os

from conformance import certificate as cert_mod
from conformance import reference
from conformance.checks import mcid_text, metrics, structure, visual_order
from conformance.checks.metrics import arabic_count, pf_count, pf_share
from conformance.readers import MATRIX, available, declared, limitations, pages_many, text_many

LEVELS = {"low": 0, "medium": 1, "high": 2}
CONFIDENCE = {"low": 0, "medium": 1, "high": 2}
ARABIC = metrics.ARABIC


def majority_needed() -> int:
    """The declared matrix's majority (3 of 5) — a structural rule, not a measured threshold."""
    return len(MATRIX) // 2 + 1


def visual_orders(texts: dict, th: dict) -> dict:
    """arafix's diagnosis per reader, with the manifest's thresholds PASSED (not assumed)."""
    thresholds = {"visual_order": th["visual_order"]["value"],
                  "presentation_forms": th["presentation_forms"]["value"],
                  "min_arabic_chars": th["min_arabic_chars"]["value"]}
    return {name: visual_order.inspect(text, thresholds) for name, text in texts.items()}


def empty_pages_for(pages: dict, names) -> dict:
    """{reader: [pages it returns empty while two or more others read]} — no threshold, a fact."""
    out = {}
    for name in names:
        gaps = []
        for i, page in enumerate(pages.get(name) or []):
            if ARABIC.search(page or ""):
                continue
            others = sum(1 for other in names if other != name and i < len(pages.get(other) or [])
                         and ARABIC.search(pages[other][i] or ""))
            if others >= 2:
                gaps.append(i + 1)
        out[name] = gaps
    return out


def _finding(sid: str, level: str, cause: str, confidence: str, detail: str, **evidence) -> dict:
    return {"id": sid, "level": level, "cause": cause, "confidence": confidence,
            "detail": detail, "evidence": evidence}


def _top(signals: list[dict]) -> str:
    if not signals:
        return "low"
    return max((s["level"] for s in signals), key=lambda lv: LEVELS[lv])


def _confidence(signals: list[dict]) -> str:
    """The weakest confidence among the signals that decided the level — never an average."""
    if not signals:
        return "medium"                      # absence of evidence is not evidence of absence
    top = _top(signals)
    return min((s["confidence"] for s in signals if s["level"] == top), key=lambda c: CONFIDENCE[c])


def _examples(text: str, pages: list[str], limit: int = 5, predicate=None) -> list[dict]:
    """Up to `limit` bounded lines; a page number is measured by finding the line in that reader's page.

    A line longer than 80 characters is CUT, not skipped: the long broken line is exactly the evidence a
    reader of the report needs, and skipping it can leave a signal with no example at all.
    """
    out = []
    for line in (text or "").splitlines():
        line = (line or "").strip()
        if not line:
            continue
        if predicate and not predicate(line):
            continue
        page = next((i + 1 for i, p in enumerate(pages) if line in (p or "")), None)
        out.append({"page": page, "text": line[:80]})
        if len(out) >= limit:
            break
    return out


def _font_signals(scan: dict, gap_high: float = 0.01) -> tuple[list[dict], list[dict]]:
    """(file signals, font rows for the report) — the RULE lives in `conformance.checks.structure.font_verdicts`.

    This function only shapes the verdicts into the report: the same per-font decision the certificate's
    `tounicode-coverage` check uses, with the measured share as its threshold. A second copy here would let
    the report and the certificate disagree about one font.
    """
    signals, rows = [], []
    for v in structure.font_verdicts(scan, gap_high):
        rows.append({"font": v["key"], "family": v["family"], "subtype": v["subtype"],
                     "embedded": v["embedded"], "tounicode": v["tounicode"],
                     "two_byte": v["two_byte"], "codes": v["codes"],
                     "missing_unicode": v["missing_unicode"], "notdef": v["notdef"],
                     "pua": v["pua"], "replacement": v["replacement"],
                     "zero_value": v["zero_value"], "bom": v["bom"], "note": v["note"]})
        if v["level"]:
            signals.append(_finding(
                "tounicode-gaps", v["level"], "file", "high",
                f"{v['name']} ({v['subtype']}): " + "; ".join(v["problems"] or v["warnings"]),
                font=v["key"], codes=v["codes"], missing_unicode=v["missing_unicode"],
                notdef=v["notdef"], pua=v["pua"], replacement=v["replacement"],
                zero_value=v["zero_value"], bom=v["bom"], threshold=gap_high))
    return signals, rows


def why_class(why) -> str:
    """The failure CLASS only, never the exception text: an ImportError message can carry a local path, and
    this string goes into a customer's report and certificate."""
    return (str(why).split(":")[0].strip() or "unavailable")[:60]


def check(pdf_path: str, thresholds: dict) -> dict:
    ok, missing = available()
    if not ok:
        raise RuntimeError("no reader is available — a report with no reader is not a report")

    texts, pages, page_unsupported = {}, {}, []
    for name in ok:
        got = pages_many(name, [pdf_path])
        if got is None or got[0] is None:
            # A reader that cannot name its pages still has text; its examples carry `page: null`, and the
            # report names it. Folding this to an empty page list would report a reading of zero characters.
            page_unsupported.append(name)
            pages[name] = []
            texts[name] = text_many(name, [pdf_path])[0]
            continue
        pages[name] = got[0]
        # ONE extraction per reader: the text is the pages joined, so an example's page and the metrics
        # cannot come from two different readings. `test_pages.py` proves the join equals `text()` under N.
        texts[name] = "\n".join(pages[name])
    scan = mcid_text.scan(pdf_path)
    file_text = "\n".join(scan["text"].values())

    # ---- file-level signals -------------------------------------------------------------------
    th = thresholds["values"]
    file_signals, font_rows = _font_signals(scan, th["tounicode_gap_ratio"]["value"])
    file_arabic = arabic_count(file_text)
    forms = pf_count(file_text)
    # The share is computed by the same function the measurement derives the threshold with.
    if pf_share(file_text) > th["presentation_forms"]["value"]:
        file_signals.append(_finding(
            "presentation-forms", "high", "file", "high",
            f"{forms} presentation-form character(s) in the text layer of {file_arabic + forms} Arabic "
            f"character(s) — a reader that trusts the CMap shows a glyph name, not a letter",
            forms=forms, arabic=file_arabic + forms, threshold=th["presentation_forms"]["value"]))
    persian = structure.persian_digits(file_text)
    if persian:
        file_signals.append(_finding(
            "numerals-persian", "high", "file", "high",
            f"{len(persian)} Persian digit(s) (U+06F0–U+06F9) in the layer — an Arabic file uses ٠-٩ or 0-9",
            digits=len(persian)))
    mixed = structure.mixed_numbers(file_text)
    if mixed:
        file_signals.append(_finding(
            "numerals-mixed", "medium", "file", "high",
            f"{len(mixed)} number(s) mix digit systems: " + ", ".join(mixed[:4]), numbers=mixed[:4]))

    all_empty = not any(metrics.N(t) for t in texts.values())
    if all_empty:
        file_signals.append(_finding("no-text-layer", "high", "file", "high",
                                     "every reader returned no text — the file has no copyable layer "
                                     "(a scan is the usual cause; OCR is out of scope)"))
    elif file_arabic + forms < th["min_arabic_chars"]["value"]:
        # The threshold is the DECLARED one, read from the manifest: below it a report about Arabic copy is
        # not about this file. Presentation forms count as Arabic here — a layer of only forms is still Arabic
        # and has its own signal; counting it as "no text" would double-report one defect.
        file_signals.append(_finding(
            "no-text-layer", "low", "file", "medium",
            f"the layer carries {file_arabic + forms} Arabic character(s) of {len(metrics.N(file_text))} "
            f"— below the declared {th['min_arabic_chars']['value']}; is this an Arabic document?",
            arabic=file_arabic + forms, threshold=th["min_arabic_chars"]["value"]))

    # ---- per-reader signals --------------------------------------------------------------------
    orders = visual_orders(texts, th)
    visual_readers = [n for n, o in orders.items() if o["visual"]]
    # The denominator is the DECLARED matrix, not the readers that happened to run: a machine without PDFKit
    # must not give the same file a different file-level verdict. The majority is half the matrix, plus one.
    need = majority_needed()
    visual_cause = "file" if len(visual_readers) >= need else "reader"
    if visual_cause == "file":
        conf = min(("high" if (o["confidence"] or 0) >= 0.9 else
                    "medium" if (o["confidence"] or 0) >= 0.6 else "low")
                   for o in (orders[n] for n in visual_readers))
        file_signals.append(_finding(
            "visual-order", "high", "file", conf,
            f"{len(visual_readers)} of {len(MATRIX)} declared readers return reversed text — the copied text "
            f"keeps the opposite order for those readers (the layer itself is not judged as a defect; a visual "
            f"layer is how most producers store Arabic)", readers=visual_readers,
            scores={n: orders[n]["score"] for n in visual_readers}))
    # Reader disagreement: ONLY the deterministic form ships. The metric form (`content_f1` between
    # readers) was measured on the clean set and REFUSED: single-word and digit-only corpus cases reach 0.0
    # between clean readers (docs/checker-v0/measurements/clean.json), so no threshold above zero separates
    # a clean file from a broken one. What remains is a fact with no threshold: a page this reader returns
    # empty while two or more readers read it.
    reader_signals, examples = {}, {}
    gaps_by_reader = empty_pages_for(pages, list(ok))
    for name, text in texts.items():
        signals = []
        order = orders[name]
        if order["visual"]:
            confidence = "high" if (order["confidence"] or 0) >= 0.9 else \
                         ("medium" if (order["confidence"] or 0) >= 0.6 else "low")
            signals.append(_finding(
                "visual-order", "high", visual_cause, confidence,
                f"returns {'reversed' if (order['score'] or 0) > 0 else 'logical'} text "
                f"(score {order['score']:+.2f}; +1 reversed, −1 logical) — "
                f"{len(visual_readers)} of {len(MATRIX)} declared readers return reversed text",
                score=order["score"], votes=order["evidence"]))
        arabic = arabic_count(text)
        forms_r = pf_count(text)
        if pf_share(text) > th["presentation_forms"]["value"]:
            # The cause is the FILE only when the file-level signal fired — the same name, not an inference
            # from a count. A reader whose count is high while the file's is below the threshold is the one
            # that turned the letters into forms.
            signals.append(_finding(
                "presentation-forms", "high",
                "file" if any(s["id"] == "presentation-forms" for s in file_signals) else "reader", "high",
                f"{forms_r} presentation-form character(s) in this reader's text of {arabic + forms_r} Arabic "
                f"character(s)", forms=forms_r, arabic=arabic + forms_r))
        # a page this reader returns empty while two others read it — deterministic, no threshold
        empty_pages = gaps_by_reader[name]
        if empty_pages:
            signals.append(_finding(
                "reader-disagreement", "high", "reader", "high",
                f"no Arabic text on page(s) {empty_pages[:5]} while two or more readers read them",
                pages=empty_pages[:5]))

        predicate = (lambda ln: pf_count(ln) > 0) if any(s["id"] == "presentation-forms" for s in signals) \
            else (lambda ln: bool(ARABIC.search(ln)))
        examples[name] = _examples(text, pages[name], predicate=predicate) if signals else []
        reader_signals[name] = signals

    # ---- risk, both claims ---------------------------------------------------------------------
    file_level = _top(file_signals)
    reader_levels = {n: _top(s) for n, s in reader_signals.items()}
    total = max([file_level] + list(reader_levels.values()), key=lambda lv: LEVELS[lv])
    all_signals = file_signals + [s for n in reader_signals for s in reader_signals[n]]
    at_top = [s for s in all_signals if s["level"] == total]
    causes = sorted({s["cause"] for s in at_top})

    # ---- the declared reader facts (limits + behaviours), each with its live control -------------
    known_limits = []
    for name, mod in ok.items():
        version = mod.version()
        limits, refused, _controls = limitations.usable(name, version)
        for lim in limits:
            known_limits.append({"id": lim["id"], "reader": name, "kind": "limit",
                                 "version": version, "measured_on": lim["reader_version_measured"],
                                 "statement": lim["claim"], "applies": True})
        for why in refused:
            known_limits.append({"id": why.split(":")[0], "reader": name, "kind": "limit-refused",
                                 "version": version, "measured_on": version,
                                 "statement": why, "applies": False})
        held, refused_d, _ = declared.usable(name, version)
        for entry in held:
            note = (f" (declared on {entry['reader_version_measured']}, live {entry['reader_version_now']})"
                    if entry["version_mismatch"] else "")
            known_limits.append({"id": entry["id"], "reader": name, "kind": "behaviour",
                                 "version": entry["reader_version_now"],
                                 "measured_on": entry["reader_version_measured"],
                                 "statement": entry["claim"] + note,
                                 "applies": True})
        for why in refused_d:
            known_limits.append({"id": why.split(":")[0], "reader": name, "kind": "behaviour-refused",
                                 "version": version, "measured_on": version,
                                 "statement": why, "applies": False})

    try:
        commit, dirty = cert_mod.pipeline_commit()
    except cert_mod.CertError:
        # The tool can run from a copy without a git checkout; the report then says so instead of failing a
        # customer's file because our provenance is unavailable.
        commit, dirty = "unknown", None
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "thresholds.json"), "rb") as fh:
        thresholds_sha = hashlib.sha256(fh.read()).hexdigest()
    return {
        "schema_version": "arabic-pdf-check/1",
        "mode": "blind",
        "file": {"sha256": _sha256(pdf_path), "bytes": os.path.getsize(pdf_path),
                 "pages": reference.page_count(pdf_path)},
        "tool": {"version": _tool_version(), "commit": commit, "dirty": dirty,
                 "arafix": visual_order.VERSION, "thresholds_sha256": thresholds_sha},
        "readers": {name: {"version": ok[name].version(), "chars": len(metrics.N(texts[name])),
                           "empty": not metrics.N(texts[name]),
                           "pages": "unsupported" if name in page_unsupported else "per-page",
                           "risk": reader_levels[name],
                           "confidence": _confidence(reader_signals[name]),
                           "signals": reader_signals[name],
                           "examples": examples[name]}
                    for name in ok},
        "missing_readers": {n: why_class(w) for n, w in missing.items()},
        "fonts": font_rows,
        "signals": file_signals,
        "risk": {"level": total, "confidence": _confidence(at_top), "causes": causes,
                 "file": {"level": file_level, "confidence": _confidence(file_signals)},
                 "readers": reader_levels},
        "known_limits": known_limits,
        "not_judged": [
            "هذا ليس حكم PDF/UA ولا PDF/A، وليس شهادة مطابقة من أي نوع",
            "لا يُحكم على رسم الحروف: التقرير يقرأ طبقة النص لا الشكل المرئي",
            "لا OCR: الملف بلا طبقة نصية يُبلَّغ عنه كما هو، ولا يُصلَح",
            "سلوك قارئ معلن يفسّر خطر ذلك القارئ، ولا يرفع حكم الملف",
            "خط بسيط بلا /ToUnicode يُعلَن ولا يُنذر (Matterhorn 31-027)؛ خريطته عبر /Encoding أو أسماء "
            "المحارف لا تُتحقَّق هنا — قيد معلن، لا حكم",
        ],
    }


def _tool_version() -> str:
    from . import __version__ as v
    return v


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()
