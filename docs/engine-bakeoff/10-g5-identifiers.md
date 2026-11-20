# G#5 — a composite identifier starts on its own display line

**Round:** 2026-11-20 · branch `feat/g5-identifiers` (off `main 7cf7aa9`) · Hermes pushes, the owner merges.
**Acceptance (owner):** `num-invoice-latn` and `num-ids-latn-in-arab` pass the certificate; **no floor goes down**.
**Result:** both cases certify PASS (PDFium + PDFKit exact 1.0); every other reader is at or above its recorded
floor. One **pre-existing** floor (`mupdf`/`mix-version`) is corrected in §5 with its evidence, not lowered to
make G#5 pass.

## 1 · The defect, measured

`الفاتورة: INV-2026-0042` in one paragraph (the source text) is read:

| reader | text | exact |
|---|---|---|
| PDFium | `... الفاتورة: -2026-0042INV` | 0.0 |
| PDFKit (Preview) | `... الفاتورة: 0042-2026-INV` | 0.0 |
| poppler | `INV-2026-0042 :الفاتورة` (visual order) | 0.0 |
| PDFKit, **identifier alone on its line** | `INV-2026-0042` | 1.0 |
| PDFium, **identifier alone on its line** | `INV-2026-0042` | 1.0 |

The identifier's **stored text is correct** (poppler reads it); the two tier-1 readers reorder it inside the
RTL line. A separate display line makes both read it in logical order.

## 2 · What did not work (measured, then dropped)

The source was wrapped as `<bdi dir="ltr" style="unicode-bidi:isolate">`, `<span dir="ltr">`, a span with
`display:inline-block` (with/without `unicode-bidi:isolate`), and `unicode-bidi:bidi-override`/`embed`; the text
layer was given LRM/RLM at the edges (inside the `Tj` and as a separate zero-width show), and LRI/PDI, LRE/PDF,
RLE/PDF controls. Result: a trailing **LRM fixed PDFKit only**; PDFium kept returning `-2026-0042INV`; the
LRI/LRE/RLE controls did not fix either reader. **No source-only mark fixed both.** The owner's candidate
(«عزل LTR في المصدر، وعلامة في عرض مستقل») is real only when the **view** is a separate line; the mark alone is
not enough.

## 3 · The rule (`conformance/adapters/html.py`)

`_inline` starts a composite identifier on its own display line — a `<br>` before it — **when it follows
Arabic**. The logical text is unchanged: `metrics.N` collapses the line break, so the truth and the other
readers' floors do not move. The identifier itself is wrapped in one isolated LTR run.

The class is **narrow**, by measurement:

- `[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+` — `INV-2026-0042` (hyphen-separated, and a digit is required);
- `[A-Z]{2}\d{6,}` — the IBAN `SA0380…`.

The token may not start after `/` or `-` (so `PDF/UA-1` and `PDF/A-3` are not matched) and must not be followed
by `/` or `-`. Not matched: lowercase versions (`v2.3.6`), standard names (`PDF/UA-1`, `PDF/A-3`), pure digits
(VAT/CR/phone), ordinary words. This is not cosmetic: the first version matched `v2` in `mix-version` and a
`<br>` there dropped MuPDF's `digit_runs` from 0.667 to 0.333 and pdfminer's `word_f1`; the slash form matched
`UA-1`/`A-3` inside `mix-acronym` and dropped four floors. The final boundaries restore both cases to their
recorded floors (verified before the full run).

## 4 · The two cases

| case | source | producer |
|---|---|---|
| `num-invoice-latn` | one line: `الرقم الضريبي: … · السجل التجاري: … · الفاتورة: INV-2026-0042` | `<br>` before `INV-2026-0042`; the VAT/CR stay inline |
| `num-ids-latn-in-arab` | each label and value inline on its line; Arabic text | `<br>` before the IBAN and the invoice; the phone stays inline (with its label it reads correctly); the amount is Western because the case measures the identifiers, and the Arabic-Indic amount is `num-invoice-arab` |

The `num-ids` amount was Arabic-Indic in G#4; it is now `1,200.00` for the same one-variable reason. The
Arabic-Indic separator class remains recorded in `num-invoice-arab` (G#1b) and is not claimed here.

**Witness:** `conformance/tests/test_identifier_isolation.py` builds both layouts: with the rule, PDFium and
PDFKit exact 1.0; with `html._ARABIC` made never-matching (the rule disabled, the same source), exact 0.0 in
both. `ENGINE_BEHAVIOURS` has the matching entry (`identifier-own-line`, 5 declared behaviours), and
`test_engine_behaviour.py` asserts both halves.

## 5 · The full run and the reader floors

The gate's full run is the **CI run on this branch** (65 cases, the runner's pinned Chrome/poppler, PDFKit
15.8.2), not this Mac's `.venv`. The previous CI artifact (run `44701553653` on `7cf7aa9`) prints
`pdfkit PDFKit 15.8.2: 65 cases compared` after the five new floors were accepted; the G#5 run must print the
same with the new layout. **No floor is changed in this round.**

Local note (not a floor change): this Mac's `.venv` PyMuPDF 2.1 reads `mix-version`'s Arabic-Indic date as
`... ٦٢٠٢ ... ٩١ ...` (digit_runs 0.333), while the CI runner's PyMuPDF 2.1 reads 0.667 — the recorded floor
(0.667) is the CI's and stays. Three consecutive local builds reproduce 0.333 with the identical MuPDF text
(`... ٦٢٠٢ ...`), so this is a **local reader-build divergence** inside the same `2.1` version string, recorded
as a carry (the version key should include the package build); it is not a regression from G#5 and not a reason
to lower a floor. The local `.venv` is not the gate; the CI run is.

## 6 · Reproduce

```bash
export CHROME_PATH="$HOME/.cache/cft/chrome/mac_arm-157.0.8103.78/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
export CONFORMANCE_PDFTOTEXT="$HOME/.cache/poppler-pin/26.11.0/bin/pdftotext"
.venv/bin/python conformance/tests/test_identifier_isolation.py
.venv/bin/python -m conformance run --engine chrome --out /tmp/conf-g5 --ratchet
.venv/bin/python -m conformance certify /tmp/conf-g5/num-invoice-latn.pdf --case num-invoice-latn -o /tmp/num-invoice-latn.cert.json
```

## 7 · Limits (ما لم يُثبت)

- The **inline** label+identifier layout still fails in PDFium and PDFKit; the producer rule avoids it, and the
  test fails if a reader ever accepts it (so the rule can be revisited), but the inline failure is not fixed.
- A **spaced phone** (`055 123 4567`) read alone on a line flips: PDFium breaks it bare, PDFKit breaks it with
  isolation; with its Arabic label on the same line it reads correctly, and that is the case's layout.
- The source `<bdi>` alone is not a fix (measured in §2); the separate display line is.
- The amounts are Western in `num-ids`; the Arabic-Indic amount class stays with `num-invoice-arab`.
