---
name: arabic-rtl-pdf
description: "Use when producing an Arabic/RTL PDF report (عربي — تقرير PDF عربي). Chrome print + PyMuPDF layer, house gold standard."
version: 1.3.0
metadata:
  hermes:
    tags: [pdf, arabic, rtl, report, chrome, weasyprint, pymupdf, interactive, bookmarks, gold-standard]
    related_skills: [pdf-generation, pdf-editing, diagram-design]
triggers: ["pdf عربي"]
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

## Delivery gate (run before every delivery — and in CI)

The house standard is machine-checkable. Assert it with ONE script that runs
identically locally and in CI (never a CI-only variant) and exits non-zero on
any failure, so a green CI badge means the standard held. Checks that catch
real regressions, cheapest first:

- **Page count matches the intended build** — a silently dropped page is the
  classic miss and no human notices at a glance.
- **Viewer preferences**: `SinglePage` layout + RTL reading direction
  (`/Direction /R2L`). Print-only defaults make the deliverable open two-page
  and left-to-right in the reader.
- **Every interactive link**: count + each rect targets its own destination —
  aliasing two buttons to one target passes code review and fails on first click.
- **TOC/bookmark entries**: count and hierarchy.
- **Fonts actually embedded** (page font list / `pdffonts`) — a fallback face
  slipping in is invisible in the HTML but obvious in print. **Assert the
  family list contains ONLY the intended faces**: an unexpected extra entry
  (e.g. `ArialMT`) is a glyph outside every web-font subset's `unicode-range`
  falling back silently — find the character and replace it, never accept it.
  Re-check the list after every text edit; adding one symbol re-introduces it.
- **Document title set.**
- **Printed contents equals the bookmark outline.** The numbers a reader sees in the body must equal what the
  sidebar says: parse the printed numbers from the contents page (digits survive extraction even where the
  surrounding Arabic does not) and compare them with `get_toc()`; on mismatch, rebuild with the measured numbers
  and regenerate. A gate that CANNOT read them must fail, not pass — a `zip()` over an empty parse iterates zero
  times and reports clean.
- **No dead buttons**: every navigation link must target a page OTHER than its own. The “next” button on the last
  content page wraps to the contents page rather than pointing at itself, and a self-link fails the build.
- **No blank / overflow pages**: reject a page whose extracted text is far below the document's MEDIAN (a page
  carrying the footer alone is an overflow artifact). Compare relative to the median and EXCLUDE the cover and the
  contents page — their text is legitimately shorter, so an absolute threshold flags valid pages and misses
  overflow on text-dense documents. A page carrying IMAGES is legitimately text-light: treat a page as blank only
  when it is below the threshold AND carries no image, or a figure page fails the build.

### Hardening the gate itself (do this the first time, not after a bug ships)

A gate that has never been seen FAILING is unverified. Each rule below exists
because the naive check passed while the defect shipped. Full recipes with code:
`references/pdf-gate-hardening.md`.

- **Prove it measures — mutate and require a refusal.** On an in-memory copy,
  swap two buttons' destinations and, separately, redact a text block; re-run the
  gate and assert a non-zero exit AND the expected check name. Ship that as
  `gate_selftest.py`. Do not accept "all checks passed" as evidence that the
  checks read anything.
- **Bind every element to its own slot — never compare a sorted set.** Two nav
  links with swapped destinations keep an identical multiset. Derive the expected
  target from the button's x-slot (plus its drawn label) and compare link by link.
- **Clip content above the footer band; bottom padding does not prevent overlap.**
  Give the content box an explicit height ending above the footer/nav strip with
  `overflow: hidden`. Then measure the hidden remainder from INSIDE the browser
  (`scrollHeight − clientHeight` per content box, read back with `--dump-dom`):
  clipped text is absent from the PDF, so no PDF-side check can ever see it.
  `zoom` does not move `scrollHeight` — tighten with real `line-height`/font-size,
  otherwise the measurement stays blind to your own fix. Bound the tightening
  steps and FAIL the build when a section still overflows; a section taller than
  the page is a structure problem — split it into two sections.
