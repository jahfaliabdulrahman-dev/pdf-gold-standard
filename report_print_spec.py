"""Print variant of «الحرف المقلوب» — the same document, without the navigation chrome.

One source (`report-v1.html`), two specs: the screen copy keeps its four-button strip because the buttons
are real links (next / previous / contents / cover); the print copy must not carry four dead targets and
four ink blobs on every page. Nothing else differs, so the words are identical and only the strip band,
the link count and the calibration grid change.

Why a second spec rather than a CSS media query: a PDF page has ONE appearance. `@media print` decides
what Chrome writes, but the result is a single fixed page — there is no "screen view" left inside it.
"""
import report_spec as _base
from report_spec import *                      # noqa: F401,F403  (inherit everything, override below)

# This document's MuPDF word-order floor: calibrated by scripts/calibrate.py --write as
# max(LINE_ORDER_FLOOR, measured - LINE_ORDER_DRIFT); the gate refuses any value below the floor.
# >>> CALIBRATED LINE_ORDER_MIN
LINE_ORDER_MIN = 0.750
# <<< CALIBRATED LINE_ORDER_MIN

# The page geometry is the screen copy's; declared here rather than inherited silently (the rest of the
# star import is B7's to remove).
FURNITURE_BANDS = _base.FURNITURE_BANDS

DOC_TITLE = _base.DOC_TITLE + " · نسخة الطباعة"
XMP_TITLE = f"{DOC_TITLE} · الإصدار {_base.GUIDE_VERSION_AR}"
DOC_SUBJECT = _base.DOC_SUBJECT + " — نسخة مهيّأة للطباعة بلا أزرار تنقّل"

# The print copy carries no navigation strip at all (the markup is removed, NAV_PAGES = ()), so the
# eight mutations that describe a strip have nothing to act on and return NA on it — measured, not
# assumed: each is named here with its reason, and gate_selftest fails if one applies after all.
# 53 − 8 = 45.
GATE_MUTATIONS = 45
GATE_NA = {
    "swap_next_prev": "no strip links: NAV_PAGES = ()",
    "self_link": "no strip links: NAV_PAGES = ()",
    "whiteout_strip": "no strip to white out on any page",
    "swap_icons": "no icons are drawn on any page",
    "foreign_icon": "no icon slot is drawn on any page",
    "moment_matched_icon": "no icon slot is drawn on any page",
    "icon_input_lost": "no strip icons exist to lose",
    "rename_nav_class": "the render check has no subject on a print copy: no icon is drawn, so a class "
                        "rename is a provenance event, not a render one",
}

# ---- the difference: no strip, no strip links, and the page must say so --------------------------------
NAV_VISIBLE = False
NAV_PAGES = ()
LINKS_CLAIM = "وبلا أزرار تنقّل"
PRINTS_LINK_COUNT = False
EXPECTED = {**_base.EXPECTED, "nav_pages": 0, "source_strips": 0, "source_icons": 0}

