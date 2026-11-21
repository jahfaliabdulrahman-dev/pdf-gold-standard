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
LEVEL_AR = {"low": "منخفض", "medium": "متوسط", "high": "عالٍ"}
CONF_AR = {"low": "منخفضة", "medium": "متوسطة", "high": "عالية"}


def _cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_blind(report: dict) -> str:
    risk = report["risk"]
    lines = [f"# فحص النسخ العربي — تقرير تشخيصي",
             "",
             f"**الملف:** `{report['file']['sha256'][:16]}…` · {report['file']['bytes']:,} بايت · "
             f"{report['file']['pages']} صفحة",
             f"**حكم الملف:** {LEVEL_AR[risk['file']['level']]} · **الثقة:** {CONF_AR[risk['file']['confidence']]}",
             (f"**أعلى خطر لدى قارئ:** {LEVEL_AR[risk['level']]}"
              + (" · السبب: " + " و".join("الملف" if c == "file" else "قارئ" for c in risk["causes"])
                 if risk["causes"] else "")),
             (f"خطر الملف نفسه: {LEVEL_AR[risk['file']['level']]}"
              + ("" if risk["file"]["level"] == "high"
                 else " — إشارات القرّاء أدناه لا تُحسب على الملف")),
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
        lines += ["", "**لم يعمل:** " + "؛ ".join(f"`{n}`: {why}" for n, why in report["missing_readers"].items())]
    lines += ["", "## إشارات الملف", ""]
    if report["signals"]:
        lines += ["| الإشارة | المستوى | الثقة | البيان |", "|---|---|---|---|"]
        for s in report["signals"]:
            lines.append(f"| `{s['id']}` | {LEVEL_AR[s['level']]} | {CONF_AR[s['confidence']]} | "
                         f"{_cell(s['detail'])} |")
    else:
        lines.append("لا إشارة على الملف: غطاء ToUnicode مكتمل، ولا أشكال عرض، ولا أرقام مخالفة.")
    per_reader = [(n, r) for n, r in report["readers"].items() if r["signals"]]
    if per_reader:
        lines += ["", "## إشارات القرّاء وأمثلة", ""]
        for name, r in per_reader:
            lines.append(f"### {name} — {LEVEL_AR[r['risk']]}")
            for s in r["signals"]:
                lines.append(f"- `{s['id']}` ({LEVEL_AR[s['level']]}, "
                             f"{'الملف' if s['cause'] == 'file' else 'القارئ'}): {s['detail']}")
            for ex in r["examples"]:
                where = f"ص {ex['page']}" if ex["page"] else "صفحة غير محددة"
                lines.append(f"  - {where}: `{ex['text']}`")
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
        lines.append(f"**النصّ المرجعي:** `{source['text_sha256'][:16]}…` · {source['chars']} محرفًا"
                     + (f" · {source['name']}" if source.get("name") else ""))
    else:
        lines.append(f"**الحالة:** {source.get('case')} ({source.get('category')})")
    lines += ["", "## القرّاء", "",
              "| القارئ | الإصدار | مطابقة تامة | word_f1 | الترتيب | الأرقام | بلا تشكيل |",
              "|---|---|---|---|---|---|---|"]
    for name, r in cert["readers"].items():
        lines.append(f"| {name} | {_cell(r['version'])} | {r['exact']:.0f} | {r['word_f1']:.3f} | "
                     f"{r['order']:.3f} | {r['digit_runs']:.3f} | {r['skeleton_exact']:.0f} |")
    if cert["tier1_unavailable"]:
        lines += ["", "**قارئ أساسي غائب:** " + "؛ ".join(f"{u['reader']}: {u['reason'][:80]}"
                                                         for u in cert["tier1_unavailable"])]
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
