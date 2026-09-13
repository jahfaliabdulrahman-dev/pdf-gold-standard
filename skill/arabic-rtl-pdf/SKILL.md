---
name: arabic-rtl-pdf
description: Use when producing any professional PDF (Arabic/RTL by default). Chrome print, PyMuPDF interactive layer, house gold standard.
version: 1.0.0
metadata:
  hermes:
    tags: [pdf, arabic, rtl, report, chrome, weasyprint, pymupdf, interactive, bookmarks, gold-standard]
    related_skills: [pdf-generation, pdf, diagram-design]
---

# Arabic / RTL PDF Generation (macOS)

For Arabic or any RTL-language PDF reports, **Chrome headless from an HTML file
is the most reliable path** on macOS. It provides full CSS `dir="rtl"`,
proper Arabic glyph shaping, `@page` margins, page counters, and rich layout
— all without font-fallback hacks. Validated 2026-08-03: produced a 17-page
Arabic RTL PDF report (731KB) with zero font issues.

fpdf2 has **no true RTL shaping** — Arabic letters render disconnected.
WeasyPrint works only after a pango fix (below). Chrome is the default.

**House standard — applies to every multi-page deliverable:** live navigation
buttons + bookmark sidebar on anything over ~4 pages, one font family with
multiple weights, dark/light page rhythm on long documents, footer with
running title + page number on every content page, Arabic-Indic numerals in
content, and an automated verification pass before delivery. Full spec (palette,
type scale, nav geometry, components): `references/professional-pdf-standard.md`.
Default typeface for the standard: IBM Plex Sans Arabic (Google Fonts,
weights 300–700, embedded); the macOS system fonts above remain fine for quick
internal reports.

## Working recipe (Chrome headless)

### 1. Write the HTML file

Self-contained HTML with:

```html
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
  @page {
    size: A4;
    margin: 18mm 16mm 20mm 16mm;
    @bottom-center { content: "الصفحة " counter(page) " من " counter(pages); font-size: 8pt; color: #8a8a8a; font-family: "SF Arabic", sans-serif; }
  }
  body { font-family: "SF Arabic", "GeezaPro", "DecoTypeNaskh", sans-serif; color: #1c1c2e; font-size: 10pt; line-height: 1.75; }
  /* section dividers */
  .section { page-break-before: always; }
  /* cards that must not split across pages */
  .card { page-break-inside: avoid; }
</style>
</head>
<body> ... </body>
</html>
```

Font stack note: `SF Arabic` (`.SF Arabic`), `GeezaPro` and `DecoTypeNaskh`
are all present on macOS at `/System/Library/Fonts/`. Use `font-family: "SF Arabic", "GeezaPro", sans-serif` — Chrome resolves them via the system font stack.

### 2. Print via execute_code (NOT raw terminal)

The raw `terminal` tool's lifecycle guard can false-positive on the Chrome
binary path (crash: "embedded null byte" from `pathlib.resolve`). Use
`execute_code` with `subprocess.run` — proven to work:

```python
import subprocess, os
out = "/Users/<user>/Downloads/report.pdf"
r = subprocess.run([
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "--headless", "--disable-gpu", "--no-sandbox",
    f"--print-to-pdf={out}",
    "--no-pdf-header-footer",
    "file:///tmp/report.html"
], capture_output=True, text=True, timeout=90)
print("exit:", r.returncode, "exists:", os.path.exists(out))
```

Exit 0 + file exists = success. stderr may print a harmless allocator warning
("Trying to load the allocator multiple times") — ignore it.

### 3. Verify

```python
data = open(out, 'rb').read()
pages = data.count(b'/Type /Page') - data.count(b'/Type /Pages')
print("Pages:", pages, "Size:", len(data), "Header:", data[:8])
```

Deliver with `MEDIA:/absolute/path.pdf` in the response.

## Interactive layer — nav buttons, bookmarks, live links

Chrome-printed PDFs carry no bookmark sidebar; the interactive layer is added
in a PyMuPDF (fitz) post-pass — proven chain: HTML design → Chrome print →
`doc.set_toc()` + `page.insert_link()` → readback verification. Button
geometry (4 fixed buttons per content page) and full code:
`references/interactive-pdf-layer.md`.

