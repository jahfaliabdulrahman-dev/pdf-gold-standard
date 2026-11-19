# G#1b/1 — the house key enters the certificate gate

The G#1 round-2 report carried one P3: `private-keys` — the rule that no `/PL*` key may ship — lived in
`scripts/verify_pdf.py` (the gate for the four documents this repository builds) and in `scripts/g1_audit.py`
(a directory audit). Neither is the certificate gate: `conformance/checks/structure.py`, which issues the
verdict the product is sold with, never ran the rule. This closes that, at the class level: one reader, one
prefix, both gates, and a mutation for every place the object graph can carry a key.

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
| 1 | `pdfops.py` | `HOUSE_KEY_PREFIX = "/PL"`, `MARK_CIDS_KEY`, and `private_keys(pdf)` — the one reader. It walks the object graph: indirect objects (`pdf.objects`), stream dictionaries (a stream is not a `Dictionary`; its keys are in `stream_dict`), direct dictionaries/arrays nested in them, and the trailer (not in `pdf.objects`). Content-stream inline dictionaries are stream syntax, not object keys, and are declared out of scope. | `conformance/tests/test_private_keys.py` — one positive per site, object streams, the prefix negative, and a fail-closed control |
| 2 | `conformance/checks/structure.py` | check id `private-keys`, generic, inside the first `pikepdf.open` block — not `n/a`, not only after post-processing; the reason names the keys. A file whose objects cannot be read inside the check is a **fail**. The check also scans a declared A-3b second file when a bake-off honours it. | five mutations in the conformance selftest + `test_a3b_claim` |
| 3 | `scripts/verify_pdf.py` | the inline loop is gone; the document gate calls the same `private_keys` (imported from `pdfops`, where the other shared readers already live). | the four documents' gates |
| 4 | `scripts/g1_audit.py` | same reader, directory scope. Its docstring says plainly: the house-key count is the gate's rule seen from a directory; the *unjudgeable fonts* count is a **diagnostic**, never failed on. | `files 4 · Type0 fonts 40 · house keys 0 · unjudgeable fonts 0` |
| 5 | `scripts/fix_text_layer.py`, `postprocess.py` | the writer and the consumer build/read the key from `pdfops.MARK_CIDS_KEY`; the prefix is declared once, so a rename cannot leave the gates looking for a name nobody writes. The writer imports it at call time, so importing the module no longer repoints `sys.path`. | the guide/report/print/najd builds |
| 6 | `conformance/selftest.py` | five mutations, one per container: `private-key-leak` (Type0 font dictionary — the incident), `private-key-on-stream`, `private-key-direct` (a direct dictionary, reopened to prove it stayed direct), `private-key-in-array`, `private-key-in-trailer`. | 15/15 CAUGHT |
| 7 | `conformance/cli.py`, `conformance/certificate.py`, `conformance/tests/test_certificate.py` | `validate --recheck` was parsed and **ignored** by the command (pre-existing; this change makes the flag the enforcement point for a stale certificate). The command now passes it; `recheck` compares stored and live check ids in **both** directions. Controls 8–10: a certificate missing a live check, the CLI path itself, and a stored check the gate no longer runs. | `cli:recheck-wired`, `recheck:missing-check-refused`, `recheck:removed-check-refused` |

`g1_audit.py` stays out of CI. Once both gates read the same function, a third step over the same files runs
the rule again; when CI goes red, two failing steps make it harder to see which gate failed. The P3's "not in
CI" described why the gap stayed hidden, not a second requirement — the certificate gate is the fix.

## The measurement

**At 7c4410e the certificate gate had no row for the rule** — `git show 7c4410e:conformance/checks/structure.py
| grep -c private-keys` → `0`. A file could carry a house key and the gate could not fail it.

**After the change**, one site at a time on the `head-h1-h3` corpus case, `run_verapdf=False`:

