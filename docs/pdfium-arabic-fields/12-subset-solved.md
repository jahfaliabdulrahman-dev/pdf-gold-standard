# عقبة الـsubset: الجذر وُجد والحل أُثبت

## الجذر (بالمصدر لا بالتخمين)

`third_party/harfbuzz/BUILD.gn:391`:

```
# SkPDF needs subsetting but does not require subsetting of layout or CFF tables.
"HB_NO_SUBSET_LAYOUT",
"HB_NO_SUBSET_CFF",
```

PDFium يبني HarfBuzz **بلا اختصار الجداول التخطيطية** (قرار من SkPDF). فأي `hb_subset` داخل الشجرة يُسقط
`GSUB` بالضرورة — ولهذا فشلت المحاولات الثلاث: ليست أعلامًا خاطئة، بل قدرة غير مبنية.

## الحل المُثبت

الاختصار **خارج PDFium** بـfontTools مع إبقاء التخطيط:

```python
opts = subset.Options(); opts.layout_features = ['*']; opts.notdef_outline = True
font = subset.load_font("najd/Najd-Regular.ttf", opts)
s = subset.Subsetter(options=opts); s.populate(unicodes=[0x644, 0x627]); s.subset(font)
```

النتيجة: **٨٠٤٨ بايت**، ثم:

```
lam-alef: in=2 glyphs=1 dir=5 script=Arab ids=7 | adv=17.5469
```

**مُثبت**: اللام-ألف تنجو (محرف واحد، معرّف ٧) والخط الناتج صغير (٨KB). المسار الصحيح للحقول:
**اختصر بـfontTools ← ضمّن ← شكّل داخل PDFium ← `glyph→CID`**.

## ما يعنيه للتصميم

- لا نستخدم `hb_subset` من نسخة PDFium أبدًا (قدرة معطّلة عن قصد).
- يمكن بناء الـsubset في خط الإنتاج عندنا (Python) وضمّه في المورد — أو تضمين الخط الكامل (٢٠٠–٥٠٠KB).
- الخريطة تصبح `CID = glyph id` (Identity) إن بُني الـsubset بـ`--retain-gids` في fontTools.

## تثبيت المعرّفات (`retain_gids`)

```
fontTools subset: layout_features=['*'], retain_gids=True, unicodes={U+0644, U+0627}
→ 11,792 بايت
→ lam-alef: in=2 glyphs=1 dir=5 script=Arab ids=210   ← نفس معرّف الخط الأصلي
```

**مُثبت**: `retain_gids` يُبقي المعرّفات كما هي مع التخطيط ⇒ `CID == glyph id` صحيح، والخط الناتج ١١٫٨KB.
هذا يُغلق سؤال الخريطة في التصميم: Identity-H بلا جدول تحويل.

## ما لم يُثبت
- أن `retain_gids` يحفظ المعرّفات والتخطيط معًا على **الوجه الكامل** لا على عيّنة محرفين فقط (المقيس أعلاه حرفان: U+0644 وU+0627).
- سلوك PDFium عند تضمين خط مبني بهذه الطريقة داخل AP (لم يُختبر على حقل حقيقي).
