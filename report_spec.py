"""Spec for «الحرف المقلوب» — the proof report.

One document, one spec: `build.py` injects the interactive layer FROM these numbers, `scripts/verify_pdf.py`
checks the PDF AGAINST them, and `postprocess.py` writes the metadata declared here. A page added or removed
breaks the build until every number below is re-measured (`scripts/calibrate.py`), never hand-tuned.

Measurement provenance: every figure printed in the report is copied from ROADMAP.md, which records the build
and the reader it was measured on. This file carries no claim of its own.
"""

MM = 2.83465  # 1 mm in pt
PAGE_H_MM = 296.8

GUIDE_VERSION = "1.4"
# Metadata is part of the document, not of the pipeline (build.py reads these).
DOC_TITLE = "الحرف المقلوب — تقرير إثبات عن طبقة النص العربية في PDF"
DOC_AUTHOR = "م. عبدالرحمن جحفلي"
DOC_SUBJECT = "تشخيص وإصلاح وإثبات لطبقة النص العربية في PDF"
DOC_KEYWORDS = "PDF, Arabic, RTL, PDF/A-3b, طبقة النص, إثبات"
GUIDE_VERSION_AR = GUIDE_VERSION.translate(str.maketrans("0123456789.", "٠١٢٣٤٥٦٧٨٩٫"))

PAGES = 17
COVER, BASMALA, CONTENTS = 0, 1, 2
# Pages that set vocalised text in the macOS system face (webfont subsets misplace tashkeel in Chrome).
VOCALISED_PAGES = {1, 9}

TOC = [
    [1, "الغلاف", 1],
    [1, "البسملة", 2],
    [1, "جدول المحتويات", 3],
    [1, "القسم الأول — التشخيص", 4],
    [2, "لماذا يُقلب الحرف؟", 5],
    [2, "القياس: خمسة قرّاء", 6],
    [1, "القسم الثاني — الإصلاح والإثبات", 7],
    [2, "إصلاح ١ — شكل واحد = حرف واحد", 8],
    [3, "النسخ المخفية وعرض الشكل", 8],
    [2, "إصلاح ٢ — الأشكال المدموجة", 9],
    [3, "اثنان وعشرون شكلًا، مئة وتسعة وثلاثون موضعًا", 9],
    [2, "إصلاح ٣ — التشكيل", 10],
    [2, "إصلاح ٤ — ترتيب السطر واللاتينية", 11],
    [2, "البوابة: أربعة وثلاثون فحصًا", 12],
    [2, "المطابقة: PDF/A-3b", 13],
    [2, "ما لا يفعله هذا الملف", 14],
    [1, "النموذج والمراجع", 15],
    [2, "المراجع والأدوات", 16],
    [1, "الغلاف الخلفي", 17],
]

# Nav strip: 4 fixed buttons on every body page. Slot x (left edge, pt) -> role.
NAV_PAGES = range(3, 16)            # pages 4..16 (index 3..15)
NAV_Y0, NAV_Y1, NAV_W = 37, 62, 25
SLOTS = {"next": 58.0, "prev": 95.33, "contents": 132.67, "home": 170.0}


def nav_target(role: str, i: int) -> int:
    """Expected destination of the button `role` on page index i."""
    return {"home": COVER, "contents": CONTENTS, "prev": i - 1, "next": i + 1}[role]


# Contents-page rows, top to bottom -> destination page index.
TOC_ROWS = [4, 5, 7, 11, 12, 13, 15]
TOC_ROW_X0, TOC_ROW_X1 = 39.54 * MM, 189.54 * MM


def toc_row_top(k: int) -> float:
    return (64 + k * 16.5) * MM


TOC_ROW_H = 13 * MM

# References page: external links, top to bottom. {{QR_1}}..{{QR_4}} in the HTML carry the same URLs.
REF_PAGE = 15
REF_URLS = [
    "https://github.com/IBM/plex",
    "https://pymupdf.readthedocs.io",
    "https://github.com/veraPDF/veraPDF-library",
    "https://developer.chrome.com/docs/chromium/headless",
]

