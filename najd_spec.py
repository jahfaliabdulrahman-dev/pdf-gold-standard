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
PRINTED_COUNTS_PAGE = 7             # the page that prints «٣٤ فحصا» and «٤٠ عطلا»
PRINTS_LINK_COUNT = False
GATE_CHECKS = 34
# Eight of the suite's 48 mutations cannot be caught on this specimen; the reasons are measured, not
# assumed, and gate_selftest fails if one of them stops being an exemption (stale) or if a mutation goes
# n/a without being declared here. 48 − 8 = 40.
GATE_MUTATIONS = 40
GATE_NA = {
    "drop_divider_art": "the divider page carries no art",
    "drop_image_object": "the references page carries no QR image",
    "drop_footer_number": "no page prints its own number",
    "swap_footer_numbers": "no page prints its own number",
    "move_footer_up": "no page prints its own number",
    "field_without_tu": "the specimen has no AcroForm fields",
    "wrong_mark": "VOCALISED_CLAIM is False — the marked-text check is off by declaration",
    "split_text_objects": "measured: splitting its single-direction lines moves MuPDF order 0.929 → 0.925, above the 0.75 floor",
}
# Measured 2026-11-17 by scripts/claim_probe.py on this build: zero rules remain under either claim.
CLAIM_EXPECTED = {"3b": set(), "ua1": set()}
# The cover carries the wall the typeface was drawn from; embedded at build time so the print stays
# deterministic (Chrome renders from a temp dir, where relative paths do not resolve).
ART_FILES = [("{{ART_NAJD_COVER}}", "embed-najd-cover.jpg")]
ART_MAX_DPI = 300
ART_DPI_DECLARED = {}
ART_PAGE_SHARE = 0.0

DEST_NAMES = [("cover", COVER), ("contents", CONTENTS), ("weights", 2), ("glyphs", 3), ("palette", 4),
              ("spirit", 5), ("features", 6), ("gate", 7), ("limits", 8), ("references", REF_PAGE), ("back", PAGES - 1)]
PAGE_LABELS = [(0, None, "غ")]
XMP_LANGUAGE = "ar"
XMP_TITLE = f"{DOC_TITLE} · الإصدار {GUIDE_VERSION_AR}"
XMP_DESCRIPTION = "عيّنة خط نجد: خمسة أوزان ثابتة، وألوان الموقع، وميزات خط الأنابيب كاملة بلا حقول كتابة"
PDFUA = True
CONFORMANCE = {"pdfaid:part": "3", "pdfaid:conformance": "B", "pdfuaid:part": "1"}
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
    0: (0.1551, (0.0029, 0.0387, 0.0497, 0.0025, 0.0, 0.1016, 0.1004, 0.0, 0.2042, 0.1898, 0.2298, 0.2321, 0.293, 0.2621, 0.4135, 0.3599)),
    1: (0.0072, (0.0006, 0.0167, 0.0232, 0.0053, 0.0023, 0.0, 0.0216, 0.0198, 0.0011, 0.0, 0.0125, 0.0088, 0.0018, 0.0, 0.0, 0.0018)),
    2: (0.0314, (0.0127, 0.0324, 0.0377, 0.039, 0.0, 0.0281, 0.0736, 0.0619, 0.0052, 0.0727, 0.0847, 0.052, 0.0003, 0.0, 0.0, 0.0016)),
    3: (0.0175, (0.0155, 0.019, 0.0371, 0.0422, 0.0064, 0.0169, 0.0255, 0.0378, 0.0056, 0.0117, 0.0118, 0.0484, 0.0003, 0.0, 0.0, 0.0016)),
    4: (0.0956, (0.0582, 0.0839, 0.0891, 0.0342, 0.3128, 0.4589, 0.2041, 0.187, 0.0146, 0.0266, 0.0184, 0.0372, 0.0002, 0.0, 0.0, 0.0018)),
    5: (0.0252, (0.0062, 0.011, 0.0323, 0.0319, 0.0197, 0.0334, 0.0326, 0.0355, 0.0294, 0.0518, 0.0516, 0.0422, 0.0004, 0.0047, 0.0134, 0.0075)),
    6: (0.0176, (0.0108, 0.0186, 0.0261, 0.0298, 0.007, 0.0575, 0.0292, 0.0363, 0.006, 0.0258, 0.0141, 0.0185, 0.0003, 0.0, 0.0, 0.0015)),
    7: (0.0224, (0.0148, 0.0258, 0.0541, 0.0787, 0.0113, 0.0247, 0.0499, 0.056, 0.0053, 0.0121, 0.0112, 0.0122, 0.0003, 0.0, 0.0, 0.0017)),
    8: (0.0185, (0.0062, 0.0269, 0.0337, 0.032, 0.0185, 0.0545, 0.041, 0.0373, 0.0, 0.0, 0.022, 0.0225, 0.0003, 0.0, 0.0, 0.0015)),
    9: (0.0079, (0.0062, 0.0074, 0.0248, 0.0257, 0.0, 0.0, 0.0133, 0.0249, 0.0, 0.0012, 0.0092, 0.0115, 0.0002, 0.0, 0.0, 0.0017)),
    10: (0.0092, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0639, 0.0682, 0.0, 0.0, 0.0082, 0.007, 0.0, 0.0, 0.0, 0.0, 0.0)),
}
# <<< CALIBRATED PAGE_INK

# >>> CALIBRATED PAGE_WORDS
PAGE_WORDS = {0: 33, 1: 43, 2: 74, 3: 105, 4: 92, 5: 143, 6: 120, 7: 106, 8: 127, 9: 58, 10: 21}
# <<< CALIBRATED PAGE_WORDS

# >>> CALIBRATED IMAGE_PAGES
IMAGE_PAGES = {0: (1, 0.4405)}
# <<< CALIBRATED IMAGE_PAGES

# >>> CALIBRATED FOOTER
FOOTER = {}
# <<< CALIBRATED FOOTER

# >>> CALIBRATED EXPECTED_LINKS
EXPECTED_LINKS = 43
# <<< CALIBRATED EXPECTED_LINKS
