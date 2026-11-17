# إثبات وحدة التشكيل (كان مجهولًا)

## ما بُني

`hb_probe/shaping.{h,cc}` — دالة واحدة:

```cpp
bool ShapeUtf16(const std::string& font_bytes, const std::u16string& text, float pixel_size, ShapedRun* out);
```

تُنشئ `hb_blob → hb_face → hb_font` بمقياس `pixel_size*64`، تُضيف النص بـ`hb_buffer_add_utf16`، تترك
`hb_buffer_guess_segment_properties` تستنتج الاتجاه والسكربت، ثم `hb_shape` وتُعيد المعرّفات والمواضع.

## البناء

```
third_party/ninja/ninja -C out/HB shaping_probe   → LINK ./shaping_probe (1,664,320 بايت)
```

عقبتان أُصلحتا: تحذيرات Chromium `-Wunsafe-buffer-usage` تُعامل كأخطاء ⇒ `#pragma allow_unsafe_buffers`
في أعلى الملفين (الطريقة المعتمدة في الشجرة)، و`printf` مع `argv` ⇒ `std::cout`.

## التشغيل (خط نجد، 26.66)

```
lam-alef: in=2 glyphs=1 dir=5 script=Arab ids=210 | adv=17.5469
Business: in=8 glyphs=8 dir=4 script=Latn ids=817 810 808 798 803 794 808 808 | adv=17.03 15.97 14.09 6.30 ...
```

**مُثبت**:
- «لا» (حرفان) ⇒ **محرف واحد** (معرّف ٢١٠) — أي أن **التراكب العربي (لام-ألف) يعمل**، والاتجاه `dir=5` = RTL.
- «Business» ⇒ ٨ محارف، `dir=4` = LTR، `script=Latn`، وأعراض موجبة.
- كل ذلك بمكتبة HarfBuzz التي يحملها PDFium، لا بمكتبة خارجية.

## قياس جديد: الخط المضمَّن في PDF لا يصلح للتشكيل

استُخرج `/FontFile2` من `/F10` (Type0، `Identity-H`) في `report.pdf`: **٣٢٩٢ بايت** فقط — مجموعة فرعية.

```
$ ./shaping_probe /tmp/embedded-font.ttf
lam-alef: in=2 glyphs=2 dir=5 script=Arab ids=0 0 | adv=12.5781 12.5781
Business: in=8 glyphs=8 dir=4 script=Latn ids=0 0 0 0 0 0 0 0 | adv=12.5781 ...
```

**مُثبت**: المجموعة الفرعية بلا `cmap` ⇒ كل المعرّفات صفر. إذن **لا يمكن التشكيل بخط PDF المضمَّن**؛ يجب
التشكيل بالخط الأصلي الكامل، ثم تحويل `glyph id → CID` بما يطابق الخط المضمَّن (Identity أو `CIDToGIDMap`)،
أو تضمين الخط كاملًا. هذا شرط تصميمي مُقاس، لا رأي.

## ما لم يُثبت

- **الدمج في مسار الحقول**: `CPVT_GenerateAP` / `FPDF_FFLDraw` لم يُعدَّلا؛ الوحدة تُستدعى من برنامج اختبار
  لا من محرّك العرض. هذا هو البند الأخير المتبقي.
- التشكيل بخطوط PDF المضمَّنة (Type0/CIDFont) بدل ملف TTF خارجي.
- المقارنة البصرية بين مخرَج الوحدة ومخرَج Chrome على نفس السطر.
