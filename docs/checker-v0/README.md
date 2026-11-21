# فاحص النسخ العربي — ملفّات العمل

هذه المجلد هو أثر التكليف كاملًا: المصادر، والخطة، والمراجعات، والقياس، والتقرير النموذجي. كل رقم فيه
له أمر يعيد إنتاجه؛ وما لا يمكن إثباته مكتوب في `03-implementation.md §4` لا مخفيًا.

| الملف | ما هو |
|---|---|
| `SPEC.md` | نصّ التكليف المعياري (المرجع الذي يُحكم به على التنفيذ). |
| `00-sources.md` | المصادر الرسمية: ISO 32000-1 §14.8.2.4.2، Matterhorn 10-001 و31-027…31-030، UAX #9، W3C alreq، veraPDF؛ وحزمة `arafix` (MIT) بديلًا معلنًا عن معجم التكليف. |
| `01-plan.md` | الخطة الأولى (قبل الإغلاق الكامل) — محفوظة كتاريخ، لا تُقرأ كحالة. |
| `02-plan-v2.md` | الخطة المنفَّذة: ما قاسه المستودع قبل الكتابة (الطبقة البصرية، حدّ MuPDF، فشل `same_words`). |
| `02-claude-round1.md` / `02-claude-round2.md` | استشارتا Claude على الخطة (كلتاهما REQUEST CHANGES) — محفوظتان بنصّهما. |
| `03-implementation.md` | ما بُني، ولماذا، وما تغيّر بعد القياس. وفيه §4 «ما لم يُنفَّذ» وقرارات المالك. |
| `04-review.md` | المراجعة المستقلة بثلاثة مقاعد (Standards · Spec · Structure): كل ملاحظة ومصيرها. |
| `samples/blind-guide-ar.md` | تقرير أعمى حقيقي على `guide-v2-ar.pdf` (ملفّنا النظيف): الملف منخفض، وpdfminer عالٍ — بلا نسبة ولا PASS. |
| `samples/blind-planted-mupdf.md` | تقرير على ملفّ مزروع (MuPDF): الملف عالٍ بإشارة `visual-order` المسمّاة. |
| `measurements/` | مخرجات القياس: `planted.json` · `clean.json` · `owner.json` · `thresholds.json` · `arafix.md` · `fixtures/` · `cases/`. المجلدات تُولَّد بالأمر لا تُحرَّر يدويًا. |

## إعادة الإنتاج

```bash
export CHROME_PATH="…/Google Chrome for Testing"
export CONFORMANCE_PDFTOTEXT="$HOME/.cache/poppler-pin/26.11.0/bin/pdftotext"
python3 scripts/checker_measure.py                     # كل الأرقام والعتبات
python3 scripts/checker_measure.py --skip-owner        # بلا مجلد المالك (ما يشغّله CI)
python3 -m conformance run --engine chrome --out /tmp/conf --ratchet
python3 -m conformance selftest
python3 -m arabic_pdf_check check some.pdf -o report.json --md report.md
```

> **الخصوصية:** مجلد المالك يُقاس تجميعيًا فقط (إشارة × عدد)، ولا يُودَع منه ملفّ ولا اسم ولا مقتطف.
