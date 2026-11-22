# التسليم — فاحص النسخ العربي v0

**الفرع:** `feat/checker-v0` · **التزام الكود المدقق:** `37a58a8` (فوق `933daa8` فوق `6b95155` فوق `1ea3335`) ·
**CI:** `Build PDF` تشغيل `44965336529` على `a0763cc` (الذي يحمل `37a58a8` كاملًا) = **success** — وفيه
`MEASUREMENT COMPLETE` و`RATCHET HELD` و`BLIND ACCEPTANCE` والاختبارات الجديدة (`v2-bad-*-is-named` ·
`examples-printable` · `why-class-drops-path`). وقبله success على `933daa8` (`44961747681`) و`b1fdcc6`
(`44959080012`).

**ما هو:** CLI مفتوح المصدر يجيب سؤالًا واحدًا: **أين تنكسر نسخ النصّ العربي من PDF، وفي أي قارئ؟** — بلا
إصلاح، وبلا OCR، وبلا واجهة ويب، وبلا Acrobat. يقرأ الطبقة النصّية وما يعيده خمسة قرّاء (PDFium · PDFKit ·
MuPDF · Poppler · pdfminer)، ويصدر تقريرًا عربيًا (Markdown) وJSON بإصدار مخطّط، أو شهادة `certificate/2`
مقابل نصّ حرّ يقدّمه العميل. كلّه طبقة رقيقة فوق `conformance/`: لا قارئ ولا مقياس ولا تطبيع ثانٍ.

## 1 · المزروعة (كل ملف يجب أن يكون عاليًا بإشارته المسمّاة)

| الملف | الإشارة المتوقعة | إشارات الملف (قياس `planted.json`) | حكم الملف |
|---|---|---|---|
| `planted-mupdf-logical` | `visual-order` | `visual-order` | عالٍ |
| `planted-chrome-raw` | `presentation-forms` | `presentation-forms` | عالٍ |
| `planted-presentation-forms` | `presentation-forms` | `presentation-forms` + `visual-order` | عالٍ |
| `planted-no-tounicode` | `tounicode-gaps` | `tounicode-gaps` + `no-text-layer` | عالٍ |

**4/4 ناجحة** (`scripts/checker_measure.py --write`، `arabic_pdf_check/tests/test_blind.py`). لا PDF
مزروع في المستودع: الملفات يبنيها مولّدها بالـChrome المثبّت.

## 2 · النظيفة (المستندات الأربعة + 66 حالة)

- **70 ملفًا · 0 ملف عالٍ على الملف** (`clean.json: summary.file_high = 0`).
- **64 ملفًا فيها قارئ واحد عالٍ:** `pdfminer` يعيد الترتيب المخزَّن (بصري في ملفات Chrome) — سبب القارئ،
  لا الملف؛ لا يُرفع به حكم الملف. الستة الباقية منخفضة كليًا.
- التغطية: `docs/checker-v0/measurements/clean.json`.

## 3 · ملفات المالك الـ55 (تجميعي فقط — لا اسم ولا مقتطف ولا ملف)

| القياس | القيمة |
|---|---|
| الملفات | 55 (قُرئت كلها، 0 أخطاء) |
| حكم الملف | **38 عالٍ · 1 متوسط · 16 منخفض** |
| `tounicode-gaps` (عدد الإشارات؛ الملف قد يحمل أكثر من واحدة) | 62 |
| `presentation-forms` | 29 |
| `visual-order` | 15 |
| `numerals-mixed` | 3 |
| `no-text-layer` | 1 |
| القرّاء (عالٍ/منخفض) | pdfminer 55/0 · mupdf 30/25 · pdfkit 30/25 · poppler 30/25 · pdfium 14/41 |

