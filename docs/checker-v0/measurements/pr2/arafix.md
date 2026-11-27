# arafix — the orientation detector, measured

- version: 1.2.0 (MIT)
- threshold: 0.3 (arafix DEFAULT_THRESHOLDS)
- clean set: maximum orientation share 0.1667
- planted: {"planted-mupdf-logical": 0.833, "planted-chrome-raw": 0.167, "planted-presentation-forms": 0.833, "planted-no-tounicode": 0.167, "planted-letter-swap": 0.833, "planted-lam-alef": 0.167}
- mechanism: three voted signals (final-only letters, joining forms, definite article) — NOT the
  assignment's «share of words a lexicon reads forward vs reversed»; the difference is declared in
  docs/checker-v0/00-sources.md §3 and the measurements above are what the adoption rests on.
