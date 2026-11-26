# فحص النسخ العربي — تقرير تشخيصي

**الملف:** `42c038e56fe781d1…` · 12,903 بايت · 1 صفحة
**حكم الملف:** لا حكم — قرأ 3 من 5، والحكم على الملف يحتاج 4 قرّاء
**أعلى خطر لدى قارئ:** عالٍ · السبب: القارئ
**ملاحظة:** لا حكم على الملف؛ الإشارات أدناه تُحسب على أداة النسخ، وثبّت القرّاء الغائبين ليصدر الحكم.

## القرّاء

| القارئ | الإصدار | الخطر | الثقة | الإشارات |
|---|---|---|---|---|
| pdfium | 5.15.2 | عالٍ | عالية | lexical-validity |
| poppler | 26.07.0 | عالٍ | عالية | lexical-validity |
| pdfminer | pdfplumber 0.11.10 · pdfminer.six 20260107 | منخفض | متوسطة | — |

**لم يعمل:** `pdfkit`: RuntimeError: `swift` is not on PATH — PDFKit extraction needs the Swift toolchain (macOS only)؛ `mupdf`: ModuleNotFoundError: optional extra not installed — pip install 'arabic-pdf-check[mupdf]' (PyMuPDF is AGPLv3 or commercial; the shipped checker runs without it)

## إشارات الملف

| الإشارة | المستوى | الثقة | البيان |
|---|---|---|---|
| `tounicode-gaps` | عالٍ | عالية | GeezaPro (/Type0): 244 mapped character(s) to U+0000 (Matterhorn 31-028) |

### إشارات محجوبة عن حكم الملف — محجوب: 3 من 4 قرّاء

| الإشارة | مستوى القارئ | البيان |
|---|---|---|
| `lexical-validity` | عالٍ | 2 of 2 judged readers return Arabic runs that are not Arabic words (pdfium 18 of 60, poppler 22 of 58 runs are in the lexicon) — the letters are shaped, the words do not exist |

## إشارات القرّاء وأمثلة

### pdfium — عالٍ
- `lexical-validity` (عالٍ, القارئ — محجوب عن حكم الملف: 3 من 4): 18 of 60 Arabic run(s) in this reader's text are in the lexicon — the remaining runs are shaped letters that do not make Arabic words
  - ص 1: `ذَا َسَجٰى مَا وَدََّعَك َر ُّكبَ وَمَا`
  - ص 1: `حِي مِ وَالُّضَىحٰ وَالَّل ْيِل ِإ`
  - ص 1: `َّر`
  - ص 1: `ْح َٰنمِ ال`
  - ص 1: `َّر`

### poppler — عالٍ
- `lexical-validity` (عالٍ, القارئ — محجوب عن حكم الملف: 3 من 4): 22 of 58 Arabic run(s) in this reader's text are in the lexicon — the remaining runs are shaped letters that do not make Arabic words
  - ص 1: `ِب ْس ِم اِهَّلل الَّرْح َٰم ِن الَّرِح يِم َوالُّض َح ٰى َوالَّلْيِل ِإَذا َس َ`
  - ص 1: `َقَلٰى َوَلآْل ِخ َرُة َخ ْيٌر َلَك ِم َن اُأْلوَلٰى َوَلَس ْوَف ُيْع ِط يَك َر `
  - ص 1: `ِئ`
  - ص 1: `َيِت يًم ا َفآَوٰى َوَوَج َدَك َض ااًّل َفَهَدٰى َوَوَج َدَك َع ا اًل َفَأْغَنٰى`
  - ص 1: `َوَأَّم ا الَّس اِئ َل َفاَل َتْنَه ْر َوَأَّم ا ِب ِن ْعَم ِة َر ِّبَك َفَح ِّد`

## حدود قرّاء معلنة (تُعلَن ولا تُحسب على الملف)

- `pdfium-rtl-row-order` — pdfium 5.15.2 (مرفوض): pdfium-rtl-row-order: stored control is unreadable ([Errno 2] No such file or directory: '/tmp/br/cache42/controls/c505e0152667e8636b9121fe41dc4e663016fea11031ba679088a24701d20eab.json') — run `arabic-pdf-check controls --refresh`
- `poppler-bidi-decorations` — poppler 26.07.0 (مرفوض): poppler-bidi-decorations: stored control is unreadable ([Errno 2] No such file or directory: '/tmp/br/cache42/controls/fe1f45e92d6963fb14a01efadf6b8bc927d21c8e728a503cf01f7bd029d34574.json') — run `arabic-pdf-check controls --refresh`

## ما لا يعنيه هذا التقرير

- هذا ليس حكم PDF/UA ولا PDF/A، وليس شهادة مطابقة من أي نوع
- لا يُحكم على رسم الحروف: التقرير يقرأ طبقة النص لا الشكل المرئي
- لا OCR: الملف بلا طبقة نصية يُبلَّغ عنه كما هو، ولا يُصلَح
- سلوك قارئ معلن يفسّر خطر ذلك القارئ، ولا يرفع حكم الملف
- خط بسيط بلا /ToUnicode يُعلَن ولا يُنذر (Matterhorn 31-027)؛ خريطته عبر /Encoding أو أسماء المحارف لا تُتحقَّق هنا — قيد معلن، لا حكم
- صحة الكلمات تُحكم على 20 تشكيلة عربية على الأقل في نص القارئ؛ ما دونها لا يُحكم عليه (لا يُعدّ مرورًا ولا فشلًا)
- كثافة انقلاب لام-ألف (لكل 1000 تشكيلة) تُحكم على قراءة تحمل 200 تشكيلة على الأقل وبأغلبية القرّاء؛ الانقلاب المفرد (مستند يقتبس العيب) يُسجَّل ولا يُرفع
- ترتيب المقاطع يُحكم بأغلبية القرّاء: ملف يخزّن الترتيب البصري حقّ لا عيب، وقارئ يعيد ترتيب الكلمات عكس الأغلبية هو الإشارة؛ فإن عكس القرّاء كلهم الترتيب نفسه فلا ناخب يخالف ولا ترفع الإشارة (حدّ معلن)
- الكلمة الموصولة بجاراتها في نصّ القارئ تُعدّ تشكيلة واحدة (لا تُجزَّأ بالمعجم)؛ نصّ كثير الوصل قد يخفض النسبة — لذلك العتبة مشتقة بهامش 0.20 ولا يرفع الحكم إلا فشل الأغلبية
- الأغلبية تُحسب على القرّاء الذين قرؤوا: 3 من 5 للاتجاه، و2 للكلمات — تغيير معلن عن قاعدة المقام المعلن 3 من 5 (ST-5)؛ الجدول المنشور يقيس قلب الأحكام
- حدود القرّاء غير مثبتة في هذه البيئة — شغّل `arabic-pdf-check controls --refresh`

*فاحص النسخ العربي 0.1.0 · `fe1616ac9b8f` · arafix 1.2.0*
