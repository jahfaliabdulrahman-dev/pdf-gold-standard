# Print-render pitfalls & local PDF production

## Force independent pages (reference-style)
- Chrome PDF output leaves page presentation to the viewer; some viewers show two-up pages.
- Fix at build time via PyMuPDF: `/PageLayout /SinglePage` plus
  `/ViewerPreferences /Direction /R2L` (+ `/DisplayDocTitle true`). Verify by reading the flags back.

## The box-shadow flattening trap
- Low-alpha `box-shadow` on light pages (cards/rows/chips) can flatten in some viewers into hard,
  displaced tinted rectangles behind elements — looks like "the box lost its background".
- Can survive a raster spot-check at ~150dpi, so verify at the viewer level too.
- Rule: on light print pages use borders only — no blur/offset shadows; dark-page art glows are fine.
- Recipe: render pages, scan for tinted runs between elements, crop-zoom vs the reference
  (the reference standard uses plain borders, no shadows).

## Tagged PDF
- Chrome headless emits Tagged PDFs (accessibility structure) — no extra tooling needed.

## Art layer & pipeline
- Art (cover/dividers/back) via OpenRouter Image API — see `image` skill:
  `references/openrouter-image-api.md`; generator `gen_art.py` (repo root).
- Pipeline: designed HTML → `build.py` (base64-local fonts → Chrome headless print → PyMuPDF
  links/outline/layout flags) → deliver. Gold-standard forensics: `docs/PDF-Gold-Standard.md` (repo).