# Accessible names: a generic label on every row announces nothing. One per row, in row order.
CONTENTS_LABELS = [
    "لماذا يُقلب الحرف؟",
    "القياس: خمسة قرّاء",
    "أربعة إصلاحات",
    "البوابة",
    "المطابقة",
    "ما لا يفعله هذا الملف",
    "المراجع والأدوات",
]
REF_LABELS = ["عائلة خطوط IBM Plex", "مكتبة PyMuPDF", "أداة veraPDF", "محرك Chrome Headless"]

LANG = "ar"
BLANK_EXEMPT_IMAGE_COVER = 0.25

HOUSE_FONT_PREFIX = "IBMPlexSansArabic"
BASMALA_FACES = {"GeezaPro"}

SOURCE_HTML = "report-v1.html"
COPY_MIN_RECALL = 0.95
COPY_MIN_SEQUENCE = 0.92
# The MuPDF word-order floor for THIS document: calibrated as max(0.75, measured - 0.02) by
# scripts/calibrate.py --write. The gate refuses any value below 0.75, so it cannot be bought down.
# >>> CALIBRATED LINE_ORDER_MIN
LINE_ORDER_MIN = 0.750
# <<< CALIBRATED LINE_ORDER_MIN
VOCALISED = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"

# --------------------------------------------------------------------------------------------------------------
# P-1 · What MUST exist. Measured on the approved build; `scripts/calibrate.py --write` rewrites the blocks
# marked CALIBRATED. Never edit one to make a failing build pass.
# --------------------------------------------------------------------------------------------------------------
# >>> DECLARED EXPECTED  (counts of structures the spec declares, not a measurement)
EXPECTED = {"pages": 17, "nav_pages": 13, "source_strips": 13, "slots_per_strip": 4, "source_icons": 52, "ref_links": 4, "toc_rows": 7}
# <<< DECLARED EXPECTED

SLOT_INK_CONTRAST, SLOT_INK_MIN, SLOT_INK_MAX = 60, 0.05, 0.60
SLOT_SHAPE = {"next": (0.168, -0.069, -0.013, 0.180, 0.170), "prev": (0.169, 0.050, -0.016, 0.179, 0.171),
              "contents": (0.141, -0.079, -0.150, 0.233, 0.146), "home": (0.357, -0.005, 0.104, 0.306, 0.268)}
SLOT_SHAPE_TOL = 0.03
SLOT_ICON_MIN_IOU = 0.80

