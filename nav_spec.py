"""Single source of truth for the guide's interactive layer.

build.py injects links FROM these numbers and scripts/verify_pdf.py checks the PDF AGAINST them,
so a geometry or target change happens in one place (house rule: CSS, rects and gate share one set
of numbers). All page indices are 0-based.
"""

MM = 2.83465  # 1 mm in pt

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

# Fonts: the house family everywhere; the vocalised basmala alone may use the macOS system face
# (webfont subsets misplace tashkeel in Chrome — measured 2026-09-13).
HOUSE_FONT_PREFIX = "IBMPlexSansArabic"
BASMALA_FACES = {"GeezaPro"}
