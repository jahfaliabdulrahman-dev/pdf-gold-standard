# خطة `arabic-pdf-check` v0

**الفرع:** `feat/checker-v0` على `origin/main = 502ebf0`. **لا PR، لا دمج.**
**المرجع الملزم:** نصّ التكليف (فاحص النسخ العربي v0، ٢١ نوفمبر). **المصادر:** `00-sources.md`.

## 1 · القاعدة الأولى: طبقة رقيقة فوق `conformance/`

| ما يحتاجه الفاحص | من أين يأخذه (بلا نسخة ثانية) |
|---|---|
| القرّاء وإصداراتهم وغيابهم | `conformance.readers.available()` / `version_of` |
| المقاييس `exact/word_f1/order/digit_runs/skeleton_exact` | `conformance.checks.metrics.measure` |
| التطبيع `N` و`digits` و`PUA` و`PRESENTATION_FORM` | `metrics` (لا ثوابت جديدة في الفاحص) |
| حدود القرّاء وتحقّقها | `conformance.readers.limitations.usable/apply` |
| عدّ الرموز و`.notdef` وخريطة ToUnicode لكل خط | `conformance.checks.mcid_text.scan` (يُوسَّع، لا يُنسخ) |
| `numerals-persian` و`numerals-mixed` | `conformance.checks.structure` (يُستخرجان إلى دالّتين مسمّاتين) |
| كشف الانعكاس | `arafix` 1.2.0 (MIT) — **لا كاشف ثانٍ** |
| نصّ لكل صفحة (للمواضع) | `readers.pages_many` — إضافة إلى الوحدات الخمس، لا قارئ جديد |

**قبول العزل:** `arabic_pdf_check/tests/test_isolation.py` يفشل إن استورد الفاحص `pymupdf`/`pypdfium2`/
`pdfplumber`/`subprocess` للاستخراج، أو عرّف نطاقًا عربيًا/تطبيعًا/مقياسًا، أو نادى `pdftotext` مباشرة.

## 2 · التغييرات في `conformance/` (كلها إضافية أو استخراج بلا تغيير سلوك)

1. **`conformance/reference.py` (جديد)** — `measure_text(pdf, truth_text) -> dict`:
   لكل قارئ متاح: `version, metrics, defects, limitations_applied, limitations_refused`.
   `certificate.certify()` يُعاد توصيله ليستدعيها بنصّ الحالة (`truth(case)`)، فلا يوجد مسار قياس ثانٍ.
   **قبول:** `test_certificate.py` يبقى أخضر، ومقارنة bloc `readers` قبل/بعد متطابقة على ملف حالة.
2. **`mcid_text.scan`** — عدّادات **لكل خط**: `codes, missing_unicode, pua, replacement, zero_value, notdef,
   has_tounicode, subtype, two_byte, embedded`. تُجمَّع في `stats["fonts"][name]` (مفاتيح جديدة فوق الموجودة).
   **قبول:** `test_mcid_text.py` يُوسَّع ليؤكد العدّادات على ملف حالة، وكل المفاتيح القديمة كما هي.
3. **`structure.py`** — استخراج `numerals_persian(text)` و`numerals_mixed(text)` (الأخيرة موجودة) واستدعاؤهما
   في `evaluate` بدل الشيفرة المضمّنة. **قبول:** حكم `evaluate` على 65 حالة لا يتغير.
4. **`readers.*.pages_many`** — دالة اختيارية لكل قارئ؛ poppler يقسم على `\f`، والبقية تعدّ الصفحات.
   **قبول:** `N("\n".join(pages)) == N(text)` لكل قارئ على عيّنة (وإلا فالفاحص لا يبني مواضع الصفحات).

## 3 · الواجهة

