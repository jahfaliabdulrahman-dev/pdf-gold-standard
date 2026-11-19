# Metrics — one normalization, six numbers, six counters

Everything on this page is implemented in `conformance/checks/metrics.py` and held by
`conformance/tests/test_metrics.py`, where each metric has an example that breaks it.

## `N(s)` — the one normalization

```
NFC  →  drop direction controls  →  collapse whitespace  →  trim
```

That is the assignment's definition and nothing else. An earlier version of this file also dropped
U+200B/U+200C/U+200D/U+2060 because `fix_text_layer` inserts them on purpose — and the review was right that it
flattered the pipeline: a character the producer put in the file is a character a copy-paste carries. The
joiners are now **counted** (`zero_width`), the file-level check `invisible-format` names them, and they make
`exact` fail. `head-h1-h3` has none; a vocalised case has several, and its certificate says so.

- **Direction controls**: U+200E, U+200F, U+061C, U+202A–U+202E, U+2066–U+2069. They are not text; a reader
  that attaches them to a run has not read anything wrong. They are **counted** (`bidi`).
- **Invisible format characters are NOT dropped**: U+200B, U+200C, U+200D, U+2060 stay in the comparison and
  are counted (`zero_width`). `fix_text_layer` maps a drawn mark and a gap glyph to them on purpose (its own
  comment: *«Preview, PDFium, MuPDF and poppler paste the invisible U+2060 inside those words»*) — which is
  exactly why the gate must keep them: the trade is real, and the metric now prices it.
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
| `zero_width` | U+200B/C/D, U+2060 above the truth's count | the producer's own joiners: counted, and the check `invisible-format` fails the file for them |
| `tatweel_excess` | U+0640 above the truth's count | an engine that adds kashida the source does not carry |

## Measured engine behaviours this corpus found (2026-11-19)

These are results, not opinions; each is reproducible with `python3 -m conformance run --cases <id>`.

1. **A `width:100%` table in a BARE fragment collapses into one text run.** Measured 3x2x2 on CfT 157: the
   defect needs the CONJUNCTION of `width:100%`, no `@page` declaration, and no `line-height` — add either
   `@page { size: A4; margin: 20mm }` OR `line-height: 1.7` and the same table reads in order. When the
   conjunction holds, Chrome prints the table as one run and PDFium returns its rows reversed
   (`خدمات ٢٠٠ رسوم ١٠٠`) with the heading shredded per glyph; `fix_text_layer` repairs it afterwards.
   `tbl-plain-fragment` is the case that reproduces it (built with `chrome-raw`, asserted by
   `tests/test_engine_behaviour.py`), and `tbl-width-100` is the harmless twin under a declared page box.
   An earlier version of this file said `width:100%` alone did it — that was a confounded measurement and the
   review was right to reject it.
2. **Synthetic bold prints as Type3 and carries Presentation Forms.** `th` inherits `font-weight: bold` from
   the UA stylesheet; Chrome then synthesises the face, prints it as Type3, and its `/ToUnicode` names
   U+FB50-block forms. Measured on a two-row table: three Type3 fonts and 9 presentation-form characters in the
   layer, and pdfminer inherits them. The answer was not to forbid bold: both real weights of each family are
   declared (@font-face 400 and 700, sha256-pinned), so `bold: true` on a block is set in the real face and
   `tests/test_engine_behaviour.py` asserts no Type3 font in `bld-word`, `bld-heading` and `bld-th`.
3. **Chrome's print output for an RTL table is a separate paint pass.** With the two fixes above, the layer's
   structure (MCIDs, tag order, per-cell text) is correct — verified cell by cell by `tables`.
4. **A line-final haraka is displaced past the closing punctuation.** Measured: `voc-full` reads
   `الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِين.َ` — the marks are all there, and the fatha of the final nūn sits AFTER
   the full stop (same in `voc-partial`: `…وَسَلَّم.َ`). This is an ordering defect at line end, not missing
   marks; an earlier report said the marks were absent and the review was right to reject it. The same text
   with no period, or with a heading above it, reads `exact` — `voc-no-heading` measures the no-heading shape
   and passes, which is why the corpus no longer claims the heading changes the outcome.
5. **MuPDF moves sentence-final punctuation to the line start** on RTL lines (`.مقدمة …`), which is why its
   `exact` is near zero on Arabic prose while its `order` stays in the 0.6–0.7 range.
6. **pdfminer.six returns visual order and presentation forms** for Chrome's CID fonts: `order` ≈ 0.1,
   `presentation_forms` in the hundreds across the corpus. It is a declared reader, not a hidden one.
