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
import os
import re

from conformance import certificate as cert_mod
from conformance import reference
from conformance.checks import lexical, mcid_text, metrics, structure, visual_order
from conformance.checks import segment_order
from conformance.checks.metrics import arabic_count, pf_count, pf_share
from conformance.hashing import sha256_file
from conformance.readers import MATRIX, available, declared, isolate, limitations

LEVELS = {"low": 0, "medium": 1, "high": 2}
CONFIDENCE = {"low": 0, "medium": 1, "high": 2}
ARABIC = metrics.ARABIC


class Refused(RuntimeError):
    """A file the checker will not judge: encrypted, empty, or not a readable PDF."""


def _preflight(pdf_path: str) -> None:
    """Classify a refusal BEFORE a reader touches the file.

    `pikepdf` is the one parser: an owner-password-only PDF opens without a password and is readable, so it
    is not refused; a user-password PDF raises `PasswordError`, and a corrupt/zero-page file is named. A
    traceback from a C reader is not a refusal — it is a tool failure, and it is reported as one line.
    """
    import pikepdf
    try:
        with pikepdf.open(pdf_path) as pdf:
            if len(pdf.pages) == 0:
                raise Refused("no pages")
    except Refused:
        raise
    except pikepdf.PasswordError:
        raise Refused("encrypted (password required)") from None
    except Exception:
        raise Refused("unreadable PDF") from None


def majority_needed(voters: int) -> int | None:
    """A majority of the readers that actually vote — `None` when fewer than two can.

    The assignment's item 1 (`len(lexical_passing) >= need`) and item 5 («الأغلبية تُحسب على القرّاء الذين
    قرؤوا») replace the earlier declared-matrix rule: the two-reader test (both failing ⇒ high) cannot be met
    by a fixed 3 of 5. A majority of one is not a majority, so one voter withholds a file-level claim.
    """
    return voters // 2 + 1 if voters >= 2 else None


def recovery_state(judged: dict, lexical_th: float) -> tuple[bool | None, str, int | None, list[str], list[str]]:
    """(recovered, label, need, passing, failing) — the assignment's item 1, with a split as `None`.

    `True` only when a majority of the judgeable readers passes; `False` only when a majority fails; a split
    (or fewer than two voters) is `None`, and `None` never lowers the ToUnicode gap. This is the function the
    two-reader test drives directly; `check` has no second copy of the rule.
    """
    passing = sorted(name for name, v in judged.items() if v["ratio"] >= lexical_th)
    failing = sorted(name for name, v in judged.items() if v["ratio"] < lexical_th)
    need = majority_needed(len(judged))
    if need is None:
        return None, "no-voters", need, passing, failing
    if len(passing) >= need:
        return True, "recovered", need, passing, failing
    if len(failing) >= need:
        return False, "failed", need, passing, failing
    return None, "split", need, passing, failing


