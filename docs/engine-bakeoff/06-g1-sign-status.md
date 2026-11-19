# G#1 — the negative sign: display fixed, PDFium fixed, Preview is a measured trade

**Owner decision (19 Nov 2026, 17:44):** isolate amount cells LTR, display `-6,006.965` with the sign on the
left; acceptance = `mon-negative-table` and `mon-negative-hindi` with a PASS certificate.

**State: 2 of 3 achieved; the third is a trade the owner must rule on.** Nothing is pushed to `main`, the
ratchet is **RED** by design of the guard, and no floor was changed.

## What was changed (three edits, each with its measurement)

| # | change | why |
|---|---|---|
| 1 | `conformance/adapters/html.py`: a **negative** amount — a table cell that is one, and an inline token that starts with a minus — is wrapped in `<bdi dir="ltr" style="unicode-bidi:isolate">` | the sign is the only character whose direction changes; digits are already LTR (UAX#9 EN). Positive amounts and dates are left untouched — measured: wrapping `+966` cost `dig-phone` word_f1 1.0 → 0.875 |
| 2 | `scripts/fix_text_layer.py`: a sign attached to a number is part of the number (`SIGNS` extends the Latin run over `+ - − %`) | without it, a leading `-` reads as a neutral at the line edge, `direction_marks` puts an RLM in front of it, and the sign jumps to the end **in PDFium** — measured: raw Chrome read `-6,006.965`, the layer turned it into `6,006.965-` |
| 3 | `postprocess.py`: the space-mapping repair now renames a glyph only when it is the font's own space glyph, or when its advance equals the font's space advance **and** it is drawn at least 3 times (a word separator) | a deliberate directional control can carry a space's advance; renaming it turned Preview's correct reading back into `6,006.965-`. Both defects are now covered by their own measurement |

## The measured result on the 60-case corpus

```
cases 60 · reader-values unchanged 117 · rose 2 · fell 1
  ROSE mon-negative-hindi           pdfium  0.000 -> 1.000
  ROSE mon-negative-table           pdfium  0.000 -> 1.000
  FELL mon-negative-table           pdfkit  1.000 -> 0.000
clean cases 27 -> 28
per-check moves: tables fail 3->2 · tagged-text fail 14->13
RATCHET FAILED:
  pdfkit PDFKit 27.2.1/mon-negative-table: digit_runs 0.5000 < floor 1.0000
  pdfkit PDFKit 27.2.1/mon-negative-table: exact 0.0000 < floor 1.0000
  pdfkit PDFKit 27.2.1/mon-negative-table: order 0.8750 < floor 1.0000
  pdfkit PDFKit 27.2.1/mon-negative-table: skeleton_exact 0.0000 < floor 1.0000
  pdfkit PDFKit 27.2.1/mon-negative-table: word_f1 0.8750 < floor 1.0000
```

**The display is right, and verified by eye:** the table prints `-6,006.965` with the sign on the left, and the
paragraph prints `المبلغ: -٦٬٠٠٦٫٩٦٥ ريال.` — both rendered from the produced PDF and inspected, not inferred from
the text layer.

**And the cost is named:** the old file printed `6,006.965-` and Preview read `-6,006.965`; the new file prints
`-6,006.965` and Preview reads `6,006.965-`. In both versions Preview's reading is the **mirror** of what the
page shows — a strong indication that Preview reads the content stream's run order, not the page.

## Why the two readers cannot both be satisfied at this level (measured, four ways)

Preview needs an LTR mark at the amount's edge; without it the sign reads last. Adding that mark with our
existing mechanism (`direction_marks`, which appends the mark **inside the amount's own `Tj`**) extends the run's
bounding box, and PDFium then sorts the amount **before** the Arabic word in the row:

| placement of the mark | pdfium exact | pdfkit exact |
|---|---|---|
| no mark | **1.0** | 0.0 |
| mark at the run's right edge | 0.0 | **1.0** |
| mark at the run's left edge | 0.0 | **1.0** |

So the fix is not "which edge" — it is that the mark must be drawn in a **text object of its own** (zero
advance, zero bounding box), so the amount's run keeps its geometry while the reader still sees the boundary.
That is a change to how `fix_text_layer` emits marks, not a parameter, and it is not in this commit.

## Two options for the owner — this is a decision, not a preference

1. **Accept the declared floor change for `mon-negative-table`'s Preview metrics**, on the record that the
   display decision (yours) costs the Preview reading of this one case, and take the certificate as
   PDFium-exact + structure-clean. Re-baselining is a deliberate act with this file as its reason, never a
   convenience.
2. **Fund the text-object mark** in `fix_text_layer` (a bounded change: emit the mark as `BT … Tj ET` at the
   run's edge), then both readers should agree and the floors stand as they are.

Until either is chosen, this branch stays off `main`: a red ratchet is exactly the guard telling us the trade
has not been accepted yet.

## ما لم يُثبت

- That the text-object mark makes Preview read correctly **without** moving PDFium. It is the mechanism the two
  measurements above point to; it has not been built.
- That Preview's reading is *always* the mirror of the display. It is the mirror in both files I measured on
  this case; two points do not make a rule.
- That `mon-negative-hindi` can reach a certificate. Its PDFium reading is now exact; Preview still splits the
  line around the amount (`٦٬- ريال.` / `المبلغ: ٠٠٦٫٩٦٥`), which the same text-object mark may or may not fix —
  unmeasured.
