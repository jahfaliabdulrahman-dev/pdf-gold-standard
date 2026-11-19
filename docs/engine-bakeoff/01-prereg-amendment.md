# PREREG AMENDMENT — engine bakeoff (Path E), cycle 2026-11-19

**Committed before any E3 measurement.** The decision rule (§1 of the preregistration) is **unchanged**: not a
threshold, an operand, or a tie-break moves. What changed is the corpus the rule is applied to, because Path C
was reviewed twice and the reviewed gate is what E3 must measure on (assignment §5.3).

## What changed, and why

| subject | at E0 (preregistration) | at E3 | why |
|---|---|---|---|
| corpus size | 55 cases | **60 cases** | C round 2 added `bld-word`, `bld-heading`, `bld-th`, `tbl-plain-fragment`, `voc-no-heading` and removed `tbl-explicit-width` (it asserted a mechanism that measurement did not support) |
| manifest sha256 | `be489998f6a2f26089602abe2a5b00fb087969834cc21c58086b570726555f56` | **`98376692b796c02ae1473a473fab7b53c087612e55a356588f12316c8a8ee361`** | consequence of the above |
| the template each engine prints | no bold (weight 400 pinned), `@page` declared, no U+20C1 owner | **real 700 faces declared and used**, `@page` declared, **Saudi-Riyal-Font (OFL) as the declared last-resort face** | the review's P1-2 and P2-3: the template must not dodge a defect, and a distributable file must not embed an Apple face |
| corpus categories | 10 | **10** (counts move: tables 8→9, shaping 6→7, headings 4→5, vocalisation 6→7) | same |
| the Chrome pipeline under test | the branch's stages | **`chrome+pp` at `main` after the C merge**, with the joiner A/B measured and the joiners LEFT IN (the owner's decision #2: removal waits for the E verdict) | assignment §5.3 |

## What this means for the comparison

The two competitors build from the **same 60 case files**, the same pinned TTFs (same sha256), and the same
`@page` declaration — the HTML template is shared by chrome and WeasyPrint, and the Typst adapter prints the
same strings. No competitor receives post-processing, and no competitor was retuned for the new cases: their
adapters either build a case or they do not, and H1 records which.

Every number in the E3 report is produced with

```
CHROME_PATH=<CfT 157.0.8103.78> CONFORMANCE_PDFTOTEXT=<pinned poppler 26.11.0> \
  .venv/bin/python -m conformance run --engine <engine> --out <dir> --time-repeats 3
```

twice per engine (determinism), and every built file's sha256 and `/Producer` is printed **before** any
comparison — the review's note that Typst and WeasyPrint returned three identical `order` values in the smoke is
exactly the kind of coincidence that must be excluded, not explained away.
