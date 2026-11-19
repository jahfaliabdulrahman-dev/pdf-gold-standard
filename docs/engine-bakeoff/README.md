# Engine bakeoff — installation and adapters (E1, E2). **The bakeoff itself (E3) has not run.**

E3 does not start before the owner accepts Path C: a measurement on a gate that has not been reviewed is not
evidence (assignment §5.3). What is here is the preregistration (E0), the installation record (E1), the two
adapters (E2), and a **smoke** over five cases to prove the adapters build and to state what they produce. The
smoke numbers are not the bakeoff and are not compared to the decision rule.

## Installation record (E1), measured 2026-11-19

| engine | version | how | bytes (sha256) | licence |
|---|---|---|---|---|
| chrome+pp | CfT **157.0.8103.78** | already installed (`chrome_pin.py`, `CHROME_PATH`) | — | Chrome for Testing, Google's terms |
| chrome-raw | the same binary | `conformance run --engine chrome-raw` | — | same |
| typst | **0.15.1** (`9dfd3a08`), the latest stable at run time (published 2026-07-17) | `typst-aarch64-apple-darwin.tar.xz` from GitHub Releases, unpacked to `~/.local/bakeoff/` (outside the repository) | tarball `48f62ed034aa3a7978309579ac6ca00045e2ef0da73114e8af27cfd8e74dc05a` · binary `7c4a136b377f3689400afe37b4f0fe3528d50faaa55cbb1106ac8a128f86ba1a` | **Apache-2.0** (`LICENSE` inside the tarball) |
| weasyprint | **70.0** | `.venv-bakeoff` (Python 3.13.3) + `pip install weasyprint==70.0`; pango **1.58.02**, harfbuzz **15.1.0** (Homebrew), pydyf 0.13.0; needs `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` | wheel from PyPI (version-exact) | **BSD** (`License-Classifier: BSD`, `LICENSE` in the installed `dist-info`) |

Both candidates installed inside the one-hour limit the assignment sets, so neither is excluded.

Flags used are the ones in the installed `--help`, pasted here rather than remembered:

- `typst compile --help` → `--pdf-standard <PDF_STANDARD>` with values including `a-3b` and `ua-1`
  (*«One (or multiple comma-separated) PDF standards»*), `--font-path`, `--ignore-system-fonts`,
  `--creation-timestamp` (*«for reproducible builds»*). Used: `--pdf-standard a-3b,ua-1 --font-path
  <fonts/full> --ignore-system-fonts --creation-timestamp 1763510400`.
- `weasyprint --help` → `--pdf-variant {pdf/a-1b,…,pdf/ua-1,…}` (one value), `--pdf-tags`, `--pdf-identifier`.
  Used: `--pdf-variant pdf/ua-1 --pdf-tags` for one file and `--pdf-variant pdf/a-3b --pdf-tags` for the second.

**Result already visible in the flags:** Typst combines PDF/UA-1 and PDF/A-3b in one file (`a-3b,ua-1`);
WeasyPrint takes one variant per file, so the adapter produces `<id>.pdf` (UA-1, the file measured) and
`<id>.a3b.pdf`. That is a declared result of E2, not a workaround.

## Adapters (E2)

`conformance/adapters/typst.py` and `conformance/adapters/weasyprint.py`. The Typst adapter emits every case
string as a `text("…")` expression — a case may contain `#`, `[`, `]`, `*`, `_`, and Typst markup would
reinterpret them; inside `#table(..)`/`#enum(..)` the expression is `text(..)` without a second `#` (measured
error: *«you are already in code mode»*). The WeasyPrint adapter reuses the same HTML the chrome adapter prints,
so three of the four candidates share one markup.

Neither competitor gets any post-processing, and none of the pipeline's stages are modified.

## Smoke (E2 verification, **not** the bakeoff)

Five cases, `conformance run`-style measurement with PDFium, just to prove the adapters build:

| case | typst 0.15.1 exact / order | weasyprint 70.0 exact / order |
|---|---|---|
| `head-h1-h3` | 0 / 0.65 | 0 / 0.65 |
| `tbl-2col` | 0 / 0.82 | 0 / 0.82 |
| `shp-lam-alef-forms` | 0 / 0.28 | 0 / 0.28 |
| `voc-full` | 0 / 0.43 | not run |
| `lst-ordered` | 0 / 0.50 | not run |

**The finding the smoke already shows:** both competitors write the layer in **visual order with decomposed
lam-alef**, and PDFium reads them identically (`األول` for `الأول`, `يف` for `في`, `الم-ألف` for `لام-ألف`). The
two engines produce the *same* text layer defects — which is what path E exists to price: Chrome's layer needs
`fix_text_layer`, and so would theirs.

## Not measured yet (E3, blocked)

- H1–H5 per candidate, P, S1–S6, determinism, median build time, size, the XML attachment (H3), U+20C1.
- The owner's visual board (E4) — and therefore H2's human half.
- The full RTL/table/vocalisation sweep across the corpus.

No number in this file is a bakeoff result. The decision rule in `00-preregistration.md` has not been applied.
