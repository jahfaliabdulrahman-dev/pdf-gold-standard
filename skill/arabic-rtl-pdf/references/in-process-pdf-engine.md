# In-process PDF engine — measured against Chrome (2026-10-19)

The question this file answers: **must a correct Arabic text layer cost a browser?** Measured
answer: no — an in-process Rust→WASM engine can both shape Arabic and keep the text layer that
Chrome corrupts. The trade-offs are named at the end.

## Candidate

| Fact | Value |
| :-- | :-- |
| Engine | Forme — Rust compiled to WASM; rustybuzz for OpenType shaping, `unicode-bidi` for RTL |
| Python API | `pip install "formepdf[local]"` (pulls `wasmtime`); `render_html(html, fonts=[...], lang="ar") -> bytes` |
| JS API | `@formepdf/core` (`renderDocument`), `@formepdf/html` (`renderHtml`) — same engine, byte-identical output claimed |
| License | MIT (npm registry + repo LICENSE) |
| Maturity at audit | 0.x, first published ~8 months earlier, one maintainer, ~226 stars |
| Native mobile | same engine reachable from a native module (Reactive Resume ships an Expo module over it) |

## Measurement (macOS, one A4 page, one Arabic font, same HTML for both)

| | Forme (`formepdf` + wasmtime) | Chrome headless `--print-to-pdf` |
| :-- | :-- | :-- |
| wall time | 0.98 s (Python call only) | 0.84 s (process start to exit) |
| peak RSS | 256 MB | 249 MB |
| output size | 22.8 KB | 46.1 KB |
| embedded faces | SFArabic, SFArabic-Bold, **NotoSans (fallback)** | GeezaPro, GeezaPro-Bold, **TimesNewRoman ×2 (fallback)** |
| fonts subsetted | **no** (`sub: no`) | yes (`sub: yes`) |
| `pdftotext` = source text | **yes**, all four probes | **no** |

The text-layer probes, run on both files after stripping bidi controls:

| Probe | Forme | Chrome |
| :-- | :-- | :-- |
| «المملكة» present verbatim | PASS | **fail** — extracted as «اململكة» |
| lam-alef intact: «المؤهلات» | PASS | fail |
| tashkeel: «مَرْحَبًا» | PASS | fail |
| Latin control line | PASS | PASS |

The Chrome result is the same defect this skill already documents from another angle (pitfall 9:
never locate Arabic content by searching for a string). The measured shape is a letter
TRANSPOSITION inside the word, not the visual reversal seen with `-layout`.

**Correction to folklore, recorded because a wrong number here would license a rewrite:**
"Chrome needs 2 GB for a one-page PDF" was NOT reproduced — both engines sat at ~250 MB on a
single page. The memory advantage should be argued for long documents or N concurrent renders,
which this measurement does not cover.

## Traps the probe exposed

1. **The extraction carries bidi control characters.** Forme wraps runs in `U+202B … U+202C` and
   injects `U+202A`/`U+202C` around embedded LTR runs like `( SGS` — so a byte-equal comparison
   against the source string fails while the document is correct. Strip
   `U+200E U+200F U+202A–U+202E U+2066–U+2069 U+061C` before any equality check, and NEVER
   "fix" the document because the diff failed.
2. **Fonts are NOT subsetted by the Python API.** Three full faces went into a one-page file.
   Reactive Resume subsets with harfbuzz first (`hb-subset --layout-features=*`, so shaping and
   ligature features survive) and hands the engine stripped bytes. Do the same, or accept the size.
3. **A fallback face appears unprompted** (`NotoSans` beside the declared family) — the same class
   as the Chrome pitfall already in this skill: assert the embedded family list contains ONLY the
   intended faces and find the character that pulled the fallback in.
4. **The runtime is a wasmtime dependency**, not the engine alone: pin it, and treat an engine
   upgrade as a re-run of this whole probe (output bytes are the contract).

## Decision rule

- **Text layer is part of the contract** (ATS, searchable CV/report, TOC located by string,
  anything a parser will read): prefer the in-process engine, and gate the delivered file with
  the probes above.
- **Visual fidelity is the whole contract** and the text layer is secondary (deck, poster,
  designed report): keep Chrome — its CSS coverage is broader and its output is already gated by
  the delivery gate in this skill.
- **Both at once**: render with Forme, and keep Chrome for comparison renders only. Do not ship
  one document from two engines — the pagination differs and the gate measures one of them.

## Reproduction

```bash
python3 -m venv fv && ./fv/bin/pip install "formepdf[local]"
# HTML: lang="ar" dir="rtl", one h1 + three paragraphs (shaping, lam-alef, tashkeel) + a Latin control
./fv/bin/python - <<'PY'
import pathlib, subprocess, time
from formepdf import render_html
html = pathlib.Path("probe.html").read_text()
fonts = [{"family": "SFArabic", "data": pathlib.Path("/System/Library/Fonts/SFArabic.ttf").read_bytes()}]
t0 = time.perf_counter(); pdf = render_html(html, fonts=fonts, lang="ar"); print(time.perf_counter() - t0)
pathlib.Path("forme_ar.pdf").write_bytes(pdf)
PY
pdftotext forme_ar.pdf - | head    # then compare against the source strings, stripped of bidi controls
pdffonts forme_ar.pdf              # embed=yes, sub=? · only the intended faces
```

The battery that must fail before you trust the comparison: run the same compare against a
Chrome print of the same HTML. If Chrome also "passes", the comparison is broken (likely the bidi
strip is missing), not the engine.

## Full-guide trial (2026-11-13) — `formepdf` 0.31.0 on the real 12-page guide

Same final HTML that Chrome prints (`build.py` → `/tmp/gold-guide-final.html`), full IBM Plex Sans Arabic TTFs
(Light–Bold, from `@ibm/plex-sans-arabic`) passed via `fonts=[{family, data, weight}]`, `lang="ar"`, `tagged=True`.

| Criterion | Chrome (v2.1) | formepdf 0.31.0 |
| :-- | :-- | :-- |
| Arabic words (≥4 letters) verbatim in `pdftotext` (bidi controls stripped) | 273/348 (78%) | 338/348 (97%) — with the font forced |
| «الأزرار» «جنائي» «الأتمتة» «الآلية» | all fail | all pass |
| Body text font | correct | **`?????` until forced**: `font-family: var(--f-sans)` is not resolved (CSS custom properties unsupported) |
| Colours / backgrounds / purple headings (all `var(--c-*)`) | correct | **lost** |
| Nav buttons (inline SVG in an absolutely positioned strip) | present | **missing** (cause not isolated) |
| Weights | 5 | 2 (Regular, Bold) |
| Arabic line containing a Latin run (`Chrome`, `IBM Plex Sans Arabic`) | correct | **glyphs overlap** — engine defect |
| Pages / images | 12 / same | 12 / same |

Verdict: the text-layer advantage is real and large, but the engine cannot render this house design today. `var()`
can be pre-resolved; the mixed-direction overlap cannot be fixed from our side. Keep Chrome; re-run this trial on each
formepdf release (the overlap is the blocking check).

Viewer note from the same day: on the Chrome-built guide, **Preview's search found «الأزرار»** while PyMuPDF's
`search_for` returned 0 — search depends on the viewer's own reconstruction; **copy/paste was garbled in Preview**
(owner's test). Copy is the contract that fails.
