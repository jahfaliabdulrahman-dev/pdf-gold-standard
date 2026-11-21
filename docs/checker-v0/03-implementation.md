# التنفيذ — ما بُني، وما غيّره القياس

## 1 · في `conformance/` (كلها إضافية أو استخراج بلا تغيير سلوك)

| الملف | التغيير | الإثبات |
|---|---|---|
| `reference.py` (جديد) | `measure_text(pdf, truth)` — مسار قياس واحد؛ `page_count` | `test_certificate.py` و`arabic_pdf_check/tests/test_reference.py` |
| `certificate.py` | `certificate/2` بـ`source` (case أو truth)؛ `certify(truth_text=…)`؛ `validate` يقبل الإصدارين؛ `recheck` يطلب النصّ للنصّ الحرّ | `test_certificate.py` (v2) و`test_schema.py` (verify + recheck + الرفض بلا نصّ) |
| `checks/mcid_text.py` | عدّادات لكل خط: `codes/notdef/missing_unicode/pua/replacement/zero_value/bom` بمفتاح `name|family` | `test_mcid_text.py` + `docs/checker-v0/measurements/clean.json` |
| `checks/structure.py` | `persian_digits` و`content_f1` و`file_checks` (نصف `evaluate` المستقل عن الحالة) | `test_certificate.py`: 20 فحصًا كما كانت |
| `readers/*.py` | `pages_many` للخمسة + `pdfkit_text.swift` يعيد `pages` | `arabic_pdf_check/tests/test_pages.py`: `N-join == N(text)` للخمسة |
| `readers/declared.py` + `declared.json` + `controls/pdfium_row_order.py` | سلوك قارئ معلن بضابط حيّ (صف PDFium المقلوب) | `conformance/tests/test_declared.py` |

## 2 · في `arabic_pdf_check/`

`blind.py` (الإشارات والمخاطر بمستويين) · `markdown.py` (تقرير عربي) · `cli.py` (check/verify/manifest) ·
`schema/report.v1.json` · `thresholds.json`. والقياس: `scripts/checker_fixtures.py` و`scripts/checker_measure.py`.

## 3 · ما غيّره القياس (لا الرأي)

1. **الترتيب البصري في الطبقة ليس عيبًا.** مستنداتنا الأربعة النظيفة طبقتها بصرية (`order_score ≈ +0.99`)
   وأربعة قرّاء يعيدون المنطقي — فالإشارة على **مخرَج القارئ**، لا على الطبقة.
2. **السبب بالأغلبية لا بالنسبة.** ملف كتبه MuPDF (طبقة منطقية): ٤ من ٥ قرّاء يعيدونه مقلوبًا ⇒ السبب
   `file`؛ مستند Chrome نظيف: قارئ واحد (pdfminer) يعيد المخزَّن ⇒ السبب `reader` وحكم الملف `low`.
3. **الشكل المتري لخلاف القرّاء رُفض.** أدنى `content_f1` بين قرّاء نظيفين = **0.000** (حالات كلمة واحدة
   وأرقام)، فلا عتبة تفصل. الذي يشحن: الصفحة الفارغة عند قارئ ويقرؤها اثنان — حتميّ، وله مزروعة موجبة.
4. **عتبة أشكال العرض على الأساس + الأشكال** (`forms/(arabic+forms)`) لا على الأساس وحده — وإلا خرجت
   نسبة ١٠٠٠٪ لملف كلّه أشكال.
5. **حدّ PDFium لصف المفتاح/القيمة** أُعلن في `declared.json` بضابط يعيد بناءه بـChrome ويقيسه على
   PDFium 5.15.2 — لا نثرًا في مستند. ونسخة القارئ تُقارَن؛ فإن تغيّرت ولم يتكرر السلوك، يُرفض الإعلان.
6. **خط بسيط بلا `/ToUnicode` ليس ثغرة.** قياس مجلد المالك: 388 خطًّا «بثغرات» ظهرت وكل ملفات الـ55 عالية،
   والسبب أن FrutigerLTArabic/Helvetica بلا خريطة أصلًا (استثناء Matterhorn 31-027). القاعدة: الخط البسيط
   بلا خريطة **يُعلَن** في التقرير ولا يُنذر؛ والثغرة ثغرة فقط حين توجد خريطة وتغيب رموز مرسومة.
7. **الثغرة تُدرَّج بنسبتها.** بعد الاستثناء بقي 52 خطًّا بخريطة وثغرات جزئية (0.26%–6.25%)، و15 خطًّا
   بخريطة **فارغة** (1.0). العتبة المُشتقة: `tounicode_gap_ratio = max(0.01, clean_max=0)`؛ فوق 1% عالٍ،
   وتحته متوسط. فصار توزيع الملفات 41 عاليًا و14 منخفضًا بدل 55/0 — والفرق كله كان في التصنيف لا في الملفات.

## 4 · ما لم يُنفَّذ (خارج v0، معلن)

- Acrobat (قارئه خارج المصفوفة).
- OCR، والإصلاح، وواجهة الويب.
- الحكم على رسم الحروف (التقرير يقرأ الطبقة).
