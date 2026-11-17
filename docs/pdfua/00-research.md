# PDF/UA-1 — بحث المصادر قبل التخطيط

## ما نقيسه الآن (مُثبت)
`verapdf --flavour ua1` على الملفات الثلاثة: غير مطابق.

| الملف | 5 | 7.1 |
|---|---|---|
| najd.pdf | 1 | 256 |
| report.pdf | 1 | 612 |
| report-print.pdf | 1 | 521 |

- **5** = امتداد تعريف PDF/UA (`pdfuaid:part`) غائب — لم نُصدره أصلًا.
- **7.1 test 3** = `isTaggedContent == true || parentsTags.contains('Artifact') == true`.
  كائن الفحص: `SESimpleContentItem`؛ الرسالة: «Content is neither marked as Artifact nor
  tagged as real content». أي أن كل عملية رسم خارج أي BDC موسوم.

## بنية ملفاتنا اليوم (مقيسة)
- `StructTreeRoot` موجود، `/ParentTree` موجود، لا `RoleMap` (ولا يحتاج: كل الأنواع قياسية).
- الأنواع: `Document` 1 · `NonStruct` 387 · `H1` 9 · `P` 10 · `Link` 43.
- **لا يوجد أي `Figure`** — صورة الغلاف غير موسومة أصلًا (Chrome تركها محتوى حرًّا).
- `MarkInfo {Marked true}` بلا `Suspects` · `/Lang ar` · `/ViewerPreferences` فيها `DisplayDocTitle`
  و`Direction /R2L` · كل صفحة `/StructParents` و`/Tabs /S`.

## المصادر
1. **ISO 14289-1 (PDF/UA-1)** وقواعد veraPDF المقابلة (`PDFUA-1.xml`): 7.1 له اختبارات فرعية،
   أهمها 7.1-1 (Artifact داخل محتوى موسوم)، 7.1-2 (محتوى موسوم داخل Artifact)، 7.1-3 (لا هذا ولا ذاك)،
   7.1-4 (`Suspects` يجب أن تكون false)، 7.1-5/6/7 (RoleMap)، 7.1-8 (Metadata stream)، 7.1-10
   (ViewerPreferences)، 7.1-11 (البنية المنطقية).
   <https://pdfix.net/pdf-ua-1-validation-errors-and-fix-guide/>
2. **Tagged PDF Best Practice Guide: Syntax** (PDF Association) — قواعد الـBDC/EMC و`/Artifact`
   والوسم الصحيح للعناصر الزخرفية.
   <https://pdfa.org/wp-content/uploads/2019/06/TaggedPDFBestPracticeGuideSyntax.pdf>
3. **WCAG PDF4** — الصور الزخرفية تُوسم Artifact لا Figure.
   <https://www.w3.org/TR/WCAG-TECHS/PDF4.html>
4. **altex** (تنفيذ مرجعي بلغة Python/pikepdf فوق PDFs مولّدة بـLaTeX): يلفّ كل عملية نصّية في BDC
   بـMCID، ويوسم غير النصّي `/Artifact`، ويضيف `pdfuaid`. قياسهم: 57,914 → 1,272 مخالفة عبر 28 مستندًا،
   و8 مستندات بصفر مخالفة. يثبت أن المسار مجدٍ بـpikepdf وحده.
   <https://github.com/ml8/altex>

## الاستنتاج
الفجوة عندنا ليست في البنية (Chrome يوسم النصّ فعلًا) بل في **المحتوى غير الموسوم**: خلفيات،
أشرطة، خطوط، صورة الغلاف، أيقونات. الحل: لفّ كل ما هو خارج أي BDC في `/Artifact BMC … EMC`،
مع شرط صريح: **لا يُفتح Artifact حول BDC قائم** (يحقق 7.1-2)، ولا يُترك BDC داخل Artifact.
