// Copyright 2026. A minimal shaping module built on the HarfBuzz copy that PDFium already carries.
//
// It exists to answer one question with code rather than opinion: can a text run be turned into positioned
// glyphs inside the PDFium tree, using the same HarfBuzz build the renderer links? Nothing here touches
// PDFium's page objects yet; it is the layer a form-field or text-object writer would call.

#ifndef PDFIUM_HB_PROBE_SHAPING_H_
#define PDFIUM_HB_PROBE_SHAPING_H_

#include <cstdint>
#include <string>
#include <vector>

struct ShapedGlyph {
  uint32_t glyph_id = 0;
  uint32_t cluster = 0;
  float x_advance = 0;
  float y_advance = 0;
  float x_offset = 0;
  float y_offset = 0;
};

struct ShapedRun {
  std::vector<ShapedGlyph> glyphs;
  int direction = 0;
  std::string script;
};

// Shapes `text` with the font in `font_bytes` at `pixel_size`, guessing script and direction from the text
// itself (the same way a caller that has no layout context would).
bool ShapeUtf16(const std::string& font_bytes,
                const std::u16string& text,
                float pixel_size,
                ShapedRun* out);

#endif  // PDFIUM_HB_PROBE_SHAPING_H_