def lam_alef_majority(judged: dict, rate: float, min_runs: int) -> tuple[dict[str, float], dict[str, float], int | None]:
    """(all rates, the readers at or above `rate`, the majority needed) — the rule, one copy.

    Everything is returned because the report needs all three: «N of M judged readers» is a different claim
    from «N of N», and a reader's own rate decides whether its single transposition is a near-miss or the
    finding itself. Only a reading with at least `min_runs` Arabic runs is judged. `check` and
    `test_lam_alef_signal` call this function; a second copy of the arithmetic would let the test certify a
    rule the report does not run.
    """
    rates = {n: v["lam_alef"] / v["runs"] * 1000.0 for n, v in judged.items() if v["runs"] >= min_runs}
    over = {n: r for n, r in rates.items() if r >= rate}
    return rates, over, majority_needed(len(rates))


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
    reader of the report needs, and skipping it can leave a signal with no example at all. The page is found
    with the RAW line (the page text carries whatever the reader returned), and the excerpt is the sanitized
    one: no control character, no bidi override, no reverse-line mark.
    """
    out = []
    for line in (text or "").splitlines():
        raw = (line or "").strip()
        if not raw:
            continue
        if predicate and not predicate(raw):
            continue
        page = next((i + 1 for i, p in enumerate(pages) if raw in (p or "")), None)
        shown = reference.sanitize_line(raw)[:80]
        if not shown:
            continue
        out.append({"page": page, "text": shown})
        if len(out) >= limit:
            break
    return out


def _font_signals(scan: dict, gap_high: float = 0.01,
                  recovered: bool | None = None,
                  recovered_by_font: dict[str, bool] | None = None) -> tuple[list[dict], list[dict]]:
    """(file signals, font rows for the report) — the RULE lives in `conformance.checks.structure.font_verdicts`.

    This function only shapes the verdicts into the report: the same per-font decision the certificate's
    `tounicode-coverage` check uses, with the measured share as its threshold. A second copy here would let
    the report and the certificate disagree about one font.
    """
    signals, rows = [], []
    # A diagnosis, not a certificate: a gap between words (a bullet, a tab) is a warning, and a gap inside a
    # word is the finding. The certificate gate calls the same rule with `inside_words_only=False`.
    for v in structure.font_verdicts(scan, gap_high, inside_words_only=True, recovered=recovered,
                                     recovered_by_font=recovered_by_font):
        rows.append({"font": v["key"], "family": v["family"], "subtype": v["subtype"],
                     "embedded": v["embedded"], "tounicode": v["tounicode"],
                     "two_byte": v["two_byte"], "codes": v["codes"],
                     "encoding": v["encoding"], "missing_in_word": v["missing_in_word"],
                     "missing_examples": v["missing_examples"], "symbol": v["symbol"],
                     "missing_unicode": v["missing_unicode"], "notdef": v["notdef"],
                     "pua": v["pua"], "replacement": v["replacement"],
                     "zero_value": v["zero_value"], "bom": v["bom"], "note": v["note"],
                     "unparsable": bool(v.get("unparsable")), "capped": int(v.get("capped") or 0),
                     "width_mismatch": bool(v.get("width_mismatch")), "status": v.get("status")})
        if v["level"]:
            signals.append(_finding(
                "tounicode-unparsable" if (v.get("status") in ("unparsable", "capped")
                                           or v.get("unparsable") or v.get("capped"))
                else "tounicode-gaps",
                v["level"], "file", "high",
                f"{v['name']} ({v['subtype']}): " + "; ".join(v["problems"] or v["warnings"]),
                font=v["key"], codes=v["codes"], missing_unicode=v["missing_unicode"],
                notdef=v["notdef"], pua=v["pua"], replacement=v["replacement"],
                zero_value=v["zero_value"], bom=v["bom"], threshold=gap_high))
    return signals, rows


def why_class(why) -> str:
    """The failure CLASS only, never the exception text: an ImportError message can carry a local path, and
    this string goes into a customer's report and certificate."""
    if isinstance(why, BaseException):
        return type(why).__name__
    return (str(why).split(":")[0].strip() or "unavailable")[:60]


_PATH = re.compile(r"(?:[A-Za-z]:)?(?:/[^\s:;]+){2,}")


def why_reason(why) -> str:
    """A one-line reason with absolute paths replaced by `<path>`; the class and the reason are two fields.

    The class alone answers "did it hang or crash?" with nothing — the assignment asks for `reader-failed`
    «مع السبب بسطر». The reason is sanitized with the same excerpt rule as the report and never carries a
    local path, so a customer's report can name a timeout without leaking the home directory.
    """
    raw = reference.sanitize_line(str(why) if why is not None else "")
    return " ".join(_PATH.sub("<path>", raw).split())[:160]


