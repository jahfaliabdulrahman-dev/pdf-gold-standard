# سجل التجارب — أرقام قابلة لإعادة الإنتاج

كل أمر هنا نُفِّذ فعلًا على هذا الجهاز (M4 · ٢٤GB · macOS 27.2.1) في ١٥ نوفمبر ٢٠٢٦.

## ١. القياس المرجعي للتشكيل (HarfBuzz) — مُثبت

```bash
cd ~/Projects/pdf-gold-standard-fix
.venv/bin/pip install uharfbuzz python-bidi
.venv/bin/python - <<'PY'
import uharfbuzz as hb
blob = hb.Blob.from_file_path("fonts/IBMPlexSansArabic-Regular.ttf")
font = hb.Font(hb.Face(blob))
def shape(s):
    b = hb.Buffer(); b.add_str(s); b.guess_segment_properties(); hb.shape(font, b)
    return [i.codepoint for i in b.glyph_infos], [p.x_advance for p in b.glyph_positions]
for s in ["عبدالرحمن", "لا", "ملاحظات", "بسم الله", "Unicode سليمًا"]:
    g, a = shape(s)
    print(f"{s!r:20} chars={len(s):2d} glyphs={len(g):2d} gids={g}")
PY
```

الخرج (حرفيًا):

```
'عبدالرحمن'          chars= 9 glyphs= 9 gids=[535, 916, 624, 455, 477, 286, 659, 316, 766]
'لا'                 chars= 2 glyphs= 1 gids=[1066]
'ملاحظات'            chars= 7 glyphs= 6 gids=[517, 293, 732, 624, 1078, 920]
'بسم الله'           chars= 8 glyphs= 8 gids=[933, 381, 477, 286, 3, 912, 359, 389]
'Unicode سليمًا'     chars=14 glyphs=14 gids=[53, 20, 15, 7, 21, 8, 9, 3, 674, 486, 992, 906, 1614, 286]
```

**الدلالة**: «لا» تنكمش من محرفين إلى شكل واحد؛ «ملاحظات» من ٧ إلى ٦. أي أن أي محرّك يرسم محرفًا لكل وحدة UTF-16 **لا يمكن** أن يُنتج الصورة الصحيحة، ولو كان الخط كاملًا.

## ٢. حقيقة PDFium البنيوية — مُثبت من الشيفرة

| ما | أين |
|---|---|
| رسم كلمة واحدة لكل نداء (uint16) | `fpdfsdk/pwl/cpwl_edit_impl.cpp:33-48` |
| عرض الحرف بمعرّف واحد | `cpwl_edit_impl.cpp:113-126` |
| الرسم حرفًا حرفًا | `cpwl_edit_impl.cpp:594, 672, 684, 695` |
| Skia يرسم gids جاهزة بلا تشكيل | `core/fxge/skia/fx_skia_device.cpp:845-868` |
| ICU مضمّن | `DEPS:387` |
| Skia: `skia_use_harfbuzz = true` | `skia/gn/skia.gni:64` |
| SkShaper يربط harfbuzz | `skia/modules/skshaper/BUILD.gn:19, 51-55` |

الأوامر:

```bash
curl -sSL -o /tmp/p/cpwl_edit_impl.cpp \
  https://raw.githubusercontent.com/chromium/pdfium/main/fpdfsdk/pwl/cpwl_edit_impl.cpp
curl -sSL -o /tmp/p/skia.gni https://raw.githubusercontent.com/google/skia/main/gn/skia.gni
grep -n "skia_use_harfbuzz" /tmp/p/skia.gni
```

## ٣. الأثر المرئي — مُثبت

- صورة `evidence-field.png`: في Chrome، تسمية الصفحة (نص مطبوع) متصلة، والنص داخل الحقل منفصل — بالخط نفسه.
- بلاغ المالك: Acrobat على الهاتف لا يُظهر إلا الحرف الأول؛ وعلى ويندوز حروف منفصلة ومعكوسة.

## ٤. صفر استدعاء تشكيل في PDFium — مُثبت

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/chromium/pdfium.git /tmp/pdfium-src
cd /tmp/pdfium-src && git sparse-checkout set fpdfsdk core
git rev-parse HEAD            # a84323421e94f484faca52dd9d027934eba42ab8
grep -rn "hb_shape\|SkShaper\|SkParagraph\|textlayout" fpdfsdk core | wc -l    # 0
```

الخرج: **0**. و`third_party/harfbuzz` غير موجود في شجرة PDFium نفسها؛ يأتي عبر Skia. وتحقّقنا على
**إصدار Skia المثبَّت في DEPS** لا على main:

```bash
SHA=a1ff58d34294ad2c1d2e74b796cd9b658be2cfe0   # skia_revision in pdfium/DEPS@a8432342
curl -sSL https://raw.githubusercontent.com/google/skia/$SHA/gn/skia.gni | grep -n skia_use_harfbuzz
# 54:  skia_use_harfbuzz = true
curl -sSL https://raw.githubusercontent.com/google/skia/$SHA/third_party/harfbuzz/BUILD.gn | grep -n externals
# 23:    _src = "../externals/harfbuzz/src"
```

أي أن **المحرّك موجود في الشجرة عند الإصدار المثبَّت، وغير موصول** — وهذا بالضبط موضع النقص.

## ٥. الأداء — مُقاس (يسدّ «التشكيل مكلف»)

شكل سطرًا من ٢٠٠ محرف (عربي + أرقام + لاتيني) ١٠٠٠ مرة بـ`hb_shape`:

```
chars=200 glyphs=194 | P50=0.015ms P95=0.017ms max=1.775ms
```

الاستنتاج: التشكيل **لا يُرى** في زمن الكتابة (ضغطة = ~١٦ms إطار). لا حاجة إلى debounce.

## ٦. ما بقي بلا قياس

1. زمن بناء PDFium الأول على هذا الجهاز (تقدير ٢–٤ ساعات).
2. سلوك PDFKit (Preview).
3. أن `FPDF_SetFormFieldValue` يكتب `/AP` بالمحارف المشكّلة في نسخة معدّلة (يُقاس في المرحلة ٥).
