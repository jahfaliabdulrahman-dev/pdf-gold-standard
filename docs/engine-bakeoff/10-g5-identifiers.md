# G#5 — the identifier extraction: the line break rejected, the key/value table measured

**Round:** 2026-11-21 · the owner's review of `4e47dbe` · **REQUEST CHANGES (P1): the fix changed the document's
design to pass the metric.** This file is the investigation after that review; **no merge by Hermes**.
**The line-break rule is removed**: `_inline` adds no `<br>` and no `display:block`; the two corpus cases are the
source layout (label and value on their line), with the P2 guard below.

## 1 · The rejected approach, measured

The G#5 round added a `<br>` before the declared identifier, so the label and the value rendered on two lines.
The extraction became exact 1.0 in PDFium and PDFKit 27.2.1, but the **document changed**: a customer invoice
with `الآيبان:` on one line and the IBAN on the next is not the invoice. The metric was blind to it because
`metrics.N` collapses line breaks. The rule and the G#5 line-break tests are removed; the source layout is back.

## 2 · The text layer (the owner's 2 h): what was tried

The owner asked for the G#1 mechanism **in the layer**, not in the source. Measured on the inline
`num-invoice-latn` PDF (`chrome` build, `fix_text_layer` + `postprocess`):

| attempt | PDFium | PDFKit 27.2.1 |
|---|---|---|
| source `<bdi dir="ltr">` / `<span>` / `inline-block` / `bidi-override` | `-2026-0042INV` | `0042-2026-INV` |
| text-layer LRM/RLM at the edges (inside the `Tj` and as separate zero-width shows) | `-2026-0042INV` | **`INV-2026-0042`** (a trailing LRM fixes Preview only) |
| text-layer LRI/PDI, LRE/PDF, RLE/PDF at the edges | identifier **correct**, line becomes visual (`INV… :الفاتورة`) | mangled (`…0042-2026-…`) |
| the identifier split into its own `BT`/`ET` (same line, same position) | worse (line order and token) | unchanged (`0042-2026-INV`) |
| `/Span <</ActualText (INV-2026-0042)>> BDC … EMC` around the glyphs | ignored | ignored |

**No layer mechanism fixed both readers.** The single-reader fixes conflict: PDFKit wants a trailing LRM,
PDFium wants the isolate (which flips the line order), and the two together did not compose. The owner's
"تسجيل في الطبقة" was tried; the result is the table above, not a fix.

## 3 · The key/value table (the owner's 1 h): measured

The natural F layout: a header `البند / القيمة` and one row per field, the label and the value in **adjacent
cells on the same line**. Synthetic case from `num-invoice-latn` (no corpus change):

| reader | exact | what it reads |
|---|---|---|
| PDFium 5.15.2 | **0.0** | the identifier is **intact** (`INV-2026-0042`); the last row's cells come back value-then-label (`INV-2026-0042 :الفاتورة`); the VAT/CR rows are in order |
| **PDFKit 27.2.1** | **1.0** | the whole table, label/value in order |
| MuPDF 2.1 | 0.0 | 0.387 word_f1 |
| poppler 26.07 | 0.0 | 0.765 word_f1 |
| pdfminer | 0.0 | 0.294 word_f1 |

The **value alone in its cell fixes the identifier** in both tier-1 readers (no more
`-2026-0042INV`/`0042-2026-INV`); what remains for PDFium is the **table row order** — a reader/table defect,
not the identifier. The table is the shape F uses; it is not a corpus trick.

## 4 · The owner's choice (the comparison)

| | source layout (label+value on one line) | key/value table |
|---|---|---|
| shape | the invoice as written | a key/value table (the F template) |
| PDFium | identifier broken (`-2026-0042INV`) | identifier **intact**; row order reversed |
| PDFKit 27.2.1 | identifier broken (`0042-2026-INV`) | **exact 1.0** |
| certificate | FAIL (both tier-1) | FAIL on PDFium's row order; PASS on PDFKit |
| other readers | the G#4 values | MuPDF/poppler/pdfminer lower (measured above) |

The owner chooses between the **presentation** (the source layout; the extraction broken) and the **table**
(the F shape; the identifier fixed; the PDFium table-row order to declare or to fix in a later round). No
option is accepted implicitly.

## 5 · The P2 guard (committed)

`test_engine_behaviour.py` now checks every paragraph/list/cell text through `_inline`: no `<br>`, no
`display:block`; and a mutation that re-adds a break must be caught by the same guard. The test prints
`layout:no-break` and `layout:mutation-caught`; the line-break rule cannot return silently.

## 6 · Limits (ما لم يُثبت)

- The layer mechanism did not fix both readers; the attempts and their numbers are above, not a claim of a fix.
- The key/value table's PDFium row order is a **reader/table defect** (the identifier itself is intact); the
  certificate on the table would FAIL on PDFium unless that class is declared/decided, and the owner decides.
- The inline source layout remains the current corpus state; its G#5 certificate is FAIL (the two readers
  reorder the identifier). The table is a synthetic measurement, not a committed corpus change.
- The Arabic-Indic amount with Western identifiers is still the G#6 carry (the `num-ids` amount is the source
  case; the interaction is not in the corpus).
- The identifier after a Latin label and the headings remain declared limits (no trigger, no rule).