def check(pdf_path: str, thresholds: dict, lexicon_path: str = lexical.SHIPPED_DATA) -> dict:
    _preflight(pdf_path)
    ok, missing = available()
    if not ok:
        raise RuntimeError("no reader is available — a report with no reader is not a report")

    texts, pages, page_unsupported, failed = {}, {}, [], {}
    for name in list(ok):
        try:
            got_pages, text = isolate.read(name, pdf_path)
            if got_pages is None:
                # A reader that cannot name its pages still has text; its examples carry `page: null`, and
                # the report names it. Folding this to an empty page list would report zero characters.
                page_unsupported.append(name)
                pages[name] = []
                texts[name] = text
            else:
                pages[name] = got_pages
                # ONE extraction per reader: the text is the pages joined, so an example's page and the
                # metrics cannot come from two readings. `test_pages.py` proves the join equals `text()`.
                texts[name] = "\n".join(got_pages)
        except Exception as exc:
            # A crash, an abort or a timeout inside a reader is a fact about this file's parser-hostility.
            # It must not take the report down, and it must not disappear: the file is not clean. The reason
            # is kept beside the class (sanitized) so "timed out after 120s" is not flattened to "ReaderFailed".
            reason = why_reason(exc)
            failed[name] = f"{why_class(exc)}: {reason}" if reason else why_class(exc)
            del ok[name]
    if not ok:
        raise RuntimeError("every reader failed on this file — a report with no reading is not a report")
    scan = mcid_text.scan(pdf_path)
    file_text = "\n".join(scan["text"].values())

    # ---- file-level signals -------------------------------------------------------------------
    th = thresholds["values"]
    lexical_th = th["lexical_validity"]["value"]
    lexical_min_runs = th["lexical_min_runs"]["value"]
    lexicon = lexical.lexicon(lexicon_path)
    seg_findings = segment_order.findings({n: texts[n] for n in ok}, lexicon, pages)
    lex = {name: lexical.validity(text, lexicon) for name, text in texts.items()}
    # A short reading is not judged: 20 runs is the declared floor, below it a report about words is not
    # about this file. The map-recovery question is answered only by the readers that can judge words.
    judged = {name: v for name, v in lex.items() if v["runs"] >= lexical_min_runs}
    recovered, recovery, need_lex, lexical_passing, lexical_failing = recovery_state(judged, lexical_th)
    text_fonts = [k for k, row in scan["fonts"].items() if row.get("codes")]
    recovered_by_font = ({text_fonts[0]: recovered}
                         if len(text_fonts) == 1 and recovered is not None else None)
    file_signals, font_rows = _font_signals(scan, th["tounicode_gap_ratio"]["value"],
                                            recovered=recovered, recovered_by_font=recovered_by_font)
    # A reader that crashed or timed out is a fact about this file's parser-hostility: the file is not clean.
    # The signal is medium, and the majority is computed after the reader is dropped (and says so).
    for name, why in sorted(failed.items()):
        file_signals.append(_finding(
            "reader-failure", "medium", "file", "high",
            f"{name} failed on this file ({why}); the majority was computed after dropping it",
            reader=name, reason=why))
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
    need_visual = majority_needed(len(ok))
    visual_cause = "file" if need_visual is not None and len(visual_readers) >= need_visual else "reader"
    if visual_cause == "file":
        conf = min(("high" if (o["confidence"] or 0) >= 0.9 else
                    "medium" if (o["confidence"] or 0) >= 0.6 else "low")
                   for o in (orders[n] for n in visual_readers))
        file_signals.append(_finding(
            "visual-order", "high", "file", conf,
            f"{len(visual_readers)} of {len(ok)} readers that read return reversed text — the copied text "
            f"keeps the opposite order for those readers (the layer itself is not judged as a defect; a visual "
            f"layer is how most producers store Arabic)", readers=visual_readers,
            scores={n: orders[n]["score"] for n in visual_readers}))
    # Lexical validity: the words themselves. A majority of the readers that can judge words is a file
    # finding; one failing reader is that reader's risk and never the file's.
    lexical_file_high = need_lex is not None and len(lexical_failing) >= need_lex
    if lexical_file_high:
        shown = ", ".join(f"{n} {judged[n]['known']} of {judged[n]['runs']}" for n in lexical_failing[:5])
        file_signals.append(_finding(
            "lexical-validity", "high", "file", "high",
            f"{len(lexical_failing)} of {len(judged)} judged readers return Arabic runs that are not Arabic "
            f"words ({shown} runs are in the lexicon) — the letters are shaped, the words do not exist",
            readers=lexical_failing,
            counts={n: {"runs": judged[n]["runs"], "known": judged[n]["known"]} for n in lexical_failing},
            threshold=lexical_th, min_runs=lexical_min_runs))
    # Lam-alef: a doubled alef is orthographically impossible («اال»), so the measure is a DENSITY, not a
    # count — the clean population's only hit is `report.pdf` quoting the defect itself («األتمتة», 1 of 1140
    # runs = 0.88/1000), while the calibration lesson measures 43.0–43.7/1000 in three readers. The shipped
    # value is the geometric midpoint of those two measured bounds (measurements/lam-alef-separation.json), and
    # the rate is judged only on a reading with enough runs for a rate to mean anything.
    lam_rates, lam_over, need_lam = lam_alef_majority(judged, th["lam_alef_rate_per_1000"]["value"],
                                                      th["lam_alef_min_runs"]["value"])
    if need_lam is not None and len(lam_over) >= need_lam:
        file_signals.append(_finding(
            "lam-alef-transposition", "medium", "file", "high",
            f"{len(lam_over)} of {len(lam_rates)} judged readers carry a lam-alef transposition density at or "
            f"above {th['lam_alef_rate_per_1000']['value']} per 1000 Arabic runs ("
            + ", ".join(f"{n} {r:.1f}" for n, r in sorted(lam_over.items()))
            + ") — a doubled alef is orthographically impossible: the words are shaped and the letters are "
              "transposed",
            readers=sorted(lam_over), rates={n: round(r, 2) for n, r in sorted(lam_over.items())},
            judged=len(lam_rates),
            counts={n: judged[n]["lam_alef"] for n in lam_over},
            runs={n: judged[n]["runs"] for n in lam_over},
            threshold=th["lam_alef_rate_per_1000"]["value"],
            min_runs=th["lam_alef_min_runs"]["value"]))
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
        seg = seg_findings.get(name) or []
        if len(seg) >= th["segment_order_min"]["value"]:
            sample = seg[0]
            # `display` is the reader's words with presentation forms folded to base letters and marks stripped
            # — the report says «كما يعرضها القارئ», because it is not a byte-for-byte quote: a reader that
            # returned U+FExx or a tashkeel is shown in its letters, not its codepoints.
            shown = reference.sanitize_line(" ".join(sample["display"]))[:80]
            signals.append(_finding(
                "segment-order", "medium", "reader", "high",
                f"{len(seg)} line(s) whose Arabic segment is the exact reverse of the order {sample['agree']} of "
                f"{sample['voters']} voting readers agree on — the letters are logical and the words are not "
                f"(كما يعرضها القارئ، بأشكال العرض مطويّة إلى حروفه): «{shown}»",
                lines=len(seg), voters=sample["voters"], agree=sample["agree"], page=sample["page"],
                example={"words": sample["words"][:6], "display": sample["display"][:6],
                         "reversed_of": sample["reversed_of"][:6]},
                threshold=th["segment_order_min"]["value"]))
        if name in judged and judged[name]["ratio"] < lexical_th:
            signals.append(_finding(
                "lexical-validity", "high", "file" if lexical_file_high else "reader", "high",
                f"{judged[name]['known']} of {judged[name]['runs']} Arabic run(s) in this reader's text are in "
                f"the lexicon — the remaining runs are shaped letters that do not make Arabic words",
                runs=judged[name]["runs"], known=judged[name]["known"],
                reversed_known=judged[name]["reversed"], threshold=lexical_th))
        elif name in judged and judged[name].get("lam_alef") and name in lam_rates \
                and lam_rates[name] < th["lam_alef_rate_per_1000"]["value"]:
            # A near-miss is a reader whose OWN rate is BELOW the file-level density: the reading passes the
            # floor and carries one or two transpositions (a document quoting the defect). A reader at or above
            # the density is the file finding itself and must not be described as «below the threshold».
            signals.append(_finding(
                "lam-alef-transposition", "low", "reader", "medium",
                f"{judged[name]['lam_alef']} lam-alef transposition(s) (e.g. «األهداف» for «الأهداف») — "
                f"{lam_rates[name]:.1f} per 1000 runs, below the file-level {th['lam_alef_rate_per_1000']['value']}"
                f"; recorded, not raised",
                runs=judged[name]["runs"], known=judged[name]["known"],
                lam_alef=judged[name]["lam_alef"], rate=round(lam_rates[name], 2),
                threshold=th["lam_alef_rate_per_1000"]["value"]))
        if order["visual"]:
            confidence = "high" if (order["confidence"] or 0) >= 0.9 else \
                         ("medium" if (order["confidence"] or 0) >= 0.6 else "low")
            signals.append(_finding(
                "visual-order", "high", visual_cause, confidence,
                f"returns {'reversed' if (order['score'] or 0) > 0 else 'logical'} text "
                f"(score {order['score']:+.2f}; +1 reversed, −1 logical) — "
                f"{len(visual_readers)} of {len(ok)} readers that read return reversed text",
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
        limits, refused, _controls = limitations.usable(name, version, mode="cached")
        for lim in limits:
            known_limits.append({"id": lim["id"], "reader": name, "kind": "limit",
                                 "version": version, "measured_on": lim["reader_version_measured"],
                                 "statement": lim["claim"], "applies": True})
        for why in refused:
            known_limits.append({"id": why.split(":")[0], "reader": name, "kind": "limit-refused",
                                 "version": version, "measured_on": version,
                                 "statement": why, "applies": False})
        held, refused_d, _ = declared.usable(name, version, mode="cached")
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
    thresholds_sha = sha256_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "thresholds.json"))
    return {
        "schema_version": "arabic-pdf-check/1",
        "mode": "blind",
        "file": {"sha256": _sha256(pdf_path), "bytes": os.path.getsize(pdf_path),
                 "pages": reference.page_count(pdf_path)},
        "tool": {"version": _tool_version(), "commit": commit, "dirty": dirty,
                 "arafix": visual_order.VERSION, "thresholds_sha256": thresholds_sha,
                 "lexicon": {"file": os.path.basename(lexicon_path),
                             "sha256": sha256_file(lexicon_path)}},
        "readers": {name: {"version": ok[name].version(), "chars": len(metrics.N(texts[name])),
                           "empty": not metrics.N(texts[name]),
                           "pages": "unsupported" if name in page_unsupported else "per-page",
                           "risk": reader_levels[name],
                           "confidence": _confidence(reader_signals[name]),
                           "signals": reader_signals[name],
                           "examples": examples[name]}
                    for name in ok},
        "missing_readers": {n: why_class(w) for n, w in missing.items()},
        "failed_readers": dict(sorted(failed.items())),
        "majority": {
            "declared": len(MATRIX),
            "readers": {"read": len(ok), "needed": need_visual},
            "lexical": {"read": len(judged), "needed": need_lex},
            "recovery": recovery,
        },
        "fonts": font_rows,
        "signals": file_signals,
        "risk": {"level": total, "confidence": _confidence(at_top), "causes": causes,
                 "file": {"level": file_level, "confidence": _confidence(file_signals)},
                 "readers": reader_levels},
        "known_limits": known_limits,
        "not_judged": [s for s in [
            "هذا ليس حكم PDF/UA ولا PDF/A، وليس شهادة مطابقة من أي نوع",
            "لا يُحكم على رسم الحروف: التقرير يقرأ طبقة النص لا الشكل المرئي",
            "لا OCR: الملف بلا طبقة نصية يُبلَّغ عنه كما هو، ولا يُصلَح",
            "سلوك قارئ معلن يفسّر خطر ذلك القارئ، ولا يرفع حكم الملف",
            "خط بسيط بلا /ToUnicode يُعلَن ولا يُنذر (Matterhorn 31-027)؛ خريطته عبر /Encoding أو أسماء "
            "المحارف لا تُتحقَّق هنا — قيد معلن، لا حكم",
            "صحة الكلمات تُحكم على 20 تشكيلة عربية على الأقل في نص القارئ؛ ما دونها لا يُحكم عليه (لا يُعدّ "
            "مرورًا ولا فشلًا)",
            (f"كثافة انقلاب لام-ألف (لكل 1000 تشكيلة) تُحكم على قراءة تحمل {th['lam_alef_min_runs']['value']} "
             f"تشكيلة على الأقل وبأغلبية القرّاء؛ الانقلاب المفرد (مستند يقتبس العيب) يُسجَّل ولا يُرفع"),
            "ترتيب المقاطع يُحكم بأغلبية القرّاء: ملف يخزّن الترتيب البصري حقّ لا عيب، وقارئ يعيد ترتيب الكلمات "
            "عكس الأغلبية هو الإشارة؛ فإن عكس القرّاء كلهم الترتيب نفسه فلا ناخب يخالف ولا ترفع الإشارة (حدّ معلن)",
            "الكلمة الموصولة بجاراتها في نصّ القارئ تُعدّ تشكيلة واحدة (لا تُجزَّأ بالمعجم)؛ نصّ كثير الوصل قد "
            "يخفض النسبة — لذلك العتبة مشتقة بهامش 0.20 ولا يرفع الحكم إلا فشل الأغلبية",
            f"الأغلبية تُحسب على القرّاء الذين قرؤوا: {len(ok)} من {len(MATRIX)} للاتجاه، و{len(judged)} "
            f"للكلمات — تغيير معلن عن قاعدة المقام المعلن 3 من 5 (ST-5)؛ الجدول المنشور يقيس قلب الأحكام",
            (f"قارئ واحد بلغ حدّ الحكم لا يكفي: لا حكم ملفي على الاسترداد ({recovery})"
             if recovery == "no-voters" else
             f"الاسترداد غير محسوم: القرّاء انقسموا ({len(lexical_passing)} ناجح، {len(lexical_failing)} فاشل) "
             f"— الانقسام لا يخفّض غطاء ToUnicode، والإشارة تبقى عالية" if recovery == "split" else ""),
            (f"استرداد نص القارئ منسوب إلى الملف لا إلى خط بعينه: الملف يرسم بـ{len(text_fonts)} خطوط؛ "
             "لا يُربط بخط إلا حين يكون خطًا واحدًا" if len(text_fonts) != 1 and recovered is not None else ""),
            ("قارئ فشل على هذا الملف وأُسقط من الأغلبية؛ فشله إشارة على الملف، والتقرير يسمّيه"
             if failed else ""),
            ("حدود القرّاء غير مثبتة في هذه البيئة — شغّل `arabic-pdf-check controls --refresh`"
             if any(not lim["applies"] for lim in known_limits) else ""),
        ] if s],
    }


def _tool_version() -> str:
    from . import __version__ as v
    return v


def _sha256(path: str) -> str:
    return sha256_file(path)
