"""The Arabic report — the surface a non-developer reads (and what an interview receives).

Rules it enforces by construction:
  · no «PASS», no percentage, no quality score: the blind report says a risk level, a confidence and the
    named evidence behind them;
  · every reader that ran is listed with its version, and every reader that could not run is listed with
    its reason — a report that silently dropped a reader would be a measurement of a different matrix;
  · every reported page number comes from the reader's own page texts (`page: null` when it cannot be
    located, never a guess);
  · the declared reader limits are printed as declarations about the READER, with the sentence that says
    they do not count against the file.
"""
import re

LEVEL_AR = {"low": "منخفض", "medium": "متوسط", "high": "عالٍ"}
CONF_AR = {"low": "منخفضة", "medium": "متوسطة", "high": "عالية"}


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _code(text) -> str:
    """A Markdown code span that survives backticks in the excerpt.

    A single backtick pair breaks as soon as the excerpt carries one; the fence is therefore one backtick
    longer than the longest run in the text (CommonMark), with a space when the text itself starts or ends
    with a backtick.
    """
    value = str(text)
    longest = max((len(m.group(0)) for m in re.finditer(r"`+", value)), default=0)
    fence = "`" * (longest + 1)
    pad = " " if value.startswith("`") or value.endswith("`") else ""
    return f"{fence}{pad}{value}{pad}{fence}"


def render_blind(report: dict) -> str:
    risk = report["risk"]
    file_claim = risk["file"]
    withheld = file_claim.get("level") is None
    voters, floor, declared = file_claim.get("voters"), risk.get("floor"), (report.get("majority") or {}).get("declared")
    # The report's own sentence for a withheld verdict is English (it is the machine field); the Markdown is
    # Arabic and composes its own from the numbers, because a customer reads this page, not the JSON.
    withheld_ar = (f"لا حكم — قرأ {voters} من {declared or '؟'}، والحكم على الملف يحتاج {floor or '؟'} قرّاء"
                   if withheld else "")
    def cause_ar(signal: dict) -> str:
        # With no file verdict there is no «file cause» to print: a withheld signal is judged per reader.
        if signal.get("cause") == "file" and not withheld:
            return "الملف"
        return "القارئ"
    reader_top = max(list(risk["readers"].values()) + ["low"], key=lambda lv: {"low": 0, "medium": 1, "high": 2}[lv])
    lines = [f"# فحص النسخ العربي — تقرير تشخيصي",
             "",
             f"**الملف:** `{report['file']['sha256'][:16]}…` · {report['file']['bytes']:,} بايت · "
             f"{report['file']['pages']} صفحة",
             (f"**حكم الملف:** {LEVEL_AR[risk['file']['level']]} · "
              f"**الثقة:** {CONF_AR[risk['file']['confidence']]}"
              if not withheld else
              # A withheld verdict is NOT «low»: a reader that prints «منخفض» for «we could not judge» is the
              # PASS this mode forbids. The sentence is Arabic and built from the numbers.
              f"**حكم الملف:** {withheld_ar}"),
             (f"**أعلى خطر لدى قارئ:** {LEVEL_AR[reader_top]}"
              + (" · السبب: " + " و".join(
                  sorted({cause_ar(s)
                          for r in report["readers"].values() if r["risk"] == reader_top
                          for s in r["signals"] if s["level"] == reader_top}))
                 if reader_top != "low" else "")),
             ("" if risk["file"].get("level") == "high"
              else ("**ملاحظة:** لا حكم على الملف؛ الإشارات أدناه تُحسب على أداة النسخ، وثبّت القرّاء الغائبين "
                    "ليصدر الحكم." if withheld else
                    "**ملاحظة:** إشارات القرّاء أدناه تُحسب على أداة النسخ، لا على الملف.")),
             ""]
    lines += ["## القرّاء", "", "| القارئ | الإصدار | الخطر | الثقة | الإشارات |", "|---|---|---|---|---|"]
    for name, r in report["readers"].items():
        ids = "، ".join(sorted({s["id"] for s in r["signals"]})) or "—"
        lines.append(f"| {name} | {_cell(r['version'])} | {LEVEL_AR[r['risk']]} | "
                     f"{CONF_AR[r['confidence']]} | {ids} |")
    nos = [n for n, r in report["readers"].items() if r.get("pages") == "unsupported"]
    if nos:
        lines += ["", "**بلا رقم صفحة:** " + "، ".join(f"`{n}`" for n in nos)
                  + " — يقرأ النص لكنه لا يسمّي صفحاته، فأمثلته بلا رقم صفحة."]
    if report["missing_readers"]:
        # The class alone («ImportError») tells a customer nothing they can act on; the reason does, and it is
        # the path-scrubbed one (`why_reason`), so the privacy rule still holds.
        reasons = report.get("missing_reasons") or {}
        lines += ["", "**لم يعمل:** " + "؛ ".join(
            f"`{n}`: {reasons.get(n) or why}" for n, why in report["missing_readers"].items())]
    lines += ["", "## إشارات الملف", ""]
    held = [s for s in report["signals"] if not s.get("withheld_from_file_level")]
    withheld_here = [s for s in report["signals"] if s.get("withheld_from_file_level")]
    if held:
        lines += ["| الإشارة | المستوى | الثقة | البيان |", "|---|---|---|---|"]
        for s in held:
            lines.append(f"| `{s['id']}` | {LEVEL_AR[s['level']]} | {CONF_AR[s['confidence']]} | "
                         f"{_cell(s['detail'])} |")
    elif not withheld_here:
        lines.append("لا إشارة على الملف: غطاء ToUnicode مكتمل، ولا أشكال عرض، ولا أرقام مخالفة.")
    if withheld_here:
        # Its own section, not a footnote: a signal nobody was allowed to promote to the file must not be read
        # as a file verdict that merely looks quiet.
        lines += ["", f"### إشارات محجوبة عن حكم الملف — محجوب: {voters} من {floor} قرّاء", "",
                  "| الإشارة | مستوى القارئ | البيان |", "|---|---|---|"]
        for s in withheld_here:
            lines.append(f"| `{s['id']}` | {LEVEL_AR[s['level']]} | {_cell(s['detail'])} |")
    per_reader = [(n, r) for n, r in report["readers"].items() if r["signals"]]
    if per_reader:
        lines += ["", "## إشارات القرّاء وأمثلة", ""]
        for name, r in per_reader:
            lines.append(f"### {name} — {LEVEL_AR[r['risk']]}")
            for s in r["signals"]:
                tag = cause_ar(s)
                if s.get("withheld_from_file_level"):
                    tag = f"{tag} — محجوب عن حكم الملف: {voters} من {floor}"
                lines.append(f"- `{s['id']}` ({LEVEL_AR[s['level']]}, {tag}): {s['detail']}")
            for ex in r["examples"]:
                where = f"ص {ex['page']}" if ex["page"] else "صفحة غير محددة"
                lines.append(f"  - {where}: {_code(ex['text'])}")
            lines.append("")
    lines += ["## حدود قرّاء معلنة (تُعلَن ولا تُحسب على الملف)", ""]
    if report["known_limits"]:
        for lim in report["known_limits"]:
            state = ("ينطبق" if lim["kind"] == "limit" else "مُعاد إنتاجه") if lim["applies"] else "مرفوض"
            on = (f" · مُثبت على {lim['measured_on']}" if lim.get("measured_on")
                  and lim["measured_on"] != lim["version"] else "")
            lines.append(f"- `{lim['id']}` — {lim['reader']} {lim['version']} ({state}){on}: {lim['statement']}")
    else:
        lines.append("- لا حدّ معلن ينطبق على هذه البيئة.")
    lines += ["", "## ما لا يعنيه هذا التقرير", ""]
    lines += [f"- {sentence}" for sentence in report["not_judged"]]
    lines += ["", f"*فاحص النسخ العربي {report['tool']['version']} · "
                  f"`{report['tool']['commit'][:12]}` · arafix {report['tool']['arafix']}*", ""]
    return "\n".join(lines)


