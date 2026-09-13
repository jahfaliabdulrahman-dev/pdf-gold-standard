# PDF forensic audit — decode a reference PDF into a design spec

Run before matching (or evaluating) any professionally produced PDF: extracts
creator tool, fonts, interactivity scheme, palette, type scale, theme rhythm,
margins, and the full button/link map. Tooling: poppler (pdfinfo, pdffonts,
pdfimages, pdftoppm), PyMuPDF (`fitz`), PIL — all installable via Homebrew and pip.

## 1. Identity & structure

```bash
pdfinfo demo.pdf     # Creator/Producer (who made it), Tagged, pages, size
pdffonts demo.pdf    # families, weights, embedded/subset/unicode flags
```

One family × N weights embedded = healthy type system; `uni yes` column means
copyable text. Record the Producer — it names the tool to compete with
(InDesign ≠ our pipeline, but the OUTPUT is the bar, not the tool).

## 2. Interactive layer (the hidden value)

```python
import fitz
doc = fitz.open('demo.pdf')
print(doc.get_toc())            # bookmark sidebar: [level, title, page]
for i, page in enumerate(doc):
    for l in page.get_links():  # kinds: 1=GOTO, 2=URI, 4=NAMED
        print(i+1, l['kind'], l['from'], l.get('page'), l.get('uri'))
```

Sort links by `from.x0` to reveal the fixed button strip and decode each
button's function from its target. Compare across pages: page-level buttons
appear on every content page; content links (TOC rows, references) differ.
Note which pages are exceptions (cover/dividers carry none).

## 3. Theme rhythm

```bash
pdftoppm -png -r 40 demo.pdf th   # all pages, tiny
```

Mean luminance per page (PIL `convert('L')`) → classify DARK <110 /
MID <195 / LIGHT. The map reveals the deliberate rhythm: dividers and
statement spreads are dark; regular content pages light. Design documents are
composed as scenes, not uniform pages.

## 4. Palette

```python
im.resize((160, 226)).quantize(colors=14, method=2).convert('RGB').getcolors(200000)
```

Top colors per key page give page bg + accents; a full-bleed page gives the
deep background. Report exact hex values in the extracted spec.

## 5. Type scale

```python
page.get_text("dict")   # → Counter over (font, round(size,1), '#rrggbb') of spans
```

Run per page (light and dark separately) → the role table: body size/color,
heading size/color, footer size, per weight.

## 6. Margins & measures

Text-block bboxes (`page.get_text("blocks")`) → min/max x/y → margins in pt
(A4 = 595×842). Nav strip y-range from the link rects; footer baseline from
the bottom text block. Convert points → mm with ×0.35278 when rebuilding in
CSS.

## 7. Visual living-through

Render key pages (cover, TOC, divider, text page, diagram page, references)
at ~130dpi and inspect them visually; crop close-ups of the nav strip and any
detail to reproduce (icon shapes, chips, cards). Decode from the crops, not
from memory.
