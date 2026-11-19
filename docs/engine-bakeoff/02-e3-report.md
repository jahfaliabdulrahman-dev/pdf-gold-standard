# E3 — the bakeoff, measured on the reviewed 60-case corpus

**Branch:** `spike/engine-bakeoff` · merged `main` (`7d529b8`) into it by merge, no rebase, no force.
**Corpus:** 60 cases · manifest sha256 `98376692b796c02ae1473a473fab7b53c087612e55a356588f12316c8a8ee361`.
**Machine:** macOS 27.2.1 (arm64) · Chrome for Testing `157.0.8103.78` · Typst `0.15.1 (9dfd3a08)` ·
WeasyPrint `70.0` (pango 1.58.02, harfbuzz 15.1.0) · poppler `26.11.0` (pinned, conda-forge) · veraPDF `1.30.0`.

Every number below is produced by one command, and the analysis that applies the rule is a script in the
repository (`scripts/e3_analyse.py`) — no figure is typed by hand:

```
CHROME_PATH=<CfT> CONFORMANCE_PDFTOTEXT=<pinned pdftotext> DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
  .venv/bin/python -m conformance run --engine <chrome|chrome-raw|typst|weasyprint> \
      --out /tmp/e3/<engine>-r1 --time-repeats 3
.venv/bin/python scripts/e3_analyse.py /tmp/e3
```

Each engine was built **twice** (`-r1` with the structural checks, `-r2` without) for the determinism question.

## 1 · The rule, applied

| engine | version | **P** (pdfium exact) | S1 (pdfkit) | S2 worst order | S3 rules | S5 median | A-3b | UA-1 | headings |
|---|---|---|---|---|---|---|---|---|---|
| **chrome+pp** | 157.0.8103.78 | **35/60 (0.583)** | 0.617 | 0.102 | 1 | 0.689 s | 60/60 | 59/60 | 60/60 |
| chrome-raw | 157.0.8103.78 | 5/60 (0.083) | 0.217 | 0.099 | 6 | 0.564 s | 0/60 | 0/60 | 56/60 |
| typst | 0.15.1 | 10/60 (0.167) | 0.400 | 0.106 | **0** | **0.016 s** | 60/60 | 60/60 | 53/60 |
| weasyprint | 70.0 | 13/60 (0.217) | **0.717** | 0.117 | **0** | 0.713 s | 60/60 | 60/60 | 60/60 |

**ΔP:** typst `−0.417`, weasyprint `−0.367`. The transition clause needs `P(competitor) ≥ P(incumbent) + 0.05`;
the tie clause needs `|ΔP| < 0.05`. **Neither holds.**

**Verdict — rule 3: `chrome+pp` stays.** The measured cost of our post-processing is the difference between the
first and second rows: **P(pp) − P(raw) = 0.583 − 0.083 = 0.500**, i.e. 30 of 60 cases are readable ONLY because
of the stages we own.

## 2 · What each competitor lacks, by the numbers

**typst (P = 0.167).** Fails all 9 digit cases and all 7 vocalised cases; keeps 4/7 shaping and 3/9 tables. Its
text layer is the cleanest of the three on punctuation (`tagged-text` 35/60 fail, but see §3) and its output is
**byte-identical across two runs** on all 60 cases, while Chrome's never is (creation date) — the text layer is
identical for both. It is the only engine with **zero** failing veraPDF rules on both flavours, and it builds a
case in **16 ms**, 43× faster than the incumbent. That speed and that cleanliness are what make it attractive
for Path F despite a P far below the bar.

**weasyprint (P = 0.217).** Reads better in Preview than our own output (S1 0.717 vs 0.617) and passes UA-1 and
A-3b on all 60 — but its tagged text loses table structure (`0 TR for 3 rows`, 12/60 table checks fail), which
is why its P is a third of ours.

**Both** fail where the corpus is hardest: money (1 and 3 of 7), digits (0 of 9), vocalisation (0 of 7).

## 3 · Two gate defects this measurement found — and the fix

The comparison was unfair until they were fixed, and both were invisible on our own files:

1. **`TJ` arrays were never read.** `[(...)]TJ` passes ONE array operand; the tag reader iterated the operand
   list, handed the array to the decoder, got `b""` and recorded an empty string. Our pipeline writes `Tj`, so
   the gate never noticed. Effect measured: `fonts {}`, `codes 0`, and three checks (`tagged-text`, `headings`,
   `tables`) accused Typst and WeasyPrint of carrying no text at all.
2. **`/Resources` inheritance was ignored.** PDF 32000-1 §7.7.3.4 lets a page leave `/Resources` to the
   `/Pages` node — most producers do, ours does not.
