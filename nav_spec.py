"""Single source of truth for the guide's interactive layer.

build.py injects links FROM these numbers and scripts/verify_pdf.py checks the PDF AGAINST them,
so a geometry or target change happens in one place (house rule: CSS, rects and gate share one set
of numbers). All page indices are 0-based.
"""

MM = 2.83465  # 1 mm in pt

# The version printed on the cover, the back cover and in the PDF title. A release tag vX.Y.Z must start with it
# (CI checks the tag, the gate checks the title and the cover).
GUIDE_VERSION = "2.3"
# Metadata is part of the document, not of the pipeline (build.py reads these).
DOC_TITLE = "معيار إنتاج ملفات PDF — دليل المعيار"
DOC_AUTHOR = "م. عبدالرحمن جحفلي"
DOC_SUBJECT = "معيار جودة إنتاج ملفات PDF التفاعلية العربية"
DOC_KEYWORDS = "PDF, Arabic, RTL, تفاعلي, معيار, Gold Standard"
GUIDE_VERSION_AR = GUIDE_VERSION.translate(str.maketrans("0123456789.", "٠١٢٣٤٥٦٧٨٩٫"))

PAGES = 12
COVER, BASMALA, CONTENTS = 0, 1, 2

# Outline: (level, title, 1-based page) — exactly what doc.set_toc() receives.
TOC = [
    [1, "الغلاف", 1],
    [1, "البسملة", 2],
    [1, "جدول المحتويات", 3],
    [1, "القسم الأول — الأساس", 4],
    [2, "لماذا هذا المعيار؟", 5],
    [2, "نظام التنقل الدائم", 6],
    [1, "القسم الثاني — البناء", 7],
    [2, "الهوية البصرية والتايبوغرافي", 8],
    [2, "الإيقاع الطباعي والمكونات", 9],
    [2, "دعم العربية والتحقق الآلي", 10],
    [1, "المراجع والأدوات", 11],
    [1, "الغلاف الخلفي", 12],
]

# Nav strip: 4 fixed buttons on content + divider pages. Slot x (left edge, pt) -> role.
NAV_PAGES = range(3, 11)            # pages 4..11
NAV_Y0, NAV_Y1, NAV_W = 37, 62, 25
SLOTS = {"next": 58.0, "prev": 95.33, "contents": 132.67, "home": 170.0}


# A drawn button: share of the slot's pixels (300 dpi, gray, slot shrunk 2pt) that differ from the slot's median by more
# than SLOT_INK_CONTRAST. Measured on the real build: 0.14 (contents) .. 0.36 (home); a slot painted over: 0.00.
SLOT_INK_CONTRAST, SLOT_INK_MIN, SLOT_INK_MAX = 60, 0.05, 0.60
# The RIGHT icon in each slot — a five-number signature of the slot's ink, measured on the real build and identical on
# all 8 pages to +-0.008: (ink share, centre of mass x, y relative to the slot centre, spread x, y as fractions of the
# slot; x right, y down). The "next" arrow points left (RTL), "prev" right, the contents lines sit high and left, the
# house sits low. Tolerance well under the smallest distance between two icons (0.12 in x between the arrows).
SLOT_SHAPE = {"next": (0.168, -0.069, -0.013, 0.180, 0.170), "prev": (0.169, 0.050, -0.016, 0.179, 0.171),
              "contents": (0.141, -0.079, -0.150, 0.233, 0.146), "home": (0.357, -0.005, 0.104, 0.306, 0.268)}
SLOT_SHAPE_TOL = 0.03
# ...and the SHAPE itself: the slot's ink against the icon drawn in the source HTML (both cropped to their ink, scaled to
# 48x48), intersection over union. Measured: own icon 0.93-0.99 on all 8 pages, any other icon <= 0.41.
SLOT_ICON_MIN_IOU = 0.80


def nav_target(role: str, i: int) -> int:
    """Expected destination of the button `role` on page index i."""
    return {"home": COVER, "contents": CONTENTS, "prev": i - 1, "next": i + 1}[role]


