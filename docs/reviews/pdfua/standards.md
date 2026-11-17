## Findings

**1.** `postprocess.py:~line 138` (feature_pdfua) · **P0** · **مثبت**
المفتاح `/Suspect` خطأ؛ الجدول 331 من ISO 32000-1 يوجب `/Suspects` (بجمع). الملف الناتج غير مطابق بنيويًّا، وبوابة `verify_pdf.py` التي تفحص `/Suspects` ستفشل حتمًا — مما يناقض ادعاء `ua1 = 0` في ROADMAP.
**الإصلاح:** `Suspects=False`.

**2.** `postprocess.py:_tag_orphan_runs` · **P0** · **مثبت**
```python
kids = document.get("/K")
if isinstance(kids, pikepdf.Array):
    kids.append(elem)
document["/K"] = pikepdf.Array([elem])
```
السطر الأخير يستبدل `/K` بمصفوفة جديدة تحوي العنصر المضاف فقط، فيمحو كل الأبناء القائمين (387 NonStruct، 9 H1، 10 P، 43 Link). الشجرة البنيوية تُهدَم.
**الإصلاح:** حذف سطر الإسناد الأخير؛ الإضافة عبر `kids.append` كافية إن كان `/K` مصفوفة، وإن كان قاموسًا واحدًا يُحوَّل إلى مصفوفة تضمّ القديم والجديد.

**3.** `scripts/verify_pdf.py:~line 440` · **P1** · **مرجح**
```python
if mark.get("/Suspects") is not False:
```
`pikepdf.Boolean(False)` ليس الكائن `False` البايتونيّ نفسه (`is` تفشل). إن أعاد pikepdf نوعه الخاصّ، مرّ الفحصُ خطأً أو فشل دائمًا