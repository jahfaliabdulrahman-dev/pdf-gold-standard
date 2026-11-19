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
| `scripts/verify_pdf.py` + `scripts/gate_selftest.py` | **بوابة التسليم** واختبارها الذاتي (٣٦ فحصاً، منها فحص يقرأ بكسلات الأزرار وشكل كل أيقونة · ٥٣ عطلاً مزروعاً يجب أن تُكشف كلها) |
| `scripts/verapdf_gate.py` + `scripts/claim_probe.py` | **بوابة المطابقة**: veraPDF مقابل أساس كل مستند (`3b` · `ua1` · `4f`) — لا قاعدة جديدة ولا استثناء ميت ولا قاعدة مُصلحة تعود · و`claim_probe` يقيس على نسخة ما يبقى لو أُعلن الادعاء |
| `scripts/test_vocalised.py` + `tests/` | **اختبار النص المشكول**: فقرتان مشكولتان من مخرج Chrome الخام يجب أن تُنسخا مطابقتين بعد `fix_text_layer.py` (والخام يجب أن يفشل) |
| `guide-v2.html` + `build.py` | **المصدر**: صفحات HTML مصممة → `python3 build.py guide-v2.html out.pdf` (الترميز الذي يُسلَّم لـChrome يشتقّه `render_markup.py` من المواصفة والمصدر — لا نسخة محفوظة بجانب المخرج) |
| `report-v1.html` + `report_spec.py` | **الوثيقة الثانية**: «الحرف المقلوب» — ١٧ صفحة، مواصفتها وحدها (`PDF_SPEC=report_spec`)، تُبنى بنفس البوابة والاختبار الذاتي |
| `spec_loader.py` + `<name>_spec.py` | **المواصفة لكل مستند**: `PDF_SPEC` يختار الملف، والبناء والبوابة والاختبار الذاتي يقرؤون منه واحدًا (لا مواصفة مكرّرة في الكود) |
| `postprocess.py` + `pdfops.py` | **المرحلة ٥**: تسميات الصفحات، المنافذ المسمّاة، XMP، OutputIntent، المرفقات (`manifest.json` و`features.toml` وأساس veraPDF — بلا مرفق مصدر)، وسم الروابط — وعمليات الرسم المشتركة بين المنتِج والبوابة |
| `features.toml` + `verapdf-baseline*.toml` | **الميزان**: كل ميزة معلنة يُفحص وجودها · وأساس veraPDF لكل مستند (‏`-report`، `-najd`) |
| `pdfium-shaping/` + `artifacts/` | **أرشيف البحث**: لقطة `hb_probe` (ليست الترقيع) · وصور أدلة الاستخراج |
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
python3.12 -m venv .venv && source .venv/bin/activate   # نسخة Python التي يستخدمها CI
python3 -m pip install -r requirements.txt
# Chrome مثبّت الإصدار: النسخة في chrome_pin.py. بدونه لا يبني — لا بديل صامت إلى Chrome النظامي.
npx --yes @puppeteer/browsers install chrome@157.0.8103.78 --path "$HOME/.cache/cft"
export CHROME_PATH="$HOME/.cache/cft/chrome/mac_arm-157.0.8103.78/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
python3 build.py guide-v2.html out.pdf
PDF_SPEC=report_spec python3 build.py report-v1.html report.pdf   # الوثيقة الثانية، بنفس البوابة
```

كل وثيقة تحمل مواصفتها: `nav_spec.py` للدليل و`report_spec.py` للتقرير — يختارها `PDF_SPEC`، ويقرؤها البناء والبوابة
والاختبار الذاتي من مكان واحد. الأرقام المقاسة (حبر كل صفحة، كلماتها، صورها) تُولَّد بـ`scripts/calibrate.py`، لا تُكتب يدويًا.
ومحرّك الرسم نفسه مثبّت: `chrome_pin.CHROME_VERSION` — البناء يقرأ `CHROME_PATH` وحده ويرفض أي إصدار آخر بالاسم،
لأن Skia هي التي تكتب طبقة النص التي تُرقَّع وتُقاس (مسارات ‎darwin/arm64‎؛ غيّر المسار حسب معماريتك).

**CI (macOS)** يبني الدليل والتقرير ويشغّل عليهما البوابة والاختبار الذاتي وveraPDF و`claim_probe`، ثم اختبار النص المشكول.
**نجد لا يُبنى في CI** (خطه غير مشحون)، فأوامره إلزامية محليًا قبل أي دمج:

```bash
PDF_SPEC=najd_spec python3 build.py najd.html najd.pdf
PDF_SPEC=najd_spec python3 scripts/verify_pdf.py najd.pdf
PDF_SPEC=najd_spec python3 scripts/gate_selftest.py najd.pdf      # 45/45 (5 معلنة لكائنات غائبة)
PDF_SPEC=najd_spec python3 scripts/verapdf_gate.py najd.pdf 3b ua1
PDF_SPEC=najd_spec python3 scripts/claim_probe.py najd.pdf --check
```

الخطوط تُضمَّن محلياً والبناء حتمي المحتوى بلا إنترنت (النص والصفحات والروابط نفسها في كل بناء؛ البايتات تختلف بتاريخ الإنشاء). يتطلب Google Chrome (طباعة headless).

## ما يميز المخرج؟

- **٤٢ رابطاً حياً** — أربعة أزرار في كل صفحة: التالي · السابق · الفهرس · الغلاف
- **فهرس جانبي** بثلاثة مستويات في شريط أي قارئ PDF
- **صفحات مستقلة** (`/SinglePage`) + اتجاه قراءة `R2L` مثل المرجع الأصلي
- **Tagged PDF** (`/MarkInfo Marked` + شجرة بنية + `Lang=ar`) و**نسخ عربي سليم**: `scripts/fix_text_layer.py` يعيد بناء طبقة النص بعد Chrome (كل شكل يحمل حرفاً واحداً) دون تغيير الرسم — ٩٨٪ من الكلمات بترتيبها في Preview (٠٫٩٨٢ بمحرّكه PDFKit وبمقياس البوابة نفسه). الحدود الباقية في ROADMAP
- **فن مولّد**: غلاف 4K (~433DPI) وعائلة فنية موحّدة (مرجع أسلوب واحد)
- **مطابقة مُعلنة ومُثبتة**: «الحرف المقلوب» وعيّنة نجد يعلنان `PDF/A-3b` و`PDF/UA-1` في XMP، و`veraPDF` يعطيهما **صفر مخالفة** تحت الادعاءين — والبوابة ترفض أي إعلان ما دام خط الأساس يسجّل مخالفة، والدليل لا يعلن ما لم يُقس

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

[ROADMAP.md](ROADMAP.md) — مراجعة دمج ١٧ نوفمبر · المتبقي بالأولوية · حدود معروفة مقاسة · طبقة نص عربية صحيحة · ثيمات (١٧ متغيراً + فحص تباين).

## English

Arabic-first pipeline producing genuinely interactive PDFs (nav buttons, multi-level
bookmarks, RTL reading direction) from designed HTML: HTML → Chrome headless →
PyMuPDF interactivity layer. Content-deterministic, offline, font-embedded.
A delivery gate (39 checks, 63 planted faults that must all be caught) and veraPDF baselines per document guard every build; the second document and the Najd specimen declare PDF/A-3b + PDF/UA-1 and measure zero violations. The forensic standard behind it: `docs/PDF-Gold-Standard.md`.
The operating skill lives under `skill/arabic-rtl-pdf/` — point your agent at that directory (Hermes: `skills.external_dirs`) instead of copying it, so there is one source.

MIT © 2026 Abdulrahman Jahfali
