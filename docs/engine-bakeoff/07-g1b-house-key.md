# G#1b/1 — the house key enters the certificate gate

The G#1 round-2 report carried one P3: `private-keys` — the rule that no `/PL*` key may ship — lived only in
`scripts/verify_pdf.py`, the gate for the four documents this repository builds. The certificate gate
(`conformance/checks/structure.py`), which issues the verdict the product is sold with, never ran it. This
closes that, at the class level: one reader, one prefix, both gates, and a mutation for every place a key can
live.

## Why the rule exists — from the standard, not from habit

- **ISO 32000-1:2008, Annex E (normative), "PDF Name Registry", E.2** (pp. 673–674): a conforming writer may
  add keys to any dictionary except the trailer, but "Developers shall only add private data that conforms to
  the registry rules." Second-class names carry a registered 4-byte developer prefix followed by a LOW LINE;
  third-class names all begin with one reserved prefix.
- Our `/PLMarkCids` is neither: no registered 4-byte prefix + LOW LINE, and not the reserved third-class
  prefix. It is how one stage of this pipeline talks to the next, consumed before the file leaves.
- **PDF Association TechNote 0010 (2017), A009 "Validation of private data"**: private data is legal in
  PDF/A and is subject to clause 6.1 syntax; following Annex E is *"outside of the scope of ISO 19005"*
  because it does not affect visual appearance. **A PDF/A validator will not catch a leaked house key.**
  veraPDF passing the file says nothing about it — so the file's own gate must.

Sources: `opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/PDF32000_2008.pdf` (Annex E) and
`pdfa.org/wp-content/uploads/2017/07/TechNote0010.pdf` (A009).

## What changed

| # | file | change | witness |
|---|---|---|---|
| 1 | `pdfops.py` | `HOUSE_KEY_PREFIX = "/PL"`, `MARK_CIDS_KEY`, and `private_keys(pdf)` — the one reader. It walks **every** place a key can live: indirect dictionaries (`pdf.objects`), stream dictionaries (pikepdf reports a stream as `Object`, and its keys are in `stream_dict`), direct dictionaries and arrays nested in them, and the trailer (not in `pdf.objects`). | `conformance/tests/test_private_keys.py` (6 controls, one per site + negatives) |
| 2 | `conformance/checks/structure.py` | check id `private-keys`, generic, inside the first `pikepdf.open` block — not `n/a`, not only after post-processing. A file whose objects cannot be read is a **fail**. | three mutations in the conformance selftest |
| 3 | `scripts/verify_pdf.py` | the inline loop is gone; the document gate calls the same `private_keys` (imported from `pdfops`, where the other shared readers already live). | the four documents' gates |
| 4 | `scripts/g1_audit.py` | same reader, directory scope. Its docstring now says plainly: the house-key count is the gate's rule seen from a directory; the *unjudgeable fonts* count is a **diagnostic**, never failed on. | `files 4 · Type0 fonts 40 · house keys 0 · unjudgeable fonts 0` |
| 5 | `scripts/fix_text_layer.py`, `postprocess.py` | the writer and the consumer build/read the key from `pdfops.MARK_CIDS_KEY`; the prefix is declared once, so a rename cannot leave the gates looking for a name nobody writes. | the guide/report/print/najd builds |
| 6 | `conformance/selftest.py` | three mutations, one per clause of "any object": `private-key-leak` (Type0 font dictionary — the incident), `private-key-on-stream`, `private-key-direct` (a direct dictionary nested in the catalog). | 13/13 CAUGHT |
| 7 | `conformance/tests/test_certificate.py` | control 8: `--recheck` refuses a certificate that predates a check the gate now runs. | `recheck:missing-check-refused` |

`g1_audit.py` stays out of CI. Once both gates read the same function, a third step over the same files runs
the rule again; when CI goes red, two failing steps make it harder to see which gate failed. The P3's "not in
CI" described why the gap stayed hidden, not a second requirement — the certificate gate is the fix.

## The measurement that justified it

**Before the change** (on a built, clean case): a `/PLMarkCids` key planted on a delivered font dictionary
changed nothing — `structure.evaluate` returned 14 checks and the same fails with and without the key
(`['invisible-format']` both times). The certificate gate was blind.

**After the change**, one site at a time, `run_verapdf=False`:

| site | `private-keys` | reason | new failing checks |
|---|---|---|---|
| clean file | pass | no `/PL*` key anywhere in the file | — |
| Type0 font dictionary | fail | `/PLFont` | `private-keys` only |
| content **stream dictionary** | fail | `/PLStream` | `private-keys` only |
| **direct** dictionary in the catalog | fail | `/PLDirect` | `private-keys` only |
| dictionary inside an **array** | fail | `/PLArray` | `private-keys` only |
| **trailer** | fail | `/PLTrailer` | `private-keys` only |

End to end through `conformance certify` on the same case: the clean file's certificate is `PASS` and lists
`private-keys: pass`; the poisoned file's verdict is `FAIL — failed checks: private-keys`, and the check's
reason is `/PLFont`.

## Counts (no threshold, floor or calibrated number touched)

- `structure.evaluate`: 14 → **15** checks (selftest baselines print 15 pass).
- Conformance selftest: 10 → **13** mutations, 0 could not be planted, **0 missed**.
- A certificate for one case now carries **17** checks (15 structural + 2 veraPDF).
- `ratchet.json` stores per-reader **floors only** — measured: its top-level keys are the five reader names,
  and each has `floors`; no check list is stored. Nothing was re-measured or accepted.
- `scripts/verify_pdf.py`: still **39** checks · 9 generic · 30 calibrated; the inventory table is unchanged.

## The four documents, on this branch

| document | gate | selftest | veraPDF | claim | inventory / constructs |
|---|---|---|---|---|---|
| guide | ALL GATES PASSED (39) | 63/63 | HELD (3 flavours) | HELD | PASSED · PASSED |
| report | ALL GATES PASSED (39) | 63/63 | HELD (3 flavours) | HELD (ua1 0) | PASSED · PASSED |
| report-print | ALL GATES PASSED (39) | 55/55 (8 declared n/a) | HELD (3 flavours) | HELD | PASSED · PASSED |
| najd | ALL GATES PASSED (39) | 58/58 (5 declared n/a) | HELD (3b + ua1) | HELD (ua1 0) | PASSED · PASSED |

Guards: `test_check_kinds` (39 · 9 · 30), `test_ci_wiring` (19 test files · 19 wired · 0 exempt),
`test_bidi_space`, `test_pdf_model`, `test_verapdf_json_guard`, `test_verapdf_test_granularity`,
`test_digit_value`, `test_baseline_guard` — all PASSED.

The corpus run, with poppler at the CI pin (`CONFORMANCE_PDFTOTEXT=…/26.11.0/bin/pdftotext`):
**60 cases · 17 checks each · `private-keys` 60/60 pass · clean 28 · RATCHET HELD** — no reader, case or
metric below its floor. (With the machine's homebrew poppler 26.07.0 the ratchet refuses by name — no floors
for that version; that is the pin doing its job, not this change.)

## ما لم يُثبت

لا شيء في نطاق هذا الملف: كل ادّعاء أعلاه يحمل الأمر الذي أنتجه. ما لا يقرؤه الحارس (ملف مشفّر لا يفتحه
pikepdf) يُفشل الفحص صراحةً — قرار لا حدّ مُعلن.