PAGE_INK_DPI, PAGE_INK_GRID, PAGE_INK_TOL = 72, 4, 0.02
PAGE_INK_MIN_RETENTION, PAGE_INK_CELL_FLOOR = 0.60, 0.005
# >>> CALIBRATED PAGE_INK
PAGE_INK = {
    0: (0.0797, (0.0, 0.2167, 0.0975, 0.0, 0.0007, 0.1771, 0.3124, 0.0116, 0.0108, 0.1594, 0.1925, 0.0121, 0.0046, 0.0203, 0.0541, 0.004)),
    1: (0.0064, (0.0, 0.01, 0.0132, 0.0, 0.0024, 0.0356, 0.0325, 0.0024, 0.0, 0.0, 0.0, 0.0, 0.005, 0.0, 0.0, 0.0004)),
    2: (0.0119, (0.0006, 0.0274, 0.0338, 0.0062, 0.0033, 0.0, 0.0301, 0.0246, 0.002, 0.0087, 0.0258, 0.0123, 0.0, 0.0077, 0.0073, 0.0)),
    3: (0.1357, (0.0073, 0.0065, 0.0, 0.0, 0.0, 0.5127, 0.6325, 0.1286, 0.0004, 0.5925, 0.2849, 0.0018, 0.0, 0.0, 0.0, 0.0)),
    4: (0.0295, (0.0252, 0.0362, 0.0414, 0.0408, 0.018, 0.0453, 0.0516, 0.0336, 0.0225, 0.0426, 0.0675, 0.0397, 0.0025, 0.0, 0.0, 0.0053)),
    5: (0.0266, (0.0116, 0.0402, 0.0601, 0.0399, 0.0061, 0.026, 0.01, 0.032, 0.022, 0.0618, 0.0394, 0.0376, 0.0043, 0.0055, 0.0175, 0.011)),
    6: (0.1195, (0.0066, 0.0065, 0.0, 0.0, 0.0011, 0.1419, 0.3711, 0.1392, 0.0092, 0.1756, 0.2206, 0.0043, 0.0011, 0.4116, 0.4161, 0.0017)),
    7: (0.1997, (0.0388, 0.0737, 0.0872, 0.0547, 0.5272, 0.8693, 0.871, 0.5358, 0.0145, 0.0289, 0.0552, 0.0284, 0.0025, 0.0, 0.0, 0.0005)),
    8: (0.0243, (0.0155, 0.0266, 0.0658, 0.0371, 0.0138, 0.0335, 0.0471, 0.0193, 0.0167, 0.0426, 0.0454, 0.0225, 0.0025, 0.0, 0.0, 0.0004)),
    9: (0.0229, (0.0065, 0.0228, 0.0335, 0.0148, 0.0167, 0.0558, 0.069, 0.0288, 0.0098, 0.0324, 0.032, 0.0246, 0.0025, 0.0, 0.0088, 0.0086)),
    10: (0.028, (0.0309, 0.0571, 0.0734, 0.0439, 0.0209, 0.052, 0.0528, 0.0429, 0.0087, 0.0186, 0.029, 0.0146, 0.0025, 0.0, 0.0, 0.001)),
    11: (0.0221, (0.0137, 0.0367, 0.0657, 0.0382, 0.0086, 0.0522, 0.0633, 0.0236, 0.0068, 0.0124, 0.0147, 0.0142, 0.0025, 0.0, 0.0, 0.0008)),
    12: (0.023, (0.0125, 0.0309, 0.0506, 0.0392, 0.0186, 0.0473, 0.0582, 0.0273, 0.0067, 0.0143, 0.0395, 0.0194, 0.0025, 0.0, 0.0, 0.0008)),
    13: (0.0159, (0.0168, 0.0243, 0.0306, 0.0361, 0.0068, 0.0048, 0.0259, 0.0357, 0.0081, 0.0146, 0.0262, 0.0221, 0.0025, 0.0, 0.0, 0.0009)),
    14: (0.0167, (0.0296, 0.0515, 0.0481, 0.0488, 0.0, 0.0, 0.0, 0.0109, 0.0057, 0.0123, 0.0142, 0.0092, 0.0032, 0.0121, 0.013, 0.0083)),
    15: (0.0199, (0.0063, 0.0182, 0.0284, 0.043, 0.0, 0.0023, 0.0429, 0.1056, 0.0, 0.0, 0.0181, 0.0386, 0.0023, 0.0052, 0.0061, 0.0008)),
    16: (0.173, (0.0, 0.0, 0.0, 0.0, 0.0024, 0.0338, 0.0355, 0.0017, 0.0935, 0.5271, 0.5167, 0.103, 0.1202, 0.5878, 0.5939, 0.1485)),
}
# <<< CALIBRATED PAGE_INK

PAGE_WORDS_TOL = 2
# >>> CALIBRATED PAGE_WORDS
PAGE_WORDS = {0: 44, 1: 38, 2: 71, 3: 10, 4: 156, 5: 160, 6: 11, 7: 155, 8: 142, 9: 105, 10: 154, 11: 133, 12: 123, 13: 96, 14: 87, 15: 67, 16: 19}
# <<< CALIBRATED PAGE_WORDS

# >>> CALIBRATED IMAGE_PAGES
IMAGE_PAGES = {0: (1, 0.9995), 3: (1, 0.9995), 6: (1, 0.9995), 15: (4, 0.0185), 16: (1, 0.9995)}
# <<< CALIBRATED IMAGE_PAGES
IMAGE_COVER_TOL = 0.02

