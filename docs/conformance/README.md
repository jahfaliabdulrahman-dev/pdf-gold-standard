# The conformance gate — a gate that does not need to know the document

`scripts/verify_pdf.py` is the gate for the four documents this repository builds: every expected number in it
was calibrated on them. That gate is excellent for those files and blind to any other file — a file
`render_document` (Path F) produces, or a file a customer brings. This package is the other half: the **general**
checks, a neutral corpus, a declared reader matrix, and a per-file certificate whose verdict is recomputed.

```bash
python3 -m conformance manifest --write                     # derive corpus/MANIFEST.json from the cases
python3 -m conformance run --engine chrome --out /tmp/conf  # build the corpus, measure every reader
python3 -m conformance run --engine chrome --ratchet        # compare to ratchet.json (CI uses this)
python3 -m conformance certify file.pdf --case head-h1-h3 -o file.cert.json
python3 -m conformance validate file.cert.json file.pdf
python3 -m conformance selftest                             # planted mutations: every check must bite
```

Requirements: `.venv` (Python 3.12), `CHROME_PATH` at the pinned Chrome for Testing, `verapdf` on `PATH`,
`pdftotext` on `PATH`, and the two fonts (the first run downloads them into `fonts/full/`, sha256-checked —
they are not committed; the owner's decision on committing them is open).

## What the certificate means — and what it does not

The certificate is **evidence about machine-checkable properties**. It is not an accessibility conformance
claim, and it does not say a file is usable by a person with a disability.

- It carries the checks that ran, each with `pass`/`fail`/`na` and a reason.
- It carries every reader's own numbers: a certificate is per reader, never a blend.
- It carries `tier1_unavailable[]`: if Preview (PDFKit) could not run, the verdict says `PASS (tier-1
  incomplete: pdfkit n/a)` instead of a bare `PASS`. Two certificates of different strength never look alike.
- It carries `not_checked` with the published totals of the **Matterhorn Protocol 1.1** (PDF Association,
  CC BY 4.0): 136 failure conditions, **87 machine-determinable, 47 requiring human judgment, 2 with no
  specific test** (23-001, 27-001). The 87 are conditions *software can determine*, not conditions this tool
  checks: the certificate claims only the ids in `checks[]`. A machine verdict that forgot the human half
  would be the most expensive kind of wrong.

The distinction that matters commercially: **PDF Declarations** (pdfa.org/declarations) are a machine-readable
claim *inside* the file's XMP (`pdfd:declarations`, `claimBy`, `claimDate`, `claimReport`). This certificate is
not a declaration: it is a separate JSON document produced by a named pipeline, with the file's sha256, and it
is only as good as the checks it lists. Cases declare `pdfuaid:part 1` and `pdfaid:part 3/B` in their XMP —
that is the claim; the certificate says whether it holds.

## The reader matrix

| reader | tool | why it is in the matrix |
|---|---|---|
| `pdfium` **tier-1** | `pypdfium2` (pinned in `requirements.txt`) | Chrome, Edge and every Chromium viewer; the primary metric P |
| `pdfkit` **tier-1** | `PDFKit` through `swift` (macOS) | Preview, and the user's own copy-paste |
| `mupdf` | `pymupdf` (pinned) | most RAG extractors and many Linux viewers |
| `poppler` | `pdftotext` (brew) | the reference command-line extractor |
| `pdfminer` | `pdfplumber` / `pdfminer.six` | the pure-Python extractor inside many pipelines |

Versions are printed in every result and in every certificate. A reader that cannot run is `n/a` **with its
reason**; it never prints `PASS`.

Two readers are **unpinned** — their version comes from the machine, not from a pin: PDFKit ships with macOS,
and poppler ships from brew with no version switch (measured: the CI runner had 26.10.0 while the floors were
taken on 26.07.0). The ratchet records both and, when the version differs, **skips that reader's floors with a
printed note** — never silently. What keeps an unpinned reader honest is the limit's control, which every `run`
re-executes: a limit that stopped reproducing on the installed version is refused by name. The three pip readers
(pdfium, mupdf, pdfminer) are gated unconditionally. A reader that disappears from a run is a **failure**,
never a skip.

## The declared limits

`conformance/readers/limitations.json`. A limit is applied only when its control reproduces the defect on the
installed version — and each one excuses a narrow, named slice:

| id | reader | excuses | control |
|---|---|---|---|
| `mupdf-ar-digit-reversal` | MuPDF | the deficit of a digit run whose exact reverse is present | `controls/mupdf_digits.py` — MuPDF writes the file, MuPDF misreads it, PDFium reads it right |
| `poppler-bidi-decorations` | poppler | direction controls up to the measured per-line count | `controls/poppler_bidi.py` — a **PyMuPDF**-written file (not our pipeline, not the engine under test), pdftotext adds 4 per line, PDFium adds 0 |

A limit with no control script, or whose control no longer reproduces, is **refused by name**
(`tests/test_limits.py` proves both refusals). `validate` never runs a control: a certificate must be checkable
without producing new facts.

## How to add a case

One JSON file in `conformance/corpus/cases/`, named after its id:

```json
{ "id": "tbl-negative-amount-01", "category": "table-rtl", "lang": "ar", "font": "plex",
  "blocks": [
    {"type": "heading", "level": 1, "text": "كشف الحساب"},
    {"type": "paragraph", "text": "…", "align": "justify"},
    {"type": "list", "ordered": true, "items": ["…"]},
    {"type": "table", "header": ["البند", "المبلغ"], "rows": [["رسوم", "-6,006.965"]]} ],
  "note": "where the case comes from, or the incident it stands for" }
```

`header` may be one row or several (`[["a","b"],["c","d"]]` — a two-row header is a real shape). Then:

1. `python3 -m conformance manifest --write` (the manifest is derived; never edited by hand)
2. `python3 -m conformance run --engine chrome --cases <id> --out /tmp/one`
3. `python3 -m conformance run --engine chrome --accept` if the new numbers are the new floors — separately,
   in their own commit, with the reason in the message.

A case that fails is a **result**, not a reason to move a threshold. Deleting a case needs its reason in the
commit message, and a category at its floor cannot lose one (`conformance/corpus/coverage.py`).

## What the run measures, and how it refuses

1. `manifest.problems()` — the derived manifest against the stored one, both directions.
2. `coverage.problems()` — the ten category floors.
3. Build each case; record engine version, bytes, sha256, median time, text-layer sha256.
4. Read with every available reader; measure; apply the declared limits.
5. Write `results.json` + `results.md`; with `--ratchet`, compare every (reader × case × metric) to its floor.

The corpus is refused before any build when 1 or 2 fails. A measurement of the wrong corpus is worse than no
measurement.

Step 3 also runs the **structural checks** and veraPDF (one batch per flavour over all 54 files) unless
`--no-structure` is passed, so a corpus run reports, per check id, how many cases pass and which cases are not
clean — the number Path E needs.

## The ratchet

`conformance/ratchet.json` records, per reader, the version it was measured on and every case's metrics. A value
below its floor fails the run and names the reader, the case and the metric. A reader version change refuses the
comparison by name (re-record with `--accept` after reading the changelog) — the same discipline as the pinned
Chrome and veraPDF. New cases start `unratcheted` and are reported, not silently floored at zero.