```
python3 -m arabic_pdf_check check  FILE.pdf [--json OUT.json] [--md OUT.md] [--readers NAME…] [--gate]
python3 -m arabic_pdf_check verify FILE.pdf --truth TEXT.txt|JSON [--json OUT.json] [--md OUT.md]
python3 -m arabic_pdf_check manifest            # العتبات + أمر إنتاجها + مصفوفة القرّاء
```

- **`check` (أعمى):** تشخيص فقط: `risk.level ∈ {low, medium, high}` + `confidence ∈ {low, medium, high}`
  + إشارات مسمّاة. **لا نسبة مئوية، لا `PASS`، لا `score` جودة.**
- **`verify` (مرجعي):** شهادة: لكل قارئ `exact/word_f1/order/digit_runs/skeleton_exact` + defects + حدود
  مطبَّقة؛ الحكم `MATCH` فقط إذا كل قارئ متاح `exact == 1` وبلا defects، وإلا `MISMATCH` مع أسماء القرّاء.
  غياب قارئ tier-1 يُعلن في `tier1_unavailable[]` ويقلب الحكم إلى `MATCH (tier-1 incomplete)` —
  شهادة PDFium وحده لا تُشبه شهادة قارئين.
- **الحدّ المعلن:** Tier-1 = PDFium + PDFKit إن توفّر (macOS)؛ وإلا PDFium وحده ويُعلن.

### مخطط التقرير (`schema_version: "arabic-pdf-check/1"`)

```json
{
 "schema_version": "arabic-pdf-check/1",
 "mode": "blind|reference",
 "file": {"sha256": "...", "bytes": 0, "pages": 0},
 "readers": {"pdfium": {"version": "...", "chars": 0, "risk": "low|medium|high",
                        "signals": [], "examples": [{"page": 1, "text": "≤80"}]}},
 "missing_readers": {"pdfkit": "reason"},
 "font_text": [{"font": "...", "subtype": "Type0", "embedded": true, "tounicode": true,
                "codes": 0, "missing_unicode": 0, "notdef": 0, "pua": 0}],
 "signals": [{"id": "tounicode-gaps|presentation-forms|visual-order|reader-disagreement|
                     numerals-persian|numerals-mixed|no-text-layer|known-reader-limit",
              "level": "...", "confidence": "...", "cause": "file|reader",
              "detail": "...", "evidence": {...}}],
 "risk": {"level": "...", "confidence": "...", "causes": ["file", "reader"]},
 "known_limits": [{"id": "...", "reader": "...", "version": "...", "applies": true}],
 "thresholds_sha256": "...", "tool": {"version": "0.1.0", "commit": "...", "dirty": false}
}
```

`examples` ≤ 5 لكل قارئ، مقتطف ≤ 80 محرفًا، ورقم الصفحة من `pages_many` لنفس القارئ؛ وإن غابت الصفحة
(`page: null`) يُعلن ذلك في التقرير ولا يُخترع رقم.

## 4 · إشارات الوضع الأعمى (الترتيب من الأقوى)