## Arabic type: tashkeel and fonts (measured 2026-09-13)

- **Webfont mark-placement trap**: Chrome + Google-Fonts woff2 subsets
  (IBM Plex Sans Arabic, Amiri) render combining marks (shadda, fatha,
  superscript alef) DISPLACED in this environment — at any size, whatever the
  mark order. macOS system fonts (GeezaPro / SF Arabic / Damascus) attach them
  correctly. Vocalized display text uses the system stack
  `'.SF Arabic','GeezaPro','Damascus',serif`; the PDF then embeds the system
  face (GeezaPro verified inside the output). Proved by rendering the same
  verse in five stacks side by side.
- **House rule — prose carries no tashkeel**: strip all combining marks with
  `[\u064B-\u0652\u0653-\u0655\u0670]`, keeping U+0640 (tatweel/kashida).
  Vocalize ONLY the basmala.
- **Never hand-type vocalized text**: source the basmala from
  `api.alquran.cloud/v1/ayah/1:1/quran-uthmani` (strip the leading BOM).
  Hand-typed mark ORDER is often non-canonical and renders broken even in
  correct fonts.
- **Local-first fonts**: base64-embed the woff2 files into the print HTML
  (deterministic + offline) and drop the remote `<link>`s in the build step —
  see the working implementation below.

## Forensic audit of a reference PDF

To match or decode a professionally produced reference — creator tool,
embedded fonts, link/button scheme, palette, type scale, dark/light rhythm,
margins — follow `references/pdf-forensics.md`. It extracts a complete design
spec from any PDF using pdfinfo, pdffonts, PyMuPDF, and PIL.

## WeasyPrint alternative (macOS pango fix)

WeasyPrint is NOT drop-in on macOS: the Python.framework interpreter cannot
find Homebrew's pango/glib/cairo — fails with
`OSError: cannot load library 'libgobject-2.0-0'` even though
`brew list` shows pango/glib/cairo installed. The fix:

```bash
cd /tmp && uv venv wp-venv --python 3.11 && source wp-venv/bin/activate
uv pip install weasyprint
DYLD_LIBRARY_PATH=/opt/homebrew/lib python3 -c "import weasyprint; print(weasyprint.__version__)"
```

`DYLD_LIBRARY_PATH=/opt/homebrew/lib` is required on EVERY invocation (the
framework Python does not search Homebrew lib dirs). Once running, WeasyPrint
69+ handles Arabic RTL correctly with proper fonts.

## Pitfalls

1. **Raw terminal + Chrome path → false-positive guard crash.** Use
   `execute_code` + `subprocess.run` instead of the `terminal` tool for the
   Chrome invocation.
2. **fpdf2 cannot shape Arabic.** Letters render disconnected — do not attempt
   RTL reports with fpdf2. Use Chrome HTML→PDF (or WeasyPrint after the fix).
3. **WeasyPrint on macOS needs `DYLD_LIBRARY_PATH=/opt/homebrew/lib`** set per
   invocation, and prefers a `uv` venv over the framework Python.
4. **Keep the HTML `dir="rtl"`** on both `<html>` and the layout — CSS
   `text-align` alone is not enough for proper RTL column/bullet layout.
5. **Page counter font**: set the `@bottom-center` content font-family to an
   Arabic-capable font or numerals may fall back oddly.
6. **Flex rows reverse under `dir="rtl"`.** A nav strip built with
   `display:flex` inside the RTL document lays items right-to-left and
   physically reverses the row, so left-to-right link rects land on the wrong
   icons. Set `direction: ltr` on the strip, and verify with an ink-density
   scan of each button slot in a rendered page.
7. **Assume no interactive layer until proven.** Bookmarks and nav buttons
   come only from the PyMuPDF post-pass; after building, read them back with
   `get_toc()` / `get_links()` and check every button's target — aliasing two
   buttons to one destination passes every code review and fails on first
   click. Recipe: `references/interactive-pdf-layer.md`.
8. **Tashkeel + webfonts don't mix in the print engine.** See the section
   above: strip marks from prose; produce vocalized text with system fonts
   from a sourced string (`api.alquran.cloud`), never hand-typed.
