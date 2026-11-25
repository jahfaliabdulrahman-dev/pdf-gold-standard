# PR-3 — ZATCA PDF-A3: هل العيب في طبقة نص الملف أم في القارئ؟

**الدليل الخام المودع:** `docs/checker-v0/measurements/pr3/zatca-forensics.json` — 16 ملفًا، نسخ كل قارئ، وعدّادات `pf_file`/`pf_reader`/`missing_unicode`.

قياس آلي على 16 ملف PDF/A-3 من عيّنات ZATCA (المنتِج iText 7.1.16 في الستة عشر). لا OCR، ولا تعديل في المستودع، ولا استدعاء حكم على قارئ واحد: كل إشارة تُقرأ بثلاثة مستويات — ما تقوله طبقة الملف نفسها، وما يفعله كل قارئ من الخمسة، ثم الأغلبية.

## الطبعات والأمر

- القياس على `5e6b258` (الشجرة كانت مشغولة بعمل آخر)، و`git diff --stat` بينه وبين `dcf0c60` في `arabic_pdf_check/` و`conformance/` = `thresholds.json` وحده. وأُعيد تشغيل الفاحص على الستة عشر عند الأخير: كل الكتل المقارنة (signals, risk, majority, fonts, readers) متطابقة.
- الفاحص: `python -m arabic_pdf_check check <file> -o /tmp/pr3/check/<i>.json` — العتبات من `arabic_pdf_check/thresholds.json` (sha256 عند القياس `857b8dc83be2f54e…`): presentation-forms 0.02 · visual-order 0.30 · tounicode_gap_ratio 0.01 · lexical 0.67/20.
- **تغيّر متزامن:** ملف العتبات تغيّر في الشجرة أثناء الجولة ثم دخل التزامًا: sha256 الحالي `5d41fb5df467656f…` — والقيم الستّ الرقمية التي حكم بها الفاحص لم تتغيّر (مقارنةً باللقطة المحفوظة في `/tmp/pr3/meta.json`).
- القرّاء ونسخهم: pdfium `5.15.2` · pdfkit `PDFKit 27.2.1` · mupdf `2.1` · poppler `26.11.0` · pdfminer `pdfplumber 0.11.10 · pdfminer.six 20260107`.
- الطبقة تُقرأ بـ`conformance.checks.mcid_text.scan` (نفس قارئ ToUnicode الذي يستعمله الفاحص)، والاتجاه بـ`conformance.checks.visual_order.inspect` (arafix)، والعدّ بـ`conformance.checks.metrics`.
- العمليات المسجَّلة في الشجرة أثناء القياس (عمل آخر، لا من هذه الجولة، وذهب بالتزام لاحق): ` M .github/workflows/build-pdf.yml`, ` M arabic_pdf_check/thresholds.json`, ` M docs/checker-v0/08-pr2-evidence-2026-11-24.md`, ` M docs/checker-v0/measurements/calibration.json`, ` M docs/checker-v0/measurements/pr2/clean.json`, ` M docs/checker-v0/measurements/pr2/owner.json`, ` M docs/checker-v0/measurements/pr2/planted.json`, ` M docs/checker-v0/measurements/pr2/thresholds.json`, ` M scripts/checker_measure.py`, `?? IDEA.md`, `?? docs/checker-v0/measurements/pr2/signal-separation.json`, `?? scripts/signal_separation.py`, `?? scripts/test_calibration.py`.

## الحكم المختصر

| الإشارة | على مستوى الملف | التصنيف | أصوات القرّاء (16 ملفًا) |
|---|---|---|---|
| presentation-forms | **11/16 بالأغلبية (4 من 5) · 16/16 على مستوى طبقة الملف** | واقعي في 16 — حكم الأغلبية يتحقق في 11 فقط | pdfium 0/16 · pdfkit 11/16 · mupdf 11/16 · poppler 11/16 · pdfminer 16/16 |
| visual-order | **0/16** | خاص بالقارئ في 16 | pdfium 5/16 · pdfkit 0/16 · mupdf 0/16 · poppler 0/16 · pdfminer 16/16 |
| tounicode-gaps | **0/16** | نفي صحيح (لا فجوة) في 16 | رسم 33264 كودًا · مفقود 0 · notdef 0 · PUA 0 |

**قراءة الحكم:** من الإشارات الثلاث، عيب واحد يخصّ الملف في هذه العيّنة — خريطة ToUnicode تسمّي محارف العرض (U+FExx) بدل الحروف. **ودرجة الحكم تختلف بحسب المعيار، وهذا فرق يجب أن يُقرأ:** الخريطة نفسها تسمّي محارف عرض في **16/16** (طبقة الملف)، وأما **أغلبية القرّاء** (4 من 5) فتُظهرها في **11/16** فقط؛ وفي الخمسة الباقية (9، 11، 12، 13، 14) لا تبلغ الإشارة أغلبية: pdfminer ينسخ المحارف كلها، وpdfkit ينسخ بعضها لا كلها، وmupdf/poppler يُخرجون حروفًا أساسية. وإشارة الاتجاه ليست عيب ملف بل سلوك قارئين (pdfminer يعكس الحروف في 16/16، pdfium يقلب أسطرًا مختلطة في 11 ويعكس الحروف في 5) لأن ثلاثة من خمسة يقرؤون الترتيب المنطقي؛ وإشارة فجوات ToUnicode لا تطلق لأن الفجوة صفر قياسًا.

**ارتباط مقيس (أُضيف في تصحيح ٢٥ نوفمبر):** الخمسة التي يعكس فيها pdfium الحروف هي **نفسها** مجموعة خطوط Type3، ونفسها الخمسة الغائب عنها `/AF` — ثلاث مجموعات متطابقة (9، 11–14)، لا ثلاث مصادفات. فحيث تكون الخطوط Type3: (أ) يعكس pdfium الحروف، (ب) يقرأ pdfminer وحده محارف العرض، (ج) لا يوجد `/AF`. الارتباط مقيس، وتفسيره غير مثبت (مذكور في «ما لم يُثبت»).

التصنيفات المستعملة: **واقعي** (العيب في طبقة الملف) · **خاص بالقارئ** (سلوك قارئ لا عيب ملف) · **إيجاب كاذب** (قاعدة تطلق على ملف سليم) · **غير مثبت** (لا دليل كافٍ) · **نفي صحيح** (الإشارة لم تطلق والعيب غائب بالقياس).

## النسخ الفعلي — أول سطر عربي في الصفحة 1، من القرّاء الخمسة

