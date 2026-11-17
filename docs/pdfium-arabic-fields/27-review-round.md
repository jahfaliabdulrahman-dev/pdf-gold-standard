# ٢٧ · جولة المراجعة الثلاثية: ما وُجد وما أُغلق

| | |
|---|---|
| **نقطة التثبيت** | `8bca5ad` |
| **الرأس المراجَع أولًا** | `11b63d8` — ثلاث مقاعد، ثلاث `REQUEST CHANGES` |
| **الرأس بعد الإصلاح** | `6b2981b` |
| **الاختبارات** | `pdfium_unittests` ١٢٦٤/١٢٦٤ · الهارنس ٩/٩ |

المقاعد الثلاثة (Standards · Spec · Structure) راجعت `11b63d8` فوجدت ١٩ ملاحظة. كل ملاحظة
أدناه إمّا أُغلقت بتغيير في `6b2981b` أو أُغلقت بدليل قياس. لا موضع مؤجَّل بلا مالك.

## ١ · الملاحظة الجذرية: `/ActualText` لا يُقرأ بالطريقة نفسها

Spec-P1 قاس أن poppler يعكس مقطع `/ActualText` كاملًا حيث كان الـAP القديم يُستخرج منه صحيحًا.
وأعدت القياس على مصفوفة كاملة (`--source` واحد، أربعة حقول، ثلاثة قرّاء):

| ما في الـAP | PDFium | poppler | MuPDF |
|---|---|---|---|
| `/ActualText` بترتيب منطقي | ✓ منطقي | ✗ **معكوس** | ✓ |
| `/ActualText` بترتيب بصري | ✗ معكوس | ✓ منطقي | ✗ |
| رمز واحد لكل معرّف، `/ToUnicode` منطقي | ✗ حرفان من الليجاتور يتبادلان | ✗ | ✓ |
| رمز واحد لكل معرّف، `/ToUnicode` بصري | ✓ | ✓ | ✗ الحرفان يتبادلان |
| **`/ToUnicode` بترتيب بصري للمجموعة، ولا `ActualText`** | **✓** | **✓** | ✗ داخل الليجاتور فقط |

والسبب مقيس: PDFium يقلب محارف المقطع RTL **إلا** إذا كانت من نوع `CharType::kActualText`
(`core/fpdftext/cpdf_textpage.cpp:867-880`)، وpoppler يقلب أي نص RTL يقرؤه. فـ`/ActualText`
المنطقي صحيح حسب المعيار، لكن قارئين من ثلاثة يقلبانه؛ و`/ToUnicode` البصري هو الشكل الوحيد
الذي يتفق عليه القارئان اللذان نستهدفهما (`PDFium` محرّكنا و`poppler` أشيع قارئ خارجي)، وثمنه
أن MuPDF يقرأ حرفَي الليجاتور بالترتيب البصري.

**القرار:** الـAP لا يحمل `ActualText` بعد الآن. كل مقطع مُشكَّل يرسم بخطّ **نسخة** من خطّ الحقل
يحمل `/ToUnicode` يغطي معرّفاته (`CPVT_FontMap::CreateShapedFontAlias`، `cpvt_fontmap.cpp:144`)،
والخطّ الأصلي يبقى لبقية الحقل. لا شيء يُكتب في خطّ المستند.

## ٢ · جدول الإغلاق

