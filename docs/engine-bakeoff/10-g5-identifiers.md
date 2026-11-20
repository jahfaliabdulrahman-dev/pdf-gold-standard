# G#5 — a declared identifier starts on its own display line

**Round:** 2026-11-20 · branch `feat/g5-identifiers` (off `main 7cf7aa9`) · Hermes pushes, the owner merges.
**Acceptance (owner):** `num-invoice-latn` and `num-ids-latn-in-arab` pass the certificate; **no floor goes down**.

**Result:** both cases certify **PASS** with the owner's installed readers (PDFium 5.15.2 + **PDFKit 27.2.1**).
The CI runner's PDFKit **15.8.2** is a declared older-reader limit (its exact is a `NOTE`, not a pass), so the
CI gate is the corpus ratchet, not a 15.8.2 certificate. **No floor is changed in this round**; the final CI run
and its committed results are named in §5.

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

`_inline` starts a **declared identifier** on its own display line — a `<br>` before it — when it **follows
Arabic or starts the paragraph** (the template is always `dir=rtl`). The logical text is unchanged: `metrics.N`
collapses the line break, so the truth and the other readers' floors do not move. The identifier itself is
wrapped in one isolated LTR run.

The class is a **declared format**, not a shape heuristic:

- `INV-[A-Z0-9][A-Z0-9/-]*` — the invoice prefix (declared in this round; a new prefix is a format + a case);
- `[A-Z]{2}\d{2}[A-Z0-9]{10,30}` — the IBAN, ungrouped (`SA0380…`);
- `[A-Z]{2}\d{2}(?:\s\d{4}){4,}` — the IBAN, grouped in 4-digit blocks.

Not matched, by test: `PDF-1.7`, `ISO-9001`, `COVID-19`, `PDF/UA-1`, `PDF/A-3`, lowercase `v2.3.6`. Matched:
`INV-2026-0042/1` and a grouped IBAN after an Arabic label. The trigger is **Arabic or the line start**, so a
Latin-only line (`IBAN: SA03 …`, the `mon-iban` case) is left exactly as written; the earlier break-all form
made `tagged-text` fail there, and the `mon-iban` certificate now passes.

Shape-only forms were measured and dropped: the first broad form (letters, optional hyphen) over-matched, the
hyphen-only form matched standard names (`ISO-9001`, `COVID-19`) and split `PDF-1.7` mid-token, and the slash
form matched `UA-1`/`A-3` inside `mix-acronym`. The declared formats end that class of over-reach.

## 4 · The two cases

| case | source | producer |
|---|---|---|
| `num-invoice-latn` | one line: `الرقم الضريبي: … · السجل التجاري: … · الفاتورة: INV-2026-0042` | `<br>` before `INV-2026-0042`; the VAT/CR stay inline |
| `num-ids-latn-in-arab` | each label and value inline on its line; Arabic text | `<br>` before the IBAN and the invoice; the phone stays inline (with its label it reads correctly); the amount is Western because the case measures the identifiers, and the Arabic-Indic amount is `num-invoice-arab` |