**بعد مراجعة المالك (P1):** خط الرموز لا يُرفع (اسمٌ معروف أو كل رموزه PUA)، وفجوة الخريطة عالية **فقط داخل
كلمة**؛ بين الكلمات تحذير يسمّي الـcode (مثلًا Calibri `0x2D` 21/336 — شرطة، لا نص). الأثر المقيس: 41 → 38
عالٍ، و14 → 16 منخفضًا + واحد متوسط، وإشارات `tounicode-gaps` 75 → 62، مع بقاء `presentation-forms 29`
و`visual-order 15` بلا تغيير. التفاصيل والقياس قبل/بعد في `04-review.md` (الجولة الخامسة).

**لا حكم على المجموعة** — قياس فقط؛ التوزيع نفسه هو النتيجة. (المجلد يُقرأ ولا يُكتب؛ ولا شيء منه في git.)

## 4 · المستندات الأربعة والمدوّنة

| المستند | بوابات `verify_pdf.py` | الطفرات |
|---|---|---|
| `guide-v2-ar.pdf` | 39/39 PASS | 63/63 |
| `report.pdf` | 39/39 PASS | 63/63 |
| `najd.pdf` | 39/39 PASS | 58/58 |
| `report-print.pdf` | 39/39 PASS | 55/55 |

**المدوّنة:** `python -m conformance run --engine chrome --ratchet` ⇒ **RATCHET HELD** — 66 حالة × 5 قرّاء،
لا قارئ ولا حالة ولا مقياس تحت أرضيته. و`selftest`: 17 طفرة، **0 مفقودة**.

## 5 · العتبات (تُشتق بالأمر، لا تُكتب بيد)

| العتبة | القيمة | المصدر |
|---|---|---|
| `presentation_forms` | 0.02 | arafix `DEFAULT_THRESHOLDS` (MIT) |
| `visual_order` | 0.30 | arafix `DEFAULT_THRESHOLDS` (MIT) — تُمرَّر إلى `diagnose` |
| `min_arabic_chars` | 8 | arafix (يُعلَن استعمالها المزدوج: حكم الاتجاه + «هل هذا مستند عربي؟») |
| `tounicode_gap_ratio` | 0.01 | `max(declared 0.01, clean_max 0.0)` — فوقه عالٍ، تحته متوسط |
| أغلبية الترتيب | 3 من 5 | **بنيوية** (`len(MATRIX)//2+1`) لا عتبة مقيسة |
| شكل خلاف القرّاء المتري | **مرفوض** | `content_f1` = 0.0 بين قرّاء نظيفين على الحالات القصيرة (`observed.refused`) |
| شهادة قديمة الشكل | تُقبل بلا `confidence/examples` | سُكّت قبل الحقلين (معلن في `certificate.validate`)؛ المُصدِر الحالي لا يكتب ذلك الشكل |

الأمر: `python3 scripts/checker_measure.py --write --out docs/checker-v0/measurements` · القياس المودع يطابق
المشحون (`test_thresholds`)، والكتابة لا تحدث إلا بعد نجاح كل البوابات.

**عتبة من منتِج آخر (P2):** `docs/checker-v0/foreign/` يحمل مصدري HTML يُنتجان بـLibreOffice، و
`scripts/checker_foreign.py` يقيسهما بلا كتابة عتبات: الملفان **ليسا عاليين** (واحد متوسط بفجوة بين كلمات،
وواحد منخفض) — القياس في `measurements/foreign.json`. العتبة **لم تُعَد اشتقاقها**: تنتظر حكم المالك البشري
على الملفات الخمسة ثم تُعاير من المجموعتين.

## 6 · ما تحقّق حيًّا في هذه الجلسة

- **الخبرة عبر Claude:** استشارتان على الخطة (Round 1 + Round 2) — REQUEST CHANGES كلتاهما، محفوظتان في
  `docs/checker-v0/02-claude-round*.md`.
- **أربع جولات مراجعة مستقلّة بثلاثة مقاعد** (Standards · Spec · Structure): على `d78a894`، ثم تدقيق
  إصلاح على `1ea3335`، ثم تحقّق على `6b95155`، ثم توقيع على `933daa8` — وكل ملاحظة أُصلحت أو رُفضت بقياس
  مكتوب: `docs/checker-v0/04-review.md`.