| # | pdfium | pdfkit | mupdf | poppler | pdfminer |
|---|---|---|---|---|---|
| 1 | p1 «Tax invoice ضريبية فاتورة» | p1 «ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice» | p1 «Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ» | p1 «Tax invoice \u202bﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ\u202c» | p1 «Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 2 | p1 «Tax invoice ضريبية فاتورة» | p1 «ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice» | p1 «Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ» | p1 «Tax invoice \u202bﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ\u202c» | p1 «Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 3 | p1 «Tax invoice ضريبية فاتورة» | p1 «ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice» | p1 «Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ» | p1 «Tax invoice \u202bﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ\u202c» | p1 «Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 4 | p1 «Credit Note دائن إشعار» | p1 «إﺷﻌﺎر داﺋﻦ Credit Note» | p1 «Credit Note إﺷﻌﺎر داﺋﻦ» | p1 «Credit Note \u202bإﺷﻌﺎر داﺋﻦ\u202c» | p1 «Credit Note ﻦﺋاد رﺎﻌﺷإ» |
| 5 | p1 «Tax invoice ضريبية فاتورة» | p1 «ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice» | p1 «Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ» | p1 «Tax invoice \u202bﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ\u202c» | p1 «Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 6 | p1 «Tax invoice ضريبية فاتورة» | p1 «ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice» | p1 «Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ» | p1 «Tax invoice \u202bﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ\u202c» | p1 «Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 7 | p1 «Simplified Tax invoice مبسطة ضريبية فاتورة» | p1 «ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ Simplified Tax invoice» | p1 «Simplified Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ» | p1 «\u202bﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ \u202aSimplified Tax invoice\u202c\u202c» | p1 «Simplified Tax invoice ﺔﻄﺴﺒﻣ ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 8 | p1 «Tax invoice ضريبية فاتورة» | p1 «ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice» | p1 «Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ» | p1 «Tax invoice \u202bﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ\u202c» | p1 «Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 9 | p1 «Self Billed tax invoice ةيبيرض ةيتاذ فاتورة» | p1 «فاتورة ذاتية ضريبية Self Billed tax invoice» | p1 «Self Billed tax invoice فاتورة ذاتية ضريبية» | p1 «Self Billed tax invoice \u202bفاتورة ذاتية ضريبية\u202c» | p1 «Self Billed tax invoice ﺔﻴﺒﻳﺮﺿ ﺔﻴﺗاذ ةرﻮﺗﺎﻓ» |
| 10 | p1 «Simplified Tax invoice مبسطة ضريبية فاتورة» | p1 «ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ Simplified Tax invoice» | p1 «Simplified Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ» | p1 «\u202bﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ ﻣﺒﺴﻄﺔ \u202aSimplified Tax invoice\u202c\u202c» | p1 «Simplified Tax invoice ﺔﻄﺴﺒﻣ ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 11 | p1 «Simplified Tax invoice ةطسبم ةيبيرض فاتورة» | p1 «فاتورة ضريبية مبسطة Simplified Tax invoice» | p1 «Simplified Tax invoice فاتورة ضريبية مبسطة» | p1 «\u202bفاتورة ضريبية مبسطة \u202aSimplified Tax invoice\u202c\u202c» | p1 «Simplified Tax invoice ﺔﻄﺴﺒﻣ ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 12 | p1 «Credit Note نئاد إشعار» | p1 «إشعار دائن Credit Note» | p1 «Credit Note إشعار دائن» | p1 «Credit Note \u202bإشعار دائن\u202c» | p1 «Credit Note ﻦﺋاد رﺎﻌﺷإ» |
| 13 | p1 «Debit Note نيدم إشعار» | p1 «إشعار مدين Debit Note» | p1 «Debit Note إشعار مدين» | p1 «Debit Note \u202bإشعار مدين\u202c» | p1 «Debit Note ﻦﻳﺪﻣ رﺎﻌﺷإ» |
| 14 | p1 «Tax invoice ةيبيرض فاتورة» | p1 «فاتورة ضريبية Tax invoice» | p1 «Tax invoice فاتورة ضريبية» | p1 «Tax invoice \u202bفاتورة ضريبية\u202c» | p1 «Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 15 | p1 «Tax invoice ضريبية فاتورة» | p1 «ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice» | p1 «Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ» | p1 «Tax invoice \u202bﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ\u202c» | p1 «Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |
| 16 | p1 «Tax invoice ضريبية فاتورة» | p1 «ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ Tax invoice» | p1 «Tax invoice ﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ» | p1 «Tax invoice \u202bﻓﺎﺗﻮرة ﺿﺮﻳﺒﻴﺔ\u202c» | p1 «Tax invoice ﺔﻴﺒﻳﺮﺿ ةرﻮﺗﺎﻓ» |

علامات poppler الظاهرة `\u202b`/`\u202c` هي RLE/PDF من pdftotext نفسه (معلنة في `conformance/readers/limitations.json: poppler-bidi-decorations`)، لا محارف في الملف. والعلامة `[PF]`/`[base]` في الجداول تُقاس على السطر المعروض نفسه: هل يحمل محارف عرض أم حروفًا أساسية.

## 1) presentation-forms — 11/16 بالأغلبية، 16/16 على مستوى طبقة الملف

