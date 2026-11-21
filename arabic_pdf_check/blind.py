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
from conformance.readers import available, declared, limitations, pages_many

LEVELS = {"low": 0, "medium": 1, "high": 2}
CONFIDENCE = {"low": 0, "medium": 1, "high": 2}
_PF = metrics.PRESENTATION_FORM
ARABIC = structure.ARABIC


def _is_pf(ch: str) -> bool:
    cp = ord(ch)
    return _PF[0] <= cp <= _PF[1] or _PF[2] <= cp <= _PF[3]


def pf_count(text: str) -> int:
    return sum(1 for ch in (text or "") if _is_pf(ch))


def arabic_count(text: str) -> int:
    return len(ARABIC.findall(text or ""))


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
    """Up to `limit` bounded lines; a page number is measured by finding the line in that reader's page."""
    out = []
    for line in (text or "").splitlines():
        line = (line or "").strip()
        if not line or len(line) > 80:
            continue
        if predicate and not predicate(line):
            continue
        page = next((i + 1 for i, p in enumerate(pages) if line in (p or "")), None)
        out.append({"page": page, "text": line[:80]})
        if len(out) >= limit:
            break
    return out


def _font_signals(scan: dict, gap_high: float = 0.01) -> tuple[list[dict], list[dict]]:
    """(file signals, font rows for the report). One signal per font, with its own numbers.

    The gap is graded by its SHARE of the codes the font draws: a 4-in-1536 gap is a real defect for those
    four characters and a different claim from an empty map. `gap_high` is derived in
    `docs/checker-v0/measurements/thresholds.json` (clean maximum 0, declared floor 1%).
    """
    signals, rows = [], []
    for key, row in sorted(scan["fonts"].items()):
        name = row["family"] or row["name"]
        note = None
        problems = []
        warnings = []
        if row["notdef"]:
            problems.append(f"{row['notdef']} .notdef glyph(s) drawn")
        if not row["tounicode"]:
            if row["two_byte"]:
                problems.append("composite font drawn with no /ToUnicode")
            else:
                note = ("simple font without /ToUnicode — allowed by Matterhorn 31-027 when the encoding or "
                        "the glyph names carry the mapping; declared, not alarmed")
        # A simple font without /ToUnicode has no map BY CONSTRUCTION: counting its codes as gaps would
        # report the Matterhorn exception as a defect on every Word/PowerPoint file. Gaps are only gaps
        # when a map exists and misses codes the file draws.
        ratio = (row["missing_unicode"] / row["codes"]) if row["codes"] else 0.0
        if row["missing_unicode"] and row["tounicode"]:
            text = (f"{row['missing_unicode']} of {row['codes']} drawn codes have no Unicode value "
                    f"({ratio:.1%})")
            (problems if ratio > gap_high else warnings).append(text)
        if row["pua"]:
            problems.append(f"{row['pua']} mapped character(s) in the private use area")
        if row["replacement"]:
            problems.append(f"{row['replacement']} mapped character(s) to U+FFFD")
        if row["zero_value"]:
            problems.append(f"{row['zero_value']} mapped character(s) to U+0000 (Matterhorn 31-028)")
        if row["bom"]:
            problems.append(f"{row['bom']} mapped character(s) to U+FEFF/U+FFFE (Matterhorn 31-029)")
        rows.append({"font": key, "family": row["family"], "subtype": row["subtype"],
                     "embedded": row["embedded"], "tounicode": row["tounicode"],
                     "two_byte": row["two_byte"], "codes": row["codes"],
                     "missing_unicode": row["missing_unicode"], "notdef": row["notdef"],
                     "pua": row["pua"], "replacement": row["replacement"],
                     "zero_value": row["zero_value"], "bom": row["bom"], "note": note})
        if problems:
            signals.append(_finding("tounicode-gaps", "high", "file", "high",
                                    f"{name} ({row['subtype']}): " + "; ".join(problems),
                                    font=key, codes=row["codes"], missing_unicode=row["missing_unicode"],
                                    notdef=row["notdef"], pua=row["pua"], replacement=row["replacement"],
                                    zero_value=row["zero_value"], bom=row["bom"]))
        elif warnings:
            signals.append(_finding("tounicode-gaps", "medium", "file", "high",
                                    f"{name} ({row['subtype']}): " + "; ".join(warnings),
                                    font=key, codes=row["codes"], missing_unicode=row["missing_unicode"],
                                    threshold=gap_high))
    return signals, rows