| # | id | القاعدة | المصدر |
|---|---|---|---|
| 1 | `tounicode-gaps` | خط **مركّب (Type0)** مرسوم بلا ToUnicode، أو مدخلات ناقصة لرموز مرسومة، أو خريطة إلى PUA/`U+FFFD`/`U+0000`/`U+FEFF`، أو `.notdef` مرسوم ⇒ **عالٍ** | ISO 9.10.2/14.8.2.4 + Matterhorn 10-001/31-027/28/29/30 |
| 2 | `presentation-forms` | نسبة محارف `FB50–FDFF`/`FE70–FEFF` إلى المحارف العربية > العتبة ⇒ عالٍ | Matterhorn 31-030 (سياق) + W3C §4.3 + قياس |
| 3 | `visual-order` | `arafix.diagnose` → `Defect.VISUAL_ORDER`؛ الشدّة من `score` والثقة من `defect_confidence` | UAX #9 + W3C §3.2 + arafix |
| 4 | `reader-disagreement` | أقلّ `word_f1` بين كل زوج قرّاء؛ فإن كان أحد الطرفين يخالف الإجماع ⇒ عالٍ/متوسط. **`cause` يُحدَّد بحدّ القارئ المعلن** | هندسي `مرجّح` |
| 5 | `numerals-persian` / `numerals-mixed` | دوال `structure` نفسها | قرار المالك (G#4) |
| 6 | `no-text-layer` | كل القرّاء أعادوا فراغًا أو لا محارف عربية، والملف فيه رسم ⇒ **عالٍ** («نصّ غير قابل للنسخ»)، وإلا لا حكم | هندسي |
| 7 | `known-reader-limit` | حدّ قرّاء مُتحقَّق من `limitations.usable` ⇒ يُعلن في `known_limits`، و**لا يرفع `risk` للملف** | `limitations.json` |

**سبب/اتهام:** كل إشارة تحمل `cause: "file" | "reader"`. مثال MuPDF/الأرقام: `reader-disagreement` عالٍ
و`cause = reader` مع `mupdf-ar-digit-reversal`؛ `risk.level` النهائي عالٍ (نسخ المستخدم ينكسر)،
لكن `file_risk` يبقى منخفضًا — وهذا نصّ «لا تُحسب على الملف».

## 5 · العتبات والقياس

`arabic_pdf_check/thresholds.json` — وكل عتبة فيها:

```json
{"presentation_forms": {"value": 0.02, "source": "arafix.DEFAULT_THRESHOLDS (MIT) — قِيس الفصل فكان …",
                        "command": "python3 scripts/checker_measure.py --out docs/checker-v0/measurements",
                        "observed": {"clean_max": 0.0, "planted_min": 1.0}}}
```

- العتبات **حتمية** تُثبَّت صفرًا أو من المصدر المعياري (`missing_unicode > 0` للخط المركّب).
- العتبات **الاحتمالية** (`presentation_forms`, `visual_order`, `disagreement`) تُشتق بالقياس:
  `t = نظيف_max` ويُشترط `planted_min − clean_max ≥ 0.2`؛ وإن لم ينفصل ⇒ الإشارة **تُرفض** ولا تُشحن.
- **لا `--accept` ولا `--force`** في الفاحص: العتبة تُكتب في الملف مع أمرها، ولا تُخفض لتصير خضراء.

## 6 · مجموعات القياس وقبولها

| المجموعة | البناء | القبول |
|---|---|---|
| **مزروعة (4)** | `scripts/checker_fixtures.py` يبني أساسًا نظيفًا بـChrome (عيّنة من المدوّنة) ثم يزرع: (١) أرقام MuPDF، (٢) `chrome-raw` قبل الإصلاح، (٣) أشكال عرض، (٤) خط بلا ToUnicode (pikepdf يحذف المفتاح) | كل واحدة ⇒ `risk=high` وبالإشارة المسمّاة في التكليف |
| **يجب ألّا تُنذر** | المستندات الأربعة (يَبنيها CI) + الحالات الـ65 الناجحة من `conformance run` | إنذار عالٍ = 0 · متوسط = n مُعلن |
| **العالم الحقيقي** | مجلد المالك `PDF_for_PDF` (55 ملفًا، خارج المستودع) | جدول توزيع (إشارة × عدد) بـ`sha256_16` فقط، بلا اسم ملف |

`scripts/checker_measure.py` هو الأمر الوحيد الذي ينتج الجداول والعتبات، ويكتبها في `docs/checker-v0/measurements/`.

## 7 · الخصوصية

- المعالجة في الذاكرة: لا يُكتب الملف، ولا نسخة مؤقتة، ولا نصّه في أي سجل.
- المقتطفات في التقرير فقط، ≤ 80 محرفًا، ≤ 5 لكل قارئ.
- لا مسارات في JSON؛ `sha256` + `bytes` + `pages` فقط.
- في تقرير ملفات المالك: لا أسماء — `sha256_16` كما في `_inventory.csv`.

## 8 · الاختبارات (تُضاف إلى وظيفة CI القائمة)

| الاختبار | ما يثبته |
|---|---|
| `test_isolation.py` | لا قارئ/مقياس/تطبيع خاص بالفاحص (AST + grep) |
| `test_schema.py` | كل تقرير (أعمى ومرجعي) يطابق `report.v1.json` |
| `test_blind.py` | المزروعة الأربع ⇒ عالٍ بالإشارة الصحيحة؛ النظيف ⇒ ليس عاليًا |
| `test_reference.py` | `verify` على حالة مدوّنة = أرقام `certify` نفسها (لا مسار ثانٍ) |
| `test_pages.py` | `pages_many` لكل قارئ يوافق نصّه بعد `N` |
| `test_numbers.py` | عتبة `presentation_forms` مفصولة على المجموعتين، والعتبة المكتوبة = المُشتقة |
| `test_privacy.py` | لا مسار/اسم ملف في JSON؛ المقتطفات ≤80؛ لا كتابة إلى القرص أثناء `check` |

## 9 · التسلسل

1. توثيق المصادر ✅
2. هذه الخطة → مراجعة Claude
3. `conformance` refactor (measure_text, per-font stats, numerals functions, pages_many) + اختباراته
4. `arabic_pdf_check` (blind + reference + report + schema + thresholds)
5. البذور والمجموعات + القياس + العتبات
6. قياس ملفات المالك (خارج التسليم)
7. `code-review-elite` (مقاعد مستقلة) حتى صفر ملاحظات
8. محتوى الفحص البشري: `docs/checker-v0/human-review.html` + التقرير النهائي بالقالب

## 10 · أسئلة لـClaude (تُجاب بالأرقام)

1. **arafix كتبعية**: المبرّر أنه يمنع كاشفًا ثانيًا (قاعدة التكليف)؛ هل تفضل تثبيت `arafix==1.2.0`
   في `requirements.txt` (MIT، نواة بلا تبعيّات) أم نسخ دالة الكشف؟ (أنا: الاستيراد.)
2. **`reference.measure_text`**: هل استخراج القياس من `certify` إلى `conformance/reference.py` كافٍ
   لإثبات «تعميم لا نسخة»، أم ترى أن الشهادة المرجعية يجب أن تكون `certificate/1` نفسه بامتداد نصّ حرّ؟
3. **`pages_many`**: هل إضافتها للقرّاء الخمسة مقبولة، أم تكتفي بمقتطفات على مستوى الملف إن غابت الصفحة؟
4. **الخلاف بين القرّاء**: هل `word_f1` بين كل زوج كافٍ، أم يلزم حكم سطري (سطر بسطر) رغم اختلاف تقسيم الأسطر؟
5. **العتبات**: هل «عتبة = أقصى قيمة في النظيف فعلًا» تُفرط في التخصيص (4 ملفات مزروعة فقط)؟ أيّهما أنسب:
   هامش +0.2، أم اعتماد عتبة المكتبة المصرَّحة (2% / 0.30) ما لم ينفصل القياس؟
6. **المزروعة**: هل بناء الأساس بـChrome (رفض بالاسم إن غاب `CHROME_PATH`) مقبول لاختبار CI،
   أم تريد بديلًا لا يحتاج Chrome (يعني أساسًا صناعيًا لا يمثّل منتجًا حقيقيًا)؟
7. **حدود القرّاء والملف**: هل صياغة `cause` (file/reader) تحقّق «تُعلَن ولا تُحسب على الملف»؟
8. **الأرقام**: أي رموز تعتبرها «نسبة مئوية» ممنوعة في الوضع الأعمى — هل درجة arafix في [-1,1] مقبولة
   داخل `evidence`؟
9. **ما ينقص الخطة**: اذكر أكبر ثلاث مخاطر تراها على القبول (المزروعة/النظيفة/الملفات الـ55).
