# سجل البناء — المرحلة ٠ أُغلقت

## ما بُني

- المستودع: `~/pdfium/pdfium` عبر `depot_tools` (gclient، standalone).
- **الإصدار المبني**: `20e2d231bbebb05b545f752571fe21bce9550764`
- الهدف: `out/Release/pdfium_test` — **٥٫٧MB**، يعمل (`--show-config`, `--help`).
- الزمن الفعلي: **~١٠ دقائق** بعد sync (الخطة قدّرت ٢–٤ ساعات؛ التقدير كان متحفظًا جدًا على M4).
- السكربت القابل لإعادة الإنتاج: `scripts/pdfium_bootstrap.sh` (يفشل صراحةً لو نقص أي اعتماد).

## ما تعلّمناه عن البيئة (يُوفّر ساعات لاحقًا)

1. `DEPOT_TOOLS_UPDATE=0` **يمنع** bootstrap فيفشل gclient برسالة مضلّلة — لا يُضبط.
2. `gclient sync --nohooks` **ينسى** `third_party/test_fonts/test_fonts/*.ttf` (تأتي من hook) فيفشل
   `ninja` على `Ahem.ttf`. الحل: sync **مع** hooks.
3. `--no-history --shallow` كافٍ ولا يحتاج تاريخًا كاملًا.

## الأثر على الدوسيه

المرحلة ٠ في `02-plan.md` كانت تشترط «بناء نظيف قبل أي C++» — وهي الآن **مُغلقة بقياس**، لا بتقدير.
الخطوة التالية: المرحلة ١ (وحدة `shaping.{h,cc}` + اختبار وحدة يقارن مع `uharfbuzz`).