def render_reference(cert: dict) -> str:
    source = cert.get("source") or {}
    lines = ["# شهادة مطابقة نصّية — الوضع المرجعي", "",
             f"**الحكم:** {cert['verdict']} — {cert['verdict_detail']}",
             f"**الملف:** `{cert['file']['sha256'][:16]}…` · {cert['file']['pages']} صفحة"]
    if source.get("kind") == "truth":
        lines.append(f"**النصّ المرجعي:** `{str(source.get('text_sha256') or source.get('sha256'))[:16]}…` · "
                     f"{source['chars']} محرفًا"
                     + (f" · {source['name']}" if source.get("name") else ""))
    else:
        lines.append(f"**الحالة:** {source.get('case')} ({source.get('category')})")
    lines += ["", "## القرّاء", "",
              "| القارئ | الإصدار | مطابقة تامة | word_f1 | الترتيب | الأرقام | بلا تشكيل | الثقة |",
              "|---|---|---|---|---|---|---|---|"]
    for name, r in cert["readers"].items():
        lines.append(f"| {name} | {_cell(r['version'])} | {r['exact']:.0f} | {r['word_f1']:.3f} | "
                     f"{r['order']:.3f} | {r['digit_runs']:.3f} | {r['skeleton_exact']:.0f} | "
                     f"{CONF_AR.get(r.get('confidence'), '—')} |")
    if cert["tier1_unavailable"]:
        lines += ["", "**قارئ أساسي غائب:** " + "؛ ".join(f"{u['reader']}: {u['reason'][:80]}"
                                                         for u in cert["tier1_unavailable"])]
    missing = cert.get("missing_readers") or {}
    if missing:
        lines += ["", "**قرّاء لم يعملوا:** " + "؛ ".join(f"`{n}`: {why[:80]}" for n, why in missing.items())]
    examples = [(n, r) for n, r in cert["readers"].items() if r.get("examples")]
    if examples:
        lines += ["", "**أمثلة (حتى 5 لكل قارئ · الصفحة null لأن النصّ الحرّ بلا بنية صفحات):**"]
        for name, r in examples:
            lines.append(f"- `{name}`: " + " · ".join(f"«{ex['text']}»" for ex in r["examples"]))
    lines += ["", "## الفحوص", "", "| الفحص | الحالة | البيان |", "|---|---|---|"]
    for c in cert["checks"]:
        lines.append(f"| `{c['id']}` | {c['status']} | {_cell(c['reason'][:160])} |")
    if cert.get("claims"):
        lines += ["", "## الادعاءات المقاسة", "",
                  f"PDF/UA-1: {cert['claims']['pdfua']} · PDF/A: {cert['claims']['pdfa']}"]
    lines += ["", "## ما لا يعنيه هذا التقرير", "",
              f"- {cert['not_checked']['note']}",
              "- الشهادة لا تُثبت المنتِج: هويّة خط الإنتاج مُعلنة لا مقيسة.",
              ""]
    return "\n".join(lines)
