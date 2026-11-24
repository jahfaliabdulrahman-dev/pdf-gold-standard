# Code Review Closure — PR-2 (`feat/lexicon-wiki50k`)

**Target:** `9ece554...11c0fad` (PR-2 commits `e1ba621`, `c2f1346`, `e99c80b`, `11c0fad`).
**First round:** three isolated seats on `9ece554...e1ba621`; their full transcripts are the review of
record. This report closes every P0–P3 item and names the declared limits. **The code measured is
`e99c80b`**; `11c0fad` is evidence/docs only. The compare records `head: e99c80b`, `dirty: false`, and the
measuring script sha256.

## Verdict

**APPROVE** — no P0/P1/P2 open. The two blocking classes (private owner rows, and a checker whose report
could not name its lexicon) are closed in `c2f1346`; the evidence is tied to `e99c80b`.

## Standards

1. **P2 · the threshold's `source` text did not match the formula, and 8/70 was undisclosed** ·
   `arabic_pdf_check/thresholds.json:28-30` cited the old 0.733/0.299 pair and omitted the 8-file
   population. Consequence: a user reading `manifest` could not reconcile 0.67 with its derivation; a
   real-broken file above the floor was invisible. Move: state the actual clean minimum, its governing
   case, and the unjudged count; name البايثون. Evidence: the source now says
   `clean minimum 0.8684 over 4 real documents of 8 judged clean files (governing doc:report)`, 62 unjudged, and the `٣`
   file above the floor; `observed.clean_min_lexical_case` is in `pr2/thresholds.json`;
   `test_thresholds` re-derives 0.67. Tag: مُثبت. **Fixed** (`c2f1346` + `checker_measure --write`).

2. **P2 · the package licence asserted a version the notice did not** · `pyproject.toml:13` said
   `MIT AND CC-BY-SA-4.0` while `LICENSE-ar_words.txt:10` said only CC-BY-SA. Consequence: the wheel's
   legal metadata could overclaim. Move: align them and state the historical limit. Evidence: the notice
   now names **CC-BY-SA-4.0**, cites `https://dumps.wikimedia.org/legal.html` (retrieved 2026-11-24),
   gives attribution, and records that the 2022 dump's historical version is not independently verified;
   `test_packaging` `license-expression` and `notice-names-both-licences` PASS. Tag: مُثبت (contradiction
   closed); the historical 2022 version remains **مجهول** (see Not proven). **Fixed** (`c2f1346`).

3. **P3 · PR-1's measurement manifest was the only committed threshold file with no guard** ·
   `docs/checker-v0/measurements/thresholds.json:1-4` still said 0.50 and was not read by the test. Move:
   mark it. Evidence: the file has `superseded_by`; `test_thresholds` scans every unmarked
   `measurements/**/thresholds.json` and requires the shipped values; it passes. Tag: مُثبت.
   **Fixed** (`c2f1346`).

4. **P3 · cache and network edges** · `conformance/checks/lexical.py:61` had `lru_cache(maxsize=None)`
   behind a public path; `scripts/build_wiki_lexicon.py:107-109` let `URLError` escape. Move: bound the
   cache; one-line refusal. Evidence: `maxsize=2`; `OSError` returns 2; `--verify-source` is a CI step
   (`build-pdf.yml:228`). Tag: مُثبت. **Fixed** (`c2f1346`).

5. **P3 · the negative fixture's declared run count was 40 but it built 36** ·
   `scripts/checker_fixtures.py:75-77`. Move: make the declaration true. Evidence: `_swap_text` uses
   `range(0, len(SWAP_WORDS), 5)` and says 36; `04-review` corrected; `test_blind` still gets a high file.
   Tag: مُثبت. **Fixed** (`c2f1346`).

## Spec

6. **P2 · the evidence's `head` predated the code it measured** ·
   `docs/checker-v0/measurements/pr2/lexicon-compare.json:23` said `9ece554`; at that commit neither the
   wiki list nor the comparison existed. Move: record head/dirty/script sha and re-run. Evidence: final
   artifact `head: e99c80b`, `dirty: false`, `script_sha256: 7b4e947d…4c88`; `calibration.json`
   regenerated from it. Tag: مُثبت. **Fixed** (`e99c80b`, artifact `11c0fad`).

7. **P2 · the “current” arm was judged at the candidate's 0.67** · `scripts/lexicon_compare.py:290` read
   the live manifest after `--write`. Consequence: “current 0/16” was a counterfactual, not PR-1's 0.50
   arm. Move: freeze the PR-1 threshold for the current side and record both. Evidence: final artifact
   `thresholds: {baseline: 0.5, candidate: 0.67, shipped: 0.67}`, `match: true`; ZATCA current **0/16 at
   0.50** and wiki **0/16 at 0.67**; swap 1/1 both. Tag: مُثبت. **Fixed** (`c2f1346`).

8. **P2 · “the literal population is 3” and “0.4043 is the decision metric” were inaccurate** ·
   `scripts/lexicon_compare.py:120-121` uses `cal + known` (four), and the 0.4043 is the
   lexical-only subset. Consequence: a reader could mistake the secondary for the assignment's metric.
   Move: name four files and compute the secondary. Evidence: `decision.population_all = "3 calibration
   + known-bad"`, `population_lexical` names the two lexical files; `separation_lexical_only` is a
   computed field; `08:136-142` labels it secondary; the literal `-0.072` is `accept`. Tag: مُثبت.
   **Fixed** (`c2f1346` + `08`).

