"""Spec for «نجد» — a specimen of the Najd typeface, set in its own five static weights and its own palette.

Same pipeline, different document: this spec only declares what is true of THIS file. Every number under the
CALIBRATED markers is written by `scripts/calibrate.py` from a real build, never typed here.

Two deliberate omissions, both stated in the document itself:
  · no AcroForm fields — the brief excludes typing;
  · no variable font — measured: Chrome embeds a variable face as Type3 glyph procedures.
"""
from report_spec import *                       # noqa: F401,F403  (shared geometry: slots, mm, page height)

GUIDE_VERSION = "1.0"
DOC_TITLE = "نجد — عيّنة خط بروح العمارة النجدية"
DOC_AUTHOR = "م. عبدالرحمن جحفلي"
DOC_SUBJECT = "عيّنة خط نجد داخل مستند PDF كامل الميزات، بألوان الخط نفسها"
DOC_KEYWORDS = "Najd, خط نجد, Arabic type, PDF/A-3b, specimen"
GUIDE_VERSION_AR = GUIDE_VERSION.translate(str.maketrans("0123456789.", "٠١٢٣٤٥٦٧٨٩٫"))

SOURCE_HTML = "najd.html"
PAGES = 11
COVER, CONTENTS = 0, 1

TOC = [
    [1, "الغلاف", 1],
    [1, "جدول المحتويات", 2],
    [1, "الأوزان الخمسة", 3],
    [1, "الحروف والبدائل", 4],
    [1, "لوحة الألوان", 5],
    [1, "من الطين إلى الحرف", 6],
    [1, "ما يفعله هذا الملف", 7],
    [1, "البوابة والأرقام", 8],
    [1, "حدود الخط والملف", 9],
    [1, "المراجع", 10],
    [1, "الغلاف الخلفي", 11],
]

# The strip sits on the eight body pages (3..10).
NAV_PAGES = range(2, 10)
TOC_ROWS = [2, 3, 4, 5, 6, 7, 8]
REF_PAGE = 9
REF_URLS = [
    "https://aziz4ai.com/najd-font",
    "https://x.com/aziz4ai",
    "https://github.com/veraPDF/veraPDF-library",
    "https://developer.chrome.com/docs/chromium/headless",
]

CONTENTS_LABELS = ["الأوزان الخمسة", "الحروف والبدائل", "لوحة الألوان", "من الطين إلى الحرف",
                   "ما يفعله هذا الملف", "البوابة والأرقام", "حدود الخط والملف"]
REF_LABELS = ["خط نجد", "المصمّم على X", "أداة veraPDF", "Chrome Headless"]

LANG = "ar"
HOUSE_FONT_PREFIX = "Najd"          # every embedded face must start with this
BASMALA_FACES = set()
BASMALA = 3                         # the specimen page that prints the basmala
VOCALISED_PAGES = {3}
VOCALISED = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"

VERSION_SPOTS = [("cover", COVER), ("back", PAGES - 1)]
PRINTED_COUNTS_PAGE = 7             # the page that prints «٣٤ فحصا» and «٤٨ اختبارا»
PRINTS_LINK_COUNT = False
GATE_CHECKS = 34
GATE_MUTATIONS = 48
ART_FILES = []
ART_MAX_DPI = 300
ART_DPI_DECLARED = {}
ART_PAGE_SHARE = 0.0

DEST_NAMES = [("cover", COVER), ("contents", CONTENTS), ("weights", 2), ("glyphs", 3), ("palette", 4),
              ("spirit", 5), ("features", 6), ("gate", 7), ("limits", 8), ("references", REF_PAGE), ("back", PAGES - 1)]
PAGE_LABELS = [(0, None, "غ")]
XMP_LANGUAGE = "ar"
XMP_TITLE = f"{DOC_TITLE} · الإصدار {GUIDE_VERSION_AR}"
XMP_DESCRIPTION = "عيّنة خط نجد: خمسة أوزان ثابتة، وألوان الموقع، وميزات خط الأنابيب كاملة بلا حقول كتابة"
CONFORMANCE = {"pdfaid:part": "3", "pdfaid:conformance": "B"}
VERAPDF_BASELINE = "verapdf-baseline-najd.toml"

ATTACHMENT_FILES = [
    ("source.html", SOURCE_HTML, "text/html", "Source"),
    ("manifest.json", None, "application/json", "Source"),
    ("features.toml", "features.toml", "application/toml", "Data"),
    ("verapdf-baseline.toml", VERAPDF_BASELINE, "application/toml", "Data"),
]

ACROFORM_FIELDS = []                # the brief excludes typing
def nav_target(role: str, i: int) -> int:
    """Destination of the button `role` on page index i — this document's pages, not the report's."""
    return {"home": COVER, "contents": CONTENTS, "prev": i - 1, "next": i + 1}[role]


LINK_LABELS = {"next": "الصفحة التالية", "prev": "الصفحة السابقة",
               "contents": "جدول المحتويات", "home": "الغلاف"}

# >>> DECLARED EXPECTED  (counts the source declares, not a measurement)
EXPECTED = {"pages": PAGES, "nav_pages": len(NAV_PAGES), "source_strips": len(NAV_PAGES),
            "slots_per_strip": 4, "source_icons": len(NAV_PAGES) * 4, "ref_links": len(REF_URLS),
            "toc_rows": len(TOC_ROWS)}
# <<< DECLARED EXPECTED

# >>> CALIBRATED PAGE_INK
PAGE_INK = {}
# <<< CALIBRATED PAGE_INK

# >>> CALIBRATED PAGE_WORDS
PAGE_WORDS = {}
# <<< CALIBRATED PAGE_WORDS

# >>> CALIBRATED IMAGE_PAGES
IMAGE_PAGES = {}
# <<< CALIBRATED IMAGE_PAGES

# >>> CALIBRATED FOOTER
FOOTER = {}
# <<< CALIBRATED FOOTER

# >>> CALIBRATED EXPECTED_LINKS
EXPECTED_LINKS = 0
# <<< CALIBRATED EXPECTED_LINKS
