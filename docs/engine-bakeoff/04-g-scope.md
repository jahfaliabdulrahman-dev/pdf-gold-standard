# G — scope, decisions and acceptance, frozen before the first change

**Engine of record:** decided by E3, and re-decided by E3b only if its six conditions all hold. G's items below
are engine-independent by construction: every one of them is a defect of the **document we produce**, and the
template is the same HTML whichever renderer prints it. If E3b switches the engine, G's list does not change —
only the pipeline its acceptance runs through.

## Decision 1 — the negative sign goes LEFT of the number, and that is the owner's call

**Owner decision, 19 November 2026, 17:44 — recorded verbatim:**

> الإشارة السالبة: عزل خلايا المبالغ LTR في القالب. القبول: mon-negative-table وmon-negative-hindi بشهادة PASS،
> وعرض -6,006.965 بالإشارة يسارًا. [قرار المالك، ١٩ نوفمبر 17:44: الإشارة يسار الرقم في العرض، -6,006.965].

**What this settles.** Today every engine renders the amount with the sign on the right — `6,006.965-` — because
the sign is the first character of an RTL run and therefore takes the paragraph direction. That is incident
#157375, and it is a defect of the **display**, before any extraction. The fix is in the template: the money
cells are isolated as LTR (`dir="ltr"` / `unicode-bidi: isolate`), so the minus sign is the leftmost character
and PDFium reads `-6,006.965`.

**Acceptance (both, measured):**

1. `mon-negative-table` and `mon-negative-hindi` reach a **PASS certificate** — literal match in PDFium and
   Preview, structure clean — under the engine of record.
2. The rendered page shows **`-6,006.965`** with the sign on the left. This is a visual assertion: it is
   checked in the eye sample, not only in the text layer, because a text layer that reads correctly while the
   page prints the sign on the right would be the same lie in the other direction.

**What is NOT claimed:** that LTR isolation alone fixes extraction in every reader. It is **مرجّح** (a mechanism
hypothesis with a named cause), and G measures it on both cases and both readers. If isolation fixes the display
but not PDFium, the display decision still stands — it is the owner's — and the extraction defect moves to the
`fix_text_layer` family with its own case.

## The rest of G, in order

| # | item | acceptance |
|---|---|---|
| 2 | `7.2-43` — the empty cell in the structure tree fails PDF/UA-1 on `tbl-empty-cell` (ours alone; both competitors pass) | UA-1 zero failing rules across the corpus |
| 3 | line-final mark after the closing punctuation (`الْعَالَمِينَ.َ`, `.⃀`) | `voc-full` and `mon-riyal-sign` at `exact=1` in both readers |
| 4 | the whole of it | **every** `money` and `tables` case reaches a PASS certificate |

## Rules that hold for every item

- **No number without a command**, and every claim carries `مُثبت | مرجّح | مجهول`.
- **The corpus does not change to fit the fix**: if a case must change, it is a new case next to the old one,
  and the old one keeps failing until the fix is real.
- **A defect of a competitor's tagger is not ours to fix in our layer** (WeasyPrint's `0 TR`): if E3b wins,
  repairing it is a precondition for F, estimated in hours, and it is not counted as G's work.
- **The measurement on which G's acceptance rests is the same gate** — `--time-repeats 3`, two runs, the same 60
  cases, `ratchet check` after the floors are accepted explicitly.