def check(pdf_path: str, thresholds: dict, reader_names=None) -> dict:
    ok, missing = available()
    if reader_names:
        ok = {k: v for k, v in ok.items() if k in reader_names}
    if not ok:
        raise RuntimeError("no reader is available — a report with no reader is not a report")

    texts, pages = {}, {}
    for name in ok:
        got = pages_many(name, [pdf_path])
        pages[name] = got[0] if got else []
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
    # The share of presentation forms is taken over the Arabic characters that COULD be written as base
    # letters: a layer of only presentation forms gives ~1.0, not 40/4.
    if file_arabic + forms and forms / (file_arabic + forms) > th["presentation_forms"]["value"]:
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
    elif file_arabic == 0:
        file_signals.append(_finding("no-text-layer", "low", "file", "medium",
                                     "the layer carries text but no Arabic letters — is this an Arabic document?"))

    # ---- per-reader signals --------------------------------------------------------------------
    orders = {name: visual_order.inspect(text) for name, text in texts.items()}
    visual_readers = [n for n, o in orders.items() if o["visual"]]
    visual_cause = ("file" if len(visual_readers) > len(ok) * th["visual_order_majority"]["value"]
                    else "reader")
    # Majority rule (the review's N2): when most readers return the opposite orientation, the finding is
    # about the FILE — the reader is not the odd one out. When one reader deviates, the finding is about
    # that reader and the file keeps its own grade.
    if visual_cause == "file":
        conf = min(("high" if (o["confidence"] or 0) >= 0.9 else
                    "medium" if (o["confidence"] or 0) >= 0.6 else "low")
                   for o in (orders[n] for n in visual_readers))
        file_signals.append(_finding(
            "visual-order", "high", "file", conf,
            f"{len(visual_readers)} of {len(ok)} readers return reversed text — the file stores the opposite "
            f"order of what most Arabic readers expect to paste", readers=visual_readers,
            scores={n: orders[n]["score"] for n in visual_readers}))
    # Reader disagreement: ONLY the deterministic form ships. The metric form (`content_f1` between
    # readers) was measured on the clean set and REFUSED: single-word and digit-only corpus cases reach 0.0
    # between clean readers (docs/checker-v0/measurements/clean.json), so no threshold above zero separates
    # a clean file from a broken one. What remains is a fact with no threshold: a page this reader returns
    # empty while two or more readers read it.
    reader_signals, examples = {}, {}
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
                f"{len(visual_readers)} of {len(ok)} readers return reversed text",
                score=order["score"], votes=order["evidence"]))
        arabic = arabic_count(text)
        forms_r = pf_count(text)
        if arabic + forms_r and forms_r / (arabic + forms_r) > th["presentation_forms"]["value"]:
            signals.append(_finding(
                "presentation-forms", "high", "file" if forms else "reader", "high",
                f"{forms_r} presentation-form character(s) in this reader's text of {arabic + forms_r} Arabic "
                f"character(s)", forms=forms_r, arabic=arabic + forms_r))
        # a page this reader returns empty while two others read it — deterministic, no threshold
        empty_pages = []
        for i, page in enumerate(pages[name]):
            if ARABIC.search(page or ""):
                continue
            readers_with_text = sum(1 for other in ok if other != name and i < len(pages[other])
                                    and ARABIC.search(pages[other][i] or ""))
            if readers_with_text >= 2:
                empty_pages.append(i + 1)
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
                                 "version": lim["reader_version_measured"], "statement": lim["claim"],
                                 "applies": True})
        for why in refused:
            known_limits.append({"id": why.split(":")[0], "reader": name, "kind": "limit-refused",
                                 "version": version, "statement": why, "applies": False})
        held, refused_d, _ = declared.usable(name, version)
        for entry in held:
            known_limits.append({"id": entry["id"], "reader": name, "kind": "behaviour",
                                 "version": entry["reader_version_measured"],
                                 "statement": entry["claim"], "applies": True})
        for why in refused_d:
            known_limits.append({"id": why.split(":")[0], "reader": name, "kind": "behaviour-refused",
                                 "version": version, "statement": why, "applies": False})

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
                           "risk": reader_levels[name],
                           "confidence": _confidence(reader_signals[name]),
                           "signals": reader_signals[name],
                           "examples": examples[name]}
                    for name in ok},
        "missing_readers": missing,
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
        ],
    }


def _tool_version() -> str:
    from . import __version__ as v
    return v


def _sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()
