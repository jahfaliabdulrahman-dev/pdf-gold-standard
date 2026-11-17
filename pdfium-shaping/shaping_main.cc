// Chromium builds with -Wunsafe-buffer-usage; this probe indexes HarfBuzz's buffers directly on purpose.
#ifdef UNSAFE_BUFFERS_BUILD
#pragma allow_unsafe_buffers
#endif

// Copyright 2026.

#include <fstream>
#include <iostream>
#include <string>
#include <utility>

#include "shaping.h"

namespace {

void PrintRun(const char* label, const std::u16string& text, const ShapedRun& run) {
  std::cout << label << ": in=" << text.size() << " glyphs=" << run.glyphs.size()
            << " dir=" << run.direction << " script=" << run.script << " ids=";
  for (const auto& g : run.glyphs)
    std::cout << g.glyph_id << ' ';
  std::cout << "| adv=";
  for (const auto& g : run.glyphs)
    std::cout << g.x_advance << ' ';
  std::cout << '\n';
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "usage: shaping_probe <font.ttf>\n";
    return 2;
  }
  std::ifstream in(argv[1], std::ios::binary);
  std::string bytes((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
  if (bytes.empty()) {
    std::cerr << "cannot read the font file\n";
    return 2;
  }

  // U+0644 U+0627: lam + alef, the pair that becomes one ligature glyph when the font carries it.
  const std::u16string arabic = u"\u0644\u0627";
  const std::u16string latin = u"Business";

  ShapedRun run;
  if (!ShapeUtf16(bytes, arabic, 26.66f, &run)) {
    std::cerr << "shaping failed\n";
    return 1;
  }
  PrintRun("lam-alef", arabic, run);

  if (!ShapeUtf16(bytes, latin, 26.66f, &run)) {
    std::cerr << "shaping failed\n";
    return 1;
  }
  PrintRun("Business", latin, run);

  // Round trip: shape, subset to the shaped glyphs, then shape again with the new subset. The second shaping
  // must produce the same glyph ids — proof the subset carries a usable cmap.
  std::string subset;
  ShapedRun first;
  if (!BuildShapedSubset(bytes, arabic, 26.66f, &first, &subset)) {
    std::cerr << "subset failed\n";
    return 1;
  }
  ShapedRun again;
  if (!ShapeUtf16(subset, arabic, 26.66f, &again)) {
    std::cerr << "reshaping the subset failed\n";
    return 1;
  }
  std::cout << "subset: " << subset.size() << " bytes, glyphs kept=" << first.glyphs.size()
            << ", reshape ids=";
  for (const auto& g : again.glyphs)
    std::cout << g.glyph_id << ' ';
  std::cout << "\n";
  if (again.glyphs.size() != first.glyphs.size() || again.glyphs[0].glyph_id != first.glyphs[0].glyph_id) {
    std::cerr << "subset round trip changed the glyphs\n";
    return 1;
  }
  return 0;
}
