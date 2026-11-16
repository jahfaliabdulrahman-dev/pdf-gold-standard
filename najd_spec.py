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
REF_LABELS = ["خط نجد", "المصمّم على X", "أداة veraPDF", "محرّك Chrome Headless"]

LANG = "ar"
HOUSE_FONT_PREFIX = "Najd"          # every embedded face must start with this
BASMALA_FACES = set()
BASMALA = 3                         # the specimen page that prints the basmala
VOCALISED_CLAIM = False             # marks do not round-trip for this face — measured, and stated on the page
VOCALISED_REASON = "ترتيب العلامات لا يُنسخ حرفيًا في هذا الوجه (مقيس في MuPDF) — لا ندّعي ما لم يثبت"
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
PAGE_INK = {
    0: (0.0231, (0.0, 0.0122, 0.0233, 0.0, 0.0, 0.1338, 0.1329, 0.0, 0.0, 0.0343, 0.0305, 0.0, 0.0, 0.0003, 0.0014, 0.0)),
    1: (0.0077, (0.0006, 0.017, 0.0242, 0.006, 0.0025, 0.0, 0.0231, 0.0212, 0.0013, 0.0, 0.0135, 0.0095, 0.002, 0.0, 0.0, 0.002)),
    2: (0.0323, (0.013, 0.0337, 0.0398, 0.0403, 0.0, 0.0294, 0.0771, 0.0652, 0.0052, 0.0731, 0.085, 0.0526, 0.0003, 0.0, 0.0, 0.0018)),
    3: (0.0207, (0.0163, 0.0199, 0.0363, 0.0412, 0.0036, 0.0199, 0.0252, 0.0638, 0.0058, 0.0126, 0.0322, 0.0517, 0.0003, 0.0, 0.0, 0.0018)),
    4: (0.0839, (0.0591, 0.0858, 0.1069, 0.0851, 0.1365, 0.4181, 0.2025, 0.1445, 0.0097, 0.036, 0.027, 0.0271, 0.0002, 0.0, 0.0, 0.002)),
    5: (0.0165, (0.0065, 0.0099, 0.0313, 0.0307, 0.0244, 0.0448, 0.0427, 0.0417, 0.0003, 0.0055, 0.0169, 0.0075, 0.0003, 0.0, 0.0, 0.0015)),
    6: (0.0182, (0.011, 0.0199, 0.0267, 0.0307, 0.0071, 0.0597, 0.0299, 0.0376, 0.0062, 0.0268, 0.0146, 0.0192, 0.0004, 0.0, 0.0, 0.0017)),
    7: (0.0235, (0.0155, 0.0275, 0.0558, 0.0812, 0.0126, 0.0261, 0.0525, 0.0588, 0.0059, 0.0131, 0.0118, 0.0125, 0.0004, 0.0, 0.0, 0.0019)),
    8: (0.0192, (0.0063, 0.0293, 0.0346, 0.0334, 0.0189, 0.0559, 0.0421, 0.0385, 0.0, 0.0, 0.0228, 0.0232, 0.0003, 0.0, 0.0, 0.0017)),
    9: (0.0089, (0.0065, 0.0079, 0.0257, 0.0271, 0.0, 0.0, 0.0162, 0.0302, 0.0, 0.0014, 0.0114, 0.0136, 0.0002, 0.0, 0.0, 0.0019)),
    10: (0.01, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0641, 0.0683, 0.0, 0.0, 0.013, 0.0126, 0.0, 0.0, 0.0004, 0.0015, 0.0)),
}
# <<< CALIBRATED PAGE_INK

# >>> CALIBRATED PAGE_WORDS
PAGE_WORDS = {0: 19, 1: 43, 2: 74, 3: 69, 4: 94, 5: 101, 6: 120, 7: 106, 8: 127, 9: 58, 10: 21}
# <<< CALIBRATED PAGE_WORDS

# >>> CALIBRATED IMAGE_PAGES
IMAGE_PAGES = {}
# <<< CALIBRATED IMAGE_PAGES

# >>> CALIBRATED FOOTER
FOOTER = {}
# <<< CALIBRATED FOOTER

# >>> CALIBRATED EXPECTED_LINKS
EXPECTED_LINKS = 43
# <<< CALIBRATED EXPECTED_LINKS
