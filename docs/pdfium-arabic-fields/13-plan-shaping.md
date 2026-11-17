# خطة تنفيذ: تشكيل العربية في Appearance Stream للحقول

> **مُتجاوَزة — لا تُقرأ كمواصفة:** جسم هذا الملف يصف الخطة قبل القياس (بما فيها ما رُفض). المعتمد هو `15-field-shaping.md`. التصحيحات: نُفِّذت في `15-field-shaping.md` بثلاثة تصحيحات: الدالة `ShapeRun` لا `ShapeUtf16`،
> ولا عكس لمخرج CPVT (القياس أثبت أنه يفسد اللام-ألف)، والمرساة تُصحّح بإزاحة باقي السطر لا بالاكتفاء بالمقطع.

> التاريخ: ١٧ نوفمبر ٢٠٢٦ · الأساس: `5c2fb12` (سجل الأبحاث) · PDFium `20e2d23`

## ١ · المصادر الرسمية (مُثبتة بالاستخراج من النص نفسه)

| المصدر | الموضع | ما يثبته |
|---|---|---|
| ISO 32000-1:2008 | §9.4.2 · Table 108 · ص٢٤٩ | `Td` «Move to the start of the next line, offset from the start of the current line» و`Tm = Tlm = [1 0 0 1 tx ty] × Tlm` ⇒ إزاحات `Td` مطلقة بالنسبة إلى أصل السطر؛ تقدّم `Tj` لا يتراكم في `Tlm` ⇒ التشكيل بمصفوفة لكل محرف آمن |
| ISO 32000-1:2008 | §9.7.5.2 · NOTE 2 · ص٢٧٥ | «When the current font is a Type 2 CIDFont in which the CIDToGIDMap entry is Identity and if the TrueType font is embedded… the 2-byte CID values shall be identical glyph indices» ⇒ **CID = glyph id** بلا جدول تحويل |
| ISO 32000-1:2008 | §9.7.4.2 · ص٢٧١ | الخط TrueType المضمَّن يلزمه `CIDToGIDMap`، و«Every CIDFont shall contain a glyph description for CID 0» ⇒ `.notdef` شرط |
| ISO 32000-1:2008 | §12.5.5 · §12.7.3.3 · Table 174 | `AP` يتقدّم على `DA`، والقارئ يولّد المظهر من `/V` + `/DA` عند غيابه ⇒ الإصلاح في مولّد الـAP يصحّ لكل قارئ يعرض الملف المحفوظ |
| HarfBuzz (رسمي) | hb-buffer / hb-subset | مخرج التشكيل للـRTL بترتيب بصري (قياس: clusters تنازلية `[3,1,0]`) وتقدّمات موجبة ⇒ الرسم من الحافة اليسرى بتقدّم موجب صحيح |
| PDFium (رسمي) | `third_party/harfbuzz/BUILD.gn:391` | `HB_NO_SUBSET_LAYOUT` ⇒ `hb_subset` داخل الشجرة يُسقط GSUB (جذر العقبة السابقة، مُثبت) |

## ٢ · التصميم

**المنتِج (Python/fontTools — خارج PDFium):**
`layout_features=['*']` + `retain_gids=True` ← خط subset يحمل GSUB وcmap ومعرّفات أصلية ← يُضمَّن
`Type0/Identity-H` + `CIDToGIDMap /Identity` + `/W` + `ToUnicode` في `/DR` للحقل.

**PDFium (C++):**
1. `core/fpdfdoc/cpvt_shaping.{h,cc}`: `ShapeUtf16(span<const uint8_t>, u16string_view, float size)` → معرّفات + تقدّمات + إزاحات (نفس وحدة `shaping.cc` المُثبتة، منقولة إلى الشجرة).
2. `cpdf_generateap.cpp`: تجميع كلمات CPVT المتتالية **RTL** على السطر نفسه وبالخط نفسه (وهي أصلًا بالترتيب البصري)، عكسها إلى منطقي، تشكيلها، ثم إصدار **`Td` لكل محرف** بقيمة CID = glyph id.
3. **مرساة اليمين**: يُرسم الشكل من `(آخر كلمة.x + عرضها − عرض المُشكَّل)` كي يبقى الهامش الأيمن (بداية السطر العربي) مطابقًا لما حسبه CPVT.
4. **البوابات (وإلا المسار القديم حرفًا بحرف):** خط CID · `/Encoding /Identity-H` · `CIDToGIDMap` غائب أو `/Identity` · `FontFile2` موجود · لا surrogates · كل المعرّفات ≠ 0.
5. البناء: `//third_party/harfbuzz` في deps `core/fpdfdoc`.

## ٣ · القياس (قبل/بعد، بأداة واحدة)

1. عيّنة: حقلان في ملف واحد — عربي «لا» ولاتيني «Business» (ضابط).
2. `field_probe` (public API): `FPDFPage_GetAnnot` (يولّد AP) ← `FPDF_SaveAsCopy` ← استخراج تدفّق `/AP/N` بـpikepdf.
3. **معيار النجاح**: العربي = **CID واحد = ٢١٠** (معرّف اللام-ألف من uharfbuzz على الخط نفسه)؛ قبل التعديل = رقمان.
4. الضابط: تدفّق AP اللاتيني **مطابق بايتًا** قبل/بعد.
5. البكسل: `pdfium_test` ٣٠٠dpi قبل/بعد — عرض حبر اللام-ألف ينقص بمقدار فرق (ligature vs two isolated forms).

## ٤ · المخاطر

| الخطر | المعالجة |
|---|---|
| سطور مختلطة الاتجاه: فراغات داخلية تتغيّر بمقدار وفر الاختصار | تُقاس وتُوثَّق؛ لا تمسّ الهامش الأيمن |
| خطوط بلا cmap أو ترميز غير Identity | بوابة → المسار القديم بلا تغيير |
| تحرير الحقل داخل Chrome (cpwl_edit) ليس هذا المسار | خارج النطاق، يُوثَّق صراحةً: الترقيع يخصّ AP لا محرّر الواجهة |
| كسر حقول قائمة | الضابط اللاتيني بايتًا + بوابة الخط |

## ٥ · معايير التسليم
بناء أخضر · قياس قبل/بعد · ضابط بايتي · `code-review-elite` صفر ملاحظات · «ما لم يُثبت» مكتوب بصدق.