The `num-ids` amount was Arabic-Indic in G#4; it is now `1,200.00` for the one-variable reason. The
Arabic-Indic amount **with** Western identifiers is therefore no longer in the corpus: `num-invoice-arab` has the
amount alone, and no case combines both (declared in §7; a candidate for G#6).

**Witness:** `conformance/tests/test_identifier_isolation.py` checks the declared formats (positives and the
negatives above), builds both layouts, and asserts the specific misreadings with the rule disabled
(`html.BREAK_IDENTIFIERS = False`): PDFium `-2026-0042INV` / `SA… :الآيبان` + `INV-2026-0042 :الفاتورة`, PDFKit
`0042-2026-INV` — plus a non-empty layer, so an empty/garbage extraction cannot pass the defect half. With the
rule on: PDFium exact 1.0 on every runner; PDFKit exact 1.0 on **27.2.1**; the CI's **15.8.2** prints a named
`NOTE` (exact 0, order 0.88/0.89) — a declared older-reader limit, not a silent skip. `ENGINE_BEHAVIOURS` has
the matching entry (`identifier-own-line`, 5 declared behaviours), and `test_engine_behaviour.py` measures both
tier-1 readers (PDFKit's exact only on 27.2.1+, NOTE otherwise).

## 5 · The full run and the reader floors

The gate's full run is the **CI run on this branch** (65 cases, the runner's pinned Chrome/poppler, PDFKit
15.8.2), not this Mac's `.venv`.

- Run `44701553653` (on `7cf7aa9`, before the accept) printed `pdfkit PDFKit 15.8.2: 60 cases compared` plus
  five `new case, no floor yet` notes; the accept added exactly those five.
- Run `44727329809` on `5011905` (the final pushed commit) prints `pdfkit PDFKit 15.8.2: 65 cases compared` and
  `RATCHET HELD`; its raw output is committed as `docs/conformance/results/2026-11-20-g5-chrome.{md,json}`. The
  earlier `44723719935` on `24146d2` was green for the pre-review rule.

**No floor is changed in this round.**

Local note (not a floor change): the earlier `mix-version`-MuPDF note was **not** a reader build difference.
A standalone `metrics.measure` reads `digit_runs` 0.333, but the gate applies the declared
`mupdf-ar-digit-reversal` limitation (`1/2` excused) and the recorded 0.667 is the limited metric; a local
`conformance run --cases mix-version` records 0.667 with `limitations_refused: []`, the same as the CI
artifact. The limit is the explanation; no carry and no floor change.

## 6 · Reproduce

```bash
export CHROME_PATH="$HOME/.cache/cft/chrome/mac_arm-157.0.8103.78/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
export CONFORMANCE_PDFTOTEXT="$HOME/.cache/poppler-pin/26.11.0/bin/pdftotext"
.venv/bin/python conformance/tests/test_identifier_isolation.py
.venv/bin/python -m conformance run --engine chrome --out /tmp/conf-g5 --ratchet
.venv/bin/python -m conformance certify /tmp/conf-g5/num-invoice-latn.pdf --case num-invoice-latn --engine chrome -o /tmp/num-invoice-latn.cert.json
.venv/bin/python -m conformance certify /tmp/conf-g5/num-ids-latn-in-arab.pdf --case num-ids-latn-in-arab --engine chrome -o /tmp/num-ids-latn-in-arab.cert.json
```

## 7 · Limits (ما لم يُثبت)

- The **inline** label+identifier layout still fails in PDFium and PDFKit; the producer rule avoids it, and the
  test fails if a reader ever accepts it (so the rule can be revisited), but the inline failure is not fixed.
- **PDFKit 15.8.2** (the CI runner) reads the split layout with exact 0 and order 0.88/0.89; the PASS
  certificate is on **27.2.1**, the owner's installed reader. The 15.8.2 floors are the old inline values and
  are not changed; the test asserts PDFium's exact 1.0 on every runner, PDFKit's exact only on 27.2.1+, and
  prints a named NOTE otherwise. This is a reader-version limit, declared — not a hidden pass.
- The rule applies to **paragraphs, lists and table cells**; headings bypass `_inline` and are not covered (no
  case has an identifier in a heading).
- The trigger is **Arabic or the paragraph start**; an identifier after a **Latin** label (`Invoice: INV-…`) is
  not isolated. The Latin-only `mon-iban` line is deliberately untouched and its certificate passes.
- The invoice **prefix is `INV-`**, declared here; another prefix is a format addition with a case. The IBAN is
  matched ungrouped and grouped; a new identifier format is a deliberate addition, not a shape guess.
- The **Arabic-Indic amount with Western identifiers** interaction is not in the corpus after the `num-ids`
  amount change; `num-invoice-arab` has the amount alone (declared above).
- A **spaced phone** (`055 123 4567`) read alone on a line flips: PDFium breaks it bare, PDFKit breaks it with
  isolation; with its Arabic label on the same line it reads correctly, and that is the case's layout.
- The source `<bdi>` alone is not a fix (measured in §2); the separate display line is.
- The amounts are Western in `num-ids`; `mupdf`/`pdfminer` sit **at** their floors on the five metrics (not
  above), as the case note now says.