# >>> CALIBRATED FOOTER
FOOTER = {1: 2, 4: 5, 5: 6, 7: 8, 8: 9, 9: 10, 10: 11, 11: 12, 12: 13, 13: 14, 14: 15, 15: 16}
# <<< CALIBRATED FOOTER
FOOTER_Y_MIN, FOOTER_Y_MAX = 770, 830

VERSION_SPOTS = [("cover", COVER), ("back", PAGES - 1)]
PRINTED_COUNTS_PAGE = 11      # the page that prints «N فحصا» and «M عطلا»

ART_MAX_DPI = 300
ART_DPI_DECLARED = {3: 205, 6: 205, 16: 205}   # measured: min(w,h) dpi of the artwork at A4
ART_PAGE_SHARE = 0.30
ART_FILES = [
    ("{{ART_COVER}}", "embed-report-cover.jpg"),
    ("{{ART_DIVIDER}}", "embed-report-divider-a.jpg"),
    ("{{ART_DIVIDER2}}", "embed-report-divider-b.jpg"),
    ("{{ART_BACK}}", "embed-back.jpg"),
]

PRINTS_LINK_COUNT = True     # page 12 prints «٦٣ رابطا»; the gate parses and compares it
LINKS_CLAIM = "و٦٣ رابطا حيا"   # injected into {{LINKS_CLAIM}}; the print variant states its own truth
GATE_CHECKS = 35
GATE_MUTATIONS = 52
GATE_NA = {}                                   # every mutation applies to this document
# Measured 2026-11-17 by scripts/claim_probe.py on this build: zero rules remain under either claim.
CLAIM_EXPECTED = {"3b": set(), "ua1": set()}

# --------------------------------------------------------------------------------------------------------------
# Stage-5 features (postprocess.py, declared in features.toml).
# --------------------------------------------------------------------------------------------------------------
DEST_NAMES = [("cover", COVER), ("basmala", BASMALA), ("contents", CONTENTS), ("section-1", 3),
              ("section-2", 6), ("form", 14), ("references", REF_PAGE), ("back", PAGES - 1)]
PAGE_LABELS = [(0, None, "غ"), (1, "D", 1)]
XMP_LANGUAGE = "ar"
# The class the navigation strip is drawn with: the producer removes it and the gate reads it.
NAV_CLASS = "nav"
XMP_TITLE = f"{DOC_TITLE} · الإصدار {GUIDE_VERSION_AR}"   # one source of truth for the title string
XMP_DESCRIPTION = "تشخيص وإصلاح وإثبات لطبقة النص العربية في PDF، بأرقام مقاسة على خمسة قرّاء"
# Declared only when veraPDF reports ZERO failures for it — the gate reads the baseline and refuses otherwise.
PDFUA = True
CONFORMANCE = {"pdfaid:part": "3", "pdfaid:conformance": "B", "pdfuaid:part": "1"}
VERAPDF_BASELINE = "verapdf-baseline-report.toml"

ATTACHMENT_FILES = [
    ("manifest.json", None, "application/json", "Source"),
    ("features.toml", "features.toml", "application/toml", "Data"),
    ("verapdf-baseline.toml", VERAPDF_BASELINE, "application/toml", "Data"),
]

# Widget rectangles in PDF points (origin bottom-left). The HTML draws the line each field sits on.
def _field(top_mm: float, height_mm: float) -> list[float]:
    y1 = (PAGE_H_MM - top_mm) * MM
    return [20.46 * MM, y1 - height_mm * MM, 189.54 * MM, y1]


ACROFORM_FIELDS = [
    {"name": "reader_name", "tu": "اسم القارئ", "page": 14, "rect": _field(72, 12)},
    {"name": "reader_email", "tu": "البريد الإلكتروني", "page": 14, "rect": _field(106, 12)},
    {"name": "reader_note", "tu": "ملاحظة عن الملف", "page": 14, "rect": _field(144, 45), "multiline": True},
]

LINK_LABELS = {"next": "الصفحة التالية", "prev": "الصفحة السابقة",
               "contents": "جدول المحتويات", "home": "الغلاف"}
# >>> CALIBRATED EXPECTED_LINKS
EXPECTED_LINKS = 63
# <<< CALIBRATED EXPECTED_LINKS
