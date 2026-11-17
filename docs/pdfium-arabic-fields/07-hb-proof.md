# إثبات HarfBuzz: يُبنى… ولا يُربط (وهذا هو الخطر الذي حذّرت منه الخطة)

## ما نُفِّذ

`scripts/pdfium_build_harfbuzz.sh`:
`gn gen out/HB --args='… skia_use_harfbuzz=true'` ثم `ninja -C out/HB pdfium_test` → **نجح** (`HB_BUILD=0`).

## ما قِيس بعد البناء (بالأوامر)

```
grep skia_use_harfbuzz out/HB/args.gn          → skia_use_harfbuzz = true
find out/HB/obj -path '*harfbuzz*' -name '*.o' | wc -l → 69
gn desc out/HB //:pdfium deps --all | grep -ci harfbuzz → 0
nm out/HB/pdfium_test | grep -ci hb_            → 0

# الدقة: الرمز موجود في الكائن لكنه ليس في المحرّك
nm out/HB/obj/third_party/harfbuzz/harfbuzz/hb-shape.o | grep "_hb_shape"
→ … 0000000000000164 T _hb_shape        (الشرطة السابقة من Mach-O، والرمز عامّ)
```

**تصحيح دقة:** غياب `hb_shape` من `pdfium_test` ليس لأن HarfBuzz لم يُترجم — بل لأن كائناته **لم تُربط**.
`hb-shape.o` يُصدِّر `_hb_shape` فعلًا، لكن المحرّك لا يحمله.

## الاستنتاج (مُثبت بالقياس، لا بالقراءة)

1. **HarfBuzz يُترجم فعلًا** عند تفعيل العلَم: ٦٩ ملف كائن.
2. **لكن PDFium لا يعتمد عليه**: عدد اعتماديات `//:pdfium` على harfbuzz = **صفر**، ولا رمز `hb_` واحد في
   `pdfium_test`.
3. أي أن تفعيل `skia_use_harfbuzz` وحده **لا يمنح PDFium تشكيلًا**؛ الخطر المذكور في `02-plan.md` تحقّق حرفيًا.

## الأثر على الخطة (تعديل إلزامي)

المرحلة ١ تبدأ بـ**إضافة اعتماد صريح** على `//third_party/harfbuzz:harfbuzz` في هدف PDFium الذي سيحمل
`shaping.{h,cc}` (لا الاعتماد على Skia)، ثم إعادة بناء والتأكد من ظهور رمز (مثل `hb_shape`) في الكائن
الجديد — قبل كتابة أي منطق تشكيل.

## ما لم يُثبت

- أن إضافة الاعتماد تمرّ بلا كسر بناء (لم تُجرَّب بعد).
- أن Skia في هذا البناء تستدعي HB أصلًا؛ لم نُثبت العكس، فقط أن PDFium لا يعتمد عليه.