| # | الإشارة | على مستوى الملف؟ | أصوات القرّاء | النسخ الفعلي (ص1) | التصنيف | السبب |
|---|---|---|---|---|---|---|
| 1 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «ضريبية»[base] · pdfkit «ﻓﺎﺗﻮرة»[PF] · mupdf «ﻓﺎﺗﻮرة»[PF] · poppler «ﻓﺎﺗﻮرة»[PF] · pdfminer «ﺔﻴﺒﻳﺮﺿ»[PF] | **واقعي** | 839 من 1035 محرفًا (0.811) محارف عرض في الطبقة |
| 2 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «ضريبية»[base] · pdfkit «ﻓﺎﺗﻮرة»[PF] · mupdf «ﻓﺎﺗﻮرة»[PF] · poppler «ﻓﺎﺗﻮرة»[PF] · pdfminer «ﺔﻴﺒﻳﺮﺿ»[PF] | **واقعي** | 812 من 1003 محرفًا (0.810) محارف عرض في الطبقة |
| 3 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «ضريبية»[base] · pdfkit «ﻓﺎﺗﻮرة»[PF] · mupdf «ﻓﺎﺗﻮرة»[PF] · poppler «ﻓﺎﺗﻮرة»[PF] · pdfminer «ﺔﻴﺒﻳﺮﺿ»[PF] | **واقعي** | 812 من 1003 محرفًا (0.810) محارف عرض في الطبقة |
| 4 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «دائن»[base] · pdfkit «إﺷﻌﺎر»[PF] · mupdf «إﺷﻌﺎر»[PF] · poppler «إﺷﻌﺎر»[PF] · pdfminer «ﻦﺋاد»[PF] | **واقعي** | 481 من 627 محرفًا (0.767) محارف عرض في الطبقة |
| 5 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «ضريبية»[base] · pdfkit «ﻓﺎﺗﻮرة»[PF] · mupdf «ﻓﺎﺗﻮرة»[PF] · poppler «ﻓﺎﺗﻮرة»[PF] · pdfminer «ﺔﻴﺒﻳﺮﺿ»[PF] | **واقعي** | 683 من 855 محرفًا (0.799) محارف عرض في الطبقة |
| 6 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «ضريبية»[base] · pdfkit «ﻓﺎﺗﻮرة»[PF] · mupdf «ﻓﺎﺗﻮرة»[PF] · poppler «ﻓﺎﺗﻮرة»[PF] · pdfminer «ﺔﻴﺒﻳﺮﺿ»[PF] | **واقعي** | 692 من 863 محرفًا (0.802) محارف عرض في الطبقة |
| 7 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «مبسطة»[base] · pdfkit «ﻓﺎﺗﻮرة»[PF] · mupdf «ﻓﺎﺗﻮرة»[PF] · poppler «ﻓﺎﺗﻮرة»[PF] · pdfminer «ﺔﻄﺴﺒﻣ»[PF] | **واقعي** | 386 من 485 محرفًا (0.796) محارف عرض في الطبقة |
| 8 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «ضريبية»[base] · pdfkit «ﻓﺎﺗﻮرة»[PF] · mupdf «ﻓﺎﺗﻮرة»[PF] · poppler «ﻓﺎﺗﻮرة»[PF] · pdfminer «ﺔﻴﺒﻳﺮﺿ»[PF] | **واقعي** | 694 من 880 محرفًا (0.789) محارف عرض في الطبقة |
| 9 | presentation-forms | نعم — high | 1/5 (pdfminer) | pdfium «ةيبيرض»[base] · pdfkit «فاتورة»[base] · mupdf «فاتورة»[base] · poppler «فاتورة»[base] · pdfminer «ﺔﻴﺒﻳﺮﺿ»[PF] | **واقعي** | 648 من 817 محرفًا (0.793) محارف عرض في الطبقة |
| 10 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «مبسطة»[base] · pdfkit «ﻓﺎﺗﻮرة»[PF] · mupdf «ﻓﺎﺗﻮرة»[PF] · poppler «ﻓﺎﺗﻮرة»[PF] · pdfminer «ﺔﻄﺴﺒﻣ»[PF] | **واقعي** | 451 من 571 محرفًا (0.790) محارف عرض في الطبقة |
| 11 | presentation-forms | نعم — high | 1/5 (pdfminer) | pdfium «ةطسبم»[base] · pdfkit «فاتورة»[base] · mupdf «فاتورة»[base] · poppler «فاتورة»[base] · pdfminer «ﺔﻄﺴﺒﻣ»[PF] | **واقعي** | 445 من 557 محرفًا (0.799) محارف عرض في الطبقة |
| 12 | presentation-forms | نعم — high | 1/5 (pdfminer) | pdfium «نئاد»[base] · pdfkit «إشعار»[base] · mupdf «إشعار»[base] · poppler «إشعار»[base] · pdfminer «ﻦﺋاد»[PF] | **واقعي** | 719 من 926 محرفًا (0.776) محارف عرض في الطبقة |
| 13 | presentation-forms | نعم — high | 1/5 (pdfminer) | pdfium «نيدم»[base] · pdfkit «إشعار»[base] · mupdf «إشعار»[base] · poppler «إشعار»[base] · pdfminer «ﻦﻳﺪﻣ»[PF] | **واقعي** | 723 من 926 محرفًا (0.781) محارف عرض في الطبقة |
| 14 | presentation-forms | نعم — high | 1/5 (pdfminer) | pdfium «ةيبيرض»[base] · pdfkit «فاتورة»[base] · mupdf «فاتورة»[base] · poppler «فاتورة»[base] · pdfminer «ﺔﻴﺒﻳﺮﺿ»[PF] | **واقعي** | 693 من 872 محرفًا (0.795) محارف عرض في الطبقة |
| 15 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «ضريبية»[base] · pdfkit «ﻓﺎﺗﻮرة»[PF] · mupdf «ﻓﺎﺗﻮرة»[PF] · poppler «ﻓﺎﺗﻮرة»[PF] · pdfminer «ﺔﻴﺒﻳﺮﺿ»[PF] | **واقعي** | 643 من 815 محرفًا (0.789) محارف عرض في الطبقة |
| 16 | presentation-forms | نعم — high | 4/5 (pdfkit, mupdf, poppler, pdfminer) | pdfium «ضريبية»[base] · pdfkit «ﻓﺎﺗﻮرة»[PF] · mupdf «ﻓﺎﺗﻮرة»[PF] · poppler «ﻓﺎﺗﻮرة»[PF] · pdfminer «ﺔﻴﺒﻳﺮﺿ»[PF] | **واقعي** | 621 من 785 محرفًا (0.791) محارف عرض في الطبقة |

### الوقائع البنيوية: خريطة كل خط

«رسم» = ما رسمه الخط فعلًا، «مدخلات» = مداخل ToUnicode، «PF» = مدخلات تسمّي U+FExx، «مرسوم PF» = محارف عرض ناتجة عن الرسم. العمود الأخير: missing/notdef/PUA.