3. **PDF/A-3b was judged on the wrong file for WeasyPrint.** It cannot combine UA-1 and A-3b in one file, so it
   writes `<id>.pdf` and `<id>.a3b.pdf`; the batch compared the UA-1 file against A-3b and reported 60/60
   failures while `verapdf --flavour 3b` passed the very file WeasyPrint wrote. Fixed in `runner.py` (the batch
   now reads the file that claims the flavour) — this is the "measurement artifact" the review warned about.

The three are guarded now: `conformance/tests/test_mcid_text.py` builds a `Tj` page, a `TJ`-array page and a
page with inherited `/Resources`, and fails if the reader misses any of them.

**Consequence for Path C's numbers: none.** Measured, not assumed: the post-fix run of `chrome` reproduces the
committed run exactly — clean cases 27/60, pdfium 35/60, and every per-check count identical — because our
pipeline writes `Tj` and puts `/Resources` on the page. `docs/conformance/results/2026-11-19-chrome.*` stands as
committed; the two reader fixes only change what the gate says about OTHER producers' files.

## 4 · The smoke suspicion, answered

The review noted that Typst and WeasyPrint returned **identical `order` values** on three cases in the smoke.
Measured on the full corpus: **47 of 60 cases have identical pdfium `order` between the two engines**, and their
files are **all distinct** (`sha256` 60/60 unique per engine, and **no file is shared across engines**). So the
coincidence is a property of the metric, not of the converters: `order` is too coarse to separate two engines
that both lay out correctly-but-differently. Each file's `sha256` and `/Producer` are in the run's `results.json`
(`producer_pdf` per case) and printed before any comparison.

## 5 · H1–H5

| gate | chrome+pp | typst | weasyprint |
|---|---|---|---|
| **H1** every case builds | 60/60 | 60/60 | 60/60 |
| **H2** no `.notdef` (U+20C1 case exempt, measured) | 0 cases | 0 cases | 0 cases |
| **H3** PDF/A-3b passes veraPDF | 60/60 | 60/60 | 60/60 (its own `.a3b.pdf`) |
| **H4** tagging + `/Lang ar` + headings | UA-1 59/60, headings 60/60 | UA-1 60/60, headings **53/60** | UA-1 60/60, headings 60/60 |
| **H5** exact version, re-installable by sha256 | CfT pin (`chrome_pin.py`) | 0.15.1 + tarball sha256 (E1) | 70.0 via `requirements-bakeoff.txt` |

`model-boundary` is `n/a` for both competitors by construction (it is our post-processing's guard, not theirs).

**H3's second half — «بمرفق XML» — is not in the corpus.** The XML attachment is a ZATCA invoice artifact (Path
F), not a property of a 60-case typographic corpus. All three engines pass PDF/A-3b as a flavour; none is asked
to attach anything. Recorded here rather than silently counted as a pass.

## 6 · Licences (from each engine's own files, E1)

| engine | licence | what a service embedding it must do |
|---|---|---|
| Chrome for Testing | Google's CfT terms (not redistributable as a PDF library) | it is a **tool we run**, not a library we ship — the shipped artifact is the PDF |
| Typst | Apache-2.0 (`LICENSE` in the tarball) | keep the NOTICE; no copyleft |
| WeasyPrint | BSD-3 (`License-Classifier: BSD` in `dist-info`) | attribution in documentation |

## 7 · Recommendation

**Keep `chrome+pp` for shipped documents (rule 3).** No competitor is within 0.36 of us on P, and `chrome-raw`
proves the stages are worth 0.50 of it.

**But two of our weaknesses are now measured and cheap to fix, and the rivals' advantages are not theoretical:**
identical `order` values on 78 % of the corpus mean the primary metric cannot see our remaining defects; our
UA-1 has a failing rule (`7.2-43` on `tbl-empty-cell`) that both competitors do not; and Typst writes a
byte-deterministic file in 16 ms. The next cycle (G) should take the `mon-negative-table` / trailing-punctuation
family first — it is the same root as the fatha-after-the-stop and the `.⃀` case: **a line-final mark is placed
after the closing punctuation.**

## 8 · ما لم يُثبت

- That Typst's `headings` 53/60 is a defect of Typst rather than of our heading-text comparison: the seven
  failures are all cases with vocalised or numbered headings, and the reason printed is "heading text does not
  match the case" — the level list matches. Not root-caused.
- That the 47 identical `order` values are all benign: I verified the files differ, not that each pair is
  semantically different in the way the metric ignores.
- H4's «ولا رفض بصري من المالك لتشكيل الحروف» — that clause is a human judgement and is **not** measured here;
  the eye sample (`~/Downloads/pdf-gold-standard-E3-eye-2026-11-19/`) asks for it.
- Whether Chrome's UA-1 failure (`7.2-43` on `tbl-empty-cell`) is our table markup or a veraPDF interpretation:
  one case, one rule, not root-caused.