| # | المقعد · الشدّة | الملاحظة | الإغلاق في `6b2981b` |
|---|---|---|---|
| ١ | Standards P1 | أصل سطر عالق في `line_stream` حين يبدأ السطر بمقطع مُشكَّل ⇒ حقل متعدد الأسطر يرسم المقطع من منسأة السطر السابق | `flush_pending` واحد يُكتب قبل كل مقطع `cpdf_generateap.cpp:418`، ويستعمله المسار العادي في المواضع الثلاثة |
| ٢ | Standards P2 | لا اختبار لكاتب الـAP | اختبارات `CreateShapedFontAlias` (٤) + `IsShapableFontDict` (٨) + مقارنة AP↔HarfBuzz وAP↔المحرّر في الهارنس |
| ٣ | Standards/Spec P3 | حارس كسر السطر يسأل عن العرض لا عن التشكيل | `is_cluster_tail = nShapedRun >= 0 && fShapedAdvance <= 0` `cpvt_section.cpp:800` |
| ٤ | Standards P3 | `cfx_face.h` بدل `cfx_font.h`، وإعفاءان متكرران | تصحيح التضمين + `compiler_specific.h`، وإبقاء الإعفاء على مستوى الملف وحده |
| ٥ | Standards P3 | اسم مجموعة الاختبار يذكر ملفًا محذوفًا | `ShapingTest` (١١ اختبارًا) |
| ٦ | Standards P3 | معرّف العلة `42290239` يعني أمرين | بقي لموضعَي HarfBuzz، ونُزع عن `field_probe.cpp` |
| ٧ | Spec P1 | poppler يعكس المقطع | §١: أُزيل `ActualText`؛ poppler يعيد الحقول الأربعة بترتيبها المنطقي |
| ٨ | Spec P2 | `/ToUnicode` لا يغطي معرّفات التشكيل | نسخة الخطّ تحمله، و`measure_text.py` يثبت الاستخراج |
| ٩ | Spec P2 | صناديق المحارف في PDFium نقطة واحدة | لا `ActualText` ⇒ لكل محرف معرّفه وموضعه؛ `mixed` صار `الصفحة 5 من 10` بلا مسافة منزاحة |
| ١٠ | Spec P2 | لا اختبار لبوابة التشكيل | `IsShapableFontDict` دالّة نقية + ٨ اختبارات (قبول، غياب الخريطة، `Identity` صريح، `Identity-V`، خريطة دفق، `CIDFontType0`، سليلان، بلا سوّليات) |
| ١١ | Spec P2 | اختبار النقر على فقرة LTR فيها مقطع RTL غير موجود | `SearchWordPlaceInsideAnRtlRunOfAnLtrParagraph` بأرقام مقيسة |
| ١٢ | Spec P3 | المسح O(n) لكل حدث مؤشّر | `SearchWordPlaceImpl` يأخذ حدّ الصندوق من بداية التالي ⇒ مقارنات عشرية بلا استعلام خطّ `cpvt_section.cpp:418-430` |
| ١٣ | Structure P1 | `CPVT_Word` يملك `vector` بلا نقل ⇒ تخصيص لكل كلمة في كل رسم | رجع span (عرض) والتوثيق على عمره `cpvt_word.h:41-45`؛ لا تخصيص |
| ١٤ | Structure P2 | المخزن يعيد بناء سجلّ القسم | المخزن صار نسخة من ٤٨ بايت (span + أرقام) بلا تخصيص، والقسم يعرض محارف العناقيد `shaped_chars()` |
| ١٥ | Structure P2 | خمس نسخ من «افرغ المعلّق» | `flush_pending` واحد |
| ١٦ | Structure P2 | مسح بلا سقف مقارنات | §١٢ |
| ١٧ | Structure P2 | فهرس خارج المدى عند أول كلمة في سطر | `nearest > begin ? nearest - 1 : -1` + اختبار السطر الثاني |
| ١٨ | Structure P3 | ثلاث تمثيلات لـ«مُشكَّل» | `is_shaped()` مشتقّة من `run_id_ >= 0` وحده |
| ١٩ | Structure P3 | حارس صفري بعرض | §٣ |
| ٢٠ | Structure P3 | تكرار `CPVT_Glyph`/`ShapedGlyph` | **ليس تكرارًا**: `ShapedGlyph` مخرج المشكِّل بوحدات الخط (يشمل `cluster` و`x_advance` الخام)، و`CPVT_Glyph` الصورة الجاهزة للتخطيط (مقاسات كنسبة من الحجم، بلا عنقود). التحويل في `cpvt_section.cpp:598-606` هو الحدّ بين الطبقتين |
| ٢١ | Structure P3 | `AppendActualText` يقرأ من المخزن | زال مع `ActualText` |

## ٣ · ما تغيّر في الرسم

**لا شيء.** مقارنة بكسليّة عند ١٤٤ نقطة/بوصة بين `11b63d8` و`6b2981b` للحقول الستة:
`ar · mixed · ltr_mixed · center · latin · nonidentity` → `same pixels: True` في الستة.
التغيير في الاستخراج وحده، وهذا هو البرهان على أن إصلاح الاستخراج لم يمسّ الرسم.

## ٤ · القياس النهائي

```
pdfium_unittests   1264/1264   (كانت 1250: +8 بوابة، +4 نسخة خطّ، +2 نقر/سطر)
run.sh             9/9 RESULT PASS

ar          text='لا'                 poppler 0644 0627 · mupdf 0627 0644
q0          text='الصفحة'             poppler ✓ · mupdf ✓
ltr_mixed   text='abc الصفحة def'      poppler ✓ · mupdf ✓
mixed       text='الصفحة 5 من 10'      poppler ✓ · mupdf ✓
```

الأوامر في `26-clusters-result.md` §٥، ولاستخراج مصفوفة §١:
`.venv/bin/python - <<…` مع `measure_text.appearance_only` ثم `pdftotext`/`pymupdf`/`text_probe`.