- **مراجعة المالك الخارجية** (`bb21128`): P1 (إنذار رموز التعداد) · P2 (عتبة من منتِج واحد) · P3 (بوابة
  `fonts` وتسمية العدّاد) — أُغلقت في الالتزام التالي؛ الأثر المقيس في §3 أعلاه، وP2 في §5.
- **تشغيل حيّ:** `conformance run --ratchet` (RATCHET HELD) · `selftest` (17/17) · بوابات المستندات
  (39/39 ×4) · كل اختبارات الفاحص وconformance (أدناه).

## 7 · الاختبارات (ما يشغّله CI على هذا الالتزام)

```
arabic_pdf_check/tests: isolation · fonts · thresholds · schema · pages · privacy · reference · blind
conformance/tests: declared · certificate · mcid_text · ratchet · limits · engine_behaviour ·
                   private_keys · a3b_claim · corpus · metrics · isolation
scripts: test_check_kinds (39 checks) · scripts/checker_measure.py --skip-owner · scripts/checker_foreign.py
conformance run --engine chrome --ratchet · conformance selftest
```

## 8 · ما يحتاج المالك (قرارات، لا ملاحظات)

1. **شكل خلاف القرّاء:** الشكل المتري (تشابه نصّي بعتبة) **مرفوض بالقياس**؛ المشحون حتمي (صفحة يعيدها قارئ
   فارغة واثنان يقرآنها). القرار: قبول الحتمي، أو تزويدي بحالة موجبة (كلمتان مختلفتان وكل القرّاء يقرؤون).
2. **`no-text-layer` إشارة سابعة** على الستّ في التكليف (الملف الممسوح لا يُنسخ منه شيء). القرار: تثبيتها
   كإضافة، أو حذفها.
3. **أمثلة الشهادة المرجعية `page: null`:** النصّ الحرّ لا يحمل بنية صفحات؛ أُعلن القيد في `not_checked`.
   القرار: إقراره، أو تزويد النصّ المرجعي بفواصل صفحات.
4. **النشر/الدمج:** الفرع مدفوع، ولم أفتح PR ولم أدمج — الدمج وCI النهائي للمالك.
5. **التحقق البشري (10 دقائق):** خمسة ملفات سُمّيت في المحادثة؛ انسخ صفحة من كلٍّ في Preview وقل: هل ضاع
   نص؟ جوابك هو مرجع P1، وعليه (مع مجموعة LibreOffice) تُعاير `tounicode_gap_ratio` من المجموعتين.

## 9 · ما لم يُثبت

- **حكم النسخ البشري** على الملفات الخمسة لم يحدث بعد — لذلك لا يُعلَن أن إشارات الفجوات كلها صحيحة، ولا أن
  الـ38/16/1 هي «الحكم النهائي» على الكوربوس؛ هي قياس الأداة بعد قواعد جديدة.
- **تعميم العتبة** على منتِجين: عُرضت LibreOffice (ملفان، لا عالٍ) كدليل أولي، لا كافٍ لإعادة اشتقاق.
- **حدود مشتركة معروفة ومعلنة:** PDFium 5.15.2 في صف المفتاح/القيمة، وMuPDF في انعكاس مجرى الأرقام —
  في `limitations.json` بضوابطها. وما عدا ذلك كل رقم أعلى يخرج من أمر مذكور، ومخرجاته في `measurements/`.

## 10 · ما لا يفعله (معلن)

لا OCR · لا إصلاح · لا حكم على رسم الحروف · لا PDF/UA أو PDF/A من هذا الفاحص (الشهادة هي شهادة conformance
حيث تُطلب) · Acrobat خارج المصفوفة · لا تخزين للملف أو النصّ.

## 11 · عيّنات للفحص البشري

- `docs/checker-v0/samples/blind-guide-ar.md` — ملفّنا النظيف: **حكم الملف منخفض**، وpdfminer عالٍ (قارئ).
- `docs/checker-v0/samples/blind-planted-mupdf.md` — المزروع: **عالٍ** بإشارة `visual-order`، 4 من 5 قرّاء.
