## النتائج

### P2 · postprocess.py:221 · معالجة الأعطال مفقودة في فكّ ترميز التدفّق · مثبت

```python
src = tu.read_bytes().decode("latin-1")
```

**لماذا يُهِمّ:** إذا لم يكن التدفّق `ToUnicode` مُرمَّزًا بـ latin-1 فعلًا (مثلًا UTF-8، أو ثنائي صِرف)، سيتعطّل `decode` ولن تُطبَّق الإصلاحات اللاحقة على أي خط — والملف ينجح من البوابة وفيه نصّ ملصوق.

**الخطوة الصريحة:** لفّ القراءة والفكّ في `try-except`، أو أضف تأكيدًا أنّ `ToUnicode` في صيغة CMap نصّية قبل الفكّ:

```python
try:
    src = tu.read_bytes().decode("latin-1")
except UnicodeDecodeError:
    continue  # or log and skip this font
```

---

### P2 · postprocess.py:226-227 · لا تحقّق من صحّة النتيجة بعد إعادة الكتابة · مرجح

```python
font["/ToUnicode"] = pdf.make_stream(dst.encode("latin-1"))
```

**لماذا يُهِمّ:** تُعيد الكتابة دون أن تتحقّق أنّ `dst` لا يزال CMap صالحًا — خطأ في النمط أو في التعويض يُفسد `/ToUnicode` ويكسر طبقة النص، ولا يُكتشف إلا في المُشاهِد.

**الخطوة الصريحة:** بعد التعويض، تحقّق أنّ النتيجة تحوي بنية CMap سليمة (`beginbfchar` / `endbfchar`، أزواج سُداسية صحيحة)، أو أضف اختبار تكامل يقرأ النص من PDF معالَج ويتحقّق أنّ المسافات `U+0020` وليست `U+200F`.

---

### P2 · scripts/verify_pdf.py:918-922 · البوابة تقرأ المُدخَل ولا تُصادِق عليه حين يُعطَّل الادّعاء · مرجح

```python
got = {"MuPDF": norm(doc[NS.BASMALA].get_text()), "PDFium": norm(texts[NS.BASMALA]) if texts else ""}
missing = [] if not claimed else [k for k, t in got.items() if want_v not in t]
check("vocalised", not missing, detail)
```

**لماذا يُهِمّ:** حين `VOCALISED_CLAIM=False`، تستخرج البوابة نصّ البسملة (`got = ...`) لكنّها لا تُصادِق عليه (`missing = []`)، فالحسابة تمرّ دومًا. هذا هدرٌ (قراءة غير مُستخدَمة) وتشويش (حسابة تُسمَّى "vocalised" لا تتحقّق من التشكيل).

**الخطوة الصريحة:** لا تَحسِب `got` إذا لم يُطالَب بالتشكيل، أو حوِّل المنطق لكي تُطلَق البوابة شرطيًّا:

```python
if not claimed:
    check("vocalised", True, "not claimed — " + getattr(NS, "VOCALISED_REASON", "no reason declared"))
else:
    got = {"MuPDF": norm(doc[NS.BASMALA].get_text()), "PDFium": norm(texts[NS.BASMALA]) if texts else ""}
    missing = [k for k, t in got.items() if want_v not in t]
    detail = f"basmala not exact in {missing}" if missing else "basmala exact in PDFium and MuPDF"
    check("vocalised", not missing, detail)
```

---

### P3 · build.py:159 · لا معالجة لفشل `copyfile` · مثبت

```python
shutil.copyfile(TMP_PDF, os.path.join(TMPDIR, "raw.kept.pdf"))
```

**لماذا يُهِمّ:** إذا فشلت النُّسخة (مثلًا `TMPDIR` ممتلئ، أذونات، قرص مُمتلئ) يستمرّ البناء دون الأثر التشخيصي — وحين يفشل اختبار البوابة لن نملك `raw.kept.pdf` لنقيس ما أنتجه Chrome قبل المعالجة.

**الخطوة الصريحة:** لفّ في `try-except` أو تحقّق من نجاح النسخة:

```python
try:
    shutil.copyfile(TMP_PDF, os.path.join(TMPDIR, "raw.kept.pdf"))
except OSError as e:
    print(f"[!] failed to keep raw.pdf: {e}")
```

---

## Not proven

- **نمط التسمية `feature_bidi_space`:** اسم الدالّة يقول "feature" والتوثيق يقول "Repair … producer defect". لكن بقية postprocess.py تُسمّي كل عمليّة `feature_*` بصرف النظر عن كونها ميزة أم إصلاحًا، فهذا متّسق مع الشيفرة.
- **البيانات المُعايَرة PAGE_INK و PAGE_WORDS:** بين واسمات `# >>> CALIBRATED`، تُوحي أنّها مُولَّدة آليًّا. لا أرى استخدامها في الفرق، فلا يُمكن الحُكم على صحّتها من السياق المُعطى.
- **نمط regex هشّ:** النمط `r"(<[0-9A-Fa-f]{4}>\s*)<200[EF]>"` يفترض صيغة محدّدة، لكن التوثيق يقول "mapping correction" لخلل Chrome مُقاس — الهدف ضيّق ومحصور، فالنمط يكفي للحالة المعروفة.
