# فحص النسخ العربي — تقرير تشخيصي

**الملف:** `10af891fe838c972…` · 1,790,793 بايت · 12 صفحة
**حكم الملف:** منخفض · **الثقة:** متوسطة
**أعلى خطر لدى قارئ:** عالٍ · السبب: قارئ
**ملاحظة:** إشارات القرّاء أدناه تُحسب على أداة النسخ، لا على الملف.

## القرّاء

| القارئ | الإصدار | الخطر | الثقة | الإشارات |
|---|---|---|---|---|
| pdfium | 5.15.2 | منخفض | متوسطة | — |
| pdfkit | PDFKit 27.2.1 | منخفض | متوسطة | — |
| mupdf | 2.1 | منخفض | متوسطة | — |
| poppler | 26.11.0 | منخفض | متوسطة | — |
| pdfminer | pdfplumber 0.11.10 · pdfminer.six 20260107 | عالٍ | عالية | visual-order |

## إشارات الملف

لا إشارة على الملف: غطاء ToUnicode مكتمل، ولا أشكال عرض، ولا أرقام مخالفة.

## إشارات القرّاء وأمثلة

### pdfminer — عالٍ
- `visual-order` (عالٍ, القارئ): returns reversed text (score +0.99; +1 reversed, −1 logical) — 1 of 5 declared readers return reversed text
  - ص 1: `GOLD STANDARD · يسسؤملا جاتنإلا رايعم`
  - ص 1: `تافلم جاتنإ رايعم`
  - ص 1: `— ةحفص دعب ةحفص يعجرم يبرع ليلد قمعأ كيكفت دعب`
  - ص 1: `.لماك يبرع معدو ،يبناج سرهف ،لقنت رارزأ :ةيلعافتلا تادنتسملل دحوم جاتنإ ماظن`
  - ص 1: `ةيلآ ميلست ةباوب تايوتسم ةثالثب يبناج سرهف ةمئاد لقنت رارزأ`

## حدود قرّاء معلنة (تُعلَن ولا تُحسب على الملف)

- `pdfium-rtl-row-order` — pdfium 5.15.2 (مُعاد إنتاجه): PDFium reads an RTL key/value row whose value starts with a Latin letter as value-before-label; the identifier itself is intact. The source declares label-then-value.
- `mupdf-ar-digit-reversal` — mupdf 2.1 (ينطبق): An Arabic-Indic digit run in an RTL context is returned reversed by MuPDF, including on a file MuPDF itself wrote. Measured on the pinned version; the reversal is the reader's, not the file's, because PDFium reads the same file's run correctly.
- `poppler-bidi-decorations` — poppler 26.11.0 (ينطبق): pdftotext wraps every RTL line in U+202A/U+202B … U+202C embedding marks. They are the extractor's own decorations, not characters the file carries: the same file read by PDFium has none. Re-measured on the pinned build 26.11.0 after the reader's supply was pinned; the control runs against the same binary the run measures with.

## ما لا يعنيه هذا التقرير

- هذا ليس حكم PDF/UA ولا PDF/A، وليس شهادة مطابقة من أي نوع
- لا يُحكم على رسم الحروف: التقرير يقرأ طبقة النص لا الشكل المرئي
- لا OCR: الملف بلا طبقة نصية يُبلَّغ عنه كما هو، ولا يُصلَح
- سلوك قارئ معلن يفسّر خطر ذلك القارئ، ولا يرفع حكم الملف
- خط بسيط بلا /ToUnicode يُعلَن ولا يُنذر (Matterhorn 31-027)؛ خريطته عبر /Encoding أو أسماء المحارف لا تُتحقَّق هنا — قيد معلن، لا حكم
- صحة الكلمات تُحكم على 20 تشكيلة عربية على الأقل في نص القارئ؛ ما دونها لا يُحكم عليه (لا يُعدّ مرورًا ولا فشلًا)
- الكلمة الموصولة بجاراتها في نصّ القارئ تُعدّ تشكيلة واحدة (لا تُجزَّأ بالمعجم)؛ نصّ كثير الوصل قد يخفض النسبة — لذلك العتبة مشتقة بهامش 0.20 ولا يرفع الحكم إلا فشل الأغلبية

*فاحص النسخ العربي 0.1.0 · `ca4156a61f68` · arafix 1.2.0*