# >>> CALIBRATED PAGE_INK
PAGE_INK = {
    0: (0.0797, (0.0, 0.2167, 0.0975, 0.0, 0.0007, 0.1771, 0.3124, 0.0116, 0.0108, 0.1594, 0.1925, 0.0121, 0.0046, 0.0203, 0.0541, 0.004)),
    1: (0.0064, (0.0, 0.01, 0.0132, 0.0, 0.0024, 0.0356, 0.0325, 0.0024, 0.0, 0.0, 0.0, 0.0, 0.005, 0.0, 0.0, 0.0004)),
    2: (0.0119, (0.0006, 0.0274, 0.0338, 0.0062, 0.0033, 0.0, 0.0301, 0.0246, 0.002, 0.0087, 0.0258, 0.0123, 0.0, 0.0077, 0.0073, 0.0)),
    3: (0.1349, (0.0, 0.0, 0.0, 0.0, 0.0, 0.5127, 0.6325, 0.1286, 0.0004, 0.5925, 0.2849, 0.0018, 0.0, 0.0, 0.0, 0.0)),
    4: (0.0287, (0.0187, 0.03, 0.0414, 0.0408, 0.018, 0.0453, 0.0516, 0.0336, 0.0225, 0.0426, 0.0675, 0.0397, 0.0025, 0.0, 0.0, 0.0053)),
    5: (0.0258, (0.0051, 0.034, 0.0601, 0.0399, 0.0061, 0.026, 0.01, 0.032, 0.022, 0.0618, 0.0394, 0.0376, 0.0043, 0.0055, 0.0175, 0.011)),
    6: (0.1187, (0.0, 0.0, 0.0, 0.0, 0.0011, 0.1419, 0.3711, 0.1392, 0.0092, 0.1756, 0.2206, 0.0043, 0.0011, 0.4116, 0.4161, 0.0017)),
    7: (0.1989, (0.0323, 0.0675, 0.0872, 0.0547, 0.5272, 0.8693, 0.871, 0.5358, 0.0145, 0.0289, 0.0552, 0.0284, 0.0025, 0.0, 0.0, 0.0005)),
    8: (0.0235, (0.009, 0.0204, 0.0658, 0.0371, 0.0138, 0.0335, 0.0471, 0.0193, 0.0167, 0.0426, 0.0454, 0.0225, 0.0025, 0.0, 0.0, 0.0004)),
    9: (0.0221, (0.0, 0.0165, 0.0335, 0.0148, 0.0167, 0.0558, 0.069, 0.0288, 0.0098, 0.0324, 0.032, 0.0246, 0.0025, 0.0, 0.0088, 0.0086)),
    10: (0.0272, (0.0244, 0.0509, 0.0734, 0.0439, 0.0209, 0.052, 0.0528, 0.0429, 0.0087, 0.0186, 0.029, 0.0146, 0.0025, 0.0, 0.0, 0.001)),
    11: (0.0214, (0.0072, 0.0305, 0.0657, 0.0382, 0.0086, 0.0533, 0.0633, 0.0236, 0.0067, 0.0125, 0.0147, 0.0142, 0.0025, 0.0, 0.0, 0.0008)),
    12: (0.0222, (0.006, 0.0246, 0.0506, 0.0392, 0.0186, 0.0473, 0.0582, 0.0273, 0.0067, 0.0143, 0.0395, 0.0194, 0.0025, 0.0, 0.0, 0.0008)),
    13: (0.0152, (0.0103, 0.0181, 0.0306, 0.0361, 0.0068, 0.0048, 0.0259, 0.0357, 0.0081, 0.0146, 0.0262, 0.0221, 0.0025, 0.0, 0.0, 0.0009)),
    14: (0.0159, (0.0231, 0.0452, 0.0481, 0.0488, 0.0, 0.0, 0.0, 0.0109, 0.0057, 0.0123, 0.0142, 0.0092, 0.0032, 0.0121, 0.013, 0.0083)),
    15: (0.0191, (0.0, 0.0121, 0.0284, 0.043, 0.0, 0.0023, 0.0429, 0.1056, 0.0, 0.0, 0.0181, 0.0386, 0.0023, 0.0052, 0.0061, 0.0008)),
    16: (0.173, (0.0, 0.0, 0.0, 0.0, 0.0024, 0.0338, 0.0355, 0.0017, 0.0935, 0.5271, 0.5167, 0.103, 0.1202, 0.5878, 0.5939, 0.1485)),
}
# <<< CALIBRATED PAGE_INK

# The strip added icons, not words, and never touched the artwork or the footers: both are inherited and
# reMEASURED by the same calibrate run below only if they change. Only the ink grid moves.
# >>> CALIBRATED PAGE_WORDS
PAGE_WORDS = {0: 44, 1: 38, 2: 71, 3: 10, 4: 156, 5: 160, 6: 11, 7: 155, 8: 142, 9: 105, 10: 154, 11: 132, 12: 123, 13: 96, 14: 87, 15: 67, 16: 19}
# <<< CALIBRATED PAGE_WORDS

# >>> CALIBRATED IMAGE_PAGES
IMAGE_PAGES = {0: (1, 0.9995), 3: (1, 0.9995), 6: (1, 0.9995), 15: (4, 0.0185), 16: (1, 0.9995)}
# <<< CALIBRATED IMAGE_PAGES

# >>> CALIBRATED FOOTER
FOOTER = {1: 2, 4: 5, 5: 6, 7: 8, 8: 9, 9: 10, 10: 11, 11: 12, 12: 13, 13: 14, 14: 15, 15: 16}
# <<< CALIBRATED FOOTER

# >>> CALIBRATED EXPECTED_LINKS
EXPECTED_LINKS = 11
# <<< CALIBRATED EXPECTED_LINKS
