# استشارة Qwen — آلية إثبات CPWL

1. **أقل دوال `IPWL_FillerNotify`**:
   - `GetWindowRect()` → مستطيل صالح (بدونه لا يُرسم شيء).
   - `GetFont()` → مؤشر خط غير فارغ (يسبب crash بدونه).
   - `GetFontSize()` → قيمة > 0.
   - `OnContentChanged()` → يمكن أن يكون فارغًا (no-op) لكن يجب أن يوجد.

2. **اختبار قائم**:
   - `FPDFFormFillTest` في `fpdfsdk/fpdf_formfill_embeddertest.cpp`، وتحديدًا اختبارات مثل **`TextField`** / **`FirstTextField`** التي تستدعي `FORM_OnFocus` ثم تتحقق من الـ appearance.

3. **النقر**:
   - نعم. `FORM_OnLButtonDown` يستقبل إحداثيات **الصفحة** (page coords). يجب تحويل إحداثيات الشاشة/الجهاز أولًا عبر `FPDF_DeviceToPage`. بدون التحويل ستُرسل إحداثيات خاطئة ولن يصل النقر للحقل.

4. **أقصر طريق ثالث**:
   - اكتب **اختبار وحدة** مباشرًا: أنشئ `CPWL_Edit` مع **stub provider** (يُرجع مستطيلًا وخطًا ثابتين)، ثم استدعِ `DrawText` / `DrawEdit` مباشرة وتحقق من الـ output عبر `CFX_RenderDevice` أو بمقارنة bitmap. هذا يتجاوز طبقة الـ FFI بالكامل ويُثبت الإصلاح بأقل اعتماديات.
