# Preregistration — engine bakeoff (Path E), cycle 2026-11-19

**This file is committed before any measurement.** Its purpose is to make the decision rule un-tunable: the
rule below is the assignment's §E5, copied verbatim, and the engines, versions and settings are named before a
single file is built. Any later change is a separate commit titled `PREREG AMENDMENT` with its reason, and it is
named in the report.

Branch `spike/engine-bakeoff`, based on the accepted-head candidate of `feat/conformance-gate`
(`a71f520`). E3 (the run) does not start before the owner accepts Path C — measuring on a gate that has not
been reviewed is not evidence.

## 1 · The decision rule (verbatim from the assignment, §E5)

**شروط صارمة (فشل أي منها ⇒ المرشّح غير مؤهَّل):**
- **H1:** كل الحالات تُبنى بلا خطأ.
- **H2:** لا `.notdef` إلا في حالة U+20C1 (تُقاس وحدها)، ولا رفض بصري من المالك لتشكيل الحروف.
- **H3:** PDF/A-3b بمرفق XML يمرّ بـveraPDF بلا فشل.
- **H4:** وسم، و`/Lang ar`، وعناوين `H1–H6`.
- **H5:** إصدار تام قابل لإعادة التثبيت بالـsha256.

**المقياس الأساسي P:** نسبة الحالات بـ`exact = 1` في pdfium.

**الثانوية:**
- S1: `exact` في pdfkit.
- S2: أدنى `order` عبر القرّاء.
- S3: عدد قواعد veraPDF المختلفة الفاشلة (UA-1 + A-3b) عبر المدوّنة.
- S4: الحتمية.
- S5: وسيط زمن البناء.
- S6: عدد أسطر المعالجة اللاحقة اللازمة (للحالي = ما لدينا، للمنافسين = 0 أو تقدير موسوم `مرجّح`).

**الحكم:**
1. **الانتقال** إلى منافس مؤهَّل فقط إن: `P(منافس) ≥ P(chrome+pp) + 0.05`، و`S1` لا يقلّ بأكثر من 0.02، و`S3` لا يزيد، و`S4` طبقة نص متطابقة على الأقل.
2. **التعادل** (`|ΔP| < 0.05`): يبقى chrome+pp لملفات العرض. إن تفوّق المنافس في S3 **و**كان S5 أسرع بـ5 أضعاف أو أكثر، فالتوصية: **المنافس للمسار F وحده** (قوالب جديدة)، دون نقل ملفات العرض.
3. **غير ذلك:** يبقى chrome+pp، ويُكتب ما ينقص المنافس بالأرقام.
4. **chrome-raw** لا يُرشَّح؛ الفرق `P(chrome+pp) − P(chrome-raw)` يُطبع كقيمة معالجتنا المقيسة.

## 2 · The candidates, as declared before measuring

| candidate | version to install | how | role |
|---|---|---|---|
| **chrome+pp** | CfT 157.0.8103.78 + this repository's stages | as installed (`CHROME_PATH`, `chrome_pin.py`) | the incumbent |
| **chrome-raw** | the same binary, no post-processing | `conformance run --engine chrome-raw` | reference only, not a candidate |
| **typst** | the latest stable release at run time (the assignment names 0.15.1, 2026-07-17) | official binary from GitHub Releases, version + sha256 recorded, outside the repository | candidate |
| **weasyprint** | 70.0 (verify at run time) | `.venv-bakeoff` + `requirements-bakeoff.txt`, pango/harfbuzz versions recorded | candidate |

A candidate that cannot be installed at an exact version within one hour is excluded, and the reason is
recorded. No engine is tuned beyond its own documented flags: **no invented flags** — the installed
`--help` output is pasted into the appendix and only what appears there is used.

## 3 · Settings declared in advance

- The same font files for every engine: the two pinned TTFs of `conformance/adapters/fonts.py`, same sha256.
- The same case files: `conformance/corpus/cases/*.json`, manifest sha256
  `be489998f6a2f26089602abe2a5b00fb087969834cc21c58086b570726555f56`.
- Each engine at its best native settings: tagged output, PDF/UA-1, PDF/A-3b, `lang: ar`, RTL, headings that
  produce an outline. If an engine cannot combine UA-1 and A-3b in one file, both files are produced and that
  fact is a result.
- **No post-processing on a competitor.** A competitor defect that our stages could fix is written as one line
  («candidate for improvement»), never implemented.
- The measurement is `conformance run --engine <engine> --time-repeats 3`, twice per engine for the determinism
  question, on this machine, with no parallel work.

## 4 · What the report will carry

- The (engine × H1–H5 × P × S1–S6) table, with the command that produced every number.
- The literal application of the rule above, and one recommendation.
- Licences: one line per engine with its licence file in its own repository and what a cloud service embedding
  it needs to do — no licence written from memory.
- `ما لم يُثبت`: every claim not measured.
