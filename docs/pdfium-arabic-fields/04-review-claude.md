**VERDICT: REQUEST CHANGES**

---

## SEVERITY: BLOCKER

**[02-plan.md Phase 0] The critical assumption is unproven in your own evidence pack**

WHY: You claim PDFium doesn't call HarfBuzz/SkShaper (00-proof.md §3), mark it "likely — not executed here," then base the entire patch design on filling that gap. If PDFium *does* shape text somewhere and the Arabic bug is a configuration/invocation issue, this multi-week engineering effort solves the wrong problem.

FIX: Execute `git -C pdfium grep -rn "hb_shape\|hb_buffer\|SkShaper\|textlayout" -- fpdfsdk core third_party/skia` on a full checkout BEFORE writing code. If any hits exist, investigate whether the pipeline is present but misconfigured. Document the grep output with line counts in 03-experiments.md. Phase 0 exit criteria must be "grep completed, output recorded, confirmed zero invocations in text rendering path."

**[01-design.md §2.3, §4] Undo/redo design is absent**

WHY: You expand CPVT_Word with shaped data and say "Backspace deletes whole cluster," but PDFium's undo stack records character-level edits. When a user types "لا" (2 chars → 1 glyph), then backspace, then undo, what state is restored? If undo granularity is per-character but your model is per-cluster, undo will resurrect half a ligature. Acceptance test list (§4) has no undo test despite claiming to test "undo."

FIX: Add §2.6 "Undo and redo" to 01-design.md. Specify: does undo operate on logical characters (requiring re-shape on every undo) or clusters (breaking user expectations when "ا" was typed separately but undoes with "ل")? Add acceptance test 9: "Type ل then ا (forms لا ligature), backspace (deletes both), undo → both characters restored and ligature re-formed." If undo can't be made consistent with cluster-based editing, this is a design-level blocker.

**[01-design.md §2.4] /AP generation is critically underspecified**

WHY: You say "embedded full font + ToUnicode" but don't address: (a) font subsetting — a "full font" per field bloats file size unacceptably; a subset requires knowing all future glyphs, which you can't during live editing; (b) interaction with /DR (document resources) — does this duplicate fonts already embedded? (c) what happens when Acrobat/Preview opens the saved PDF and the user edits the field — do they regenerate /AP and lose your shaping? If so, the fix only works in read-only scenarios.

FIX: Expand §2.4 with: (1) Font embedding strategy: subset of *used* glyphs written at save time (like `postprocess.form_font` subsetting), not live. Cite the code path where PDFium finalizes /AP on save. (2) /DR reuse: check if font already exists in /DR, reference it rather than re-embed. (3) Regeneration resilience: test that after Chrome saves the PDF, opening in Acrobat and *saving without editing* preserves the /AP. If Acrobat regenerates /AP on any save, document that the fix is Chrome-only for active editing, but cross-reader for read-only forms. (4) Add acceptance test 10: "Save PDF in Chrome, open in Acrobat, save again without edits, verify shaped /AP persists."

**[02-plan.md Risks, Phase 1] Circular dependency: design requires HarfBuzz, fallback says "builds without HarfBuzz"**

WHY: Acceptance test 8 says "builds without HarfBuzz (fallback) doesn't break," but the entire patch is predicated on HarfBuzz existing (Phase 1 links `//third_party/harfbuzz`). If HarfBuzz is optional, what does the fallback actually do? If it's required, test 8 is impossible.

