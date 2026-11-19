# Metrics — one normalization, six numbers, six counters

Everything on this page is implemented in `conformance/checks/metrics.py` and held by
`conformance/tests/test_metrics.py`, where each metric has an example that breaks it.

## `N(s)` — the one normalization

```
NFC  →  drop direction controls  →  drop invisible format characters  →  collapse whitespace  →  trim
```

- **Direction controls**: U+200E, U+200F, U+061C, U+202A–U+202E, U+2066–U+2069. They are not text; a reader
  that attaches them to a run has not read anything wrong. They are **counted** (`bidi`).
- **Invisible format characters**: U+200B, U+200C, U+200D, U+2060. The pipeline inserts them on purpose —
  `fix_text_layer` maps a drawn mark and a gap glyph to U+200B/U+2060, and its own comment says *«Preview,
  PDFium, MuPDF and poppler paste the invisible U+2060 inside those words»*. They are counted (`zero_width`).
- **Not** dropped: Arabic diacritics (that is `skeleton`, its own metric), tatweel U+0640 (an engine-added
  kashida is a difference), the digit script (٢٠٢٦ is not 2026), or anything about order.

One function, used for the truth and for every reader. A reader-specific normalization is forbidden — a
reader's defect is declared as a `limitations.json` entry with a control file, never smoothed away.

## The six numbers

| metric | definition | what it separates |
|---|---|---|
| `exact` | `N(out) == N(truth)` | the whole text, in order |
| `word_f1` | token-level F1 of `N(out)` vs `N(truth)` | missing or extra words |
| `order` | LCS of the two word sequences ÷ length of the truth | word order with the content held constant |
| `digit_runs` | fraction of the truth's digit runs present in the output | a reversed or moved number |
| `skeleton_exact` | `exact` after removing diacritics | a mark defect from a letter defect |

**A digit run** is a *signed number with its internal separators*: `[+-]?` then a digit of any script, then any
of digit / `,` / `.` / `٫` (U+066B) / `٬` (U+066C). `-6,006.965` is one run, and the incident behind the corpus
(`hermes-agent #157375`) moved its sign to the other end in an RTL cell — `6,006.965-` no longer contains the
run, so the metric names the defect that `exact` would only bury in a whole-page comparison.

`/` is **not** a separator: `٢٠٢٦/١١/١٩` is three runs, so a reversed year loses one of three and the other two
still count. Counted per run with a `Counter`, not «does this string appear somewhere»: a page that prints
٢٠٢٦ twice and loses one copy is not intact.

## The counters

| counter | counts | how it is judged |
|---|---|---|
| `presentation_forms` | U+FB50–FDFF, U+FE70–FEFF | a reader that returns a glyph name instead of a letter; the file-level check `presentation-forms` names the same defect in the layer |
| `pua` | U+E000–U+F8FF | private-use codes |
| `replacement` | U+FFFD | a code the font map could not name |
| `bidi` | direction controls **above the file's own count** | a reader that adds decorations, never the producer's deliberate LRM/RLM |
| `zero_width` | U+200B/C/D, U+2060 above the truth's count | the producer's own joiners are visible as a number, not as a failure |
| `tatweel_excess` | U+0640 above the truth's count | an engine that adds kashida the source does not carry |

## Measured engine behaviours this corpus found (2026-11-19)

These are results, not opinions; each is reproducible with `python3 -m conformance run --cases <id>`.

1. **A table with an explicit width is painted as one text run.** `table { width: 100% }` (also `90%`,
   `min-width:100%`, `table-layout:fixed`) makes Chrome print the whole table as a single run, and PDFium then
   returns the rows in reverse order — on a page that renders perfectly. With `width: auto` the same table is
   correct. The corpus template therefore uses `width: auto`; the finding is recorded here because a customer
   who sizes a table will hit it.
2. **Synthetic bold prints as Type3 and carries Presentation Forms.** `th` inherits `font-weight: bold` from
   the UA stylesheet; Chrome then synthesises the face, prints it as Type3, and its `/ToUnicode` names
   U+FB50-block forms. Measured on a two-row table: three Type3 fonts and 9 presentation-form characters in
   the layer, and the transfer's `pdfminer` output inherits them. The template now pins `font-weight: 400` on
   `th`, `b`, `strong`; the case `tbl-*` family measures the result.
3. **Chrome's print output for an RTL table is a separate paint pass.** With the two fixes above, the layer's
   structure (MCIDs, tag order, per-cell text) is correct — verified cell by cell by `tables`.
4. **PDFium returns a single-line vocalised paragraph's words in reverse** when the paragraph has no heading
   above it; with a heading the same text is exact. The corpus keeps the heading because a document has one.
5. **MuPDF moves sentence-final punctuation to the line start** on RTL lines (`.مقدمة …`), which is why its
   `exact` is near zero on Arabic prose while its `order` stays in the 0.6–0.7 range.
6. **pdfminer.six returns visual order and presentation forms** for Chrome's CID fonts: `order` ≈ 0.1,
   `presentation_forms` in the hundreds across the corpus. It is a declared reader, not a hidden one.
