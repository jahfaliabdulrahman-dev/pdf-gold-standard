"""arabic-pdf-check — tell a PDF's owner where Arabic copy-paste breaks, and in which reader.

A thin layer over `conformance/`: the readers, the metrics, the normalization, the ToUnicode scan and the
declared limits are imported, never re-implemented. Two modes:

  · `check FILE.pdf`            — blind: no source text. Named signals with a risk level and a confidence,
                                  per reader and for the file. No percentage, no PASS.
  · `verify FILE.pdf --truth T` — reference: the same `certificate/2` the corpus gate issues, with the
                                  truth text in place of a corpus case.

See `docs/checker-v0/` for the sources, the plan, the review rounds and the measurements.
"""
__version__ = "0.1.0"
