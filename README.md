# معيار PDF الذهبي 🜔 · PDF Gold Standard

معيار إنتاج ملفات PDF تفاعلية عربية بجودة دار نشر: أزرار تنقل دائمة، فهرس جانبي
متعدد المستويات، اتجاه RTL أصيل، وفن مولّد ثلاثي الأبعاد — من HTML مصمم إلى PDF نهائي.

[![Build PDF](https://github.com/jahfaliabdulrahman-dev/pdf-gold-standard/actions/workflows/build-pdf.yml/badge.svg)](https://github.com/jahfaliabdulrahman-dev/pdf-gold-standard/actions/workflows/build-pdf.yml)

**⬇️ التحميل:** [دليل المعيار — الإصدار الثاني (PDF)](https://github.com/jahfaliabdulrahman-dev/pdf-gold-standard/releases/latest/download/guide-v2-ar.pdf)

![غلاف الدليل](docs/images/cover.jpg)

## ماذا يوجد هنا؟

| المسار | الوصف |
|---|---|
| `docs/PDF-Gold-Standard.md` | **المعيار المرجعي** — فحص جنائي كامل لدليل مرجعي حقيقي: 155 رابطاً، 38 مدخلاً، أزرار بمواضع بكسلية |
| `docs/recipes/` | **الوصفات الموثقة (5)**: الطبقة التفاعلية · الفن المولّد · المعيار المهني · تقاطعات الطباعة · تدقيق PDF الجنائي |
| `docs/automation-plan.md` | **خطة الأتمتة** — بوابة الاختيار، تحليل سير العمل، الحوكمة، مؤشرات KPI (وفق دليل الأتمتة) |
| `skill/arabic-rtl-pdf/` | **المهارة — المصدر الوحيد لها** (SKILL.md + 7 مراجع). لا تنسخها: وجّه الوكيل إلى هذا المجلد (انظر «مزامنة المهارة») |
| `nav_spec.py` | **رقم واحد لكل شيء**: الفهرس، مواضع الأزرار ووجهاتها، صفوف المحتويات، الخطوط المسموحة — يبني منه `build.py` ويفحص عليه البوابة |
| `scripts/verify_pdf.py` + `scripts/gate_selftest.py` | **بوابة التسليم** واختبارها الذاتي (٣٤ فحصاً، منها فحص يقرأ بكسلات الأزرار وشكل كل أيقونة · ٤٨ عطلاً مزروعاً يجب أن تُكشف كلها) |
| `scripts/test_vocalised.py` + `tests/` | **اختبار النص المشكول**: فقرتان مشكولتان من مخرج Chrome الخام يجب أن تُنسخا مطابقتين بعد `fix_text_layer.py` (والخام يجب أن يفشل) |
| `guide-v2.html` + `build.py` | **المصدر**: صفحات HTML مصممة → `python3 build.py guide-v2.html out.pdf` |
| `report-v1.html` + `report_spec.py` | **الوثيقة الثانية**: «الحرف المقلوب» — ١٧ صفحة، مواصفتها وحدها (`PDF_SPEC=report_spec`)، تُبنى بنفس البوابة والاختبار الذاتي |
| `gen_art.py` | توليد فن الأغلفة (OpenRouter Image API — `gemini-3-pro-image`) |
| `fonts/` | IBM Plex Sans Arabic + Amiri (SIL OFL 1.1) — تُضمَّن base64 في البناء |
| [آخر إصدار](https://github.com/jahfaliabdulrahman-dev/pdf-gold-standard/releases/latest) | المخرج النهائي (12 صفحة · 42 رابطاً حياً · 2.5MB) — النسخة المنشورة الوحيدة، يبنيها CI عند كل وسم `v*`. لا نسخة PDF داخل المستودع: نسخة `main` تُبنى بـ`python3 build.py guide-v2.html out.pdf` |

## مزامنة المهارة (مصدر واحد)

هذا المستودع هو المرجع الوحيد لمهارة `arabic-rtl-pdf`. أي تعديل يتم هنا أولاً، ويمر على البوابة واختبارها الذاتي في CI.

- **Hermes:** أضف مجلد `skill/` من نسخة المستودع المحلية إلى `skills.external_dirs` في `~/.hermes/config.yaml`، واحذف أي نسخة بنفس الاسم من `~/.hermes/skills/` (النسخة المحلية تتقدم على المجلد الخارجي).
- **Claude:** تُحدَّث نسخة المهارة في الحساب من هذا المجلد بعد كل تغيير.
- **التحقق:** `diff -r skill/arabic-rtl-pdf <نسخة الوكيل>` لا يُظهر فرقاً.

## كيف تبني؟

```bash
python3 -m pip install -r requirements.txt
python3 build.py guide-v2.html out.pdf
PDF_SPEC=report_spec python3 build.py report-v1.html report.pdf   # الوثيقة الثانية، بنفس البوابة
```

كل وثيقة تحمل مواصفتها: `nav_spec.py` للدليل و`report_spec.py` للتقرير — يختارها `PDF_SPEC`، ويقرؤها البناء والبوابة
والاختبار الذاتي من مكان واحد. الأرقام المقاسة (حبر كل صفحة، كلماتها، صورها) تُولَّد بـ`scripts/calibrate.py`، لا تُكتب يدويًا.

الخطوط تُضمَّن محلياً والبناء حتمي المحتوى بلا إنترنت (النص والصفحات والروابط نفسها في كل بناء؛ البايتات تختلف بتاريخ الإنشاء). يتطلب Google Chrome (طباعة headless).

## ما يميز المخرج؟

- **٤٢ رابطاً حياً** — أربعة أزرار في كل صفحة: التالي · السابق · الفهرس · الغلاف
- **فهرس جانبي** بثلاثة مستويات في شريط أي قارئ PDF
- **صفحات مستقلة** (`/SinglePage`) + اتجاه قراءة `R2L` مثل المرجع الأصلي
- **Tagged PDF** (`/MarkInfo Marked` + شجرة بنية + `Lang=ar`) و**نسخ عربي سليم**: `scripts/fix_text_layer.py` يعيد بناء طبقة النص بعد Chrome (كل شكل يحمل حرفاً واحداً) دون تغيير الرسم — ٩٨٪ من الكلمات بترتيبها في Preview (٠٫٩٨٢ بمحرّكه PDFKit وبمقياس البوابة نفسه). الحدود الباقية في ROADMAP
- **فن مولّد**: غلاف 4K (~433DPI) وعائلة فنية موحّدة (مرجع أسلوب واحد)
- **مطابقة مُعلنة ومُثبتة**: «الحرف المقلوب» يعلن `PDF/A-3b` في XMP، و`veraPDF` يعطيه **صفر مخالفة** — والبوابة ترفض أي إعلان ما دام خط الأساس يسجّل مخالفة

## المهارة الجاهزة (Hermes + Claude)

`skill/arabic-rtl-pdf/` هي المهارة التشغيلية الكاملة التي تُدير هذا الخط من البداية للنهاية —
قواعد القرار، الوصفة، تقاطعاتها، وتدقيق أي PDF مرجعي جنائياً. لا تنسخها — وجّه الوكيل إلى هذا المجلد
(انظر «مزامنة المهارة»). مثال Hermes في `~/.hermes/config.yaml`:

```yaml
skills:
  external_dirs:
    - ~/Projects/pdf-gold-standard/skill
```

## نسختان ومستند ثانٍ

```bash
PDF_SPEC=report_spec       python build.py report-v1.html report.pdf        # نسخة الشاشة (٦٣ رابطًا)
PDF_SPEC=report_print_spec python build.py report-v1.html report-print.pdf  # نسخة الطباعة (١١ رابطًا، بلا أزرار)
PDF_SPEC=najd_spec         python build.py najd.html najd.pdf               # عيّنة خط نجد (لا حقول كتابة)
```

ملفّات خط نجد لا تُرفَق بالمستودع (ترخيصها «كل الحقوق محفوظة»)؛ ضعها في `najd/` محليًا لبناء المستند.

## خارطة الطريق

[ROADMAP.md](ROADMAP.md) — حدود معروفة مقاسة · طبقة نص عربية صحيحة · ثيمات (١٧ متغيراً + فحص تباين).

## English

Arabic-first pipeline producing genuinely interactive PDFs (nav buttons, multi-level
bookmarks, RTL reading direction) from designed HTML: HTML → Chrome headless →
PyMuPDF interactivity layer. Content-deterministic, offline, font-embedded.
The forensic standard behind it: `docs/PDF-Gold-Standard.md`.
The operating skill lives under `skill/arabic-rtl-pdf/` — point your agent at that directory (Hermes: `skills.external_dirs`) instead of copying it, so there is one source.

MIT © 2026 Abdulrahman Jahfali