| # | الخط | النوع | رسم | مدخلات | PF | مرسوم PF | missing/notdef/PUA |
|---|---|---|---|---|---|---|---|
| 1 | `/F5` Somar-SemiBold | /Type0 | 681 | 83 | 39 | 234 | 0/0/0 |
| 1 | `/F7` SSTArabic-Medium | /Type0 | 1903 | 130 | 53 | 605 | 0/0/0 |
| 2 | `/F5` Somar-SemiBold | /Type0 | 681 | 83 | 39 | 234 | 0/0/0 |
| 2 | `/F7` SSTArabic-Medium | /Type0 | 1827 | 130 | 53 | 578 | 0/0/0 |
| 3 | `/F5` Somar-SemiBold | /Type0 | 681 | 83 | 39 | 234 | 0/0/0 |
| 3 | `/F7` SSTArabic-Medium | /Type0 | 1829 | 130 | 53 | 578 | 0/0/0 |
| 4 | `/F5` Somar-SemiBold | /Type0 | 715 | 94 | 47 | 210 | 0/0/0 |
| 4 | `/F7` SSTArabic-Medium | /Type0 | 973 | 113 | 51 | 271 | 0/0/0 |
| 5 | `/F5` Somar-SemiBold | /Type0 | 796 | 88 | 42 | 278 | 0/0/0 |
| 5 | `/F7` SSTArabic-Medium | /Type0 | 1478 | 124 | 51 | 405 | 0/0/0 |
| 6 | `/F5` Somar-SemiBold | /Type0 | 761 | 85 | 41 | 262 | 0/0/0 |
| 6 | `/F7` SSTArabic-Medium | /Type0 | 1395 | 125 | 52 | 430 | 0/0/0 |
| 6 | `/F9` TimesNewRomanPS-BoldMT | /Type0 | 2 | 1 | 0 | 0 | 0/0/0 |
| 7 | `/F5` Somar-SemiBold | /Type0 | 433 | 80 | 37 | 145 | 0/0/0 |
| 7 | `/F7` SSTArabic-Medium | /Type0 | 834 | 108 | 48 | 241 | 0/0/0 |
| 8 | `/F5` Somar-SemiBold | /Type0 | 761 | 85 | 41 | 265 | 0/0/0 |
| 8 | `/F7` SSTArabic-Medium | /Type0 | 1494 | 129 | 53 | 429 | 0/0/0 |
| 9 | `/F5` Somar-SemiBold | /Type0 | 601 | 78 | 35 | 206 | 0/0/0 |
| 9 | `/F6` Somar-SemiBold | /Type0 | 98 | 44 | 16 | 31 | 0/0/0 |
| 9 | `/F7` SSTArabic-Medium | /Type3 | 52 | 10 | 0 | 0 | 0/0/0 |
| 9 | `/F10` SSTArabic-Medium | /Type3 | 496 | 57 | 0 | 0 | 0/0/0 |
| 9 | `/F11` SSTArabic-Medium | /Type3 | 324 | 47 | 47 | 324 | 0/0/0 |
| 9 | `/F12` SSTArabic-Medium | /Type0 | 60 | 1 | 0 | 0 | 0/0/0 |
| 9 | `/F13` SSTArabic-Medium | /Type3 | 321 | 52 | 0 | 0 | 0/0/0 |
| 9 | `/F14` SSTArabic-Medium | /Type3 | 87 | 38 | 38 | 87 | 0/0/0 |
| 9 | `/F15` SSTArabic-Medium | /Type0 | 20 | 1 | 0 | 0 | 0/0/0 |
| 10 | `/F5` Somar-SemiBold | /Type0 | 513 | 82 | 39 | 176 | 0/0/0 |
| 10 | `/F7` SSTArabic-Medium | /Type0 | 963 | 111 | 49 | 275 | 0/0/0 |
| 11 | `/F5` Somar-SemiBold | /Type0 | 359 | 74 | 33 | 123 | 0/0/0 |
| 11 | `/F6` Somar-SemiBold | /Type0 | 74 | 40 | 16 | 22 | 0/0/0 |
| 11 | `/F7` SSTArabic-Medium | /Type3 | 36 | 9 | 0 | 0 | 0/0/0 |
| 11 | `/F10` SSTArabic-Medium | /Type3 | 380 | 53 | 0 | 0 | 0/0/0 |
| 11 | `/F11` SSTArabic-Medium | /Type3 | 244 | 44 | 44 | 244 | 0/0/0 |
| 11 | `/F12` SSTArabic-Medium | /Type0 | 52 | 1 | 0 | 0 | 0/0/0 |
| 11 | `/F13` SSTArabic-Medium | /Type3 | 200 | 45 | 0 | 0 | 0/0/0 |
| 11 | `/F14` SSTArabic-Medium | /Type3 | 56 | 32 | 32 | 56 | 0/0/0 |
| 11 | `/F15` SSTArabic-Medium | /Type0 | 13 | 1 | 0 | 0 | 0/0/0 |
| 12 | `/F5` Somar-SemiBold | /Type0 | 860 | 96 | 48 | 267 | 0/0/0 |
| 12 | `/F6` Somar-SemiBold | /Type0 | 120 | 50 | 20 | 37 | 0/0/0 |
| 12 | `/F7` SSTArabic-Medium | /Type3 | 72 | 22 | 0 | 0 | 0/0/0 |
| 12 | `/F10` SSTArabic-Medium | /Type3 | 5 | 5 | 5 | 5 | 0/0/0 |
| 12 | `/F11` SSTArabic-Medium | /Type3 | 496 | 60 | 0 | 0 | 0/0/0 |
| 12 | `/F12` SSTArabic-Medium | /Type3 | 323 | 45 | 45 | 323 | 0/0/0 |
| 12 | `/F13` SSTArabic-Medium | /Type0 | 60 | 1 | 0 | 0 | 0/0/0 |
| 12 | `/F14` SSTArabic-Medium | /Type3 | 341 | 53 | 0 | 0 | 0/0/0 |
| 12 | `/F15` SSTArabic-Medium | /Type3 | 87 | 38 | 38 | 87 | 0/0/0 |
| 12 | `/F16` SSTArabic-Medium | /Type0 | 18 | 1 | 0 | 0 | 0/0/0 |
| 13 | `/F5` Somar-SemiBold | /Type0 | 859 | 96 | 48 | 269 | 0/0/0 |
| 13 | `/F6` Somar-SemiBold | /Type0 | 120 | 50 | 20 | 37 | 0/0/0 |
| 13 | `/F7` SSTArabic-Medium | /Type3 | 68 | 20 | 0 | 0 | 0/0/0 |
| 13 | `/F10` SSTArabic-Medium | /Type3 | 7 | 7 | 7 | 7 | 0/0/0 |
| 13 | `/F11` SSTArabic-Medium | /Type0 | 1 | 1 | 0 | 0 | 0/0/0 |
| 13 | `/F12` SSTArabic-Medium | /Type3 | 502 | 62 | 0 | 0 | 0/0/0 |
| 13 | `/F13` SSTArabic-Medium | /Type3 | 323 | 45 | 45 | 323 | 0/0/0 |
| 13 | `/F14` SSTArabic-Medium | /Type0 | 60 | 1 | 0 | 0 | 0/0/0 |
| 13 | `/F15` SSTArabic-Medium | /Type3 | 341 | 53 | 0 | 0 | 0/0/0 |
| 13 | `/F16` SSTArabic-Medium | /Type3 | 87 | 38 | 38 | 87 | 0/0/0 |
| 13 | `/F17` SSTArabic-Medium | /Type0 | 18 | 1 | 0 | 0 | 0/0/0 |
| 14 | `/F5` Somar-SemiBold | /Type0 | 663 | 81 | 39 | 234 | 0/0/0 |
| 14 | `/F6` Somar-SemiBold | /Type0 | 98 | 44 | 16 | 31 | 0/0/0 |
| 14 | `/F7` SSTArabic-Medium | /Type3 | 56 | 9 | 0 | 0 | 0/0/0 |
| 14 | `/F10` SSTArabic-Medium | /Type3 | 491 | 56 | 0 | 0 | 0/0/0 |
| 14 | `/F11` SSTArabic-Medium | /Type3 | 341 | 45 | 45 | 341 | 0/0/0 |
| 14 | `/F12` SSTArabic-Medium | /Type0 | 60 | 1 | 0 | 0 | 0/0/0 |
| 14 | `/F13` SSTArabic-Medium | /Type3 | 321 | 52 | 0 | 0 | 0/0/0 |
| 14 | `/F14` SSTArabic-Medium | /Type3 | 87 | 38 | 38 | 87 | 0/0/0 |
| 14 | `/F15` SSTArabic-Medium | /Type0 | 18 | 1 | 0 | 0 | 0/0/0 |
| 15 | `/F5` Somar-SemiBold | /Type0 | 716 | 86 | 40 | 247 | 0/0/0 |
| 15 | `/F7` SSTArabic-Medium | /Type0 | 1477 | 129 | 51 | 396 | 0/0/0 |
| 16 | `/F5` Somar-SemiBold | /Type0 | 681 | 83 | 39 | 234 | 0/0/0 |
| 16 | `/F7` SSTArabic-Medium | /Type0 | 1294 | 127 | 52 | 387 | 0/0/0 |

