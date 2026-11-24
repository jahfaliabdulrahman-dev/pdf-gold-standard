# فاحص النسخ العربي v0 — المصادر الرسمية والآلية

**الغرض:** إثبات أن كل إشارة في الفاحص لها أصل معياري أو قياس، لا رأي.
**الوسم:** `مُثبت` = نصٌّ مقتبس من المصدر بعد تنزيله وقراءته؛ `مرجّح` = استنتاج هندسي؛ `مجهول` = يُعلن.

## 1 · الطبقة المعيارية (لماذا ينكسر النسخ أصلًا)

### 1.1 ISO 32000-1:2008 (PDF 1.7) — §9.10.2 `مُثبت`

> "A conforming reader can use these methods, in the priority given, to map a character code to a Unicode value.
> **Tagged PDF documents, in particular, shall provide at least one of these methods** (see 14.8.2.4.2,
> "Unicode Mapping in Tagged PDF"): If the font dictionary contains a ToUnicode CMap … use that CMap…"

و§14.8.2.4.1:

> "Tagged PDF enables character codes to be **unambiguously** converted to Unicode values representing the
> information content of the text."

و§14.8.2.4.2:

> "Tagged PDF requires that **every character code in a document can be mapped** to a corresponding Unicode value."

و§14.8.2.4.2 NOTE 2 — وهذا سبب فحص **ActualText** لا النصّ وحده:

> "some conforming readers may choose to use the Alt or ActualText value and ignore all text and other content
> associated with the structure element and its descendants."

**التحقق:** نُزِّل الملف الرسمي `PDF32000_2008.pdf` من `opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/`
(22,491,828 بايت)، ثم:

```
~/.cache/poppler-pin/26.11.0/bin/pdftotext -q iso32000.pdf iso32000.txt
grep -n "Tagged PDF requires that every character code" iso32000.txt     # 50804
grep -n "^9.10.2$" iso32000.txt                                          # 25183
```

### 1.2 Matterhorn Protocol 1.1 (PDF Association، CC BY 4.0) — `مُثبت`

البروتوكول هو التفكيك القابل للاختبار لـ ISO 14289-1 (PDF/UA-1). الشروط التي تخصّ النسخ:

| الشرط | نصّه | Section | How |
|---|---|---|---|
| `10-001` | Character code cannot be mapped to Unicode. | UA1:7.2-2 | M |
| `31-027` | A font dictionary does not contain the ToUnicode entry **and none of the following is true** … (MacRoman/WinAnsi، أو أسماء حروف من Adobe Glyph List، أو مجموعات CID المعروفة، أو TrueType غير رمزي) | UA1:7.21.7-1 | M |
| `31-028` | One or more Unicode values specified in the ToUnicode CMap are **zero (0)**. | UA1:7.21.7-2 | M |
| `31-029` | One or more Unicode values … equal to either **U+FEFF or U+FFFE**. | UA1:7.21.7-3 | M |
| `31-030` | One or more characters used in text showing operators reference the **.notdef** glyph. | UA1:7.21.8-1 | M |
| `31-009` | For a font used by text intended to be rendered the font program is not embedded. | UA1:7.21.4.1-1 | M |
| `31-011` | … embedded but it does not contain glyphs for all of the glyphs referenced by the text used for rendering. | UA1:7.21.4.1-3 | M |

**الأعداد المعلنة (نصّ المقدمة):** 31 checkpoint · 136 failure condition · **87 حاسوبية** · 47 تحتاج حكمًا بشريًا ·
2 بلا اختبار (`23-001`, `27-001`). في 1.1 أُضيف `13-008` فصار عدد الصفوف 137 والتوطئة تقول 136 —
نقلًا عن مقارنة `horn.report` (طرف ثالث)؛ **لا نعتمد هذا الرقم في أي حكم**، ونعلن فقط ما نفحصه بالاسم.

**التحقق:** `web_extract` لملف PDFA الرسمي
`pdfa.org/download-area/publications/Matterhorn-Protocol-1-1.pdf` (الصفحة مقتبسة أعلاه حرفيًا).

### 1.3 W3C — Arabic & Persian Layout Requirements (Group Draft Note، 2 أكتوبر 2025) `مُثبت`

- §3.1: «Arabic script is written from right to left. **Numbers, even Arabic numbers, are written from left to
  right**» → أساس فحص اتجاه الأرقام داخل سطر عربي.
- §3.2: يحيل إلى UAX #9 ويشرح أن الترتيب المخزَّن **منطقي** وأن ترتيب العرض بصري — أي أن نصًّا «معكوسًا»
  في الطبقة هو نقلٌ لترتيب العرض إلى المخزَّن، وهو الخرق الذي يقيسه الفاحص.
- §4.3: فئات الوصل (Joining Categories) وأشكال السياق — أي أن الأشكال `U+FB50–FDFF`/`U+FE70–FEFF`
  ليست «حروفًا» بل **أشكال عرض** يجب أن يعيد القارئ طيّها إلى حروف أساس.
