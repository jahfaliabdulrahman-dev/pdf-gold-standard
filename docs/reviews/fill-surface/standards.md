# مراجعة STANDARDS · d7670da

المراجعة على `9bcdd84 → d7670da` (سطح التعبئة، الحل ١).

---

## P0 — حرج، يوقف الإصدار

### 1. البناء العادي لا ينشر الملف

**الموقع:** `build.py:219`

**المشكلة:** السطر `os.replace(PARTIAL, OUT)` كان بعد كتلة `if gate.returncode != 0` في الكود القديم، فإذا مرّت البوابة (returncode == 0) يُنقل الملف من `.partial.pdf` إلى الخرج النهائي. في الكود الجديد، السطر **انتقل إلى داخل** معالج الاستثناءات المعلنة (`if allowed and failing...`)، ولم يُضف مرة أخرى في المسار الطبيعي. النتيجة:

```python
if gate.returncode != 0:
    # ... معالجة الاستثناءات أو خروج بخطأ
    # os.replace موجود هنا فقط داخل if allowed...
print("[5/5] gate passed — published:", OUT)  # ← لم يُنقل الملف!
```

إذا مرّت البوابة بلا أخطاء (الحالة العادية)، نطبع `published: OUT` لكن الملف ما زال عند `PARTIAL` — كذب صريح.

**لماذا يهمّ:** كل بناء عادي (غير معبّأ) ينكسر: CI تفشل، `make` يُنتج `.partial.pdf` لا الملف المطلوب، والمالك يرى «نُشر» لكن الملف غير موجود.

**الحل:** أعد `os.replace(PARTIAL, OUT)` قبل السطر 219:

```python
if gate.returncode != 0:
    allowed = set(getattr(NS, "FILL_ALLOWED_FAILURES", ())) if getattr(NS, "FILL_MODE", False) else set()
    failing = {m.group(1) for m in re.finditer(r"^FAIL (\S+)", gate.stdout, re.M)}
    if allowed and failing and failing <= allowed:
        print("[5/5] filled copy — declared exceptions:", ", ".join(sorted(failing)))
        os.replace(PARTIAL, OUT)
        raise SystemExit(0)
    raise SystemExit(f"GATE FAILED — {OUT} left untouched; inspect {PARTIAL}")
os.replace(PARTIAL, OUT)        # ← أعده هنا
print("[5/5] gate passed — published:", OUT)
```

**الوسم:** مُثبت — تتبّعت المسار الكودي من السطر 206 (gate.returncode) حتى 219، ووجدت `os.replace` مفقودًا في مسار النجاح.

---

## P1 — عالٍ، أصلحه قبل الدمج

### 1. فحص الإدخال يبحث عن مسافة بدلًا من NUL

**الموقع:** `fill_server.py:35`

**المشكلة:**

```python
if " " in raw:
    raise ValueError("NUL in a value")
```

الكود يفحص `" "` (مسافة، ASCII 32)، لكن الرسالة تقول `NUL` (صفر، ASCII 0). المسافات شرعية في الأسماء («عبدالرحمن جحفلي») والملاحظات، لكن `\x00` ليس كذلك (يكسر معالجة النصوص، قد يسبب حقن). الشرط خطأ.

**لماذا يهمّ:** إذا أدخل المستخدم اسمًا فيه مسافة، يُرفض بخطأ مضلل («NUL in a value» بينما لا NUL فيه). وبايت NUL الحقيقي يمرّ دون رفض.

**الحل:** غيّر السطر 35 إلى:

```python
if "\x00" in raw:
    raise ValueError("NUL in a value")
```

**الوسم:** مُثبت — قرأت السطر ومقارنة السلسلة واضحة: `" "` ليس `"\x00"`.

---

## P2 — متوسط، يُحبّذ الإصلاح

### 1. تحليل خرج البوابة بـregex هشّ

**الموقع:** `build.py:210–214`

**المشكلة:**

```python
allowed = set(getattr(NS, "FILL_ALLOWED_FAILURES", ())) if getattr(NS, "FILL_MODE", False) else set()
failing = {m.group(1) for m in re.finditer(r"^FAIL (\S+)", gate.stdout, re.M)}
if allowed and failing and failing <= allowed:
```

يعتمد على نمط نصي في `verify_pdf.py` stdout (`^FAIL <name>`). إذا تغيّر شكل الخرج، الـregex لا يطابق، `failing` تصبح فارغة، والشرط `and failing` يفشل (آمن)، لكن السبب مخفي — قد يظنّ المطوّر أن البوابة مرّت بينما هي فشلت بشكل آخر.

**لماذا يهمّ:** الكود آمن عند الفشل (fail-safe) لكنه هشّ: أي تعديل في `verify_pdf.py` يكسره. معيار أفضل: `verify_pdf.py` تُخرج JSON (`{"failures": ["page-ink", ...]}`)، و`build.py` تحلّله بـ`json.loads`.