**نمط مقيس:** كل ملف يحمل خطًّا (أو خطين) تُسمّي خريطته محارف العرض **كلها** — مثل `/F11` في الملف 14: 45/45 مدخلًا PF و341 رسمًا، و`/F14`: 38/38 و87. الملفات 9 و11–14 تحمل خطوط Type3 بهذه الصفة، والملفات الأخرى توزّع المحارف بين خطوط Type0 مختلطة (39 PF من 81 في `/F5`). الخريطة واحدة في المجموعتين: الكود `0x1E4` ← U+FE94 في الملفين 1 و9 معًا.

**أكثر محارف العرض ورودًا في 16 ملفًا:** `U+FEDF` ×1323 · `U+FE94` ×779 · `U+FEE4` ×753 · `U+FE8E` ×707 · `U+FEAE` ×478.

### مساران للمنتِج — ملاحظة بنيوية مقيسة

| # | خطوط Type3 | `/AF` (مرفق مضمَّن) | `/Alt` | pdfkit/mupdf/poppler في السطر الأول |
|---|---|---|---|---|
| 1 | 0 | نعم | 0 | محارف عرض |
| 2 | 0 | نعم | 0 | محارف عرض |
| 3 | 0 | نعم | 0 | محارف عرض |
| 4 | 0 | نعم | 0 | محارف عرض |
| 5 | 0 | نعم | 0 | محارف عرض |
| 6 | 0 | نعم | 0 | محارف عرض |
| 7 | 0 | نعم | 0 | محارف عرض |
| 8 | 0 | نعم | 0 | محارف عرض |
| 9 | 5 | لا | 1 | حروف أساسية |
| 10 | 0 | نعم | 0 | محارف عرض |
| 11 | 5 | لا | 1 | حروف أساسية |
| 12 | 6 | لا | 1 | حروف أساسية |
| 13 | 6 | لا | 1 | حروف أساسية |
| 14 | 5 | لا | 1 | حروف أساسية |
| 15 | 0 | نعم | 0 | محارف عرض |
| 16 | 0 | نعم | 0 | محارف عرض |

الخمسة التي بلا `/AF` (9، 11، 12، 13، 14) هي نفسها التي تحمل خطوط Type3 وفيها `/Alt` واحد، وهي نفسها التي يُخرج فيها pdfkit/mupdf/poppler حروفًا أساسية. ارتباط مقيس، لا سبب مُثبت (انظر «ما لم يُثبت»). ولا `/ActualText` في أي ملف من الستة عشر (فُحص كل كائن، لا البايتات المضغوطة).

**الأثر على المستخدم:** كلمة «فاتورة» في السطر الأول تخرج عند pdfkit/mupdf/poppler بـU+FED3 U+FE8E U+FE97 U+FEEE ثم U+0631 U+0629 — أربعة محارف عرض وحرفان أساسيان في الكلمة نفسها — فلا تطابق بحثًا بالحروف الأساسية ولا تُنسخ نصًّا عربيًّا سليمًا. pdfminer يقرأ الخريطة دائمًا فتظهر المحارف عنده في 16/16؛ وpdfkit/mupdf/poppler يُظهرونها كاملة في 11؛ وفي الخمسة الباقية: pdfminer ينسخها كلها، وpdfkit بعضها، وmupdf/poppler حروفًا أساسية (الفرق بين المجموعتين غير مفسَّر — «ما لم يُثبت»)؛ وpdfium يُخرج حروفًا أساسية في الستة عشر، لكنه في الخمسة نفسها (Type3) لا يستعمل الخريطة بل يعكس الحروف، وفي الأحد عشر يعكس ترتيب كلمات المقاطع العربية — فـ«pdfium سليم» ليست دقيقة، و«pdfium يُخرج حروفًا أساسية» هي الدقيقة.

## 2) visual-order — 0/16 على الملف، 21 إشارة قارئ

