## Findings

### P0 — البناء الناجح لا يُنشر الملف
**build.py:219-220** (بعد `if gate.returncode != 0` block):
```python
    raise SystemExit(f"GATE FAILED — {OUT} left untouched; inspect {PARTIAL}")
print("[5/5] gate passed — published:", OUT)
```

**مُثبت** — قرأت الكود من commit d7670da. المقارنة بـ9bcdd84 تُظهر أن `os.replace(PARTIAL, OUT)` للـsuccessful case **حُذف**.

عند نجاح البوابة (returncode == 0)، الكود يطبع "gate passed — published" لكنه **لا يُنفذ os.replace()** أبداً — الملف الجزئي يبقى في `PARTIAL` ولا يُنقل إلى `OUT`. البناء الناجح لا يُنتج ملفاً نهائياً.

في 9bcdd84 كان الترتيب: `if gate fails → exit؛ else → os.replace() ثم print`.  
في d7670da: السطر `os.replace(PARTIAL, OUT)` اختفى خارج الـfilled-copy branch.

**الإصلاح:** إضافة `os.replace(PARTIAL, OUT)` قبل السطر الأخير:
```python
    raise SystemExit(f"GATE FAILED — {OUT} left untouched; inspect {PARTIAL}")
os.replace(PARTIAL, OUT)
print("[5/5] gate passed — published:", OUT)
```

---

### P2 — استدعاء subprocess + regex parsing بدلاً من استيراد مباشر
**build.py:206-214** — `subprocess.run([..., "verify_pdf.py", ...], capture_output=True)` ثم `re.finditer(r"^FAIL (\S+)", gate.stdout, re.M)`.

**مُثبت** — قرأت verify_pdf.py:568 (`def gate(doc) -> list[str]`) وbuild.py:214 (الـregex).

verify_pdf.py يُصدّر `gate(doc) -> list[str]` التي تُرجع أسماء الفحوصات الفاشلة مباشرة، لكن build.py يستدعيها كـsubprocess ويستخرج النتائج من stdout بـregex.

إذا تغيّر format الطباعة في verify_pdf.py (prefix، مسافات، رموز)، الـregex يفشل بصمت: `failing` تُصبح `set()` فارغة، وbuild.py يرفض البناء رغم أن الـallowed failures صحيحة.

**الإصلاح:** استيراد `scripts.verify_pdf` واستدعاء `gate()` مباشرة:
```python
from scripts.verify_pdf import gate, open_for_gate
doc = open_for_gate(PARTIAL)
failing = set(gate(doc))
```
يُزيل coupling على text format ويُرجع structured data مباشرة.

---

### P2 — duplicate import
**build.py:102** `import html as _html` داخل `build_html()` function.

**مُثبت** — قرأت build.py:11 (top-level import) وbuild.py:102 (داخل function) من commit d7670da.

`html` مُستورد في السطر ١١ كـtop-level، ثم يُستورد مرة ثانية داخل build_html(). تكرار بلا فائدة.

**الإصلاح:** حذف السطر ١٠٢ — الاستيراد العلوي كافٍ.

---

### P3 — أسماء gate checks مُكررة كـstring literals
**report_fill_spec.py:21** `FILL_ALLOWED_FAILURES = {"page-ink", "page-words"}` و **verify_pdf.py:699,913** `check("page-ink", ...)` `check("page-words", ...)`.

**مُثبت** — قرأت verify_pdf.py:699,913 وreport_fill_spec.py:21.

الأسماء "page-ink" و "page-words" مُعرّفة كـliterals في verify_pdf.py، ومُكررة كـliterals في report_fill_spec.py. إذا تغيّر اسم check في verify_pdf.py (مثلاً: "ink" بدلاً من "page-ink")، FILL_ALLOWED_FAILURES لن يطابق، والبناء يفشل — ليس لخطأ حقيقي بل لـmismatch في السلاسل النصية.

**الإصلاح:** verify_pdf.py يُعرّف constants:
```python
CHECK_PAGE_INK = "page-ink"
CHECK_PAGE_WORDS = "page-words"
```
ويستخدمها في check() calls؛ report_fill_spec.py يستوردها:
```python
from scripts.verify_pdf import CHECK_PAGE_INK, CHECK_PAGE_WORDS
FILL_ALLOWED_FAILURES = {CHECK_PAGE_INK, CHECK_PAGE_WORDS}
```

---

### P3 — تكرار منطق فحص ACROFORM_FIELDS
**postprocess.py:217-219** و **verify_pdf.py:441-444**:
```python
declared = getattr(NS, "ACROFORM_FIELDS", None)
if isinstance(declared, (list, tuple)) and not declared:
    return ...
```

**مُثبت** — قرأت الكودين.

نفس المنطق (check if declared is empty list/tuple) في مكانين. تغيير الشرط يتطلب تحديثين.

**الإصلاح:** function مشتركة في spec_loader أو util module:
```python
def has_no_acroform_fields(spec) -> bool:
    declared = getattr(spec, "ACROFORM_FIELDS", None)
    return isinstance(declared, (list, tuple)) and not declared
```

---

### P3 — منطق gate interpretation في __main__ block
**build.py:210-218** — منطق (parse stdout، compare sets، decide to publish) في main block.

**مُثبت** — قرأت build.py:210-218.

الـmain block يجب أن يكون orchestration خفيفة. المنطق الذي يقرر "هل البناء ناجح رغم gate failures؟" يستحق function مُسمّاة قابلة للاختبار.

**الإصلاح:** function جديدة:
```python
def should_publish_despite_failures(gate_stdout: str, spec) -> tuple[bool, set[str]]:
    if not getattr(spec, "FILL_MODE", False):
        return False, set()
    allowed = set(getattr(spec, "FILL_ALLOWED_FAILURES", ()))
    failing = {m.group(1) for m in re.finditer(r"^FAIL (\S+)", gate_stdout, re.M)}
    return bool(allowed and failing and failing <= allowed), failing
```

---

## Not proven

**منطق FILL placeholder replacement في build.py** — هل يجب أن يكون في module منفصل؟

**مرجّح** — السياق: build_html() يُنفذ placeholder replacement للـQR codes (lines 93-99, 105-106) والـart files (110-114) بنفس الأسلوب. إضافة FILL_* placeholders (103-104) امتداد لنمط موجود، ليس duplication لـpipeline component.

**الاختبار الأرخص:** البحث عن fill/form utilities في postprocess.py أو spec_loader — لا يوجد. build.py هو orchestrator يُطبق transformations على HTML قبل الطباعة.

لا أُثبت أن هذا defect — قد يكون المكان الصحيح — لكن إذا نما منطق FILL (validation، escaping معقد، multiple formats)، يستحق module منفصل.