# Contents-page rows, top to bottom -> destination page index.
TOC_ROWS = [4, 5, 7, 8, 9, 10]
TOC_ROW_X0, TOC_ROW_X1 = 39.54 * MM, 189.54 * MM


def toc_row_top(k: int) -> float:
    return (64 + k * 16.5) * MM


TOC_ROW_H = 13 * MM

# References page: external links, top to bottom.
REF_PAGE = 10
REF_URLS = [
    "https://github.com/IBM/plex",
    "https://pymupdf.readthedocs.io",
    "https://pagedjs.org",
    "https://developer.chrome.com/docs/chromium/headless",
]
# The four fixed references the guide prints as QRs on its content pages (same URLs, different
# placement). {{QR_n}} on the references page is filled from REF_URLS in order.
QR_FIXED = list(zip(("{{QR_IBM}}", "{{QR_PYMUPDF}}", "{{QR_PAGEDJS}}", "{{QR_CHROME}}"), REF_URLS))

# Tagged PDF: declared in README, so the gate guards it.
LANG = "ar"
# The class the navigation strip is drawn with: the producer removes it and the gate reads it.
NAV_CLASS = "nav"
# A page far below the median text is excused only when images cover at least this share of it (cover, dividers = 1.0;
# the references page with its QR codes = 0.018 and needs no excuse).
BLANK_EXEMPT_IMAGE_COVER = 0.25

# Fonts: the house family everywhere; the vocalised basmala alone may use the macOS system face
# (webfont subsets misplace tashkeel in Chrome — measured 2026-09-13).
HOUSE_FONT_PREFIX = "IBMPlexSansArabic"
BASMALA_FACES = {"GeezaPro"}

# Copy/paste: the gate re-extracts the PDF with PDFium and compares it with the words of this source file.
# Measured on guide v2.1: Chrome's raw text layer 0.387 / 0.365, after scripts/fix_text_layer.py 0.971 / 0.945.
SOURCE_HTML = "guide-v2.html"
COPY_MIN_RECALL = 0.95
COPY_MIN_SEQUENCE = 0.92
# Stream-order readers (MuPDF): raw Chrome output 0.16, after the line-joining pass 0.80 (measured on guide v2.1).
# The MuPDF word-order floor for THIS document: calibrated as max(0.75, measured - 0.02) by
# scripts/calibrate.py --write. The gate refuses any value below 0.75, so it cannot be bought down.
# >>> CALIBRATED LINE_ORDER_MIN
LINE_ORDER_MIN = 0.765
# <<< CALIBRATED LINE_ORDER_MIN
# Vocalised text that must copy exactly (letters with their marks, in order).
VOCALISED = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"

# --------------------------------------------------------------------------------------------------------------
# P-1 · What MUST exist. The gate enumerates the document against these expectations BEFORE any qualitative
# comparison: an element that disappears must break the build, not silence the check that looked for it.
# Every number below was measured on the approved build (2026-11-14, HEAD 08e921f + the gate fixes); re-measure
# and update in the SAME commit as any declared design change. Never edit one to make a failing build pass.
# --------------------------------------------------------------------------------------------------------------
EXPECTED = {
    "pages": 12,
    "nav_pages": 8,
    "source_strips": 8,          # <div class="nav"> containers in the source HTML
    "slots_per_strip": 4,
    "source_icons": 32,          # 8 strips x 4 icons
    "ref_links": 4,
    "toc_rows": 6,
}