9. **P3 · `foreign.json` had no provenance and the evidence contradicted itself** ·
   `docs/checker-v0/measurements/pr2/foreign.json:1-5` lacked
   threshold/command/time and §7 said it was not re-run. Move: add provenance; re-run at 0.67. Evidence:
   `foreign.json` now has `generated_at 2026-11-24T18:34:44Z`, `thresholds_sha256 ba982d1c…`, and the
   command; `files 2`, `high 0`; the stale “not re-run” line is removed. Tag: مُثبت. **Fixed**
   (`c2f1346`).

10. **P3 · the evidence's §6 was uncommitted and claimed 32 of 43 files** ·
    `docs/checker-v0/08-pr2-evidence-2026-11-24.md:146-152` had only the
    output block; the working tree's command was outside the reviewed commit. Move: run all and commit.
    Evidence: `/tmp/pr2-finaltests.log` — 11 checker + 18 conformance + 14 scripts = **43**, all `exit=0`;
    `test_furniture_band.py report.pdf` 3/3; `08:150-165` carries the command and count. Tag: مُثبت.
    **Fixed** (`11c0fad`).

## Structure

11. **P1 · private owner rows were committed** · `scripts/lexicon_compare.py:312` (before the fix)
    emitted every owner file's per-reader counts under `owner-NN`. Consequence: a committed artifact
    contradicted `checker_measure.py:15-16`'s aggregate-only contract and exposed document sizes. Move:
    aggregate the 51, keep only the three calibration names. Evidence: `lexicon-compare.json` now has
    `counts.owner = 51`, `owner.*.files = 51`, 97 records (70+5+2+3+1+16), no `owner-NN`;
    `calibration.json` has the three names; `08:53` states it; `test_lexicon_compare` pins the labels.
    Tag: مُثبت. **Fixed** (`c2f1346`).

12. **P2 · the shipped report could not name the lexicon that judged it** · `arabic_pdf_check/blind.py:250`
    called `lexical.validity(text)` against a process global, while `tool` recorded only
    `thresholds_sha256`. Consequence: two reports with the same threshold hash could disagree and
    neither would say why; the global's restore was to a constant. Move: thread the path. Evidence:
    `blind.check(..., lexicon_path=)` (`blind.py:213`), `tool.lexicon {file, sha256}`
    (`blind.py:436`), schema required (`report.v1.json:56-95`), `set_default` and `DEFAULT` deleted
    (`lexical.py:61-68`), `test_blind` `tool:lexicon-named`/`tool:explicit-lexicon-recorded` PASS.
    Tag: مُثبت. **Fixed** (`c2f1346`).

13. **P2 · the comparison duplicated the clean-set harness and the threshold formula** ·
    `scripts/lexicon_compare.py:59-75,288-289` had its own `build_clean` and `round(clean_min-0.20,2)`. Consequence:
    two sources could drift. Move: reuse and extract. Evidence: `clean_files` is imported from
    `checker_measure`; `derive_lexical_threshold` is one function used by `derive` and the comparison;
    `decision.threshold_matches_manifest: true`. Tag: مُثبت. **Fixed** (`c2f1346`).

14. **P3 · the tests did not pin the seam or the evidence head** · `scripts/test_lexicon_compare.py:32-54`
    drove only `summarize`; `test_lexical` proved the old `set_default`, not `tool.lexicon`. Move: add
    controls. Evidence: `test_blind` `tool:lexicon-named`/`tool:explicit-lexicon-recorded`;
    `test_lexicon_compare` `separation-lexical-only`/`known-bad-label`; `test_lexical`
    `shipped-is-default`/`baseline-not-default`; `test_thresholds` `unmarked-measurement-*`; final
    **43/43** test files, all `exit=0`. Tag: مُثبت. **Fixed** (`c2f1346` + `11c0fad`).

## Declined to judge / declared limits

- **`٣ - درس - البايثون` is not caught by the lexical signal** (0.6638–0.7113 > 0.67). The owner
  adjudicated it broken; PR-2 does not lower the threshold to catch it.
- **The literal separation is negative** (−0.072) because `نظام الشركات` (numerals, lexically valid) is
  the highest “real broken” at 0.9053; the candidate still improves on the current (−0.106), which is
  the assignment's rule. The lexical-only number (0.4043) is secondary.
- **All 16 ZATCA files remain high for other signals**; `lexical-validity` contributes 0/16.
- **The historical 2022 dump's licence version** is not independently verified; the official page
  currently states 4.0, and the notice says so with the limit.
- **8 of 70 clean files are judged** by the 20-run floor; the governing 0.8684 case is `doc:report` (four documents, 8 judged files).
  This is declared in `thresholds.json` and `08`; the 62 unjudged cases contribute no lexical evidence.

## Not proven

- **CI on GitHub** has not run on this branch; the 43 tests and RATCHET/SELFTEST are local. Ends with a
  green `Build PDF` on `feat/lexicon-wiki50k` (macOS + Linux).
- **The 2022 Wikipedia dump's historical licence version** — the official page current is 4.0; the dump's
  own `COPYING` was not read. Ends with the dump's licence file or legal review.
- **The owner's verdict on `٣ - درس - البايثون`** — its defect class is owner-adjudicated, not measured.
  Ends with the owner's classification; the threshold is not changed.
- **The negative literal separation is a policy choice** — the assignment's rule accepts the candidate;
  whether a negative absolute separation is acceptable is a product decision. Ends with the owner's read
  of `08:136-142`.

## Next steps

1. Push `feat/lexicon-wiki50k`; run `Build PDF`; read macOS + Linux.
2. Owner reviews `08-pr2-evidence-2026-11-24.md` and decides the four declared limits.
3. Merge only through the owner's CI; PR-3 remains after تكليف F.
