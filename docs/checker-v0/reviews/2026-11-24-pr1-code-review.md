# Code Review: checker v0.1 — PR-1 (`fix/checker-v0.1`)

**Target:** `576c46e...d296f10` (11 commits كود + 4 التزامات سلك CI؛ ملفات الإصلاح). المقاعد قرأت الشجرة
المثبّتة عند `d0ee8b0`/`dec5ea1`؛ الفارق `e304650..1868251` هو استجابة المراجعة، والفارق
`c10e906..d296f10` سلك CI فقط (لا كود فاحص). لا تغييرات غير مُودَعة في المدى (عدا `IDEA.md`، خارج النطاق).
**Context:** `arabic-pdf-check` فاحص نسخ عربي أعمى: مستوى خطر وثقة وأدلة مسمّاة، بلا PASS وبلا نسبة؛ طبقة رقيقة
فوق `conformance/` (قارئ واحد، مقياس واحد، تطبيع واحد). PR-1 يغلق تدقيقًا خارجيًا: `recovered`، ومحلّل
ToUnicode، والتقطيع، والضوابط المخزّنة، وعزل القرّاء، والرفض، والتعقيم، و`lcs`، وسلك CI.

## Verdict

**APPROVE** — لا P0/P1/P2 مفتوحًا في المدى النهائي؛ الثلاثة الحاجزة عند Standards وSpec وStructure أُغلقت
وأُعيد قياسها. Blocking: none.

## Standards

1. **P1** `conformance/readers/isolate.py:57` — كان القارئ يكتب نصّ الملف كاملًا في `out.json` داخل مجلد مؤقت،
   و`README` يعدّ بـ«لا ملف مؤقت»، و`test_privacy` يرى الأب فقط. consequence: نصّ مستند غير موثوق على القرص.
   Move: pipe موروث. Evidence: `test_privacy` PASS و`test_reader_isolation` PASS بعد `e304650`. Tag: مُثبت.
   **Fixed** (`e304650`): `_isolated_reader` يكتب إلى fd، و`isolate.read` يقرأه بخيط تصريف؛ لا ملف.
2. **P1** `arabic_pdf_check/blind.py:361` — تفصيل `visual-order` كان يطبع «of 5 declared» بينما الأغلبية على من
   قرأ؛ `README` يثبّت 3 من 5. consequence: تقرير يخالف قاعدته على جهاز بثلاثة قرّاء. Move: مقام واحد.
   Evidence: `test_blind` PASS بعد أن صار `len(ok)`؛ `README:37` يعلن `need = ⌊n/2⌋+1` وتجاوز ST-5. Tag: مُثبت.
   **Fixed** (`3d95ddc`): السطر والتوثيق والقياس تستعمل `majority_needed`.
3. **P2** `conformance/readers/isolate.py:26` — `TIMEOUT=120` كان حدًّا غير معلن، و`reader-failure` إشارة
   جديدة غير موثقة. consequence: عقد قديم. Move: أعلنه. Evidence: `README:42` يذكر 120 ثانية،
   و`known_limits` يذكرها في التقرير. Tag: مُثبت. **Fixed** (`3d95ddc`).
4. **P2** `.github/workflows/build-pdf.yml:269` — وظيفة Linux تثبّت poppler من التوزيع بلا تثبيت، بينما
   توثيق `conformance` يثبّت 26.11.0. consequence: بابان لقراءة مختلفة. Move: سمّها فحصًا غير مثبّت أو ثبّت.
   Evidence: تعليق الوظيفة يعلنها «UNPINNED poppler smoke run… not the conformance floors». Tag: مُثبت.
   **Resolved as declared** (`3d95ddc`): الفحص يعلن ما هو، ولا يدّعي أرضيات conformance.
5. **P2** `conformance/checks/structure.py:174` — تحذير «الخريطة الناقصة» كان قائمة سماح من ثلاث سلاسل،
   فخريطة فيها surrogate أو نطاق >256 تخرج `level=None`. consequence: خريطة معطوبة تبدو نظيفة. Move: كل
   مشكلة غير قاتلة إلى موضعها. Evidence: `test_mcid_text` PASS: `surrogate-problem-is-high`،
   `usecmap-is-medium`، `capped-is-one-problem`. Tag: مُثبت. **Fixed** (`3d95ddc` + `1868251`).