# Ink per page at 72 dpi: (share of the page differing from the page's median by > SLOT_INK_CONTRAST,
# 4x4 grid of the same share per cell). The grid is what stops a "same total ink, moved elsewhere" forgery;
# the scalar alone can be moment-matched. Measured on two independent builds: max |delta| = 0.00000, so the
# tolerance below is ten times the observed jitter.
PAGE_INK_DPI, PAGE_INK_GRID, PAGE_INK_TOL = 72, 4, 0.02
# A cell that had ink must keep most of it: on a page with 0.8% ink a ±0.02 absolute tolerance cannot tell
# "nothing" from "everything" (it is larger than the whole page), so removal is judged by retention instead.
PAGE_INK_MIN_RETENTION, PAGE_INK_CELL_FLOOR = 0.60, 0.005
# >>> CALIBRATED PAGE_INK
PAGE_INK = {
    0: (0.1227, (0.0254, 0.1697, 0.0891, 0.0078, 0.0007, 0.1141, 0.2429, 0.0136, 0.0119, 0.2259, 0.2252, 0.0155, 0.0056, 0.3936, 0.4133, 0.0044)),
    1: (0.0077, (0.0, 0.01, 0.0132, 0.0, 0.0049, 0.0423, 0.0395, 0.0054, 0.0, 0.0, 0.0, 0.0, 0.0051, 0.0016, 0.0, 0.0004)),
    2: (0.0103, (0.0007, 0.0272, 0.0324, 0.0051, 0.002, 0.0, 0.0425, 0.024, 0.0005, 0.0087, 0.0148, 0.0062, 0.0, 0.0, 0.0, 0.0)),
    3: (0.0313, (0.0066, 0.0066, 0.0, 0.0, 0.0037, 0.0137, 0.0541, 0.133, 0.0457, 0.0838, 0.0765, 0.0266, 0.0016, 0.0244, 0.0235, 0.0011)),
    4: (0.0213, (0.0186, 0.0355, 0.0392, 0.0445, 0.0173, 0.0404, 0.0524, 0.0356, 0.0073, 0.0144, 0.0168, 0.0144, 0.003, 0.0007, 0.0, 0.0004)),
    5: (0.0186, (0.0118, 0.0234, 0.0384, 0.0409, 0.0065, 0.0308, 0.0238, 0.0297, 0.012, 0.0293, 0.03, 0.0166, 0.003, 0.0007, 0.0, 0.0003)),
    6: (0.0284, (0.0067, 0.0065, 0.0, 0.0, 0.0036, 0.0149, 0.0213, 0.1176, 0.0262, 0.0767, 0.0832, 0.0464, 0.0011, 0.0234, 0.0244, 0.0017)),
    7: (0.0411, (0.0122, 0.0849, 0.161, 0.1027, 0.022, 0.0325, 0.0951, 0.0732, 0.0058, 0.0154, 0.0296, 0.0184, 0.003, 0.0007, 0.0, 0.0005)),
    8: (0.0264, (0.0499, 0.0904, 0.1095, 0.0589, 0.0134, 0.0335, 0.0317, 0.0306, 0.0, 0.0, 0.0, 0.0, 0.003, 0.0007, 0.0, 0.0004)),
    9: (0.0258, (0.0208, 0.0339, 0.0611, 0.0531, 0.0134, 0.0406, 0.0669, 0.0449, 0.0063, 0.024, 0.0276, 0.0156, 0.003, 0.0007, 0.0, 0.0009)),
    10: (0.0205, (0.0065, 0.0147, 0.0289, 0.0435, 0.0014, 0.0015, 0.0471, 0.1063, 0.0005, 0.0, 0.0208, 0.0397, 0.003, 0.0059, 0.0061, 0.001)),
    11: (0.1737, (0.0, 0.0, 0.0, 0.0, 0.0024, 0.0392, 0.0424, 0.0017, 0.0935, 0.5271, 0.5167, 0.103, 0.1202, 0.5878, 0.5928, 0.1485)),
}
# <<< CALIBRATED PAGE_INK

# Words per page, tokenised exactly like copy-fidelity (NFC, bidi controls and tatweel dropped, tashkeel dropped;
# Arabic letters, Arabic-Indic digits and Latin words). Latin footer digits are NOT tokens — footer-numbers owns them.
PAGE_WORDS_TOL = 2
# >>> CALIBRATED PAGE_WORDS
PAGE_WORDS = {0: 48, 1: 44, 2: 54, 3: 11, 4: 126, 5: 108, 6: 8, 7: 86, 8: 65, 9: 141, 10: 65, 11: 21}
# <<< CALIBRATED PAGE_WORDS