- §6.1: عائلات الأرقام (Arabic-Indic / Eastern Arabic-Indic / European) — أساس `numerals-*`.

**التحقق:** `https://www.w3.org/TR/alreq/` — نُزِّل النصّ كاملًا (147,689 محرفًا) وقُتبست المواضع أعلاه.

### 1.4 Unicode — UAX #9 (الإصدار 18.0.0، 2026-09-01، مراجعة 52) `مُثبت`

الخوارزمية المرجعية للـbidi؛ الفاحص لا يعيد تنفيذها — **بل يقيس أثرها**: نصٌّ عربي في ترتيب بصري
يعني أن كاتب الملف نقل ترتيب العرض إلى المخزَّن (خرق §3.2 أعلاه).

### 1.5 نطاقات Unicode للأشكال والـPUA `مُثبت`

`U+FB50–U+FDFF` (Arabic Presentation Forms-A)، `U+FE70–U+FEFF` (Presentation Forms-B)،
`U+E000–U+F8FF` (Private Use Area) — مستخدمة كما هي في `conformance/checks/metrics.py`
(`PRESENTATION_FORM`, `PUA`)، ولا تُكتب مرة ثانية في الفاحص.

## 2 · الآلية: كيف يُبنى فاحص نسخ (المنهج المُتبَع)

المنهج الكلاسيكي في أدبيات الاستخراج يقوم على أربع طبقات، وكلها قابلة للقياس بلا نموذج مدرَّب:

1. **اكتمال الخريطة** (ToUnicode): هل لكل رمز مرسوم قيمة Unicode؟ — شرط ISO أعلاه، ويُقاس بعدّ
   `missing_unicode` و`.notdef` من تدفّق المحتوى مباشرة (`conformance/checks/mcid_text.py`).
2. **طيّ الأشكال**: هل خرجت أشكال عرض بدل حروف؟ — عدّ نطاقي حتمي.
3. **الترتيب**: منطقي أم بصري؟ — لا معيار واحد يقيسه، فالحل المتعارف ثلاثة شواهد لغوية مصوَّت عليها
   (حروف لا تبدأ بها الكلمة، صيغ الوصل، أداة التعريف) — وهي آلية `arafix.detect_visual_order` (MIT).
4. **الخلاف بين القرّاء**: لا سطر معياري له؛ إشارة هندسية: نصّان مختلفان لملف واحد يعني أن أحدهما على
   الأقل لا يُنتج ما رآه صاحب الملف.

## 3 · ما هو موجود أصلًا — قياس قبل الكتابة `مُثبت`

| المكتبة | الرخصة | ما تقدّمه | القرار |
|---|---|---|---|
| **arafix 1.2.0** | **MIT** (نواة بلا تبعيّات) | `diagnose()` + `detect_visual_order()` بثلاثة شواهد، عتبات مصرَّحة `DEFAULT_THRESHOLDS` (visual_order 0.30)، ثقة تفصل القاطع عن الظنّي، معجم مضمَّن 1.7k مدخلًا (MIT) | **يُستورد** لإشارة الانعكاس — لا نكتب كاشفًا ثانيًا |
| **arabic-repair 0.1.0** | MPL-2.0 (+ `arabic-rt` MPL-2.0) | `detect()` = نسبة كلمات تحمل أشكال عرض فقط؛ **لا كاشف انعكاس** (`is_shaped` عدّ نطاقي) | **يُرفض** — يضيف تبعية لمقياس يملكه `conformance` بالفعل |
| **qalam** | GPL-3.0 | استخراج عربي صحيح + حكم لكل صفحة | **لا يُستورد** (GPL-3 يعدي المستودع)؛ يُذكر كسابقة أدبية فقط |
| **Horn** | أداة PDF/UA | يغطّي Matterhorn كاملًا | سابقة منتج، لا تبعية |

**قياس arafix (جملة عربية واحدة، 2026-11-21):**

```
logical   score -1.0   final_only_letters -1.0 · definite_article -1.0
reversed  score +1.0   final_only_letters +1.0 · definite_article +1.0   → Defect.VISUAL_ORDER، ثقة 1.0
```

## 4 · ما لا يوجد في المصادر (يُعلن ولا يُخترع)

- **عتبة رسمية لـ«خلاف القرّاء»** لا توجد؛ إشارتنا مشتقة من `metrics.word_f1` القائم، وتُعلن بوسمها.
- **عتبة رسمية لأشكال العرض** لا توجد في ISO (ISO يمنع «Unicode value = 0/FEFF» فقط)؛ نستخدم عتبة arafix
  المصرَّحة (2%) كسقف خطر عالٍ، ونقيس الفصل على مجموعات القياس قبل تثبيتها.
- **قارئ Acrobat** خارج v0؛ غيابه يُعلن في كل تقرير.
