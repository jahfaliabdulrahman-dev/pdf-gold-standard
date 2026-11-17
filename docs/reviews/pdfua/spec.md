**Finding 1** — `scripts/verify_pdf.py:474` · **P1** · مثبت

الادّعاء (ROADMAP): «لا يعبر Artifact `q/Q` أو `BT/ET`».
السلوك: `untagged_runs` يتتبع عمق `BMC/BDC/EMC` فقط؛ لا يعدّ `q`/`Q` ولا `BT`/`ET`. Artifact يفتح قبل `q` ويغلق بعد `Q` يمرّ دون إنذار، والباب الداخلي أعمى عن القيد الذي يعلنه.
الإصلاح: إضافة عدّاد `gs_depth` و`bt_depth`؛ إذا تغيّر أحدهما بين فتح Artifact وإغلاقه يُضاف خطأ.

**Finding 2** — `scripts/verify_pdf.py:527` · **P2** · مثبت

الادّعاء (docstring): «Figure without /Alt is an image a screen reader must skip or guess».
السلوك: الفحص يشترط `/Alt` فقط. ISO 14289-1 §7.3 يسمح بـ `/ActualText` بديلًا مكافئًا. Figure يحمل `/ActualText` بلا `/Alt` يُبلَّغ خطأً كمخالفة، فيكسر البوابة على ملف مطابق.
الإصلاح: `if not node.get("/Alt") and not node.get("/ActualText")`.

**Finding 3** — `scripts/verify_pdf.py:1090` · **P2** · مرجّح

الادّعاء (docstring): «When Chrome's rendered copy sits next to the file being judged, that copy is the source of truth».
السلوك: `getattr(doc, "name", "")` ليس سمة مضمونة في `pikepdf.Pdf` (تُضبط فقط عند الفتح بمسار، لا من stream أو bytes). إذا غابت، `rendered = None` ويُستدعى `source_text()` صامتًا — أي أن الوعد «المصدر هو ما طُبع فعلًا» يتعطّل بلا أي تحذير، والنتيجة تُقاس ضد الأصل الذي يحمل شريط التنقّل المحذوف.
الإصلاح: تمرير مسار الملف صراحةً كمعامل، أو رفع تحذير عندما لا يُعثر على `.source.html`.

**Finding 4** — `report_spec.py:185` · **P3** · مرجّح

الادّعاء (ROADMAP): «`pdfuaid:part` مع `pdfaid` يحتاج وصف مخطط `pdfaExtension`».
السلوك: `CONFORMANCE` أضاف `"pdfuaid:part": "1"` لكن لا يظهر في الـ diff أي كتابة لـ `pdfaExtension` في XMP. إن كان يُكتب في ملف آخر فلم يُعرض، وإن لم يُكتب فالمطالبة نفسها تنكسر عند تحقق PDF/A (6.6.2.3.1).
الإصلاح: إضافة مخطط `pdfaExtension` في كتلة XMP أو الإشارة إلى الموضع.

Not proven.