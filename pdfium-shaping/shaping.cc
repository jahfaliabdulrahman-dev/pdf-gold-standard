// Chromium builds with -Wunsafe-buffer-usage; this probe indexes HarfBuzz's buffers directly on purpose.
#ifdef UNSAFE_BUFFERS_BUILD
#pragma allow_unsafe_buffers
#endif

// Copyright 2026.

#include "shaping.h"

#include <hb.h>

bool ShapeUtf16(const std::string& font_bytes,
                const std::u16string& text,
                float pixel_size,
                ShapedRun* out) {
  if (!out || font_bytes.empty() || text.empty())
    return false;

  hb_blob_t* blob = hb_blob_create(font_bytes.data(),
                                   static_cast<unsigned int>(font_bytes.size()),
                                   HB_MEMORY_MODE_READONLY, nullptr, nullptr);
  hb_face_t* face = hb_face_create(blob, 0);
  hb_font_t* font = hb_font_create(face);
  hb_font_set_scale(font, static_cast<int>(pixel_size * 64),
                    static_cast<int>(pixel_size * 64));

  hb_buffer_t* buffer = hb_buffer_create();
  hb_buffer_add_utf16(buffer, reinterpret_cast<const uint16_t*>(text.data()),
                      static_cast<int>(text.size()), 0, static_cast<int>(text.size()));
  hb_buffer_guess_segment_properties(buffer);
  hb_shape(font, buffer, nullptr, 0);

  unsigned int count = 0;
  hb_glyph_info_t* info = hb_buffer_get_glyph_infos(buffer, &count);
  hb_glyph_position_t* pos = hb_buffer_get_glyph_positions(buffer, &count);

  out->glyphs.clear();
  out->glyphs.reserve(count);
  for (unsigned int i = 0; i < count; ++i) {
    ShapedGlyph g;
    g.glyph_id = info[i].codepoint;
    g.cluster = info[i].cluster;
    g.x_advance = pos[i].x_advance / 64.0f;
    g.y_advance = pos[i].y_advance / 64.0f;
    g.x_offset = pos[i].x_offset / 64.0f;
    g.y_offset = pos[i].y_offset / 64.0f;
    out->glyphs.push_back(g);
  }
  out->direction = hb_buffer_get_direction(buffer);
  hb_script_t script = hb_buffer_get_script(buffer);
  char tag[5] = {0};
  hb_tag_to_string(hb_script_to_iso15924_tag(script), tag);
  out->script = tag;

  hb_buffer_destroy(buffer);
  hb_font_destroy(font);
  hb_face_destroy(face);
  hb_blob_destroy(blob);
  return true;
}
