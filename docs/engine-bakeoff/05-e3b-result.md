# E3b — the result: our stages pay on Chrome, and nowhere else

**Preregistration:** `03-e3b-preregistration.md`, committed at `268253b` **before** the first `weasyprint+pp`
build existed. This file reports what that rule produced; it does not amend it.

**Verdict: E closes on `chrome+pp`.** The candidate was refused before it could be judged — and then, on the
documents that were not refused, it was measured and turned out to change nothing. Both facts point the same
way, and neither is a matter of degree.

## 1 · The refusal (preregistered as a result, not a retry)

```
=== r1 (structure)
built dig-phone                     0.75s   12049 B
postprocess: the document is outside the declared model — refused, not interpreted:
  p1: text rise 9.421 (Ts) — a glyph off its baseline is not modelled
```

The layer did not crash and did not time out: `postprocess` **refused** the document, by name and by feature,
exactly as its model boundary is designed to. Per the preregistration ("a refusal from the layer is a result,
not a retry") the six thresholds were never consulted.

**How wide the refusal is** — `scripts/ts_scan.py`, counting `Ts` in each engine's own output (E3's runs):

| engine | files with `Ts` | share |
|---|---|---|
| **weasyprint 70.0** | **17 / 60** | **28.3 %** |
| chrome 157.0.8103.78 | 0 / 60 | 0 |
| typst 0.15.1 | 0 / 60 | 0 |

The 17 are not random: **all 7 vocalisation cases**, 5 punctuation cases, `dig-year`, `kash-justify-tatweel`,
`lst-ordered`, and 2 table cases — the classes where a combining mark or a raised glyph is placed off the
baseline. WeasyPrint draws those marks as glyphs positioned with a text rise; the model refuses text rise.

## 2 · The diagnostic (so the refusal's shadow has a size) — decides nothing

The rule closed E on the refusal. But "refused" would be an empty answer if the layer were about to do something
great, so the 43 documents the model **accepts** were run through the full candidate. This is a diagnostic, not a
transition decision, and it is labelled as such.

| on the 43 accepted documents | weasyprint+pp | chrome+pp | raw weasyprint |
|---|---|---|---|
| **P** — cases at PDFium `exact == 1.0` | **12** | **26** | **12** |
| **S1** — cases Preview reads exactly | 39 | 32 | 39 |
| structure clean | 24 | 27 | — (E3: 31/60 raw) |
| certificate PASS | 8 | 18 | — |
| failing veraPDF rules | **0** | 1 (`7.2-43`) | **0** |

**The number that ends the question:** on those 43 documents, `weasyprint+pp` is **identical to raw
weasyprint** — P 12, S1 39, case by case. Our entire pipeline, with every stage unchanged, changes **not one
case** on WeasyPrint's output. On Chrome, the same stages move P from 5 to 35.

So the layer's worth is not "0.5 on Chrome and a little on WeasyPrint" — it is **+0.500 on Chrome and exactly
0.000 on WeasyPrint**. `chrome-raw 5 → chrome+pp 35` was never a property of "PDFs"; it is a property of *what
Chrome's text layer gets wrong*, and WeasyPrint already gets those things right.

## 3 · What this settles, and what it opens

**Settled.** The engine of record for the shipped document is `chrome+pp`, and Path G's hours — all of which go
into `fix_text_layer`, a Chrome-shaped layer — are spent on the right engine. E is closed; there is no E4.

**Opened — a product limitation, not a bakeoff curiosity.** Our model refuses `Ts`, and a real invoice can carry
text rise for reasons that have nothing to do with an engine's mark strategy: a footnote marker, a superscript
in a legal reference, a raised currency symbol. The corpus has **no case that produces `Ts` under Chrome**, so
the pipeline would meet this limitation for the first time in production. Two honest options, priced in G/F:

1. **Model it:** teach `pdfops`/`postprocess` that a run may sit at a vertical offset (the structure is
   unchanged; only the geometry of the glyph), and add a case that produces `Ts` under Chrome to prove it.
2. **Refuse it in the template:** forbid `<sup>`-style markup in the document spec, and say so in F's template
   rules — the model boundary then refuses by construction, which is at least planned.

Option 1 is the one that matches "fix the root, not the symptom" — but it is not free, and it is not G's first
item (the owner's sign decision is).

## 4 · What E3b does not decide

Nothing about Path F, nothing about licences, nothing about typst's speed. It answers one question — *on which
engine do our stages pay?* — and the answer is measured twice, once by a refusal and once by a no-op.

## 5 · ما لم يُثبت

- That the 17 refusals are all the same mechanism. I verified the operator (`Ts`), its count per file, and its
  presence in the 17 named cases; I did **not** verify, case by case, that removing `Ts` would let the layer
  accept the file — that is a G/F experiment, not a claim.
- That Chrome can never produce `Ts`. The corpus contains no case that does; a document with a superscript
  might. Absence in 60 cases is not absence in Chrome.
- That the 43-document comparison is free of selection bias. The subset is "documents the model accepts", which
  is a property of the model, not a random sample. The comparison is still valid *for that subset*, and it is
  the subset the candidate would have had to win on.