**الحل:** إما (أ) وثّق عقد الخرج (`^FAIL <check-name>` صيغة رسمية)، أو (ب) اجعل `verify_pdf.py --json` تُخرج `{"passed": bool, "failures": [...]}`، والبناء يحلّل JSON بدلًا من regex.

**الوسم:** مرجّح — الرمز يعمل (مُثبت في الاختبار)، لكن الهشاشة استنتاج؛ الاختبار الأرخص: `echo "unexpected format" | python -c 'import re; print(set(m.group(1) for m in re.finditer(r"^FAIL (\S+)", input(), re.M)))'` → `set()`.

---

### 2. قطع UTF-8 قد يشطر محرفًا متعدد البايتات

**الموقع:** `fill_server.py:86–88`

**المشكلة:**

```python
msg = html.escape(str(exc))[:1200].encode("utf-8")
```

القطع `[:1200]` يحدث **بعد** `encode("utf-8")`، فإذا انتهى عند منتصف محرف عربي (٢–٣ بايتات)، النتيجة بايتات غير صالحة. الترتيب الصحيح: قطع السلسلة، ثم ترميزها.

**لماذا يهمّ:** إذا كانت رسالة الخطأ طويلة وفيها عربية، المتصفّح قد يعرض `�` (replacement character) أو يرفض الـUTF-8.

**الحل:** اقطع السلسلة قبل الترميز:

```python
msg = html.escape(str(exc)[:400]).encode("utf-8")  # 400 حرف × ٣ بايت أسوأ حالة < 1200
```

**الوسم:** مُثبت — الترتيب واضح في الكود (`[:1200].encode`). اختبار: `"عربي" * 300` يُنتج ~1800 بايت، قطع عند 1200 يكسر المحرف الأخير.

---

### 3. ملف JSON غير مغلق صراحةً

**الموقع:** `report_fill_spec.py:17`

**المشكلة:**

```python
FILL_VALUES = json.load(open(_name, encoding="utf-8")) if _name else {}
```

`open()` لا يُغلق صراحةً. Python GC سيغلقه لاحقًا، لكن ليس فوريًا. في عملية قصيرة (بناء واحد) هذا مقبول، لكنه يخالف best practice.

**لماذا يهمّ:** في بناءات متكررة (CI loop، خادم طويل الأمد)، الـfile descriptors قد تتسرّب. هنا الخطر منخفض (عملية build.py تنتهي)، لكن الأسلوب سيّئ.

**الحل:**

```python
with open(_name, encoding="utf-8") as fh:
    FILL_VALUES = json.load(fh) if _name else {}
```

أو:

```python
FILL_VALUES = json.loads(open(_name, encoding="utf-8").read()) if _name else {}
```

(الثانية تُغلق فورًا بعد read، لكن الأولى أوضح.)

**الوسم:** مُثبت — قرأت السطر، لا `with` ولا `.close()`.

---

## P3 — منخفض، فكّر في الإصلاح

### 1. استيراد داخل دالّة (غير تقليدي)

**الموقع:** `build.py:101`

```python
import html as _html
```

داخل `build_html()`. PEP 8 تفضّل الاستيراد في أعلى الملف. الكود يعمل، لكنه غير تقليدي (قد يُربك القارئ: لماذا هنا؟).

**لماذا يهمّ:** لا يكسر شيئًا، لكن قارئ الكود قد يظنّ السبب تقني (circular import، lazy load)، بينما لا سبب واضح.

**الحل:** انقل `import html as _html` إلى أعلى `build.py` (بعد `import subprocess`).

**الوسم:** مُثبت — السطر 101 واضح.

---

### 2. رسائل الخطأ قد تُسرّب مسارات داخلية

**الموقع:** `fill_server.py:53`

```python
tail = (run.stdout + run.stderr).strip().splitlines()[-6:]
raise RuntimeError("the build failed:\n" + "\n".join(tail))
```

آخر ٦ أسطر من stderr/stdout تُرسل إلى المتصفّح (عبر السطر 88). قد تحتوي مسارات (`/Users/.../.venv/...`)، متغيرات بيئة، أو تفاصيل داخلية.

**لماذا يهمّ:** في خادم عام، هذا تسريب معلومات. في خادم محلي (`127.0.0.1:8765`)، الخطر منخفض (المستخدم يرى نظامه)، لكن لو نُشر الخادم، المهاجم يرى البنية.

**الحل:** رشّح الرسالة: `"the build failed (check server logs for details)"` بدلًا من tail، أو استبدل المسارات بـ`...`.

**الوسم:** مرجّح — الكود موجود، لكن التسريب يحدث فقط إذا فشل البناء؛ الاختبار الأرخص: شغّل `fill_server.py`، أرسل قيمًا سيئة، اقرأ الرسالة.

---

### 3. رقم صفحة سحري بلا تعليق

