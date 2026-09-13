# Professional PDF standard (the house gold standard)

Every multi-page PDF delivered to the owner meets this bar. It was decoded by
full forensic audit of the owner's reference model — a professionally produced
Arabic guide made in Adobe InDesign 21.5 (PDF 1.7, tagged, 36 A4 pages, 155
live links, 38-entry 3-level bookmark outline, IBM Plex Sans Arabic ×5 weights
embedded) — so documents from our pipeline (Chrome headless + PyMuPDF,
see SKILL.md) read as its equal. To audit other references:
`references/pdf-forensics.md`.

## Standing rules (per deliverable)

1. Over ~4 pages → live navigation: 4 fixed buttons on every content page
   (see geometry below) plus a real bookmark sidebar (3 levels). The TOC page
   rows are clickable; reference lists get live external links and QR codes.
2. One font family, multiple weights — no family mixing. Default: IBM Plex
   Sans Arabic 300/400/500/600/700, embedded.
3. Long documents alternate themes deliberately: dividers and statement
   spreads dark (full-art), regular content light. Dividers carry no footer
   and no nav buttons.
4. Footer on every content page: running title + subtitle (one side) and page
   number (other side, Latin digits). Content numerals use Arabic-Indic ١٢٣.
5. Every button targets something real and distinct — ≡ goes to an actual TOC
   page, never aliased to ⌂. (On the first content page, prev and ≡ both
   point at the TOC page; that is correct.)
6. Automated verification before delivery: `get_toc()` + per-page
   `get_links()` readback; geometry probes for any generated diagram
   (diagram-design's scripts pattern).

## Design tokens

Palette:
- royal violet page bg `#4928b5` (gradient stripes `#301a95` / `#6c53c8`)
- deep cosmic (cover/dividers) `#020018` → `#150a58` → `#1a0b70`
- heading violet `#571cbd` · element violet `#7449e7` / `#6d3ff0`
- teal accent `#79e9e0` / `#57e3d8` (numeral chips, emphasis words)
- light bg `#f8f6fb` · body text `#000000` · secondary `#4f5d75` · muted `#a4a2a7`

Type scale — light pages: H1 20pt bold violet · subsection 18pt · card
titles 12pt · body 12pt · secondary 9pt. Dark pages: display titles 28–30pt
white, body 10pt, emphasis teal. Running footer 8pt Light. Display headings
may use decorative kashida (manual tatweel ـ stretches) on selected words.

Geometry: A4. Margins L/R ≈61pt (21.5mm), content width ≈474pt. Nav strip at
top, y = 37–62pt. Footer baseline ≈805–813pt.

Nav convention: 4 buttons 25–26pt at x = 58 (next ←) · 95 (prev →) · 133
(TOC ≡) · 170 (home ⌂); icons white on dark pages, violet `#6d3ff0` on light.

## Component library (demonstrated by the reference model)

Info cards ×3 per row · wide cards ×2 · two-column timeline on a centre spine
with glass 3D milestone icons · violet tool strip with logos + open icons ·
QR card overlapping a photo · reference rows (QR + ↗ icon + name + hairline
separators) · full-art section dividers with a tilted violet lozenge over the
title · coloured highlight words inside headings.

## Known gaps vs a DTP suite (accepted, with workarounds)

- Tagged PDF (accessibility structure): InDesign exports it, the Chrome chain
  does not. Acceptable; WeasyPrint can produce structure-tagged output when a
  deliverable truly needs it.
- 3D glass artwork: generate (image model) or build in CSS — keep ONE
  consistent style family across a document.
- Perfect Arabic kashida: insert tatweel characters manually in the chosen
  display headings.

## Pipeline

HTML/CSS (pages generated in Python so numbers and rects are known) → Chrome
headless print (`--no-pdf-header-footer`) → PyMuPDF post-pass (bookmarks, nav
buttons, TOC links, external links — `references/interactive-pdf-layer.md`) →
readback verification → deliver with `MEDIA:`. For long flowing documents
where hand-laying pages is impractical, Paged.js provides automatic
pagination, running elements, `counter(page)` and
`target-counter(attr(href), page)` for real TOC page numbers — then the same
Chrome + PyMuPDF finish. QR codes: generate at build time with Python
(qrcode/segno).

Working reference implementation of the whole chain:
`~/Projects/pdf-gold-standard/` (`guide-v1.html` designed source +
`build.py` print/QR/fonts/interactivity pipeline + `fonts/` local woff2).
Built 2026-09-13: the 12-page "دليل معيار إنتاج ملفات PDF" — 42 live links,
12-entry outline, GeezaPro-embedded basmala.
