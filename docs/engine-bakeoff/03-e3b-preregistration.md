# E3b — preregistration, written before any measurement of `weasyprint+pp`

**Status at commit time:** nothing has been built for `weasyprint+pp` on this branch, by us or by anyone. The
only WeasyPrint runs in existence are the four `weasyprint` runs of E3, whose numbers are in
`docs/engine-bakeoff/02-e3-report.md`. This file is the commitment; the measurement follows it and may not
amend it. If the measurement contradicts the expectation, the contradiction is the result.

**Why one more experiment.** E3's table says something the transition rule does not ask:

| | chrome+pp | chrome-raw | weasyprint (raw) |
|---|---|---|---|
| Preview reads exactly (cases at `exact=1`) | 37/60 | 13/60 | **43/60** |
| structure clean | 27/60 | 0/60 | **31/60** |
| veraPDF UA-1 | 59/60 | 0/60 | **60/60** |
| veraPDF A-3b | 60/60 | 0/60 | **60/60** |
| P (PDFium exact) | 35/60 | 5/60 | 13/60 |

WeasyPrint's raw output beats our whole pipeline everywhere **except** in PDFium — and PDFium is exactly the
reader our post-processing was built for (chrome-raw 5 → chrome+pp 35). So the question is not "which engine
is better", it is **"is our layer worth more on WeasyPrint's output than on Chrome's?"** If it is, Path G's
hours — all of which go into `fix_text_layer`, a Chrome-shaped layer — would be spent on the wrong engine.

## The candidate, exactly

`weasyprint+pp` = the same 60 corpus cases, rendered by the same `conformance/adapters/weasyprint.py`
(WeasyPrint 70.0, `--pdf-variant pdf/ua-1 --pdf-tags --pdf-identifier <id>`), then the shipping stages, in this
order **and nothing else**:

1. `fix_text_layer.process(raw, fixed, strict_widths=True)` — the same call the Chrome adapter makes.
2. the docinfo stamp (`/SourceFile`, `/SourceSHA256`).
3. `postprocess.apply(stamped, out, profile="web", features_path=FEATURES, rendered_sha=<markup sha256>,
   chrome_version=<weasy version>, doc_spec=case_spec.make(case))`.
4. `set_outline(out, case)`.

**Allowed to adapt:** input paths, the version string stamped as `chrome_version` (it carries the *producer*
version, and WeasyPrint's own version is the honest value), and the CLI mode wiring.
**Forbidden:** any change to `fix_text_layer.py`, `postprocess.py`, `pdfops.py` or the corpus. If the layer
needs a change to accept WeasyPrint's output, that is a refusal, not a fix — E3b does not edit the product.

## The decision rule — ALL six, no averaging

`weasyprint+pp` replaces `chrome+pp` only if every line is true. Each is the same metric E3 used, on the same
60 cases, measured with:

```
.venv/bin/python -m conformance run --engine weasyprint+pp --out /tmp/e3b/weasyprint-pp-r1 --time-repeats 3
.venv/bin/python -m conformance run --engine weasyprint+pp --out /tmp/e3b/weasyprint-pp-r2 --no-structure
.venv/bin/python scripts/e3b_analyse.py /tmp/e3b        # prints the six, and applies the rule
```

| # | condition | threshold | why this number |
|---|---|---|---|
| 1 | P — cases at PDFium `exact == 1.0` | **≥ 35** | the incumbent's count; a tie is not a win |
| 2 | S1 — cases Preview reads exactly | **≥ 37** | the incumbent's count |
| 3 | structure clean | **≥ 27** | the incumbent's count |
| 4 | certificate PASS | **≥ 18** | the incumbent's count (same `certificate.decide` rule) |
| 5 | veraPDF UA-1 **and** A-3b | **zero failing rules across the corpus** | the incumbent fails one rule (`7.2-43`), so this is where a challenger can win outright |
| 6 | determinism | **text layer identical on 60/60 across r1 and r2** | bytes may differ (timestamps); what is printed may not |

**If the layer refuses the file — an exception from `fix_text_layer`, `model_boundary`, or `postprocess` — that
is a result:** it is recorded with its exception type and message, E closes on Chrome, and no threshold in this
table is consulted.

**Tables.** WeasyPrint's tagged text loses table structure (`0 TR` for 3 rows, 12/60 table checks fail). That is
a defect of its tagger, not something our layer repairs, so it is **not** part of the transition rule — the rule
asks whether the layer is worth more on this engine, not whether the engine is perfect. But if `weasyprint+pp`
wins, fixing `Table/TR` (an upstream patch or a rebuild inside `postprocess`) becomes a precondition for Path F,
and the report must estimate it in hours.

**Time limit: 4 hours.** At the limit, whatever is measured is delivered, `chrome+pp` stays, and E closes. No
extension without a new preregistration.

## What E3b does not decide

Nothing about Path F, nothing about G's scope, and nothing about licence or speed. Those were decided by E3.
It answers one question: **on which engine do our stages pay?**

## Until it runs

The rule of E3 holds: **`chrome+pp` is the engine of record.** E3b is a measurement, not a switch.
