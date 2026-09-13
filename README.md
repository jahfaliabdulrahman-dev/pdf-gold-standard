# معيار PDF الذهبي 🜔 · PDF Gold Standard

معيار إنتاج ملفات PDF تفاعلية عربية بجودة دار نشر: أزرار تنقل دائمة، فهرس جانبي
متعدد المستويات، اتجاه RTL أصيل، وفن مولّد ثلاثي الأبعاد — من HTML مصمم إلى PDF نهائي.

[![Build PDF](https://github.com/jahfaliabdulrahman-dev/pdf-gold-standard/actions/workflows/build-pdf.yml/badge.svg)](https://github.com/jahfaliabdulrahman-dev/pdf-gold-standard/actions/workflows/build-pdf.yml)

**⬇️ التحميل:** [دليل المعيار — الإصدار الثاني (PDF)](https://github.com/jahfaliabdulrahman-dev/pdf-gold-standard/releases/latest/download/guide-v2-ar.pdf)

![غلاف الدليل](docs/images/cover.jpg)

## ماذا يوجد هنا؟

| المسار | الوصف |
|---|---|
| `docs/PDF-Gold-Standard.md` | **المعيار المرجعي** — فحص جنائي كامل لدليل مرجعي حقيقي: 155 رابطاً، 38 مدخلاً، أزرار بمواضع بكسلية |
| `docs/recipes/` | **الوصفات الموثقة (5)**: الطبقة التفاعلية · الفن المولّد · المعيار المهني · تقاطعات الطباعة · تدقيق PDF الجنائي |
| `docs/automation-plan.md` | **خطة الأتمتة** — بوابة الاختيار، تحليل سير العمل، الحوكمة، مؤشرات KPI (وفق دليل الأتمتة) |
| `skill/arabic-rtl-pdf/` | **مهارة Hermes الجاهزة** — الدليل التشغيلي الكامل (SKILL.md + 5 مراجع): انسخ المجلد إلى `~/.hermes/skills/productivity/` |
| `guide-v2.html` + `build.py` | **المصدر**: صفحات HTML مصممة → `python3 build.py guide-v2.html out.pdf` |
| `gen_art.py` | توليد فن الأغلفة (OpenRouter Image API — `gemini-3-pro-image`) |
| `fonts/` | IBM Plex Sans Arabic + Amiri (SIL OFL 1.1) — تُضمَّن base64 في البناء |
| `examples/` | المخرج النهائي: 12 صفحة · 42 رابطاً حياً · 2.4MB |

## كيف تبني؟

```bash
python3 -m pip install pymupdf segno pillow
python3 build.py guide-v2.html out.pdf
```

الخطوط تُضمَّن محلياً والبناء حتمي بلا إنترنت. يتطلب Google Chrome (طباعة headless).

## ما يميز المخرج؟

- **٤٢ رابطاً حياً** — أربعة أزرار في كل صفحة: التالي · السابق · الفهرس · الغلاف
- **فهرس جانبي** بثلاثة مستويات في شريط أي قارئ PDF
- **صفحات مستقلة** (`/SinglePage`) + اتجاه قراءة `R2L` مثل المرجع الأصلي
- **Tagged PDF** — بنية وصول كاملة ونص Unicode قابل للبحث والنسخ
- **فن مولّد**: غلاف 4K (~433DPI) وعائلة فنية موحّدة (مرجع أسلوب واحد)

## المهارة الجاهزة (Hermes Skill)

`skill/arabic-rtl-pdf/` هي المهارة التشغيلية الكاملة التي تُدير هذا الخط من البداية للنهاية —
قواعد القرار، الوصفة، تقاطعاتها، وتدقيق أي PDF مرجعي جنائياً. لتثبيتها:

```bash
cp -R skill/arabic-rtl-pdf ~/.hermes/skills/productivity/
```

## خارطة الطريق

[ROADMAP.md](ROADMAP.md) — ثيمات الألوان الستة · LangChain · خدمة للجمهور.

## English

Arabic-first pipeline producing genuinely interactive PDFs (nav buttons, multi-level
bookmarks, RTL reading direction) from designed HTML: HTML → Chrome headless →
PyMuPDF interactivity layer. Deterministic, offline, font-embedded.
The forensic standard behind it: `docs/PDF-Gold-Standard.md`.
The operating Hermes skill ships under `skill/arabic-rtl-pdf/` — copy it into your skills directory.

MIT © 2026 Abdulrahman Jahfali