- **Locate headings by page count, not font size.** Measuring section starts by
  "max span ≥ 15pt" breaks the moment you tighten or zoom a page (headings fall
  under the threshold and the build claims sections vanished). Assert instead
  that the file has exactly `cover + contents + N` pages and map section → page
  by order; that is the failure mode you actually care about (an overflowed
  section spawning an extra page).
- **Coverage of rendered text: whitespace-insensitive, and not ASCII-only.** The
  Chrome text layer inserts a space inside `->` and breaks a long unbreakable
  token when it wraps, so match with ALL whitespace stripped ("did this line
  appear" ≠ "did it print with the same spacing"). An ASCII-only filter silently
  covers a fraction of an Arabic code appendix while reporting "N/N lines" — add
  a numeric-total check (declared ranges contiguous, ending at the real line
  count) and a per-page Arabic-character budget (drawn ≤ source × 1.02 = suspect),
  since headers add Arabic text to every page.
- **Page number and total can share ONE text span.** Extract char-level positions
  (`get_text("rawdict")`) and compare the x-order of the decoded runs; reading a
  span's bbox makes both numbers share an x and the order check blind. On the last
  page the two numbers are equal — require two runs there and skip the ordering.
- **Never leave a number in the report body that is not derived from a delivered
  evidence file.** Deposit raw logs plus a derived summary under `evidence/`, and
  build the prose from that summary. A hand-typed figure (a measured count, a
  timing, a distribution) survives review and goes stale on the next rebuild.
- **Embed the producing code's hash + a timestamp inside every run record.**
  Otherwise "the same code produced these N runs" is unverifiable: two batches
  writing the same temp paths are byte-identical and prove nothing.
- **Prove embedded images are the delivered files.** Count equality alone passes
  while an image is duplicated. Match each embedded image to its file with a
  downsampled perceptual signature and require a unique 1-to-1 mapping, and fail
  on byte-identical consecutive screenshots — a "live" shot taken after the run
  already finished is a duplicate, not evidence.

Reference implementation — this skill lives in the `pdf-gold-standard` repo (`skill/arabic-rtl-pdf/`);
paths below are relative to the repo root (`../../` from this file):
`nav_spec.py` (ONE set of numbers: outline, button slots + targets, contents rows, allowed fonts —
`build.py` injects from it and the gate checks against it), `scripts/verify_pdf.py` (the gate: per-slot
targets, R2L, font allow-list, printed contents numbers = links = outline, blank pages),
`scripts/gate_selftest.py` (9 mutations, each must be caught) and `.github/workflows/build-pdf.yml`
(macOS runner — same fonts as the owner's Mac — build → gate → selftest → artifact; release on `v*`).
`build.py` builds into `<out>.partial.pdf` and publishes only after the gate passes.

## Working recipe (Chrome headless)

### 0. Size the deliverable to its purpose, not to the toolchain

Match the document's weight to what it is FOR. A homework answer is two pages
of condensed answers plus one evidence page (the screenshot, the comparison,
a source line) — no literature review, no methodology section, no reference
list unless the course itself is the source. When the requester says «هذا ليس
بحث», condense the answers to what the grader asked and let the page breathe;
padding a short answer with prose to fill a page reads as inflation and gets
penalised. Ask for the page budget if it is not stated.

When the source is course material, mine it for the course's own vocabulary
and quote its exact phrases — an answer written in the lecturer's terms scores
better than one translated into generic prompt-engineering English.

### 1. Write the HTML file

**House default: embed the font in the file.** One family — IBM Plex Sans Arabic, whose Arabic and Latin
subsets share one family name — inlined as base64 woff2 from `@fontsource/ibm-plex-sans-arabic`
(`npm pack @fontsource/ibm-plex-sans-arabic && tar xzf *.tgz` → `package/`). The output then no longer depends on
the machine's fonts. Measured 2026-11-13 (Chrome, Linux): the same page built under two different system font sets
embedded only `IBMPlexSansArabic-Regular` + `-Bold`, gate PASS both times; a system-font stack instead resolved Latin
to whatever `sans-serif` maps to (`LiberationSans`, then `Inter` after one `fc-cache` rebuild). Residual, cause not
isolated: glyph x-positions shifted ≤ ~1.3 pt between the two font sets — fonts, text and page count identical.

In this repo `build.py` does it: `fonts/fonts.css` + the woff2 files in `fonts/` (IBM Plex Sans Arabic
300–700, SIL OFL) are inlined as base64 data URIs and remote font `<link>`s are dropped. For another project copy
`fonts/` and that step; or inline a `@fontsource/ibm-plex-sans-arabic` npm package's `<weight>.css` the same way —
every subset keeps its own `unicode-range` under the one family name.

```html
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
  /* {FONT_CSS}  ← inlined by build.py from fonts/fonts.css */
  @page {
    size: A4;
    margin: 18mm 16mm 20mm 16mm;
    @bottom-center { content: "الصفحة " counter(page) " من " counter(pages); font-size: 8pt; color: #8a8a8a; font-family: "IBM Plex Sans Arabic", sans-serif; }
  }
  body { font-family: "IBM Plex Sans Arabic", sans-serif; color: #1c1c2e; font-size: 10pt; line-height: 1.75; }
  /* section dividers */
  .section { page-break-before: always; }
  /* cards that must not split across pages */
  .card { page-break-inside: avoid; }
</style>
</head>
<body> ... </body>
</html>
```

Gate: the embedded family list must be exactly `IBMPlexSansArabic-*`; `sans-serif` is only a safety net and its
appearance fails the build. Tashkeel still needs the system font — see "Arabic type" below.

**Quick internal report on the owner's Mac only (no embedding):** `font-family: "GeezaPro", "Helvetica Neue",
sans-serif` in EVERY stack including `@page` boxes. `SF Arabic` / `.SF Arabic` exist on macOS but Chrome does NOT
resolve either name (measured 2026-11-13; Pitfall 12c). Not reproducible on any other machine.

### 2. Print via execute_code (NOT raw terminal)

The raw `terminal` tool's lifecycle guard can false-positive on the Chrome
binary path (crash: "embedded null byte" from `pathlib.resolve`). Use
`execute_code` with `subprocess.run` — proven to work:

```python
import subprocess, os
final = "/Users/<user>/Downloads/report.pdf"
out = final[:-4] + ".partial.pdf"   # same directory -> atomic os.replace (Pitfall 10)
r = subprocess.run([
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "--headless", "--disable-gpu", "--no-sandbox",
    f"--print-to-pdf={out}",
    "--no-pdf-header-footer",
    "file:///tmp/report.html"
], capture_output=True, text=True, timeout=90)
print("exit:", r.returncode, "exists:", os.path.exists(out))
# only after the delivery gate passes on `out`:
# os.replace(out, final)   # a failed run never clobbers the last good file
```

Exit 0 + file exists = success. stderr may print a harmless allocator warning
("Trying to load the allocator multiple times") — ignore it.

### 3. Verify — machine checks, then the human look

```python
data = open(out, 'rb').read()
pages = data.count(b'/Type /Page') - data.count(b'/Type /Pages')
print("Pages:", pages, "Size:", len(data), "Header:", data[:8])
```

Exit 0 proves the printer ran, not that the page is readable. Before delivering,
**render the first page to an image and look at it** — glyphs connected, direction
right-to-left, table columns in the intended order, nothing clipped at the margins:

```bash
sips -s format png out.pdf --out /tmp/page1.png    # then view the PNG
```

**When the source is a markdown file that will change again**, convert it with a
small repo tool rather than hand-writing HTML per document — hand-written HTML makes
the second revision a new project. Subset to cover, in order: headings, paragraphs,
blockquote, ordered/unordered lists, pipe tables, bold, inline code, horizontal
rules — HTML-escape the text FIRST, then re-apply inline markup. Working shape:
`tools/to_pdf.py --md <doc> --out <file>`, with the converter unit-tested (RTL
attributes present, table rows parsed, HTML escaped).

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

## Engine alternative — in-process, no browser

Chrome is the house default, not the only correct answer. A Rust→WASM engine (`formepdf`, MIT,
`pip install "formepdf[local]"`) shapes Arabic in-process and — measured on the same one-page HTML
— **keeps a text layer Chrome corrupts**: `pdftotext` reproduced «المملكة» and lam-alef «المؤهلات»
verbatim, where Chrome's output transposed letters inside the word. Same order of wall time and
peak memory on a single page (≈0.9 s, ≈250 MB for both); line up the memory advantage only for
LONG or concurrent renders, which was not measured.

Use it when the text layer is part of the contract (ATS, searchable report, TOC located by
string). Keep Chrome when visual/CSS fidelity is the whole contract. Never ship one document from
two engines — the pagination differs and the gate measures one of them.

Three traps before adoption: the Python API does **not** subset fonts (Reactive Resume subsets
with harfbuzz first), a fallback face can appear beside the declared family, and the extraction
carries bidi control characters (`U+202B/202C`, `U+202A`) that break byte-equal comparisons on a
correct document. Measurements, commands and the decision rule:
`references/in-process-pdf-engine.md`.

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
9. **Chrome's Arabic text layer is VISUAL-ORDER and unshaped — never locate
   content by searching for an Arabic string.** `page.search_for("<heading>")`
   either misses or matches the wrong page, because the extracted glyphs come
   out in visual order with the marks detached, so a generated table of
   contents picks up wrong page numbers. Locate headings by LAYOUT instead:
   collect the text spans with `size >= ~15pt` per page in order, and identify
   each heading by an ORDER-INDEPENDENT character multiset (letters only —
   strip diacritics, spaces and digits — with intersection/min-length ≥ ~0.8).
   Then close the loop with the gate above: compare the printed numbers with the
   measured outline, feed the measured pages back, and rebuild — bounded to
   about three passes, since replacing a placeholder number with a real one does
   not change the layout, so it converges. A page whose headings are located
   from the wrong source produces a TOC that is confidently and uniformly off by
   one, which no code review catches and a reader sees immediately.

   **Simpler and deterministic — do not locate headings at all: stamp an
   invisible LATIN anchor into each one at authoring time.** A heading written as
   `<h2><span style="font-size:1pt;color:#ffffff">SECMARK3</span>النص العربي</h2>`
   is findable with a plain `page.search_for("SECMARK3")` — Latin text survives
   the text layer intact, so no multiset matching, no tolerance tuning, and the
   mapping is exact rather than inferred. Generate the anchors with a regex pass
   over the built HTML (`re.sub(r'<h2>(.*?)</h2>', …)`) so they cannot be
   forgotten, keep the section titles in the build script in the same order, and
   **assert the anchor count equals the title count** before writing the TOC — a
   missing anchor must fail the build, not silently shorten the outline. Use this
   for the printed-TOC/outline lock; keep the multiset method for a document you
   did not author.
10. **Publish generated PDFs atomically, and make the cover fit the PRINTABLE box.**
   Build into a sibling `<name>.partial.pdf` in the SAME directory (same
   filesystem ⇒ atomic `os.replace`) and swap the target only after every gate
   passes, so a failed or stale run leaves a previously delivered file untouched.
   Separately, size the cover/art block against `page height − top margin −
   bottom margin` exactly: a canvas a few millimetres taller silently overflows
   onto a second page, and the blank-page check above is what catches it.
11. **Arrows and symbol glyphs fall back to a system font — draw them, do not
   type them.** Google-Fonts woff2 subsets cover only part of the arrows block
   (`U+2191`, `U+2193` are in the Latin range; `U+2190` / `U+2192` are NOT), so
   a typed `←` embeds `ArialMT` alongside the intended family and breaks the
   one-family rule. Emit an inline SVG (`<svg class="arw" viewBox="0 0 20 10">`
   with a path) — deterministic, colours with the palette, and no glyph
   coverage question. Same rule for any symbol the subset omits.

12. **A lone Arabic-only system family silently routes Latin runs AND the page-counter footer to the default Serif face.**
   Declaring `font-family: 'GeezaPro'` (or any Arabic-only face) alone makes Chrome pick `Times-Roman`/`Times-Bold`
   for digits and Latin — visibly in the body and in `@page`/`@bottom-center` counters — with no warning and no tofu.
   `pdffonts` then shows `ArialMT`/`Times-Roman` beside the intended family (measured 2026-10-11: 4 of 5 pages,
   footer-only trigger isolated by ablation). **Declare an explicit Arabic+Latin PAIR everywhere, including inside
   `@page` margin boxes** (`font-family: 'GeezaPro','Helvetica Neue'`); a `@page` rule carrying only the Arabic face
   is enough to re-introduce the fallback. Verify with `pdffonts` and require the family list to contain nothing else.
   Two traps when diagnosing this: (a) a control page built with the SAME single Arabic family also falls back, so
   "it appears in my minimal test too" proves nothing — the control must declare the paired stack to be meaningful;
   (b) symbol characters are their own trap — measured fallbacks: `⇒` U+21D2 → HiraginoSans, `⟷` U+27F7 → AppleSymbols,
   `←`/`→` → Arial, while `≤ ≥ ≈ ± ° × · — – « » ؛ ،` are safe. Test symbols ONE AT A TIME, and replace a falling-back
   symbol with an Arabic word rather than chasing a font that has it.
   (c) **Every stack needs an Arabic face Chrome actually RESOLVES — a listed name is not proof.** Measured
   2026-11-13: footer stack `"SF Arabic","Helvetica Neue"` resolved no Arabic face, so the system chose the
   fallback, and the choice VARIED WITH PAGE CONTENT — `GeezaPro` when the body was Latin, `ArialMT` for the
   footer word «الصفحة» when the body was Arabic (reproduced twice, located with `get_text("rawdict")`). A clean
   control page therefore proves nothing; test the real page. Fix: `"GeezaPro","Helvetica Neue"` in the `@page`
   box and the body → only `GeezaPro` + `HelveticaNeue` embedded. Deterministic across machines: embed the woff2.

13. **A line-oriented markdown→HTML filter leaves `**` literal when a bold pair spans a line break.**
   Markdown wraps long prose, so `**وإعادةُ الحكم` and its closing `…**` often sit on two lines; a converter
   that runs its inline regexes per line never pairs them and the markers print verbatim (measured: 4 leaks in
   a 12-page report, all inside wrapped list items, while page-count, font, RTL and blank-page checks passed
   green). **Join continuation lines into their paragraph/list item FIRST, then apply inline markup** — and
   keep a gate that counts literal markers (`**`, `##`) in the EXTRACTED text; that one-line check is what
   catches the class, since structure gates cannot see legibility.

14. **Inline SVG carries its own font choices into the PDF and breaks the one-family gate.**
   An `<img src="data:image/svg+xml">` or an inline `<svg>` whose text styles name
   `GeezaPro`/`Tahoma` embeds those faces in the PDF; a gate that allows only the house
   family then fails with `unexpected ['GeezaPro', 'Tahoma-Bold', …]`. First try the
   house stack in the SVG and re-run the font check. If the SVG is generated (archify
   and similar), the robust route is: render the SVG to PDF with Chrome, reopen it with
   PyMuPDF and `page.get_svg_image(text_as_path=True)`, then embed that font-free SVG
   as an `<img>` data URI. Text becomes paths (not selectable, expected for a diagram),
   the page stays vector, and the gate sees no foreign font. Measured on a production
   report: the same figure went from a font-gate failure to a clean build with a
   smaller PDF.
