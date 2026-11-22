# A second calibration set — from a different producer

The threshold `tounicode_gap_ratio` was derived from the 70 clean files the pipeline itself builds with Chrome.
A clean set from ONE producer cannot calibrate a checker for other producers' files, so this directory holds
the sources of a small set produced by **LibreOffice** (a different layout engine, a different font subsetter,
a different ToUnicode writer):

| source | purpose |
|---|---|
| `lo-arabic-body.html` | headings, a paragraph, a bulleted list, Arabic-Indic and Latin digits |
| `lo-arabic-table.html` | a table, a total, a phone number, a closing line |

They are HTML, not PDF: the repository does not carry generated PDFs. Rebuild them (macOS, LibreOffice):

```bash
mkdir -p /tmp/foreign-set
soffice --headless --convert-to pdf --outdir /tmp/foreign-set \
  docs/checker-v0/foreign/lo-arabic-body.html docs/checker-v0/foreign/lo-arabic-table.html
python3 scripts/checker_foreign.py /tmp/foreign-set --out docs/checker-v0/measurements/foreign.json
```

The command exits non-zero if any file is `high`: on a **clean** foreign set an alarm is a calibration failure,
and the human verdict decides which side is wrong. It never writes the thresholds.

## The run deposited in `measurements/foreign.json` (2026-11-22)

| file | level | signals |
|---|---|---|
| `lo-arabic-body.pdf` | medium | `tounicode-gaps` ×2 — 1 of 21 and 4 of 171, **between words** |
| `lo-arabic-table.pdf` | low | — |

No file is high, and the gaps land between words (the rule now names them as such). This is evidence that the
shipped threshold does not alarm a clean file from this producer — **not** proof that it generalises: two files
are a probe, and the human verdict on them (does a copy lose text?) is still the reference. The set is measured
on demand; it does not enter `thresholds.json` until the owner accepts a re-derivation.
