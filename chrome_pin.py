"""The one Chrome this pipeline builds with.

Skia writes the text layer that `fix_text_layer.py` patches and that every calibrated number here measures
(object splitting, spacing, ink). A build on another Chrome is not the same document, so the engine is pinned
to a downloadable build — Chrome for Testing — and named in one place: this file.

Measured on 157.0.8103.80 (the owner's system Chrome, which Chrome for Testing does not publish); the pin is
the nearest published patch, 157.0.8103.78, and the battery is re-run on it before the pin is trusted.
"""
CHROME_VERSION = "157.0.8103.78"