| site | `private-keys` | reason | new failing checks |
|---|---|---|---|
| clean file | pass | no `/PL*` key in the object graph | — |
| Type0 font dictionary | fail | `/PLFont` | `private-keys` only |
| content **stream dictionary** | fail | `/PLStream` | `private-keys` only |
| **direct** dictionary in the catalog | fail | `/PLDirect` | `private-keys` only |
| dictionary inside an **array** | fail | `/PLArray` | `private-keys` only |
| **trailer** | fail | `/PLTrailer` | `private-keys` only |

End to end through `conformance certify` on the same clean case (`head-h1-h3`): the certificate is `PASS` and
lists `private-keys: pass`; the poisoned copy's verdict is `FAIL — failed checks: private-keys`, and the
check's reason is `/PLFont`.

## Counts (no threshold, floor or calibrated number touched)

- `structure.evaluate`: 14 → **16** checks (`private-keys` + the `tagged` pass row it exposed: the check
  existed but emitted no row on success, so the certificate could not show it ran).
- Conformance selftest: 10 → **15** mutations, 0 could not be planted, **0 missed**.
- A certificate for one case now carries **18** checks (16 structural + 2 veraPDF).
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
`test_digit_value`, `test_baseline_guard` — all PASSED, plus `test_private_keys` (7 controls) and
`test_a3b_claim` (8 controls).

The corpus run, with poppler at the CI pin, is committed beside this file:
`docs/conformance/results/2026-11-19-g1b-chrome.md` — **60 cases · 18 checks each · `private-keys` 60/60
pass · clean 28 · RATCHET HELD**. (With the machine's homebrew poppler 26.07.0 the ratchet refuses by name —
no floors for that version; that is the pin doing its job, not this change.)

## Commands (every number above)

```bash
export CHROME_PATH="$HOME/.cache/cft/chrome/mac_arm-157.0.8103.78/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"

.venv/bin/python -m conformance selftest                       # 15 mutations, 0 missed
.venv/bin/python conformance/tests/test_private_keys.py        # reader: 7 controls
.venv/bin/python conformance/tests/test_certificate.py         # 10 controls, incl. the CLI --recheck
.venv/bin/python conformance/tests/test_a3b_claim.py           # 8 controls, incl. the second file's key

PDF_SPEC=nav_spec          .venv/bin/python build.py guide-v2.html guide-v2-ar.pdf
PDF_SPEC=nav_spec          .venv/bin/python scripts/verify_pdf.py guide-v2-ar.pdf      # + gate_selftest,
                           # verapdf_gate 3b ua1 4f, claim_probe --check, artifact_inventory, constructs
PDF_SPEC=report_spec       .venv/bin/python build.py report-v1.html report.pdf
PDF_SPEC=report_print_spec .venv/bin/python build.py report-v1.html report-print.pdf
PDF_SPEC=najd_spec         .venv/bin/python build.py najd.html najd.pdf
# each document: verify_pdf · gate_selftest · verapdf_gate · claim_probe --check · inventory · constructs

mkdir -p /tmp/g1b-docs && cp guide-v2-ar.pdf report.pdf report-print.pdf najd.pdf /tmp/g1b-docs/
.venv/bin/python scripts/g1_audit.py /tmp/g1b-docs             # files 4 · fonts 40 · keys 0 · blind 0

export CONFORMANCE_PDFTOTEXT=~/.cache/poppler-pin/26.11.0/bin/pdftotext
.venv/bin/python -m conformance run --engine chrome --out /tmp/conf-g1b-final --ratchet
```

## ما لم يُثبت

لا شيء في نطاق هذا الملف: كل ادّعاء أعلاه يحمل الأمر الذي أنتجه. حدّان مُعلنان لا ادّعاءان: مفتاح مكتوب
داخل تدفّق محتوى (`BDC`/صورة مضمّنة) ليس مفتاح كائن ولا يُقرأ — منصوص عليه في دالّة القارئ؛ وملف لا يفتحه
pikepdf لا يُصدر شهادة أصلًا (الفحص لا يُنفَّذ، لا يمرّ).
