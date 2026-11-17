# وحدة التشكيل داخل شجرة PDFium

نسخة محفوظة من `~/pdfium/pdfium/hb_probe/` كي تبقى مع المشروع. تُبنى بأمر:

```
cd ~/pdfium/pdfium && third_party/ninja/ninja -C out/HB shaping_probe
./out/HB/shaping_probe ~/Projects/pdf-gold-standard-fix/najd/Najd-Regular.ttf
```

الوحدة لا تمسّ كائنات PDFium بعد: تُدخل نصًّا UTF-16 وخطًّا، وتُخرج محارف بمواضعها عبر HarfBuzz الذي
يحمله PDFium نفسه (`skia_use_harfbuzz=true`).
