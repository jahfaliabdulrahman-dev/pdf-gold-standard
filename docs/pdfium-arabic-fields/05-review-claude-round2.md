## Prior Findings Status

**BLOCKER 1: Unproven no-shaping assumption**
**CLOSED** — `03-experiments.md §4`: commit `a8432342`, `grep` returns 0, command provided.

**BLOCKER 2: Missing undo/redo**
**CLOSED** — `01-design.md §2.6`: logical ranges, relayout after undo, cluster-based backspace, test #9.

**BLOCKER 3: Underspecified /AP**
**CLOSED** — `01-design.md §2.4`: subset embedding, `/DR` reuse, `ToUnicode`, constraint in §5 (reading/saving, not live editing). Tests #7, #10.

**BLOCKER 4: Fallback contradiction**
**CLOSED** — `01-design.md §2.5`: HarfBuzz mandatory for build; fallback = font without GSUB → current per-char path. Test #8.

**MAJOR 1: bidi selection algorithm**
**CLOSED** — `01-design.md §2.3`: visual↔logical via `ubidi_getVisualRun`/`ubidi_getLogicalRun` (ICU), not hand-rolled. Test #6.

**MAJOR 2: unversioned citations**
**CLOSED** — ISO sections, file:line references, commit SHA, reproducible commands in `03-experiments.md`.

**MAJOR 3: /AP editability**
**CLOSED** — `01-design.md §2.4`, §5: constraint stated (benefit for reading/saving; other readers regenerate on edit). Test #10.

**MAJOR 4: unmeasured performance**
**CLOSED** — `03-experiments.md §5`: 200 chars, P95=0.017ms. Milestone 0.5 done.

**MAJOR 5: missing ToUnicode path**
**CLOSED** — `01-design.md §2.4`: cluster→char via `cpdf_tounicodemap.{h,cpp}`. Test #7 (`pdftotext`).

---

## New Findings

**MINOR 1: HarfBuzz availability proven for wrong Skia version**
`03-experiments.md §2` fetches `skia.gni` from Skia **main**, not the Skia revision pinned by PDFium DEPS at `a8432342`. **Close**: `curl pdfium/DEPS` → extract Skia SHA → verify `skia_use_harfbuzz` at that revision.

**MINOR 2: Milestone 0 "clean build" claim unsupported**
Plan states milestone 0 "أُنجز" with "clean build in `out/Release`" but no `ninja` log provided; §6 notes build time unmeasured. **Close**: provide build success log OR state "build deferred to milestone 1 start".

**MINOR 3: ToUnicode one-to-many mapping (ligatures) not proven**
لا = 1 glyph from 2 chars requires CMap `<GID> <U+0644 U+0627>`. Plan references existing `cpdf_tounicodemap` but doesn't prove it supports one-to-many. **Already gated by test #7**; just note the risk explicitly.

---

## Verdict

**APPROVE WITH FIXES**

All prior blockers closed. New gaps are proof-layer (wrong Skia version, no build log), not design flaws. Easily closed.
