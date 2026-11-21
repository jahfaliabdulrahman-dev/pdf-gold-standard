# خطة `arabic-pdf-check` v0 — النسخة ٢ بعد مراجعة Claude والقياس

> **حالة:** نُفِّذت، مع تغييرين أثبتهما القياس بعد كتابة هذه النسخة: (١) الشكل المتري من `reader-disagreement`
> **رُفض** (أدنى `content_f1` بين قرّاء نظيفين = 0.000) ويشحن الشكل الحتمي وحده؛ (٢) `known_limits`
> يضمّ حدّ PDFium عبر `declared.json` + ضابط حيّ. التفاصيل في `03-implementation.md`.

**ما تغيّر:** كل بند أدناه مقيس على `502ebf0` بهذه الأوامر (نُفِّذت فعلًا في ٢١ نوفمبر).

## 0 · ما كشفه القياس (يغيّر التصميم)

| القياس | النتيجة | الأثر |
|---|---|---|
| `arafix.diagnose` على طبقة نصّ المستندات الأربعة | `order_score ≈ +0.99` (بصري) | **الطبقة المخزَّنة بصرية في مستنداتنا النظيفة** (كاتب Chrome) — لا يجوز أن تكون إشارة على الملف |
| القرّاء على المستندات الأربعة | pdfium/pdfkit/mupdf/poppler ≈ −0.99 (منطقي) · **pdfminer +0.99** | إشارة الترتيب **لكل قارئ**، لا للملف. pdfminer يعيد ترتيب المخزَّن |
| ملف كتبه MuPDF (نصّ منطقي) | الطبقة −1.00 · pdfium/pdfkit/mupdf/poppler **+1.00** · pdfminer −1.00 | المزروعة الأولى تُكشف بـ`visual-order`؛ وانعكاس الأرقام في MuPDF حدّ قارئ (reference) |
| `content_f1` بين كل زوج على النظيف | أدنى قيمة **0.704** (mupdf/poppler) | عتبة الخلاف تُشتق من أرضية الضجيج: عالٍ < 0.50، متوسط < 0.60 |
| `same_words` صفحة بصفحة (قارئ ↔ طبقة) | 1–5 من 12/17 | **لا يصلح** إشارةً؛ تقطيع MCID يغيّر حدود الكلمات |
| حدّ PDFium (صف مفتاح/قيمة) | مُقاس ومُعلن في `docs/engine-bakeoff/10-g5-identifiers.md` §3b (PDFium 5.15.2) | يُعلن في `known_limits` بمصدره؛ لا يُضاف إلى `limitations.json` لأنه لا يُعفي نقصًا في مقياس |
| عدد الحالات | `manifest.derive()["total"] == 66` | يُقرأ من الملف، لا يُكتب |

**النتيجة المعمارية:** `risk` ثلاث طبقات:
`file` (إشارات الملف فقط) · `readers.*` (لكل قارئ، بحدوده المعلنة) · `overall` = الأقصى مع `causes`.
التكليف «لا تُحسب على الملف» يُحقَّق حرفيًا: `file.level` لا يتأثر بحدّ قارئ، و`readers.*.risk` يقول للمستخدم
أي أداة تكسر نسخه.

## 1 · التغييرات في `conformance/` (نُفِّذت)

| # | التغيير | الحالة |
|---|---|---|
| 1 | `conformance/reference.py::measure_text(pdf, truth)` — مسار قياس واحد | ✅ |
| 2 | `certificate.certify` يستهلكه (لا حلقة ثانية) | ✅ |
| 3 | `mcid_text.scan` عدّادات لكل خط: `codes/notdef/missing_unicode/pua/replacement/zero_value/bom` بمفتاح `name|family` | ✅ |
| 4 | `structure.persian_digits` + `structure.content_f1` | ✅ |
| 5 | `readers.*.pages_many` للخمسة + `pdfkit_text.swift` يعيد `pages` (تحقق: `N-join == N(text)` للخمسة على `tests/vocalised_raw.pdf`) | ✅ |
| 6 | يُضاف: `conformance/checks/visual_order.py` (غلاف arafix) | قيد التنفيذ |
| 7 | يُضاف: `structure.file_checks(pdf, scan, producer)` مفصولة عن فحوص الحالة | قيد التنفيذ |

## 2 · الواجهة

```
python3 -m arabic_pdf_check check  FILE.pdf [-o OUT.json] [--md OUT.md]
python3 -m arabic_pdf_check verify FILE.pdf --truth TEXT.txt [-o OUT.json] [--md OUT.md]
python3 -m arabic_pdf_check manifest
```
`pyproject.toml` يضيف console script `arabic-pdf-check`. **حُذف `--gate` و`--readers`** (خطر إخفاء إشارة).

## 3 · الإشارات