| # | الإشارة | على مستوى الملف؟ | أصوات القرّاء | النسخ الفعلي (ص1) | التصنيف | السبب |
|---|---|---|---|---|---|---|
| 1 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «ضريبية» · pdfkit -1.00 «ﻓﺎﺗﻮرة» · mupdf -1.00 «ﻓﺎﺗﻮرة» · poppler -1.00 «ﻓﺎﺗﻮرة» · pdfminer +0.92 «ﺔﻴﺒﻳﺮﺿ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 1 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |
| 2 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «ضريبية» · pdfkit -1.00 «ﻓﺎﺗﻮرة» · mupdf -1.00 «ﻓﺎﺗﻮرة» · poppler -1.00 «ﻓﺎﺗﻮرة» · pdfminer +0.92 «ﺔﻴﺒﻳﺮﺿ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 1 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |
| 3 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «ضريبية» · pdfkit -1.00 «ﻓﺎﺗﻮرة» · mupdf -1.00 «ﻓﺎﺗﻮرة» · poppler -1.00 «ﻓﺎﺗﻮرة» · pdfminer +0.92 «ﺔﻴﺒﻳﺮﺿ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 1 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |
| 4 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «دائن» · pdfkit -1.00 «إﺷﻌﺎر» · mupdf -1.00 «إﺷﻌﺎر» · poppler -1.00 «إﺷﻌﺎر» · pdfminer +0.93 «ﻦﺋاد» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 2 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |
| 5 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «ضريبية» · pdfkit -1.00 «ﻓﺎﺗﻮرة» · mupdf -1.00 «ﻓﺎﺗﻮرة» · poppler -1.00 «ﻓﺎﺗﻮرة» · pdfminer +0.93 «ﺔﻴﺒﻳﺮﺿ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 1 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |
| 6 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «ضريبية» · pdfkit -1.00 «ﻓﺎﺗﻮرة» · mupdf -1.00 «ﻓﺎﺗﻮرة» · poppler -1.00 «ﻓﺎﺗﻮرة» · pdfminer +0.92 «ﺔﻴﺒﻳﺮﺿ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 1 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |
| 7 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «مبسطة» · pdfkit -1.00 «ﻓﺎﺗﻮرة» · mupdf -1.00 «ﻓﺎﺗﻮرة» · poppler -1.00 «ﻓﺎﺗﻮرة» · pdfminer +0.92 «ﺔﻄﺴﺒﻣ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 1 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |
| 8 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «ضريبية» · pdfkit -1.00 «ﻓﺎﺗﻮرة» · mupdf -1.00 «ﻓﺎﺗﻮرة» · poppler -1.00 «ﻓﺎﺗﻮرة» · pdfminer +0.92 «ﺔﻴﺒﻳﺮﺿ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 1 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |
| 9 | visual-order | لا | 2/5 (pdfium, pdfminer) | pdfium +0.61 «ةيبيرض» · pdfkit -1.00 «فاتورة» · mupdf -1.00 «فاتورة» · poppler -1.00 «فاتورة» · pdfminer +0.92 «ﺔﻴﺒﻳﺮﺿ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يعكس الحروف؛ pdfkit/mupdf/poppler منطقيون |
| 10 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «مبسطة» · pdfkit -1.00 «ﻓﺎﺗﻮرة» · mupdf -1.00 «ﻓﺎﺗﻮرة» · poppler -1.00 «ﻓﺎﺗﻮرة» · pdfminer +0.92 «ﺔﻄﺴﺒﻣ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 1 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |
| 11 | visual-order | لا | 2/5 (pdfium, pdfminer) | pdfium +0.66 «ةطسبم» · pdfkit -1.00 «فاتورة» · mupdf -1.00 «فاتورة» · poppler -1.00 «فاتورة» · pdfminer +0.93 «ﺔﻄﺴﺒﻣ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يعكس الحروف؛ pdfkit/mupdf/poppler منطقيون |
| 12 | visual-order | لا | 2/5 (pdfium, pdfminer) | pdfium +0.55 «نئاد» · pdfkit -1.00 «إشعار» · mupdf -1.00 «إشعار» · poppler -1.00 «إشعار» · pdfminer +0.93 «ﻦﺋاد» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يعكس الحروف؛ pdfkit/mupdf/poppler منطقيون |
| 13 | visual-order | لا | 2/5 (pdfium, pdfminer) | pdfium +0.55 «نيدم» · pdfkit -1.00 «إشعار» · mupdf -1.00 «إشعار» · poppler -1.00 «إشعار» · pdfminer +0.92 «ﻦﻳﺪﻣ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يعكس الحروف؛ pdfkit/mupdf/poppler منطقيون |
| 14 | visual-order | لا | 2/5 (pdfium, pdfminer) | pdfium +0.64 «ةيبيرض» · pdfkit -1.00 «فاتورة» · mupdf -1.00 «فاتورة» · poppler -1.00 «فاتورة» · pdfminer +0.92 «ﺔﻴﺒﻳﺮﺿ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يعكس الحروف؛ pdfkit/mupdf/poppler منطقيون |
| 15 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «ضريبية» · pdfkit -1.00 «ﻓﺎﺗﻮرة» · mupdf -1.00 «ﻓﺎﺗﻮرة» · poppler -1.00 «ﻓﺎﺗﻮرة» · pdfminer +0.92 «ﺔﻴﺒﻳﺮﺿ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 1 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |
| 16 | visual-order | لا | 1/5 (pdfminer) | pdfium -1.00 «ضريبية» · pdfkit -1.00 «ﻓﺎﺗﻮرة» · mupdf -1.00 «ﻓﺎﺗﻮرة» · poppler -1.00 «ﻓﺎﺗﻮرة» · pdfminer +0.92 «ﺔﻴﺒﻳﺮﺿ» | **خاص بالقارئ** | pdfminer يعكس الحروف؛ pdfium يقلب 1 سطرًا مختلطًا؛ pdfkit/mupdf/poppler منطقيون |

### الدرجة والاتجاه لكل قارئ

الدرجة من arafix: +1 معكوس، −1 منطقي. «الاتجاه المقيس» من مقارنة كلمات كل قارئ بمجموع كلمات pdfkit على الصفحة 1 (مطابقة تامة، أو معكوسة الحروف، أو معكوسة المقاطع).