**الموقع:** `scripts/test_fill_surface.py:53`

```python
text = " ".join(doc[14].get_text().split())
```

`doc[14]` هي صفحة النموذج (الصفحة ١٥ بالترقيم البشري). إذا تغيّر ترتيب الصفحات، الاختبار ينكسر بلا تفسير.

**لماذا يهمّ:** القارئ لا يعرف لماذا ١٤ (لماذا ليس الأولى أو الأخيرة؟). تعليق يوضّح.

**الحل:** أضف تعليقًا:

```python
text = " ".join(doc[14].get_text().split())  # page 15 (0-indexed): the form page
```

**الوسم:** مُثبت — السطر واضح.

---

### 4. timeout سخيّ قد يخفي تراجع الأداء

**الموقع:** `scripts/test_fill_surface.py:43`

```python
with urllib.request.urlopen(req, timeout=600) as r:
```

٦٠٠ ثانية (١٠ دقائق) لبناء يُفترض أن يستغرق «نحو دقيقة» (من `fill.html` السطر 45). إذا أصبح البناء بطيئًا (٥ دقائق بسبب regression)، الاختبار لا يكتشف.

**لماذا يهمّ:** الاختبار يمرّ حتى لو تدهور الأداء ٥×.

**الحل:** اخفض إلى `timeout=180` (٣ دقائق، ضعف المتوقع + هامش). إذا تجاوز، الاختبار يفشل، فتُكتشف المشكلة.

**الوسم:** مُثبت — السطر واضح.

---

### 5. لا حماية CSRF في النموذج

**الموقع:** `fill.html` (السطر 54، `fetch('/api/build', ...`)

**المشكلة:** POST بلا CSRF token. إذا فُتح الخادم على شبكة (`0.0.0.0`)، موقع خبيث قد يُرسل طلبًا من متصفّح الضحية.

**لماذا يهمّ:** في الوضع الحالي (`127.0.0.1` فقط)، الخطر صفر (لا يصله إلا المستخدم المحلي). لكن إذا نُشر لاحقًا (مثلًا خادم داخلي في شركة)، CSRF ممكن.

**الحل (إذا نُشر الخادم):** أضف token في النموذج:

```python
# في Handler.do_GET:
token = secrets.token_urlsafe(32)
session[client] = token
body = body.replace("{{CSRF}}", token)

# في Handler.do_POST:
if form.get("csrf") != session.get(client):
    self.send_error(403)
```

لكن للاستخدام المحلي، هذا غير ضروري (قبول الحالي).

**الوسم:** مُثبت — قرأت `fill.html` و`fill_server.py`، لا token.

---

## غير مُثبت

العناصر التالية **ليست** نتائج (لأنها لم تُفحص بدليل)، لكنها جديرة بالمتابعة:

1. **هل `scripts/test_fill_surface.py` يُنفّذ في CI؟** ROADMAP تذكره كإثبات، لكن الـdiff لا يُعدّل `.github/workflows/`. إذا كانت CI تختبر fill فقط، العيب P0 (build.py:219) لن يُكتشف في البناء العادي.

   **الفحص الأرخص:** `git grep test_fill_surface .github/` — إذا فارغ، CI لا تُنفّذه.

2. **هل postprocess.py تُحدّث `/Producer` في النسخة المُعبّأة؟** المعيار يقول الملف «مولّد بـClaude Code»، لكن النسخة المُعبّأة قد تحتاج producer مختلف («filled by fill_server.py v1.0» مثلاً).

   **الفحص الأرخص:** `pikepdf.open("filled.pdf").docinfo.Producer` بعد بناء.

3. **هل `FILL_ALLOWED_FAILURES` واسع جدًا؟** يسمح بـ`page-ink` و`page-words` مختلفَين. إذا كان النص المُضاف قليلًا (اسم + بريد + سطرَين ملاحظة)، الزيادة محدودة (مثلًا +٣٠٠ محرف). هل يمكن قياسها والتحقق منها (مثلاً `page-words` يجب أن يزيد بـ≤١٠٠ كلمة)؟ الاستثناء الحالي مطلق (أي زيادة تُقبل).

   **الفحص الأرخص:** بناء نسخة معبّأة بقيم طويلة (`note` ٦٠٠ محرف)، قارن `page-words` بالقالب، واحسب الفرق. إذا كان ثابتًا (± ١٠ كلمات)، يمكن فحصه؛ إذا عشوائي، الاستثناء ضروري.

---

**التوصية:** العيب P0 حرج — يوقف كل بناء عادي. أصلحه فورًا، وأعد اختبار `make` أو البناء اليدوي (ليس fill) قبل الدمج. العيب P1 يكسر التحقق من الإدخال. P2 و P3 غير عاجلة، لكن P2 تستحق إصلاحًا (خاصة regex parsing — اجعل العقد موثّقًا أو العملية JSON-based).