| id | على ماذا | القاعدة | cause |
|---|---|---|---|
| `tounicode-gaps` | الملف (per font) | Type0 بلا ToUnicode / ثغرات / PUA / FFFD / 0000 / FEFF / notdef ⇒ عالٍ. خط بسيط بلا ToUnicode = استثناء Matterhorn 31-027 يُعلن ولا يُنذر | file |
| `presentation-forms` | الملف + كل قارئ | نسبة أشكال العرض > العتبة ⇒ عالٍ | file (الطبقة) / reader |
| `visual-order` | كل قارئ | `visual_order.score > 0.30` (عتبة arafix المصرَّحة) ⇒ عالٍ؛ الثقة من `defect_confidence` | reader |
| `reader-disagreement` | كل قارئ | `content_f1` الأدنى مع بقية القرّاء < 0.50 ⇒ عالٍ، < 0.60 ⇒ متوسط؛ صفحة فارغة عند قارئ وغير فارغة عند اثنين ⇒ عالٍ حتمي | reader إن وُجد إجماع (زوج ≥0.9)، وإلا file |
| `numerals-persian` / `numerals-mixed` | الملف + كل قارئ | دوال `structure` نفسها | file / reader |
| `no-text-layer` | الملف | كل القرّاء بلا محارف عربية والملف غير فارغ ⇒ عالٍ (نصّ غير قابل للنسخ) | file |
| `known-reader-limit` | — | تُعلن في `known_limits`؛ لا ترفع `file.risk` | reader |

**حدّ PDFium للنموذج:** يُعلن في `known_limits` بالنصّ المقاس من G#5b ومصدره، ولا يدخل حساب خطر الملف.

## 4 · الوضع المرجعي = `certificate/2`

- `source`: `{"kind":"case", …}` أو `{"kind":"text","sha256":…,"chars":…}` بدل `corpus` المُلزَم.
- نفس `certificate.decide` — لا قاعدة ثانية. الأرضيات تُطبَّق حين تكون الحالة معروفة؛ النصّ الحرّ بلا أرضيات.
- `checks`: الفحوص المستقلة عن الحالة (markinfo, lang, private-keys, tagged, all-text-tagged, notdef,
  invisible-format, presentation-forms, tounicode-coverage, numerals-*)؛ وفحوص الحالة في `not_checked` بالسبب.
- `validate` يقبل `certificate/1` و`certificate/2`؛ و`--recheck` لنصّ حرّ يطلب `--truth` وإلا رفض بالاسم.

## 5 · العتبات

`max(العتبة المصرَّحة, أقصى قيمة في النظيف)`، والقياس يُثبت **الفصل** فقط (فاصل ≥ 0.2)؛
وإن لم ينفصل ⇒ الإشارة تُرفض ولا تُشحن. كل عتبة في `manifest.json` مع الأمر الذي أنتجها.

## 6 · مجموعات القياس والقبول

| المجموعة | القبول |
|---|---|
| المزروعة الأربع | `overall.risk == high` + الإشارة: (١) `visual-order` [مقيس: 4 قرّاء +1.00]، (٢) `visual-order`+`presentation-forms` من `chrome-raw`، (٣) `presentation-forms`، (٤) `tounicode-gaps` |
| النظيفة (4 مستندات + 66 حالة) | `file.risk != high` لكل ملف؛ وكل `readers.*.risk == high` مُفسَّر بسلوك مقيس (pdfminer/الترتيب) ويُعدّ ويُعلن |
| ملفات المالك 55 | جدول تجميعي فقط (إشارة × عدد) بلا مقتطفات وبلا أسماء؛ JSON بلا محارف عربية |

## 7 · الاختبارات

`test_isolation` (لا قارئ/مقياس/arafix خارج conformance) · `test_schema` · `test_blind` (المزروعة/النظيفة) ·
`test_reference` (أرقام `verify` = أرقام `certify` على حالة) · `test_pages` · `test_thresholds` (المكتوب = المشتق) ·
`test_markdown` (لا `PASS`/`%`، والقرّاء الغائبون مذكورون) · `test_privacy` (لا كتابة قرص، لا مسار في JSON).

## 8 · أسئلة عاجلة لـClaude

1. `visual-order` على **الطبقة**: قياسنا يقول إن مستنداتنا النظيفة طبقتها بصرية؛ فهل توافق أن الإشارة على القرّاء فقط،
   وأن بصريّة الطبقة تُعلن كخاصية منتِج لا كعيب؟ (بديلك P0-2 يقتضي ذلك.)
2. المزروعة الأولى: هل يكفي أن نسمّي إشارتها `visual-order` (cause=reader) مع إعلان أن الملف يخزّن منطقيًا،
   أم تريد إشارة سابعة لـ«الملف يخزّن ترتيبًا لا يوافق ما يعيده ٤ من ٥ قرّاء»؟
3. `content_f1` أرضية الضجيج 0.704 — عتبة 0.50/0.60 مقبولة؟ وهل صفحة-فارغة-حتمية تُغني عن العتبة؟
4. `certificate/2` بـ`source` مقابل تعديل `certificate/1` — أيّهما أقل كسرًا لعقود موجودة؟
5. هل `known_limits` بلا `limitations.json` (حدّ PDFium) مقبول إن ذُكر المصدر والقياس، أم تريد ملف تحكّم جديدًا؟
