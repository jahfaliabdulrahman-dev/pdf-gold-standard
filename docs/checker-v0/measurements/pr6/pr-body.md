## What this changes

`visual-order` stops being a majority vote and never raises `risk.file` again. It becomes `copy_order`: a table in the JSON (`report.v1`) and a «ترتيب النص عند النسخ» section near the Markdown header, in every report — one row per reader that read (reversed / logical / inconclusive + score), plus the readers that are not installed, named instead of dropped. The Arabic summary sentence is generated from the rows.

Per-reader `visual-order` signals stay (`cause: reader`). No threshold, no other signal, and `FILE_CLAIM_MIN_VOTERS = 4` are unchanged.

## Conditions (declared before the run, `scripts/pr6_verify.py`)

| # | Condition | Result |
|---|---|---|
| أ | only `planted-mupdf-logical` moves, downward | ✅ `high → low` (declared `low` before the run) |
| ب | no clean file `high` | ✅ 70/70 `low` |
| ج | five other planted keep level + named signal; only `visual-order` disappears | ✅ |
| د | `copy_order` in every report, equal to an independent re-measurement (guide + ZATCA invoice) | ✅ `scripts/test_copy_order.py` |
| هـ | mac6 and linux4 give the same level, differing only in table rows | ❌ **`calibration-55`** |
| و | no owner text, `owner-NN` only, name guard green | ✅ |

**هـ diagnosis (measured, not interpreted):** `lexical-validity` is also a majority of the judged readers. On mac6, 3 of 6 fail (pdfium 0.6653, pdfminer 0.6638, pdfjs 0.6159) and the majority needs 4 ⇒ no file signal (`medium`). On linux4, 3 of 4 fail and the majority needs 3 ⇒ file signal (`high`). The same file moved `medium`/`high` between mac6 and linux5 in `pr5d`, **before** this PR. Fixing it is outside §1, which forbids touching any other signal's quorum.

## What the table says about readers (149 files, mac6)

143 of 149 files have at least one reader that copies reversed; pdfminer reverses 140 of them, pdfium 22, pdf.js 9, PDFKit 18, poppler 4, MuPDF 4. That distribution is why a majority vote on orientation followed the jury rather than the file.

## Artifacts

`docs/checker-v0/measurements/pr6/`: `verdicts-mac6.json` (149), `verdicts-linux4.json` (149), `calibration-55-lexical.json`, `README.md`.

## Guards

`test_blind` (copy-order checks), `test_report_language` (7 Arabic-table checks), `test_schema`, `scripts/test_copy_order.py` (new), `checker-bare` (no file-level visual accusation + table on three readers; four rows on Linux). Batch: 10/10 green locally.

**Draft on purpose:** condition هـ fails; no merge until the owner decides.
