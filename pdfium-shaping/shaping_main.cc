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
  return 0;
}