| # | pdfium | pdfkit | mupdf | poppler | pdfminer |
|---|---|---|---|---|---|
| 1 | -1.00 · segments-reversed (0/82) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | +0.92 · letters-reversed (78/82) |
| 2 | -1.00 · segments-reversed (0/82) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | +0.92 · letters-reversed (78/82) |
| 3 | -1.00 · segments-reversed (0/82) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | +0.92 · letters-reversed (78/82) |
| 4 | -1.00 · segments-reversed (0/119) | -1.00 · logical (0/119) | -1.00 · logical (0/119) | -1.00 · logical (0/119) | +0.93 · letters-reversed (111/119) |
| 5 | -1.00 · segments-reversed (0/81) | -1.00 · logical (0/81) | -1.00 · logical (0/81) | -1.00 · logical (0/81) | +0.93 · letters-reversed (77/81) |
| 6 | -1.00 · segments-reversed (0/80) | -1.00 · logical (0/80) | -1.00 · logical (0/80) | -1.00 · logical (0/80) | +0.92 · letters-reversed (74/82) |
| 7 | -1.00 · segments-reversed (0/89) | -1.00 · logical (0/89) | -1.00 · logical (0/89) | -1.00 · logical (0/89) | +0.92 · letters-reversed (86/89) |
| 8 | -1.00 · segments-reversed (0/82) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | +0.92 · letters-reversed (78/82) |
| 9 | +0.61 · letters-reversed (53/83) | -1.00 · logical (0/100) | -1.00 · logical (0/83) | -1.00 · logical (0/83) | +0.92 · letters-reversed (69/83) |
| 10 | -1.00 · segments-reversed (0/93) | -1.00 · logical (0/93) | -1.00 · logical (0/93) | -1.00 · logical (0/93) | +0.92 · letters-reversed (90/93) |
| 11 | +0.66 · letters-reversed (55/98) | -1.00 · logical (0/139) | -1.00 · logical (0/98) | -1.00 · logical (0/98) | +0.93 · letters-reversed (75/98) |
| 12 | +0.55 · letters-reversed (53/86) | -1.00 · logical (0/104) | -1.00 · logical (0/86) | -1.00 · logical (0/86) | +0.93 · letters-reversed (71/86) |
| 13 | +0.55 · letters-reversed (53/86) | -1.00 · logical (0/104) | -1.00 · logical (0/86) | -1.00 · logical (0/86) | +0.92 · letters-reversed (71/86) |
| 14 | +0.64 · letters-reversed (52/82) | -1.00 · logical (0/99) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | +0.92 · letters-reversed (68/82) |
| 15 | -1.00 · segments-reversed (0/85) | -1.00 · logical (0/85) | -1.00 · logical (0/85) | -1.00 · logical (0/85) | +0.92 · letters-reversed (81/85) |
| 16 | -1.00 · segments-reversed (0/82) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | -1.00 · logical (0/82) | +0.92 · letters-reversed (78/82) |

**ما يقوله هذا:** الحروف في الطبقة مرسومة بالترتيب البصري (رسم حرفًا حرفًا: أول حرف مرسوم في السطر هو آخر حرف في الكلمة)، وهذا اختيار منتِج لا عيب؛ ثلاثة قرّاء يعيدون الترتيب فيقرؤون الكلمة صحيحة، وpdfminer لا يعيده فيُخرج الحروف معكوسة: 1394 كلمة عربية في مجموع الصفحات الأولى، 0 منها تطابق pdfkit حرفًا بحرف، و1263 منها هي معكوس الحروف لكلمة عند pdfkit. وpdfium يقلب ترتيب الكلمات في أسطر مختلطة (لاتيني + عربي) — 17 سطرًا في الصفحة 1 عبر 16 ملفًا، مطابقًا للمعلن `pdfium-rtl-row-order` — ويعكس الحروف أيضًا في 5 ملفات.

## 3) tounicode-gaps — 0/16، والفجوة صفر لا تُخفى

| # | الإشارة | على مستوى الملف؟ | أصوات القرّاء | النسخ الفعلي (ص1) | التصنيف | السبب |
|---|---|---|---|---|---|---|
| 1 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ضريبية» · pdfkit «ﻓﺎﺗﻮرة» · mupdf «ﻓﺎﺗﻮرة» · poppler «ﻓﺎﺗﻮرة» · pdfminer «ﺔﻴﺒﻳﺮﺿ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2584 كودًا |
| 2 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ضريبية» · pdfkit «ﻓﺎﺗﻮرة» · mupdf «ﻓﺎﺗﻮرة» · poppler «ﻓﺎﺗﻮرة» · pdfminer «ﺔﻴﺒﻳﺮﺿ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2508 كودًا |
| 3 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ضريبية» · pdfkit «ﻓﺎﺗﻮرة» · mupdf «ﻓﺎﺗﻮرة» · poppler «ﻓﺎﺗﻮرة» · pdfminer «ﺔﻴﺒﻳﺮﺿ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2510 كودًا |
| 4 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «دائن» · pdfkit «إﺷﻌﺎر» · mupdf «إﺷﻌﺎر» · poppler «إﺷﻌﺎر» · pdfminer «ﻦﺋاد» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 1688 كودًا |
| 5 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ضريبية» · pdfkit «ﻓﺎﺗﻮرة» · mupdf «ﻓﺎﺗﻮرة» · poppler «ﻓﺎﺗﻮرة» · pdfminer «ﺔﻴﺒﻳﺮﺿ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2274 كودًا |
| 6 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ضريبية» · pdfkit «ﻓﺎﺗﻮرة» · mupdf «ﻓﺎﺗﻮرة» · poppler «ﻓﺎﺗﻮرة» · pdfminer «ﺔﻴﺒﻳﺮﺿ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2158 كودًا |
| 7 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «مبسطة» · pdfkit «ﻓﺎﺗﻮرة» · mupdf «ﻓﺎﺗﻮرة» · poppler «ﻓﺎﺗﻮرة» · pdfminer «ﺔﻄﺴﺒﻣ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 1267 كودًا |
| 8 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ضريبية» · pdfkit «ﻓﺎﺗﻮرة» · mupdf «ﻓﺎﺗﻮرة» · poppler «ﻓﺎﺗﻮرة» · pdfminer «ﺔﻴﺒﻳﺮﺿ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2255 كودًا |
| 9 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ةيبيرض» · pdfkit «فاتورة» · mupdf «فاتورة» · poppler «فاتورة» · pdfminer «ﺔﻴﺒﻳﺮﺿ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2059 كودًا |
| 10 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «مبسطة» · pdfkit «ﻓﺎﺗﻮرة» · mupdf «ﻓﺎﺗﻮرة» · poppler «ﻓﺎﺗﻮرة» · pdfminer «ﺔﻄﺴﺒﻣ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 1476 كودًا |
| 11 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ةطسبم» · pdfkit «فاتورة» · mupdf «فاتورة» · poppler «فاتورة» · pdfminer «ﺔﻄﺴﺒﻣ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 1414 كودًا |
| 12 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «نئاد» · pdfkit «إشعار» · mupdf «إشعار» · poppler «إشعار» · pdfminer «ﻦﺋاد» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2382 كودًا |
| 13 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «نيدم» · pdfkit «إشعار» · mupdf «إشعار» · poppler «إشعار» · pdfminer «ﻦﻳﺪﻣ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2386 كودًا |
| 14 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ةيبيرض» · pdfkit «فاتورة» · mupdf «فاتورة» · poppler «فاتورة» · pdfminer «ﺔﻴﺒﻳﺮﺿ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2135 كودًا |
| 15 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ضريبية» · pdfkit «ﻓﺎﺗﻮرة» · mupdf «ﻓﺎﺗﻮرة» · poppler «ﻓﺎﺗﻮرة» · pdfminer «ﺔﻴﺒﻳﺮﺿ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 2193 كودًا |
| 16 | tounicode-gaps | لا | — (فحص بنيوي) | pdfium «ضريبية» · pdfkit «ﻓﺎﺗﻮرة» · mupdf «ﻓﺎﺗﻮرة» · poppler «ﻓﺎﺗﻮرة» · pdfminer «ﺔﻴﺒﻳﺮﺿ» | **نفي صحيح** | missing 0 · notdef 0 · PUA 0 · FFFD 0 · NUL 0 · BOM 0 من 1975 كودًا |

