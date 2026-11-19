# G#1b — the four Preview money failures, classified

Preview = **PDFKit 27.2.1** (macOS 27.2). PDFium = **pypdfium2 5.15.2**. Engine = Chrome for Testing
**157.0.8103.78**. Everything below comes from one command:

```bash
CHROME_PATH=<CfT 157.0.8103.78> python3 scripts/preview_money_probe.py --out /tmp/g1b-probe
```

The probe builds each corpus case twice (`chrome` and `chrome-raw`), builds six controlled one-paragraph
probes under a heading, and prints every reader's exact reading. It is a diagnostic, not a gate.

## The four failures, and how Preview reads them

| case | truth | Preview's reading | where it splits |
|---|---|---|---|
| `mon-decimal-table` | `١٬٢٠٠٫٠٠٠` | `١٬٢٠٠` / `٫` / `٠٠٠` (three lines) | at the decimal separator; the same table's `٩٨٧٫٦٥٤` (no thousands separator) reads exact |
| `mon-negative-hindi` | `-٦٬٠٠٦٫٩٦٥ ريال.` | `٦٬- ريال.` + `المبلغ: ٠٠٦٫٩٦٥` | after the first digit and the thousands separator; the sign lands at the right of the first fragment |
| `mon-riyal-sign` | `١٢٣٤٫٥٦ ⃁، … ٧٨٩٫٠٠ ⃁.` | `٧٨٩٫ ⃁.` + `المبلغ ١٢٣٤٫٥٦ ⃁، والمبلغ ٠٠` | the second amount's fractional `٠٠` detaches; the paragraph reads in two fragments |
| `mon-rs-abbrev` | `الرسوم ٢٥٠٫٠٠ ر.س شهريًّا.` | `٢٥٠٫ ر.س شهريًّا. اختصار العملة` + `الرسوم ٠٠` | the amount's `٠٠` detaches and the paragraph start moves to a second line with it |

Two facts hold for all four: the amount that splits carries the Arabic thousands separator (**U+066C**, `٬`) or
decimal separator (**U+066B**, `٫`), and the fragment after the split is reordered to the wrong line. But a
separator alone is not the trigger — the matrix below shows a 3+3 amount with the same decimal separator
reading exact. What reproduces the split is a **four-digit integer part with three decimals** (`١٢٣٤٫٠٠٠`,
`١٢٠٠٫٠٠٠`), or a thousands separator combined with a decimal (`١٬٢٠٠٫٠٠٠`, `١٬٢٠٠٬٠٠٠`).

## The probe matrix (what reproduces, and what does not)

| probe (paragraph text) | PDFium exact | Preview exact | Preview's reading |
|---|---|---|---|
| `المبلغ ١٢٠٠٠٠٠ ريال.` (no separator) | 1 | **1** | exact |
| `المبلغ ١٢٣٫٤٠٠ ريال.` (3 + 3 digits) | 1 | **1** | exact |
| `المبلغ ١٢٣٤٫٠٠٠ ريال.` (4 + 3 digits) | 1 | **0** | `١٢٣٤٫ ريال.` + `المبلغ ٠٠٠` |
| `المبلغ ١٬٢٠٠٫٠٠٠ ريال.` (thousands + decimal) | 1 | **0** | `١٬٢٠٠ ريال.` + `٫` + `المبلغ ٠٠٠` |
| `المبلغ 1,200.000 ريال.` (Latin, ASCII) | 1 | **1** | exact |
| `-٦٬٠٠٦٫٩٦٥` (the amount is the whole line) | 1 | **0** | `٦٬-` + `٠٠٦٫٩٦٥` |

This is a **classification, not an explanation**: the matrix names the conditions under which the split
reproduces. PDFKit is a closed framework; its internal rule is not observable, so no claim is made about it.

## Is the text layer the cause? No — measured on raw Chrome

`chrome-raw` stops after Chrome, before `fix_text_layer`. Preview's exact is **0 on all four** raw files: the
failure is already in Chrome's output. The probe's `same-shape?` column compares the **line structure** of the
raw and installed readings after NFKC (letter forms folded, lines kept apart): **yes** for three cases, **no**
for `mon-rs-abbrev` — our layer changes which line the fragments land on there, but the failure is present
either way. So the layer can move fragments; it is not what makes the line split.

## The sign at line start — the open item from `06`

`06-g1-sign-status.md` listed one unproven case: *a signed amount that is the first thing on a line with no
following glyph*. Measured now (heading + paragraph `-٦٬٠٠٦٫٩٦٥`, the amount is the line's only glyph run):

- **PDFium: exact 1.0**, reads `-٦٬٠٠٦٫٩٦٥` in order — the sign is first. The separate-show mark works; it is
  not the cause.
- **Preview: exact 0**, reads `٦٬-` + `٠٠٦٫٩٦٥` — the same separator split as the four corpus cases, and the
  sign ends at the right of the first fragment.

The 06 line is closed as a *mark* question: the mark is fine in PDFium, and Preview's failure is the split
class, not the mark.

## `mon-negative-hindi` — status

Unchanged: PDFium 1.0, Preview 0. Same class as the other three; the measured split reproduces on raw Chrome.
next lever is the one already named in `06`: merge a visual line's runs into one text object in the layer.
That change is **not built** and is not part of this commit.

## Scope

The corpus case `mon-negative-line-start` does not exist; this measurement lives in the committed probe
(`scripts/preview_money_probe.py`, its inputs are in the script) rather than in the corpus, because adding a
61st case moves the manifest, the category counts and every published total. If the merge lever is built, the
case should enter the corpus with it.

## ما لم يُثبت

لا شيء في نطاق ما يُدّعى: كل سطر أعلاه مطبوع من الأمر المذكور. داخل PDFKit نفسه خارج النطاق ولم يُدَّعَ فيه شيء.