# Images: page index -> (distinct image objects, share of the page under them). Covers and dividers are one
# full-page image; the references page carries the four QR codes; every other page carries none.
# >>> CALIBRATED IMAGE_PAGES
IMAGE_PAGES = {0: (1, 0.9995), 3: (1, 0.9995), 6: (1, 0.9995), 10: (4, 0.0185), 11: (1, 0.9995)}
# <<< CALIBRATED IMAGE_PAGES
IMAGE_COVER_TOL = 0.02

# Printed footer numbers: page index -> the Latin number it must print (1-based page number). Pages absent from
# this table must print NO Latin-digit footer (cover, contents, both dividers, back cover — measured).
# >>> CALIBRATED FOOTER
FOOTER = {1: 2, 4: 5, 5: 6, 7: 8, 8: 9, 9: 10, 10: 11}
# <<< CALIBRATED FOOTER
FOOTER_Y_MIN, FOOTER_Y_MAX = 770, 830

# Every place the version is printed: (name, 0-based page index). The source must contain exactly this many
# occurrences, and each named page must print it (PDFium text: MuPDF reverses Arabic-Indic digits — known limit).
VERSION_SPOTS = [("cover", 0), ("back", 11)]
PRINTED_COUNTS_PAGE = 9      # the page that prints «N فحصا» and «M عطلا»

# Declared totals. The gate counts its own checks, gate_selftest counts its mutations, and a check reads the
# printed numbers off the document: all three must agree, so adding a check without updating the guide
# fails the build instead of leaving the page lying.
ART_MAX_DPI = 300          # spec §3.4: art serving >30% of a page is capped at 300 dpi (cover was 411)
# Divider/back art is 205-217 dpi and is DECLARED below the 290-330 band: upscaling it increases the file
# (spec §3.4, measured). The floor is therefore enforced only on pages absent from this table.
ART_DPI_DECLARED = {3: 205, 6: 205, 11: 205}
ART_PAGE_SHARE = 0.30       # an image counts as page art above this share of the page

GATE_CHECKS = 35
GATE_MUTATIONS = 52
GATE_NA = {}                                   # every mutation applies to this document
# What remains failing when this file DECLARES conformance — measured by scripts/claim_probe.py, one table
# per document (the guide's file has one untagged rule; the other two are clean under both claims).
CLAIM_EXPECTED = {"3b": set(), "ua1": {"7.1-3"}}
ART_FILES = [
    ("{{ART_COVER}}", "embed-cover.jpg"),
    ("{{ART_DIVIDER}}", "embed-divider.jpg"),
    ("{{ART_BACK}}", "embed-back.jpg"),
]

# --------------------------------------------------------------------------------------------------------------
# Stage-5 features (postprocess.py, declared in features.toml). Metadata/structure only — no drawing.
# --------------------------------------------------------------------------------------------------------------
# A name -> page map, so a target is an identity, not an index that shifts when a page is added.
DEST_NAMES = [("cover", 0), ("contents", 2), ("section-1", 3), ("section-2", 6), ("references", 10), ("back", 11)]
# Printed numbering: (start page, style or None, prefix or start value). The cover is a prefix-only label.
PAGE_LABELS = [(0, None, "غ"), (1, "D", 1)]
# Minimum XMP fields the archive/search tools read.
XMP_LANGUAGE = "ar"
ATTACHMENT_FILES = [("manifest.json", None, "application/json", "Source")]
# Link accessible names, derived from the geometry the build already uses.
LINK_LABELS = {"next": "الصفحة التالية", "prev": "الصفحة السابقة",
               "contents": "جدول المحتويات", "home": "الغلاف"}
# >>> CALIBRATED EXPECTED_LINKS
EXPECTED_LINKS = 42
# <<< CALIBRATED EXPECTED_LINKS

