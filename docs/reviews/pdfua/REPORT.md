# مراجعة PDF/UA-1 — ثلاثة مقاعد، وكل finding إما مُغلق أو مدحوض بالدليل

النطاق: `git diff facc0e7..HEAD` · ثلاثة مقاعد مستقلة (Standards · Spec · Structure) على Qwen 3.8-max
بجهد minimal (Claude بلغ حدّه الأسبوعي). المقاعد للقراءة فقط، ولم تشارك في كتابة الكود.

## ما أُغلق

| # | المقعد | الموضع | الشدّة | العيب | الإغلاق |
|---|---|---|---|---|---|
| ١ | Structure | `postprocess.py:145` | **P0** | `document["/K"] = Array([elem])` يمحو أبناء المستند كلهم | يُضاف العنصر إلى المصفوفة القائمة، ويُغلَّف الطفل المفرد بدل استبداله. قياس: `report.pdf` أبناء المستند ١١ → **٥٣** بعد الإصلاح، وعقد الشجرة ٤٠٦ |
| ٢ | Standards | `scripts/verify_pdf.py:440` | P1 | `/Suspects` الغائب كان يُقرأ كخطأ، والمواصفة تجعله `false` | يُشترط `is True` فقط |
| ٣ | Standards + Structure | `postprocess.py:270` | P1 | حقن مخطط XMP بدمج نصّي صامت داخل أول `rdf:Description` | وصف مستقلّ `rdf:Description` بمساحاته، ثم **تحقق بعد الكتابة** أن `pdfuaid:part` نجا |
| ٤ | Spec | `scripts/verify_pdf.py:474` | P1 | البوابة لا تتحقق من ادّعاء «لا يعبر Artifact حدود `q/Q` أو `BT/ET`» | تتبّع `gs`/`bt` داخل `untagged_runs`؛ أي عبور = مخالفة صريحة |
| ٥ | Structure | `postprocess.py:67` + `verify_pdf.py` | P1 | `PAINT_OPS` معرَّفة مرتين | `pdfops.py` واحد يستورده الطرفان |
| ٦ | Standards + Spec | `scripts/verify_pdf.py:527` | P2 | Figure يُقبل بـ`/Alt` فقط، و`/ActualText` بديل مكافئ في 7.3 | يُقبل أيّهما غير فارغ |
| ٧ | Standards | `scripts/verify_pdf.py:_parent_tree` | P2 | قراءة `/Nums` وحدها تتجاهل عقد `/Kids` الوسيطة | اجتياز تكراري للعقد |
| ٨ | Structure | `postprocess.py:~195` | P2 | تمييز مواصفة المستند بـ`hasattr(spec,"PAGES")` هشّ | `isinstance(spec, types.ModuleType)` |
| ٩ | Structure + Spec | `scripts/verify_pdf.py:1085` | P2 | `copy_fidelity` قد يسقط صامتًا إلى الأصل عند غياب نسخة الطباعة | فشل مغلق عند `NAV_VISIBLE=False`، ونشر `*.source.html` بجانب الملف المُصدَر ليُحاكَم لاحقًا |
| ١٠ | Structure | `postprocess.py:~215` | P3 | `queue.pop(0)` ⇒ O(n²) على مئات الـForms | `collections.deque` |
| ١١ | Structure | `postprocess.py:~100` | P3 | قائمة `dos` ميتة تُجمع وتُهمل | حُذفت |

## ما دُحض بالدليل

- **`"n"` ليس عملية رسم (Standards P3)**: `n` ينهي مسارًا بعد `W` (قصّ) ويظهر كعنصر محتوى عند veraPDF؛
  إخراجه من مجموعة المنتِج يخلق تباعدًا بين ما نلفّه وما يقيسه المدقّق. أُبقي، والسبب مكتوب في `pdfops.py`.
- **`pdfaExtension` غير موجود (Spec P3)**: موجود في `postprocess.py` (`_pdfua_description`)، والدليل
  `verapdf --flavour 3b` = صفر مخالفة على الملفات الثلاثة بعد الإصلاح.

## القياس النهائي

- `najd.pdf` · `report.pdf` · `report-print.pdf`: **`3b` صفر و`ua1` صفر**.
- البوابة خضراء على الثلاثة، والملف المُصدَر للطباعة يُحاكَم من جديد بلا أخطاء.
- `gate_selftest.py`: **48/48** طفرة في الجانب الصحيح، وخط أساس نظيف.
- هجوم متعمّد (إزالة أزواج `Artifact` من صفحة) ⇒ `FAIL pdfua - p1: 2 untagged run(s)`.

## ما لم يُثبت

- أن الشجرة المنطقية **بترتيب قراءة صحيح** بعد إضافة ٤٢ عنصر `/P` للتشغيلات اليتيمة — veraPDF يقبل البنية،
  ولا يوجد قارئ شاشة عربي في هذه البيئة للحكم على الترتيب فعليًا.
- أن `figure_alt_problems` يغطي صورًا داخل Form XObjects غير مفحوصة.
- أن ملفًا ثالثًا (غير الثلاثة) يمرّ: القياس على نجد والتقرير ونسخته المطبوعة فقط.