## Spec

1. **P2** `arabic_pdf_check/blind.py:231` — `why_class(exc)` يعيد `ReaderFailed` وحده، فيضيع سبب المهلة/الانهيار.
   consequence: `reader-failure` لا يفرّق hang من crash، وهو سبب الإشارة. Move: سبب بسطر مع التعقيم.
   Evidence: `test_blind` `reader-failure:reason` PASS؛ `why_reason` يحذف المسارات. Tag: مُثبت.
   **Fixed** (`e304650`).
2. **P2** `conformance/cmap.py:254` — وجهة UTF-16 لا تُفكّ كانت تُسقط والـ`unparsable` يبقى False، فيقبل
   `FontState` خريطة ناقصة ويكتب الطبقة. consequence: «لا خريطة ناقصة بصمت» مخرومة. Move: الفجوة fatal.
   Evidence: `test_parse_tu` `bad-destination:report` و`bad-destination:strict-raises` PASS. Tag: مُثبت.
   **Fixed** (`e304650` + `565302e`).
3. **P2** `scripts/font_intake.py:74` — خط تجاري بـnameID 13 نص EULA بلا «all rights reserved» يعطي
   `redistribution_unclear=False`. consequence: «clear» لوجه بلا منح. Move: `restricted = not granted`.
   Evidence: `test_font_intake` `eula-name13-no-phrase` PASS. Tag: مُثبت. **Fixed** (`e304650`).
4. **P2** `conformance/checks/mcid_text.py:103` — `/UseCMap` قانوني، وكان يُصنَّف `unparsable` عاليًا مع تحذير
   متوسط في آن. consequence: ملف مطابق يأخذ high كاذبًا. Move: تحذير متوسط، والكاتب الصارم يرفض.
   Evidence: `test_mcid_text` `usecmap-is-medium` PASS والنوع `status=usecmap`. Tag: مُثبت.
   **Fixed** (`e304650` + `1868251`).
5. **P3** `arabic_pdf_check/blind.py:448` — قارئ واحد يطبع `needed: 0`، أي «أغلبية» لا وجود لها. consequence:
   إعلان ST-5 نفسه خاطئ. Move: `null`. Evidence: `test_blind` `majority:one-voter-none` PASS، والمخطط
   `integer|null`. Tag: مُثبت. **Fixed** (`71e47b7`).

## Structure

1. **P1** `conformance/checks/mcid_text.py:82-127` — حالة التحليل كانت أربع رايات + سلسلة `problem` قابلة
   للكتابة فوقها، فـ`capped` صار `unparsable` **و**`capped` (رسالتان)، و`UseCMap` أعطى high+medium،
   و`problems` تُهمل للخرائط التي تُقرأ. consequence: قانون واحد بأربع درجات. Move: `status` واحد.
   Evidence: `test_mcid_text` `capped-is-one-problem` و`usecmap-is-medium` و`surrogate-problem-is-high` PASS؛
   `blind` يختار id من `status`. Tag: مُثبت. **Fixed** (`1868251`): `status` في `mcid_text` و`structure`،
   والرايات دليل لا حكم.
2. **P2** `conformance/readers/_isolated_reader.py:20` — كان يعيد تنفيذ `readers.pages_many/text_many`.
   consequence: نسختان من التوزيع. Move: الدالتان القياسيتان. Evidence: `test_pages` PASS بعد `e304650`.
   Tag: مُثبت. **Fixed** (`e304650`): `pages_many(name,[path])` ثم `text_many`.
3. **P2** `conformance/readers/controls_runner.py:179` — `mode` كان له افتراضي `live`، و`reference.py` لم
   يمرّره. consequence: استدعاء منسي يشغّل Chrome/Swift. Move: بلا افتراضي. Evidence: كل المستدعين يمررون
   `mode` صراحة (`grep`)، و`test_declared`/`test_limits` PASS. Tag: مُثبت. **Fixed** (`e304650`).
