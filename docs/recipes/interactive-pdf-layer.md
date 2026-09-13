# Interactive PDF layer — buttons, bookmarks, live links (Chrome + PyMuPDF)

Proven end-to-end: HTML design → Chrome `--print-to-pdf` → PyMuPDF (fitz)
post-pass adds the bookmark sidebar, on-page navigation buttons, TOC links,
and external links → readback verification. This is how multi-page
deliverables get their "buttons" without a DTP suite. Design tokens and the
standing bar: `references/professional-pdf-standard.md`.

## 1. Author pages so geometry is known

One fixed-size block per page, and the nav strip drawn as inline SVG at
absolute positions:

```css
@page { size: A4; margin: 0; }
.page { width:210mm; height:296.8mm; position:relative; overflow:hidden; page-break-after: always; }
.nav { position:absolute; top:13.05mm; left:20.46mm; display:flex; gap:4.05mm; direction:ltr; }
.nav i { display:block; width:8.82mm; height:8.82mm; }   /* 25pt buttons */
```

- The `direction: ltr` on the strip is mandatory inside an RTL document: flex
  under `dir="rtl"` lays items right-to-left and physically reverses the row,
  so rects computed in left-to-right order land on the wrong icons. Verify by
  ink-density scanning each slot in a rendered page (crop each rect, count
  pixels differing from the background).
- Icons adapt per theme: `#ffffff` on dark pages, `#6d3ff0` on light pages.
- Footer (running title + page number) lives inside each page block — Chrome
  ignores `@page` margin boxes, but pages generated in Python know their own
  number. For long flowing documents Paged.js does this automatically:
  `position: running(name)` + `@bottom-center { content: element(name) }`,
  `counter(page)` / `counter(pages)`, and `target-counter(attr(href), page)`
  for real TOC page numbers.

## 2. Print

Chrome headless with `--no-pdf-header-footer` (parent SKILL.md recipe).

## 3. Inject the layer

```python
import fitz
doc = fitz.open('/tmp/printed.pdf')
doc.set_toc([[1, "الغلاف", 1], [1, "جدول المحتويات", 2],
             [1, "القسم الأول", 3], [2, "صفحة محتوى ١", 3]])   # 1-based pages
# Nav buttons — rect uses fitz top-left origin; convert the SAME mm constants used
# in CSS with 1mm = 2.83465pt. Strip: y 37..63; x = 58 next / 95 prev / 133 toc / 170 home.
for i, page in enumerate(doc):
    page.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(170,37,196,63), "page": 0})    # home -> cover
    page.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(133,37,159,63), "page": 1})    # toc  -> TOC page
    if i > 0:                page.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(95,37,121,63), "page": i-1})
    if i < doc.page_count-1: page.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(58,37,84,63),  "page": i+1})
# TOC-page rows the same way; external links: {"kind": fitz.LINK_URI, "from": rect, "uri": url}
doc.save('/tmp/out.pdf', deflate=True, garbage=3)
```

## 4. Verify by readback — never trust the write

```python
v = fitz.open('/tmp/out.pdf')
print(v.get_toc())
for i, pg in enumerate(v):
    print(i+1, sorted((round(l['from'].x0), l.get('page')) for l in pg.get_links()))
```

Assertions to eyeball per page:
- Every button has a real, DISTINCT target: ⌂ (x=170) → cover, ≡ (x=133) →
  the TOC page. Aliasing ≡ to ⌂ passes silently and fails on first click.
- First content page: prev and ≡ both point at the TOC page — correct by
  geometry, not a bug. Last content page: next → back cover.
- Non-button pages (cover, divider, back cover) carry no nav rects.

## 5. Traps

- Regenerate → re-inject; never inject twice into the same file (duplicate
  annots stack).
- If icons move, update BOTH the CSS constants and the rects — derive both
  from one set of numbers.
- PyMuPDF link rects may overlap page content freely; they are invisible
  annots, so misalignment shows only as a wrong click target — hence the
  ink-scan + readback checks.