| # | رسم | missing | notdef | PUA | FFFD | NUL | BOM | خطوط | خطوط بلا ToUnicode | حالات غير ok |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2584 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |
| 2 | 2508 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |
| 3 | 2510 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |
| 4 | 1688 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |
| 5 | 2274 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |
| 6 | 2158 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | — |
| 7 | 1267 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |
| 8 | 2255 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |
| 9 | 2059 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 0 | — |
| 10 | 1476 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |
| 11 | 1414 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 0 | — |
| 12 | 2382 | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 0 | — |
| 13 | 2386 | 0 | 0 | 0 | 0 | 0 | 0 | 11 | 0 | — |
| 14 | 2135 | 0 | 0 | 0 | 0 | 0 | 0 | 9 | 0 | — |
| 15 | 2193 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |
| 16 | 1975 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | — |

**المجموع:** 33264 كودًا مرسومًا في 16 ملفًا و71 خطًّا، ولا كود واحد يفتقد مدخلًا. لا إشارة تُطلق، ولا عيب في هذه الإشارة.

## الصياغات العلنية المسموح بها والممنوعة (أُضيف في تصحيح ٢٥ نوفمبر)

هذه النتيجة تُقرأ حرفيًّا، والحدّ بين ما يثبته الدليل وما يوحي به أكبر من الفرق بين رقمين:

**مسموح:**
- «في 11 من 16 عيّنة PDF/A-3 مضمّنة في حزمة SDK الفوترة الإلكترونية، أربعة من خمسة قرّاء شائعين ينسخون النص العربي أشكال عرض لا حروفًا أساسية.»
- «خريطة ToUnicode في 16 من 16 عيّنة تسمّي محارف العرض (U+FExx)، وأغلبية القرّاء تُظهرها في 11.»
- «هذه عيّنات مرجعية مضمّنة في الحزمة، ومنتِجها المعلن iText 7.1.16.»

**ممنوع:**
- «مولّد ZATCA الرسمي معيب» — لا إثبات أن ZATCA تولّد هذه الملفات؛ العيّنات **مضمّنة في الحزمة**، والمنتِج المعلن طرف ثالث.
- «كل فواتير ZATCA معيبة» — العيّنة 16 ملفًا لمنتِج واحد.
- «Chrome يقرؤها سليمة» — pdfium يُخرج حروفًا أساسية في 16/16 **لكنه** يعكس الحروف في 5 ويعكس ترتيب كلمات المقاطع العربية في 11 (55 مقطعًا مقيسًا).
- أي شعار أو اسم لجهة رسمية يُوحي بشراكة أو تأييد. ونسخ النص **ليس شرط امتثال** لدى ZATCA؛ فلا تُسمّى النتيجة «شهادة مطابقة».

## ما لم يُثبت

- **سبب اختلاف القرّاء بين مجموعتَي الملفات:** pdfkit/mupdf/poppler يُخرجون حروفًا أساسية في الملفات الخمسة التي تحمل خطوط Type3 (9، 11، 12، 13، 14) ويُخرجون U+FExx في الأحد عشر الأخرى، مع أن الخريطة واحدة (الكود `0x1E4` ← U+FE94 في الملف 1 والملف 9). الخمسة هي أيضًا الوحيدة بلا `/AF` وبـ`/Alt` واحد — ارتباط مقيس لا يفسّر الآلية.
- **مصدر الحرف عند الأربعة:** مسبار وضع علامة `Z` في خريطة `/F11` (Type3) أظهر أن pdfminer وحده يقرأ الخريطة (102 حرف Z)، بينما pdfium/pdfkit/mupdf/poppler لا يقرؤونها (0) — ومع ذلك يُخرجون كلماتها حروفًا أساسية؛ من أين يستمدون القيمة غير معروف، وأسماء المحارف `/gXXXX` لا تحمل معنى.
- **تكرار الأسطر عند pdfminer:** لا `/ActualText` في أي ملف (فُحص كل كائن)، ولا رسم عربي مكرّر يفسّر العدد (عدد محارف pdfminer يطابق الطبقة: 817 في الملف 9)، لكن pdfminer يكرّر أسطر الأرقام («123456 123456») — التكرار غير مفسَّر.
- **هل تفوت arafix عكس pdfium للأسطر؟** الدرجة −1.00 على الأحد عشر ملفًا التي تُظهر نسخُها 1–2 سطرًا مختلطًا معكوس الترتيب (المعلن في `pdfium-rtl-row-order`)، أي أن الكاشف لا يرى عكس المقاطع حين تكون الحروف سليمة. **وهذا القياس نفسه صار إشارة في الفاحص (٢٥ نوفمبر):** `segment-order` تقارن ترتيب كلمات المقطع بأغلبية القرّاء وتَسِم القارئ الشاذّ (pdfium: 55 مقطعًا في 11 ملفًا، وغيره صفر)، والقياس محفوظ في القياس المرفق بفرع المعالجة؛ والملف هنا يبقى دليلًا على الحالة لا على الإصلاح.
- **سلامة شكل الحرف في خطوط Type3:** لا فحص رسم/بكسل ولا OCR في هذه الجولة، فالحكم على الطبقة لا على الصورة.

## الحدود

- لا OCR ولا فحص بكسلي: الحكم على طبقة النص والخريطة، لا على شكل الحرف المرسوم.
- العيّنة 16 ملفًا من منتِج واحد (iText 7.1.16)؛ التعميم على منتِج آخر يحتاج عيّنته.
- «واقعي» يعني أن الخريطة في الملف تسمّي محارف العرض؛ ولا يعني أن كل مستخدم يرى العيب: pdfium يُخرج حروفًا أساسية في 16/16، وpdfkit/mupdf/poppler في 5/16، وpdfminer يُظهر المحارف في 16/16.
- أرقام الفاحص نفسها محفوظة في `/tmp/pr3/check/<رقم>.json`، والقياسات الخام في `/tmp/pr3/raw/<رقم>.json`.