4. **P2** `conformance/readers/controls_runner.py:79` — البصمة كانت تمشي `conformance/**` بما فيه `tests` و
   `corpus`، فتعديل اختبار يُبطل كل ضابط مخزّن. consequence: `check` يرفض كل الحدود بعد تعديل اختبار. Move:
   استثنِ ما لا يستورده الضابط. Evidence: `walk` يتجاوز `tests`/`corpus`؛ `test_controls` PASS. Tag: مُثبت.
   **Fixed** (`e304650`).
5. **P3** `scripts/fix_text_layer.py:58` — محلّل ToUnicode الوحيد كان داخل سكربت 1,159 سطرًا، و`mcid_text`
   يضع `scripts/` على `sys.path`. consequence: حدود مكسورة. Move: `conformance/cmap.py`. Evidence:
   `test_parse_tu` (أربعة CMaps حقيقية) و`test_fix_text_layer_parity` PASS بعد `565302e`. Tag: مُثبت.
   **Fixed** (`565302e`): المحلّل والكاتب في `conformance/cmap.py`، والسكربت يعيد التصدير.

## Declined to judge

- **نسبة استرداد متعددة الخطوط** — الخطة تعلنها والتقرير يطبعها في `not_judged`؛ تحتاج ملفًا بأكثر من خط
  قابل للنسبة، وهو خارج PR-1.
- **العزل بعملية** — لم يُطلب حرفيًا، لكنه السبيل الوحيد للنجاة من segfault؛ أُبقي وقياسه 3.4 ث/فحص.
- **ثبّت veraPDF 1.30.4** — نتيجة قرار سابق (لا يوجد مُثبِّت 1.30.0 عام)؛ أُعيد قياسه: مجموعات الفشل
  الأربعة متطابقة، والبوّابة HELD على المستندات الأربعة بمواصفاتها.

## CI closure

- `Build PDF` run [`45438456585`](https://github.com/jahfaliabdulrahman-dev/pdf-gold-standard/actions/runs/45438456585)
  على `d296f10` = **success**؛ `build` (macOS) و`checker-linux` (أربعة قرّاء) كلاهما أخضر.
- macOS: veraPDF 1.30.4 من الرابط+sha256، وخطوة LibreOffice الأجنبية، وقياس الفاحص.
- Linux: `test_poppler_dash` على poppler أوبنتو، والضوابط، و41 اختبارًا، وأربعة قرّاء.
- الدليل من داخل التشغيل: https://github.com/jahfaliabdulrahman-dev/pdf-gold-standard/actions/runs/45438456585

## Not proven  (ما لم يُثبت)

- **`test_blind` الكامل على Linux** — وظيفة Linux تفحص ملفًا لاتينيًا نظيفًا بأربعة قرّاء وتؤكد غياب
  PDFKit؛ لا تشغّل الملفات المزروعة العربية. ينتهي بتوسيع الوظيفة أو إعلان اقتصارها على المصفوفة (المعلن).
- **حكم عرض خريطة 2 بايت لخط 1 بايت (متوسط)** — الملف يُقرأ كاملًا (994–1000 محرف)؛ ينتهي بقرار المالك
  بعد فتح `الاستثمار في سوق الاسهم.pdf` ومقارنة النسخ.
- **Windows** — لم يُختبر أصلًا؛ ينتهي بتشغيل `check` عليه أو إعلان macOS/Linux فقط.

## Next steps

1. Push `fix/checker-v0.1` and let the owner run CI; fix any CI-only failure (Linux poppler, LibreOffice,
   veraPDF console install).
2. PR-2 (`feat/lexicon-wiki50k`) فوق PR-1، بقياس القرّاء الخمسة والـ55 وZATCA 16.
3. PR-3 (`refactor/drop-pymupdf`) بعد تكليف F.
4. Review only — لا دمج من الوكيل؛ الدمج للمالك بعد CI.
