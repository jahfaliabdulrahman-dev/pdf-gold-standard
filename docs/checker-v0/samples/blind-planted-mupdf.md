# فحص النسخ العربي — تقرير تشخيصي

**الملف:** `492957995532b107…` · 253,570 بايت · 1 صفحة
**حكم الملف:** عالٍ · **الثقة:** عالية
**أعلى خطر لدى قارئ:** عالٍ · السبب: الملف


## القرّاء

| القارئ | الإصدار | الخطر | الثقة | الإشارات |
|---|---|---|---|---|
| pdfium | 5.15.2 | عالٍ | عالية | visual-order |
| pdfkit | PDFKit 27.2.1 | عالٍ | عالية | visual-order |
| mupdf | 2.1 | عالٍ | عالية | visual-order |
| poppler | 26.11.0 | عالٍ | عالية | visual-order |
| pdfminer | pdfplumber 0.11.10 · pdfminer.six 20260107 | منخفض | متوسطة | — |

## إشارات الملف

| الإشارة | المستوى | الثقة | البيان |
|---|---|---|---|
| `visual-order` | عالٍ | عالية | 4 of 5 declared readers return reversed text — the copied text keeps the opposite order for those readers (the layer itself is not judged as a defect; a visual layer is how most producers store Arabic) |

## إشارات القرّاء وأمثلة

### pdfium — عالٍ
- `visual-order` (عالٍ, الملف): returns reversed text (score +1.00; +1 reversed, −1 logical) — 4 of 5 declared readers return reversed text
  - ص 1: `.لاير 1,250.75 غلبملاو ٢٠٢٦ خيراتلا`
  - ص 1: `.رابتخالل ٍناث يبرع رطس اذه`

### pdfkit — عالٍ
- `visual-order` (عالٍ, الملف): returns reversed text (score +1.00; +1 reversed, −1 logical) — 4 of 5 declared readers return reversed text
  - ص 1: `.لاير 1,250.75 غلبملاو ٢٠٢٦ خيراتلا`
  - ص 1: `.رابتخالل ٍناث يبرع رطس اذه`

### mupdf — عالٍ
- `visual-order` (عالٍ, الملف): returns reversed text (score +1.00; +1 reversed, −1 logical) — 4 of 5 declared readers return reversed text
  - ص 1: `غلبملاو ٦٢٠٢ خيراتلا1,250.75 .لاير`
  - ص 1: `.رابتخالل ٍناث يبرع رطس اذه`

### poppler — عالٍ
- `visual-order` (عالٍ, الملف): returns reversed text (score +1.00; +1 reversed, −1 logical) — 4 of 5 declared readers return reversed text
  - ص 1: `‫‪.‬لاير ‪ 1,250.75‬غلبملاو ‪ ٢٠٢٦‬خيراتلا‬`
  - ص 1: `‫‪.‬رابتخالل ٍناث يبرع رطس اذه‬`

## حدود قرّاء معلنة (تُعلَن ولا تُحسب على الملف)

- `pdfium-rtl-row-order` — pdfium 5.15.2 (مُعاد إنتاجه): PDFium reads an RTL key/value row whose value starts with a Latin letter as value-before-label; the identifier itself is intact. The source declares label-then-value.
- `mupdf-ar-digit-reversal` — mupdf 2.1 (ينطبق): An Arabic-Indic digit run in an RTL context is returned reversed by MuPDF, including on a file MuPDF itself wrote. Measured on the pinned version; the reversal is the reader's, not the file's, because PDFium reads the same file's run correctly.
- `poppler-bidi-decorations` — poppler 26.11.0 (ينطبق): pdftotext wraps every RTL line in U+202A/U+202B … U+202C embedding marks. They are the extractor's own decorations, not characters the file carries: the same file read by PDFium has none. Re-measured on the pinned build 26.11.0 after the reader's supply was pinned; the control runs against the same binary the run measures with.

## ما لا يعنيه هذا التقرير

- هذا ليس حكم PDF/UA ولا PDF/A، وليس شهادة مطابقة من أي نوع
- لا يُحكم على رسم الحروف: التقرير يقرأ طبقة النص لا الشكل المرئي
- لا OCR: الملف بلا طبقة نصية يُبلَّغ عنه كما هو، ولا يُصلَح
- سلوك قارئ معلن يفسّر خطر ذلك القارئ، ولا يرفع حكم الملف

*فاحص النسخ العربي 0.1.0 · `1ea33358d965` · arafix 1.2.0*