FIX: Resolve the contradiction. Either: (a) HarfBuzz is mandatory (remove test 8, make it a build-time requirement, phase 0 confirms it's in DEPS), OR (b) fallback means "if `hb_shape` returns zero glyphs, render character-by-character" (current behavior), not "builds without the library." Rewrite test 8 as "Font without shaping tables falls back to current rendering" and move it to phase 1.

---

## SEVERITY: MAJOR

**[01-design.md §2.3] Bidirectional selection algorithm is asserted, not designed**

WHY: You say "selection stored logically (start, end), displayed visually (rectangles per run)" but don't specify the algorithm. When text is "ملاحظة 2026" (RTL, LTR, RTL per §2.2), and the user drags from visual position X to Y, how do you compute the logical range? The UBA visual-to-logical mapping is nontrivial, and getting it wrong makes selection visually broken (rectangles in wrong places or spanning wrong text).

FIX: Add pseudocode or reference an algorithm. Example: "Use `ubidi_getLogicalRun` to map visual X-coordinate to (run index, offset), then map to logical position via run's start index. Selection rectangles: iterate logical range, map each character to its visual run, accumulate rects per run." If you're depending on Skia/ICU to do this, cite the API. Add acceptance test: "Select 'حظة 20' (crosses RTL/LTR boundary) by dragging visually left-to-right, verify logical selection is correct via copy/paste output."

**[00-proof.md §3 table] Code references are URLs to main branch, not commit SHAs**

WHY: You cite `fpdfsdk/pwl/cpwl_edit_impl.cpp:33-48` as evidence, but the line numbers will drift as PDFium evolves. When an upstream reviewer reads this in 2027, the lines won't match. More critically, *you haven't verified this locally* — the file was fetched via curl from GitHub main, not from a local checkout at a known commit.

FIX: Check out PDFium at a specific commit (e.g., `chromium/6706` or latest as of 2026-11-15), record the commit SHA in 03-experiments.md, and cite line numbers against that SHA. Example: "As of commit `abc123def456` (2026-11-15), `fpdfsdk/pwl/cpwl_edit_impl.cpp:33-48`…". This makes the evidence reproducible and version-pinned.

**[02-plan.md Phase 5] /AP test only checks *display*, not *editability* after save**

WHY: Exit criteria is "MuPDF and Acrobat (after save) display connected," but the real test is whether editing still works. If another reader regenerates /AP with its own (broken) shaping when the user clicks the field, your fix is defeated. You need to know if the /AP survives editing or is ephemeral.

FIX: Extend Phase 5 exit criteria: "Open saved PDF in Acrobat Reader, click into the field (focus it), type one more character, save → verify /AP still contains shaped glyphs (via manual inspection of PDF stream or MuPDF rendering). If /AP is regenerated by Acrobat's engine, document that cross-reader benefit is read-only." Add a note: if Acrobat regenerates, consider whether a `/Lock` or `/NeedAppearances false` flag can prevent it (research required).

**[02-plan.md Risks table, Risk 3] "Re-layout line only" performance claim is unsubstantiated**

WHY: You say re-shaping a line on every keystroke is "cheap" and mitigate with "re-layout line only, cache on (line text, font)." But: (a) what if the field is a multi-line `<textarea>`-style widget and the user is editing line 1 of 50? (b) What if the line is 200 characters of mixed Arabic/Latin/numbers (multiple fonts via fallback)? (c) HarfBuzz shaping isn't free — `hb_shape` on a 200-char line with font fallback could be milliseconds, visible as lag.

FIX: Add Phase 1.5: "Performance baseline." Shape a 200-character Arabic string with `hb_shape` 1000 times, measure P50/P95 latency on the target machine (M4 24GB), record in 03-experiments.md. If P95 > 5ms, add a debounce or async shaping strategy. Update risk mitigation with measured numbers, not "cheap."

**[01-design.md §3] Missing file: generation of ToUnicode CMap**

WHY: You list files to modify but don't mention where ToUnicode CMap generation happens. The /AP must map shaped glyph IDs back to Unicode code points so text extraction works (copy/paste, screen readers). If you embed glyphs without ToUnicode, the PDF becomes unsearchable and inaccessible.

FIX: Add to file map: "core/fpdfapi/font/cpdf_tounicodemap.{h,cpp} — generate CMap from cluster → logical character mapping." Verify PDFium has existing ToUnicode generation for embedded fonts (it should, for text objects), and confirm it can be reused for /AP. Add acceptance test 11: "Fill field with 'ملاحظات', save, extract text via `pdftotext` → output is 'ملاحظات' in logical order (not glyph IDs, not garbage)."

---

## SEVERITY: MINOR

**[01-design.md §2.3] Copy/paste behavior unspecified**

WHY: When a user selects shaped text in a field and copies it, what goes to the clipboard? If you copy the visual glyphs, pasting into another app gives garbage. If you copy the logical Unicode, that's correct — but your design doesn't state this.

FIX: Add one sentence to §2.3: "Copy uses logical selection (cluster start indices) to extract original UTF-16 code points, not shaped glyph IDs. Paste inserts logical characters, triggering re-layout." (This should be obvious, but make it explicit.)

**[03-experiments.md §4] Missing: verification that IBMPlexSansArabic is actually used in the form**

WHY: You measure shaping with IBMPlexSansArabic-Regular.ttf, but don't confirm the test PDF uses that font. If the PDF references a different font (or uses Helvetica with a broken /ToUnicode), your measurements aren't measuring the actual scenario.

FIX: Add to §3: "Verify test PDF font: `pdffonts evidence-field.pdf` → expect `IBMPlexSansArabic-Regular (CID)` or subset. If different, re-run §1 measurements with the actual font." (Or use `mutool info -F` if pdffonts isn't installed.)

**[02-plan.md Phase 7] "code-review-elite" is undefined jargon**

WHY: An upstream PDFium reviewer reading this plan won't know what "code-review-elite" means. Is it an internal tool? A quality bar? A typo for `/code-review ultra`?

FIX: Either define it ("code-review-elite: internal tool, performs X, Y, Z checks") or replace with a concrete action: "Static analysis via `clang-tidy`, manual review by two engineers, and automated pixel regression suite."

---

## WHAT REMAINS UNPROVEN (your own §5 + additions)

1. **That PDFium never calls HarfBuzz/SkShaper** — marked "likely" but not executed (blocker until Phase 0 done).
2. **That `third_party/harfbuzz` is in PDFium's DEPS tree** — you infer from Skia's BUILD.gn, but haven't run `gclient sync` and checked.
3. **Undo/redo consistency** — no design, no test.
4. **Bidirectional selection visual→logical algorithm** — asserted, not specified.
5. **Performance of re-shaping on every keystroke** — "cheap" is not a measurement.
6. **Font subsetting strategy for /AP** — "subset of shaped glyphs" doesn't answer *when* the subset is computed (can't know future glyphs during live edit).
7. **Whether Acrobat/Preview regenerate /AP on edit** — if yes, cross-reader benefit is read-only only.
8. **Security review of HarfBuzz/ICU attack surface** — you're adding a complex text-processing library to a PDF parser (historically a high-value exploit target).
9. **Upstream PDFium maintainer appetite** — no evidence they want this complexity (risk 5 mitigation is "write good tests," not "confirm they'll accept it").
10. **License compatibility of embedding shaped glyphs** — some fonts prohibit embedding or require subsetting; does shaping create a derivative work?

---

**SUMMARY**: The proposal has the right intuition (use HarfBuzz, handle bidi, fix /AP), but the design is underspecified in the critical paths (undo, /AP generation, cross-reader editing), and several "facts" are assumptions. The implementation plan is verifiable in phases 0-3, but phases 4-6 have gaps. Fix the blockers (prove HarfBuzz absence, design undo, specify /AP subsetting, resolve the fallback contradiction) before writing C++. The 3-4 week estimate is optimistic; add 1-2 weeks for the missing pieces.
