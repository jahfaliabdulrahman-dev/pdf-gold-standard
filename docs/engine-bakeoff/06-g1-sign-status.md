# G#1 — the sign: display, PDFium and Preview agree on the table; one case still open

**Owner decision:** option 2 — the direction mark is drawn in a text object of its own; no floor is lowered.
This file replaces the earlier "measured trade" state with what that produced.

## Result

| | before | after |
|---|---|---|
| page display | `6,006.965-` | **`-6,006.965`** (sign on the left, verified on the rendered page) |
| `mon-negative-table` PDFium | 0 | **1.0** |
| `mon-negative-table` Preview | 1.0 | **1.0** |
| `mon-negative-hindi` PDFium | 0 | **1.0** |
| `mon-negative-hindi` Preview | 0 | **0 — open** |

On the 60-case corpus: **rose 2 · fell 0 · 118 reader-values unchanged · clean 27 → 28**,
`tables` fail 3 → 2, `tagged-text` fail 14 → 13, and **RATCHET HELD** with **no floor edited**.

The display is verified by eye on the rendered page, not inferred from the text layer.

## What the fix is (three edits, each with its witness)

| # | change | why |
|---|---|---|
| 1 | `conformance/adapters/html.py`: a **negative** amount — a table cell that is one, and an inline token that starts with a minus — is wrapped in `<bdi dir="ltr" style="unicode-bidi:isolate">` | the sign is the only character whose direction changes; digits are already LTR (UAX#9 EN). Positive amounts and dates stay untouched — measured: wrapping `+966` cost `dig-phone` word_f1 1.0 → 0.875 |
| 2 | `scripts/fix_text_layer.py`: a sign attached to a number belongs to the number (`SIGNS = + - −`), and the amount is closed with an LRM emitted as a **show of its own** (`<CID> Tj`) right after its last show | without the first, the leading `-` reads as a neutral at the line edge and the sign jumps to the end **in PDFium**; without the second, a mark inside the amount's hex string extends that run's bounding box and PDFium sorts the amount before the Arabic word — `pdfium/pdfkit` exact flip `1/0 ↔ 0/1` with the mark at either edge |
| 3 | `postprocess.py`: the space repair is decided by a **name** — `fix_text_layer` publishes the marks closing a signed amount in `/PLMarkCids` and the repair never renames them; any other control-named glyph that **occupies width** is a space (a real bidi control has zero advance) | a deliberate LRM carrying a space's advance was being renamed to U+0020, which reversed Preview's reading. The "drawn at least 3 times" threshold is gone: a name replaced a count. Guarded by `scripts/test_bidi_space.py` (one space on a page is repaired · a declared mark is preserved) |

One rule learned the hard way: `%` is **not** in `SIGNS`. It is ET, not a sign; with it `dig-percent` was
treated as a signed amount, the mark landed where the percent glyph was, and Preview fell 1.0 → 0.0.

## §2 — the four documents, on this branch

| document | gate | selftest | veraPDF | claim | inventory / constructs |
|---|---|---|---|---|---|
| guide | ALL GATES PASSED | 62/62 | HELD (3 flavours) | HELD | PASSED · PASSED (no `Ts`) |
| report | ALL GATES PASSED | 62/62 | HELD (ua1 0 failing) | HELD | PASSED · — |
| report-print | ALL GATES PASSED | 54/54 | HELD (ua1 0 failing) | HELD | PASSED · — |
| najd | ALL GATES PASSED | 57/57 | HELD (3b + ua1, 0 failing) | HELD | — · PASSED |

`scripts/test_vocalised.py`: **PASSED**.

## `Ts` and `<sup>` — the owner's ten-minute experiment, answered

Chrome does **not** emit `Ts` for `<sup>` or for `vertical-align: super`: it places the raised glyph with `Td`
(a new relative move), which the model already handles. Built three ways (one footnote digit, two footnote
digits, a raised `<span>` currency symbol): the produced PDF carries **zero `Ts` operators** and the page
renders the superscripts raised. So `Ts` is a **WeasyPrint-only** mechanism in this corpus, E closed on Chrome,
and **`<sup>` needs no template ban** for Path F. The model boundary stays as it is — it refuses `Ts` by name,
and our engine does not produce it.

## Still open: `mon-negative-hindi` in Preview

Chrome writes the paragraph around an isolated amount as **several text objects**, and Preview emits **one line
per text object** — measured on the RAW Chrome output too, so it is not this layer:

```
raw : ٦٬- ريال. | ٠٠٦٫٩٦٥ | المبلغ: ...
pp  : ٦٬- ريال. | المبلغ: ٠٠٦٫٩٦٥
```

Tried and measured, all equal or worse: no isolation (sign ends on the right, PDFium 0) · Unicode isolates
`U+2066/U+2069` instead of `<bdi>` (PDFium 1, Preview fragments further) · literal LRM characters in the markup
with no element (PDFium 0). The next lever is the layer's run assembly for a paragraph containing an isolated
amount — merging the fragments back into one text object — a different change from this one, not attempted here.

## ما لم يُثبت

- That the separate-show mark works for a signed amount that is the **first** thing on a line with no following
  glyph: the mark is placed relative to the next glyph, and that case is not in the corpus.
- That `mon-negative-hindi` is fixable by merging runs: the fragmentation is measured, the merge is not built.
- That the four documents' numbers equal `main`'s for the same code: they are measured on this branch after the
  rebase; CI is the independent check, not a hand comparison.
