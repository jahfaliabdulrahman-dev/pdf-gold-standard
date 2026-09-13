# Generated-art layer for Arabic PDFs (v2 house pattern)

Goal: premium AI-generated 3D art (cover / dividers / back cover) integrated into the
HTML → Chrome headless → PyMuPDF pipeline, without breaking determinism.

## Pipeline pattern
1. Generate art via OpenRouter Image API (see image skill:
   `references/openrouter-image-api.md`) — 4K for the cover, 2K for interior art.
   Keep a coercive no-text clause in prompts and build the family with a style reference.
2. Convert masters to embed JPEGs (quality 91): a 4K cover lands at ~1.4MB, 2K art ~0.3MB
   — the final PDF stays ~2.5MB instead of ballooning with PNGs.
3. In the designed HTML keep placeholders: `{{ART_COVER}}`, `{{ART_DIVIDER}}`, `{{ART_BACK}}`.
4. In `build.py`, replace placeholders with `data:image/jpeg;base64,...` before writing the
   temp HTML. Chrome prints from `/tmp`, so relative art paths would break; local-embed keeps
   the build deterministic and offline like the fonts.
5. CSS: `.artbg{position:absolute;inset:0;width:210mm;height:296.8mm;object-fit:cover}`.
   Put `<img class="artbg">` as the FIRST child of the page; positioned text siblings paint
   above it via DOM order. Variant `.artbg.mirror{transform:scaleX(-1)}` to vary art reused
   across identical divider pages (art has no text, so mirroring is safe).
6. Cover legibility: add a veil between art and text —
   `linear-gradient(180deg, rgba(7,2,24,.62) 0%, rgba(7,2,24,.28) 55%, rgba(7,2,24,0) 100%)`
   over the top ~125mm.
7. On art pages, DELETE the old CSS-art fixtures (beam / stars / platform / panels / cubes)
   to avoid double imagery; page keeps its `cosmic` bg class as a load fallback only.
8. Keep the existing text overlays untouched — they layer over generated art as-is.

## Measured facts (2026-09, guide v2)
- 4K cover 3584×4800 = ~433 DPI at A4; 2K interior 1792×2400 = ~217 DPI.
- Delivered v2: 12 pages, 42 links, 12 outline entries, ~2.5MB, art visible in all viewers.
- Doc identity: edition text lives in cover-tags and the back-cover chip — update BOTH when
  bumping editions (plus build.py metadata title).
