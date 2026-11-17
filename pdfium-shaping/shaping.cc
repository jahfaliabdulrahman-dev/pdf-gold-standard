// Chromium builds with -Wunsafe-buffer-usage; this probe indexes HarfBuzz's buffers directly on purpose.
#ifdef UNSAFE_BUFFERS_BUILD
#pragma allow_unsafe_buffers
#endif

// Copyright 2026.

#include "shaping.h"

#include <hb-subset.h>
#include <hb.h>

namespace {

// Shapes `text` with an already-built face. Kept separate so the subset round-trip can shape twice without
// rebuilding the blob reading code.
void ShapeWithFace(hb_face_t* face, const std::u16string& text, float pixel_size, ShapedRun* out) {
  hb_font_t* font = hb_font_create(face);
  hb_font_set_scale(font, static_cast<int>(pixel_size * 64), static_cast<int>(pixel_size * 64));
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
  char tag[5] = {0};
  hb_tag_to_string(hb_script_to_iso15924_tag(hb_buffer_get_script(buffer)), tag);
  out->script = tag;
  hb_buffer_destroy(buffer);
  hb_font_destroy(font);
}

}  // namespace

bool BuildShapedSubset(const std::string& font_bytes,
                       const std::u16string& text,
                       float pixel_size,
                       ShapedRun* run,
                       std::string* subset_bytes) {
  if (!run || !subset_bytes || font_bytes.empty() || text.empty())
    return false;
  hb_blob_t* blob = hb_blob_create(font_bytes.data(),
                                   static_cast<unsigned int>(font_bytes.size()),
                                   HB_MEMORY_MODE_READONLY, nullptr, nullptr);
  hb_face_t* face = hb_face_create(blob, 0);
  ShapeWithFace(face, text, pixel_size, run);

  hb_subset_input_t* input = hb_subset_input_create_or_fail();
  if (!input) {
    hb_face_destroy(face);
    hb_blob_destroy(blob);
    return false;
  }
  // Keep the original glyph ids: with RETAIN_GIDS a CID can simply equal the glyph id, which is exactly the
  // identity mapping an Identity-H CIDFontType2 wants.
  hb_subset_input_set_flags(input, HB_SUBSET_FLAGS_RETAIN_GIDS);
  hb_set_t* keep = hb_subset_input_glyph_set(input);
  hb_set_add(keep, 0);  // .notdef must survive
  for (const auto& g : run->glyphs)
    hb_set_add(keep, g.glyph_id);
  // Without the code points the subset keeps an empty cmap and every lookup returns .notdef — measured here as
  // ids 0 0 on the first round trip.
  hb_set_t* unicodes = hb_subset_input_unicode_set(input);
  for (char16_t unit : text) {
    hb_set_add(unicodes, static_cast<hb_codepoint_t>(unit));
    // Component glyphs keep the ligature lookup alive: a subset holding only the ligature loses the rule that
    // produces it, and reshaping then falls back to the two separate glyphs.
    std::u16string one(1, unit);
    hb_font_t* font = hb_font_create(face);
    hb_font_set_scale(font, static_cast<int>(pixel_size * 64), static_cast<int>(pixel_size * 64));
    hb_buffer_t* b = hb_buffer_create();
    hb_buffer_add_utf16(b, reinterpret_cast<const uint16_t*>(one.data()), 1, 0, 1);
    hb_buffer_guess_segment_properties(b);
    hb_shape(font, b, nullptr, 0);
    unsigned int n = 0;
    hb_glyph_info_t* inf = hb_buffer_get_glyph_infos(b, &n);
    for (unsigned int k = 0; k < n; ++k)
      hb_set_add(keep, inf[k].codepoint);
    hb_buffer_destroy(b);
    hb_font_destroy(font);
  }
  hb_face_t* subset = hb_subset_or_fail(face, input);
  bool ok = false;
  if (subset) {
    hb_blob_t* out_blob = hb_face_reference_blob(subset);
    unsigned int len = 0;
    const char* data = hb_blob_get_data(out_blob, &len);
    subset_bytes->assign(data, len);
    ok = len > 0;
    hb_blob_destroy(out_blob);
    hb_face_destroy(subset);
  }
  hb_subset_input_destroy(input);
  hb_face_destroy(face);
  hb_blob_destroy(blob);
  return ok;
}

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
  ShapeWithFace(face, text, pixel_size, out);
  hb_face_destroy(face);
  hb_blob_destroy(blob);
  return true;
}
