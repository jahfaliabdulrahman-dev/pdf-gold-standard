#!/usr/bin/env python3
"""Delivery gate — verify a built PDF against the Gold Standard and nav_spec.py.

Usage: python3 scripts/verify_pdf.py out.pdf

Exit 0 = every check passed; exit 1 = at least one FAIL (names printed). The same script runs
locally, inside build.py (before publishing) and in CI. Every check compares element by element
against nav_spec — never a count or a sorted set, which two swapped buttons would still pass.

Two rules make this gate trustworthy:
  * A check that cannot read what it needs FAILS; it never passes by default (P-1).
  * Every entity has an EXPECTED count/measure in nav_spec, and the gate enumerates the document
    against it before any qualitative comparison — an element that disappears breaks the build.
"""
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pymupdf as fitz  # noqa: E402
import pikepdf  # noqa: E402

import spec_base  # noqa: E402
import spec_loader  # noqa: E402
import render_markup  # noqa: E402

NS = spec_loader.load()  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(HERE, "..")

# Same tokeniser as copy-fidelity: NFC, bidi controls and tatweel dropped, tashkeel dropped; Arabic letters,
# Arabic-Indic digits and Latin words are tokens. Latin footer digits are not — footer-numbers owns them.
BIDI = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c\u0640\u2060]")  # U+2060: invisible intended joiner
MARKS = re.compile("[\u064b-\u0652\u0653-\u0655\u0670]")
WORD = re.compile(r"[\u0621-\u064a\u0671]+|[\u0660-\u0669]+|[A-Za-z][A-Za-z0-9.]*")


def source_words(text: str) -> list[str]:
    """Tokens of a text, with the normalisation copy-fidelity and page-words share."""
    import unicodedata
    return WORD.findall(MARKS.sub("", unicodedata.normalize("NFC", BIDI.sub("", text))))


def source_path() -> str:
    return os.path.join(PROJ, NS.SOURCE_HTML)


def source_text() -> str:
    return open(source_path(), encoding="utf-8").read()


def source_markup() -> str:
    """The markup this spec asks Chrome to print, derived from the same two inputs the producer used.

    The gate used to read a copy beside the output. A copy can go stale or belong to another build;
    this is recomputed instead, so the comparison is about this document. Raises whatever the derivation
    raises — the caller reports it by name. No cache of the result: the expensive pure steps inside
    `render_markup` are cached by their arguments (a file replaced mid-process is out of scope).
    """
    return render_markup.rendered_markup(NS, source_text(), PROJ)


class GateInput(Exception):
    """A file the gate cannot judge: reported by name, never as a traceback."""


def open_for_gate(path: str):
    """Open a PDF for judgement; refuse — by name — what cannot be judged."""
    try:
        doc = fitz.open(path)
    except Exception as e:
        raise GateInput(f"unreadable PDF: {type(e).__name__}: {e}") from None
    if doc.needs_pass:
        raise GateInput("encrypted PDF: a user password is required, so the content cannot be judged")
    if getattr(doc, "is_repaired", False):
        raise GateInput("truncated or damaged PDF: the reader had to repair its structure")
    if doc.page_count == 0:
        raise GateInput("no pages")
    return doc


def goto_links(page):
    return [l for l in page.get_links() if l.get("kind") == fitz.LINK_GOTO]


def catalog_value(doc, key: str) -> str:
    """A catalog key as object text — resolving an indirect reference (a valid PDF may use either)."""
    kind, val = doc.xref_get_key(doc.pdf_catalog(), key)
    if kind == "xref":
        return doc.xref_object(int(val.split()[0]))
    return val


def info_key(doc, key: str) -> str:
    """A key of the document information dictionary ('' when absent)."""
    kind, ref = doc.xref_get_key(-1, "Info")
    if kind != "xref":
        return ""
    kind, val = doc.xref_get_key(int(ref.split()[0]), key)
    return val.strip("()") if kind == "string" else ""


def source_stamp() -> tuple[str, str]:
    """(file name, sha256) of the source the gate measures copy fidelity against."""
    import hashlib
    return NS.SOURCE_HTML, hashlib.sha256(open(source_path(), "rb").read()).hexdigest()


# ---------------------------------------------------------------------------------------------------------
# Pixels: the page as a whole, not only the 32 button slots (H1/H3).
# ---------------------------------------------------------------------------------------------------------
def page_ink(page) -> tuple[float, list[float]]:
    """(ink share of the page, ink share per cell of a PAGE_INK_GRID x PAGE_INK_GRID grid).

    Ink = a pixel whose gray value differs from the page's median by more than SLOT_INK_CONTRAST. The median
    (not the mode) is used because a painted-over dark page flips its dominant colour — an attack must not be
    able to move the reference it is measured against.
    """
    from PIL import Image
    pm = page.get_pixmap(dpi=NS.PAGE_INK_DPI, colorspace=fitz.csGRAY, alpha=False)
    im = Image.frombytes("L", (pm.width, pm.height), pm.samples)
    bg = statistics.median(pm.samples)
    ink = im.point(lambda v: 255 if abs(v - bg) > NS.SLOT_INK_CONTRAST else 0)
    n = pm.width * pm.height
    cells = []
    g = NS.PAGE_INK_GRID
    for gy in range(g):
        for gx in range(g):
            c = ink.crop((gx * pm.width // g, gy * pm.height // g,
                          (gx + 1) * pm.width // g, (gy + 1) * pm.height // g))
            cells.append(c.histogram()[255] / (c.width * c.height))
    return ink.histogram()[255] / n, cells


def image_inventory(page) -> tuple[int, float]:
    """(distinct image objects on the page, share of the page under them capped at 1)."""
    xrefs = {im[0] for im in page.get_images()}
    area = sum(abs(r & page.rect) for im in page.get_images() for r in page.get_image_rects(im[0]))
    return len(xrefs), min(1.0, area / abs(page.rect))


def pdfium_texts(doc) -> list[str] | None:
    """Text of every page from PDFium (Chrome/Edge's engine), or None when it cannot be read."""
    try:
        import pypdfium2
        pd = pypdfium2.PdfDocument(doc.tobytes())
        return [pd[i].get_textpage().get_text_range() for i in range(len(pd))]
    except Exception:
        return None


NUMERAL_CHARS = frozenset("٠١٢٣٤٥٦٧٨٩0123456789")
NUMERAL_GAP_PT = 12          # two numerals further apart than this are two numerals, not one footer
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _digit_value(span) -> int | None:
    """The number this span PRINTS, read from where its digits are drawn.

    MuPDF may return an Arabic-Indic run reversed (measured on a number MuPDF itself wrote: ٢٠٢٦ → ٦٢٠٢).
    Deciding by «is the token — or its reverse — somewhere in PDFium's page text?» loses as soon as the page
    prints both: ١٢ in the footer and ٢١ in the body made the footer read 21 (B4). A numeral is written
    left-to-right in Arabic as well as in Latin, so sorting the span's digit glyphs by x gives the value
    whatever string the reader built. Two numerals in one span (a gap over NUMERAL_GAP_PT) are not a footer number.
    """
    text = "".join(c["c"] for c in span.get("chars", ())).strip()
    # A footer number is a numeral, not a number inside prose: the cover also prints «٤٫١ · نوفمبر ٢٠٢٦»
    # in the band, and reading the digits out of that sentence invented a footer 14 (measured). «²» passes
    # str.isdigit() and then breaks int(); the whitelist is the only answer that holds.
    if not text or any(ch not in NUMERAL_CHARS for ch in text):
        return None
    glyphs = list(span.get("chars", ()))
    if not glyphs:
        return None
    glyphs.sort(key=lambda c: c["bbox"][0])
    runs, cur = [], [glyphs[0]]
    for c in glyphs[1:]:
        if c["bbox"][0] - cur[-1]["bbox"][2] < NUMERAL_GAP_PT:      # same numeral
            cur.append(c)
        else:
            runs.append(cur); cur = [c]
    runs.append(cur)
    if len(runs) > 1:
        return None
    return int("".join(c["c"] for c in runs[0]).translate(AR_DIGITS))


def footer_numbers(page, limit: int | None = None) -> list[int]:
    """Digit spans inside the footer band, top to bottom — Latin or Arabic-Indic, in printed order.

    `limit` (usually the page count) drops numbers that cannot be a page number: the cover's year also
    sits in the band, and reading ٢٠٢٦ as a footer would invent a footer the document never printed.
    """
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                t = "".join(c["c"] for c in s.get("chars", ())).strip()
                if not t or not NS.FOOTER_Y_MIN <= s["bbox"][1] <= NS.FOOTER_Y_MAX:
                    continue
                v = _digit_value(s)
                if v is not None and (limit is None or v <= limit):
                    out.append(v)
    return out


def printed_counts(page) -> dict:
    """{'checks': N, 'mutations': M} as PRINTED on the page (visual order, Arabic-Indic aware).

    The number and its marker («فحصا» / «عطلا») share a line. Digits are rebuilt left-to-right from their
    positions, grouped into runs, and the run nearest the marker is the one that belongs to it — the page also
    prints standalone numerals, and grabbing every digit on the line would read «٣٢٣» instead of «٢٣».
    """
    out = {}
    for b in page.get_text("rawdict")["blocks"]:
        for line in b.get("lines", []):
            chars = [c for s in line["spans"] for c in s["chars"]]
            text = "".join(c["c"] for c in chars)
            for key, marker in (("checks", "فحصا"), ("mutations", "عطلا"), ("links", "رابطا")):
                if key in out or marker not in text:
                    continue
                # the marker may be split across spans (Chrome re-shapes Arabic), so locate it in the LINE text
                at = text.find(marker)
                mchars = chars[at:at + len(marker)]
                digits = sorted((c for c in chars if c["c"].isdigit()), key=lambda c: c["bbox"][0])
                if not digits:
                    continue
                runs, cur = [], [digits[0]]
                for c in digits[1:]:
                    if c["bbox"][0] - cur[-1]["bbox"][2] < NUMERAL_GAP_PT:      # same numeral
                        cur.append(c)
                    else:
                        runs.append(cur); cur = [c]
                runs.append(cur)
                mx = (mchars[0]["bbox"][0] + mchars[-1]["bbox"][2]) / 2
                near = min(runs, key=lambda r: min(abs(r[0]["bbox"][0] - mx), abs(r[-1]["bbox"][2] - mx)))
                out[key] = int("".join(c["c"] for c in near))
    return out


def version_spots_in_source() -> list[str]:
    """Every printed version in the source HTML, in document order (Arabic-Indic or Latin digits)."""
    return re.findall(r"الإصدار\s+([٠-٩0-9]+[٫.][٠-٩0-9]+)", source_text())


# ---------------------------------------------------------------------------------------------------------
# Stage-5 features: metadata/structure, read with pikepdf (the same library that wrote them).
# ---------------------------------------------------------------------------------------------------------
def pikepdf_open(doc):
    import io
    import pikepdf
    return pikepdf.open(io.BytesIO(doc.tobytes()))


def derived_page_labels(pdf) -> list[str] | None:
    """Labels the reader will show, derived from the RAW /Nums (pymupdf drops the prefix — spec §4.2)."""
    try:
        nums = pdf.Root.PageLabels.Nums
    except (AttributeError, KeyError):
        return None
    rules = [(int(nums[k]), nums[k + 1]) for k in range(0, len(nums), 2)]
    out = []
    for i in range(len(pdf.pages)):
        rule = None
        for start, d in rules:
            if start <= i:
                rule = (start, d)
        if rule is None:
            out.append(str(i + 1))
            continue
        start, d = rule
        if "/S" in d:
            style, st = str(d["/S"]), int(d.get("/St", 1))
            out.append(str(st + i - start) if style == "/D" else f"{style}{st + i - start}")
        else:
            out.append(str(d.get("/P", "")).strip("()"))
    return out


def named_destination_pages(pdf) -> dict[str, int]:
    """name -> 0-based page index, resolved from the /D array of each destination."""
    out = {}
    try:
        arr = pdf.Root.Names.Dests.Names
    except (AttributeError, KeyError):
        return out
    index = {page.obj.objgen: k for k, page in enumerate(pdf.pages)}
    for k in range(0, len(arr), 2):
        d = arr[k + 1]
        ref = d["/D"][0]
        out[str(arr[k])] = index.get(ref.objgen, -1)
    return out


def xmp_values(pdf) -> dict:
    with pdf.open_metadata() as m:
        return {k: m.get(k) for k in ("dc:title", "dc:creator", "dc:language", "xmp:CreatorTool",
                                      "pdf:Producer", "xmpMM:DocumentID")}


def output_intent_problems(pdf) -> list[str]:
    bad = []
    try:
        oi = pdf.Root.OutputIntents[0]
    except (AttributeError, KeyError, IndexError):
        return ["no /OutputIntents"]
    if str(oi.get("/S", "")) != "/GTS_PDFA1":
        bad.append(f"intent subtype {oi.get('/S')}")
    try:
        n = int(oi.DestOutputProfile.get("/N", 0))
        size = len(bytes(oi.DestOutputProfile.read_bytes()))
    except Exception:
        n, size = 0, 0
    if n not in (3, 4):
        bad.append(f"ICC /N={n}")
    if size < 1024:
        bad.append(f"ICC {size} bytes")
    for i, page in enumerate(pdf.pages):
        media = [float(v) for v in page.obj["/MediaBox"]]
        trim = page.obj.get("/TrimBox")
        bleed = page.obj.get("/BleedBox")
        if trim is None or bleed is None:
            bad.append(f"p{i+1} missing {'/TrimBox' if trim is None else '/BleedBox'}")
            continue
        trim = [float(v) for v in trim]
        bleed = [float(v) for v in bleed]
        inside = lambda outer, inner: outer[0] <= inner[0] and outer[1] <= inner[1] \
            and inner[2] <= outer[2] and inner[3] <= outer[3]
        if not inside(media, bleed):
            bad.append(f"p{i+1} BleedBox outside MediaBox")
        if not inside(bleed, trim):
            bad.append(f"p{i+1} TrimBox outside BleedBox")
    return bad


def attachment_problems(pdf) -> list[str]:
    bad, got = [], {}
    declared = getattr(NS, "ATTACHMENT_FILES", None)
    if not declared:
        return ["the spec declares no ATTACHMENT_FILES: a file cannot be judged on a list the code assumes"]
    want = [f[0] for f in declared]
    for name, spec in pdf.attachments.items():
        try:
            data = spec.get_file().read_bytes()
        except Exception:
            data = b""
        if not data:
            bad.append(f"{name}: empty")
        if "/AFRelationship" not in spec.obj:
            bad.append(f"{name}: no /AFRelationship")
        got[name] = len(data)
    if sorted(got) != sorted(want):
        bad.append(f"attachments {sorted(got)}, expected {sorted(want)}")
    return bad



# ---------------------------------------------------------------------------------------------------------
# Icons (unchanged behaviour; H2 turns a missing input into a failure)
# ---------------------------------------------------------------------------------------------------------
def _icon_norm(mask):
    """Ink mask (PIL 'L', ink = 255) -> 48x48, cropped to the ink, thickened one pixel: position and scale drop out."""
    from PIL import Image, ImageFilter
    box = mask.getbbox()
    if box is None:
        return None
    m = mask.crop(box).resize((48, 48), Image.BILINEAR).filter(ImageFilter.MaxFilter(3))
    return m.point(lambda v: 255 if v > 96 else 0)


def source_icons():
    """The nav icons as the source HTML draws them: one list of normalised masks per nav strip, left to right."""
    from PIL import Image
    strips = []
    for nav in re.findall(r'<div class="%s">(.*?)</div>' % re.escape(NS.NAV_CLASS), source_text(), re.S):
        row = []
        for svg in re.findall(r"<svg.*?</svg>", nav, re.S):
            svg = re.sub(r'stroke="#[0-9a-fA-F]+"', 'stroke="#000000"', svg)
            px = fitz.open(stream=svg.encode(), filetype="svg")[0].get_pixmap(dpi=600, colorspace=fitz.csGRAY, alpha=False)
            row.append(_icon_norm(Image.frombytes("L", (px.width, px.height), px.samples).point(lambda v: 255 if v < 128 else 0)))
        strips.append(row)
    return strips


def icon_iou(pm, ref) -> float:
    """Shape agreement between a rendered slot (gray pixmap) and the source icon: intersection over union."""
    from PIL import Image
    bg = statistics.median(pm.samples)
    top = max(abs(v - bg) for v in pm.samples)        # half the strongest contrast: background art specks stay out
    got = _icon_norm(Image.frombytes("L", (pm.width, pm.height), pm.samples).point(lambda v: 255 if abs(v - bg) > max(NS.SLOT_INK_CONTRAST, top / 2) else 0))
    if got is None or ref is None:
        return 0.0
    a, b = got.tobytes(), ref.tobytes()
    return sum(1 for x, y in zip(a, b) if x and y) / max(1, sum(1 for x, y in zip(a, b) if x or y))


def slot_drawings(doc) -> list[str]:
    """Drawings or images whose rectangle sits INSIDE a navigation slot (a page-wide fill does not).

    Criterion for a print copy: no icon was drawn. The rectangle must be contained (0.5 pt slack), not
    merely intersect: every page paints a background that intersects all four slots. Kept as its own
    predicate so the self-test can exercise it on a page it builds, not only through a whole document.
    """
    drawn = []
    for i in range(doc.page_count):
        page = doc[i]
        rects = [fitz.Rect(g["rect"]) for g in page.get_drawings()]
        for xref in {im[0] for im in page.get_images()}:
            rects += [fitz.Rect(r) for r in page.get_image_rects(xref)]
        for role, x in NS.SLOTS.items():
            slot = fitz.Rect(x, NS.NAV_Y0, x + NS.NAV_W, NS.NAV_Y1)
            inside = [r for r in rects if r.x0 >= slot.x0 - 0.5 and r.x1 <= slot.x1 + 0.5
                      and r.y0 >= slot.y0 - 0.5 and r.y1 <= slot.y1 + 0.5]
            if inside:
                r = inside[0]
                drawn.append(f"p{i+1} {role}: a drawing {tuple(round(v, 1) for v in r)} sits in the slot")
    return drawn


def blank_pages(doc, body):
    """Pages of `body` far below the median text that images do not excuse -> (blank, low, median).

    A page is excused only when images cover BLANK_EXEMPT_IMAGE_COVER of it; "has an image" is not enough."""
    lens = {i: len("".join(doc[i].get_text().split())) for i in body}
    med = statistics.median(lens.values())
    low = {i: image_inventory(doc[i])[1] for i, n in lens.items() if n < 0.15 * med}
    blank = [f"p{i+1}({lens[i]} chars, images cover {c:.0%})" for i, c in low.items() if c < NS.BLANK_EXEMPT_IMAGE_COVER]
    return blank, low, med


def art_dpi_problems(doc) -> list[str]:
    """Art serving >ART_PAGE_SHARE of a page must not exceed ART_MAX_DPI; declared pages must match."""
    bad = []
    for i, page in enumerate(doc):
        for xref in {im[0] for im in page.get_images()}:
            info = doc.extract_image(xref)
            for r in page.get_image_rects(xref):
                if abs(r) < NS.ART_PAGE_SHARE * abs(page.rect):
                    continue
                dpi = min(info["width"] / (r.width / 72), info["height"] / (r.height / 72))
                declared = NS.ART_DPI_DECLARED.get(i)
                if declared is not None:
                    if abs(dpi - declared) > 3:
                        bad.append(f"p{i+1}: {dpi:.0f} dpi, declared {declared}")
                elif dpi > NS.ART_MAX_DPI + 1:
                    bad.append(f"p{i+1}: {dpi:.0f} dpi > {NS.ART_MAX_DPI}")
    return bad


def conformance_flavour(declared: dict) -> str | None:
    """veraPDF flavour of a declared identifier: PDF/A part+conformance -> "3b", PDF/UA-1 -> "ua1"."""
    if declared.get("pdfaid:part"):
        conformance = str(declared.get("pdfaid:conformance", "")).strip().lower()
        return f"{declared['pdfaid:part']}{conformance}" if conformance else None
    if str(declared.get("pdfuaid:part", "")) == "1":
        return "ua1"
    return None


def pdfua_problems(pdf) -> list[str]:
    """Structure floor, plus the claim rule: an identifier is allowed only when the declared baseline is empty.

    A conformance identifier is a CLAIM, not a decoration. The document may declare PDF/A-3b only if
    the document's `VERAPDF_BASELINE` records ZERO failing rules for that flavour; the gate reads the claim from XMP and
    the evidence from the baseline, so a claim can never outlive the failures it was allowed to drop.
    """
    import tomllib
    bad = []
    claim = getattr(NS, "CONFORMANCE", None)
    with pdf.open_metadata() as m:
        declared = {k: m.get(k) for k in ("pdfuaid:part", "pdfaid:part", "pdfaid:conformance") if m.get(k)}
        if claim:
            if declared != claim:
                bad.append(f"conformance claim {declared or 'absent'} != spec {claim}")
            # every claimed identifier needs its OWN measured, EMPTY baseline: a PDF/UA claim is never
            # checked against PDF/A's evidence
            flavours = []
            if declared.get("pdfaid:part"):
                conf = str(declared.get("pdfaid:conformance", "")).strip().lower()
                flavours.append(f"{declared['pdfaid:part']}{conf}" if conf else "")
            if str(declared.get("pdfuaid:part", "")) == "1":
                flavours.append("ua1")
            flavours = [f for f in flavours if f]
            if not flavours:
                bad.append(f"cannot map the claim {declared} to a veraPDF flavour: it cannot be checked")
            try:
                baseline_path = os.path.join(PROJ, NS.VERAPDF_BASELINE)
            except AttributeError:
                raise SystemExit(f"{NS.__name__} declares no VERAPDF_BASELINE — the baseline is per document")
            try:
                base = tomllib.load(open(baseline_path, "rb"))
            except (OSError, tomllib.TOMLDecodeError) as e:
                bad.append(f"cannot read the baseline: {type(e).__name__}")
            else:
                # fail closed: each flavour must be measured, present, and empty
                for flavour in flavours:
                    if flavour not in base.get("flavours", []):
                        bad.append(f"{flavour} is not a measured flavour in {os.path.basename(baseline_path)}")
                    if flavour not in base or "failing" not in base[flavour]:
                        bad.append(f"the baseline has no [{flavour}].failing list: the claim cannot be checked")
                    elif base[flavour]["failing"]:
                        bad.append(f"{flavour} claimed while the baseline still lists {base[flavour]['failing']}")
        elif declared:
            bad.append(f"{declared} claimed without conformance")
    cat = pdf.Root
    if "/StructTreeRoot" not in cat:
        bad.append("no StructTreeRoot")
    elif "/ParentTree" not in cat.StructTreeRoot:
        bad.append("StructTreeRoot has no ParentTree")
    if str(cat.get("/Lang", "")).strip("()") != NS.LANG:
        bad.append("Lang")
    if "/MarkInfo" not in cat:
        bad.append("no MarkInfo")
    vp = cat.get("/ViewerPreferences")
    if vp is None or not vp.get("/DisplayDocTitle"):
        bad.append("DisplayDocTitle")
    # The UA floor applies to a file that CLAIMS PDF/UA (or a spec that opted in). A document that makes
    # no accessibility claim is judged by PDF/A and by its own declared checks, not by a rule its producer
    # never promised to meet.
    if str(cat.get("/Lang", "")).strip("()") == NS.LANG and (
            getattr(NS, "PDFUA", False) or str(declared.get("pdfuaid:part", "")) == "1"):
        mark = cat.get("/MarkInfo")
        if mark is not None and mark.get("/Suspects") is True:   # absent means false (Table 321)
            bad.append("MarkInfo /Suspects is not false: the file admits its own tagging is unreliable")
        bad += untagged_runs(pdf)
        bad += figure_alt_problems(pdf)
    return bad


def _parent_tree(pdf) -> dict:
    """Flatten /ParentTree, following /Kids: large files keep their numbers in intermediate nodes."""
    table = {}

    def walk(node):
        if not isinstance(node, pikepdf.Dictionary):
            return
        nums = node.get("/Nums")
        if nums is not None:
            for i in range(0, len(nums) - 1, 2):
                table[int(str(nums[i]))] = nums[i + 1]
        for kid in node.get("/Kids", []):
            walk(kid)

    try:
        walk(pdf.Root.StructTreeRoot["/ParentTree"])
    except (AttributeError, KeyError, TypeError):
        return {}
    return table


from pdfops import PAINT_OPS, artifact_shows, form_resolver, model_stats, outside_bands, props_of  # noqa: E402
from gate_policy import LINE_ORDER_FLOOR  # noqa: E402
import chrome_pin  # noqa: E402  (the engine every number here was measured on)


def untagged_runs(pdf) -> list[str]:
    """The file's own 7.1 floor: every painted thing is an Artifact or carries an MCID that resolves.

    veraPDF proves this from outside; this check proves it from inside, so a regression is caught by the
    gate even on a machine without veraPDF installed. Fail closed: an unparsable stream is a failure.
    """
    bad = []
    table = _parent_tree(pdf)
    for pi, page in enumerate(pdf.pages):
        sp = page.obj.get("/StructParents")
        arr = table.get(int(sp)) if sp is not None else None
        try:
            instrs = list(pikepdf.parse_content_stream(page))
        except Exception as e:                       # noqa: BLE001 — unreadable means unproven
            bad.append(f"p{pi+1}: content stream unreadable ({type(e).__name__})")
            continue
        depth, loose = 0, 0
        gs = bt = 0                 # q/Q and BT/ET nesting, tracked so an artifact cannot straddle them
        art_open = False
        art_marks = []              # (gs, bt) at the moment each top-level artifact opened
        for ins in instrs:
            op = str(ins.operator)
            if op in ("BMC", "BDC"):
                if depth == 0:
                    props = {}
                    if op == "BDC" and len(ins.operands) > 1 and isinstance(ins.operands[1], pikepdf.Dictionary):
                        props = ins.operands[1]
                    if str(ins.operands[0]) == "/Artifact":
                        art_open = True
                        art_marks.append((gs, bt))
                    else:
                        mcid = props.get("/MCID")
                        if mcid is None:
                            loose += 1
                        elif arr is None or int(mcid) >= len(arr):
                            loose += 1
                depth += 1
            elif op == "EMC":
                depth = max(0, depth - 1)
                if depth == 0 and art_open:
                    art_open = False
                    opened_gs, opened_bt = art_marks.pop() if art_marks else (gs, bt)
                    # the producer's rule, now enforced: an artifact may not wrap q/Q or BT/ET
                    if (opened_gs, opened_bt) != (gs, bt):
                        bad.append(f"p{pi+1}: an artifact spans a graphics/text state container")
            elif op == "q":
                gs += 1
            elif op == "Q":
                gs = max(0, gs - 1)
            elif op == "BT":
                bt += 1
            elif op == "ET":
                bt = max(0, bt - 1)
            elif depth == 0 and op in PAINT_OPS:
                loose += 1
        if loose:
            bad.append(f"p{pi+1}: {loose} untagged run(s)")
    return bad


def figure_alt_problems(pdf) -> list[str]:
    """A Figure without /Alt is an image a screen reader must skip or guess."""
    bad = []

    def walk(node):
        if isinstance(node, pikepdf.Array):
            for x in node:
                walk(x)
            return
        if not isinstance(node, pikepdf.Dictionary):
            return
        alt = str(node.get("/Alt", "")).strip() or str(node.get("/ActualText", "")).strip()
        if str(node.get("/S", "")) == "/Figure" and not alt:
            bad.append(f"Figure {node.objgen} has no /Alt")
        if "/K" in node:
            walk(node["/K"])

    st = pdf.Root.get("/StructTreeRoot")
    if st is not None:
        walk(st.get("/K"))
    return bad


def acroform_problems(pdf) -> list[str]:
    """Every declared field must exist, on its page, at its rect, named as the spec says, and be ANNOUNCED.

    A field that is drawn but not reachable from the structure tree (no /StructParent -> /Form element ->
    OBJR pointing at THIS widget) is invisible to a screen reader; the check resolves the OBJR, not the
    element's type name alone.
    """
    bad = []
    import spec_loader as _sl
    if _sl.declares_no_acroform(NS):
        return [] if "/AcroForm" not in pdf.Root else \
               ["/AcroForm present although the spec declares no fields (a filled copy must not leave widgets)"]
    if "/AcroForm" not in pdf.Root:
        return ["no /AcroForm"]
    fields = pdf.Root.AcroForm.get("/Fields", [])
    if not len(fields):
        return ["AcroForm has no fields"]
    want = getattr(NS, "ACROFORM_FIELDS", None)
    if want and len(fields) != len(want):
        bad.append(f"{len(fields)} fields, expected {len(want)}")
    try:
        nums = list(pdf.Root.StructTreeRoot["/ParentTree"]["/Nums"])
        tree = {int(str(nums[i])): nums[i + 1] for i in range(0, len(nums), 2)}
    except (AttributeError, KeyError):
        return bad + ["no ParentTree: widgets cannot be announced"]

    def objs(val):
        return list(val) if isinstance(val, pikepdf.Array) else ([val] if val is not None else [])

    widgets = {}                                    # /T -> (page index, annotation)
    for pi, page in enumerate(pdf.pages):
        page_widgets = [a for a in page.obj.get("/Annots", []) if str(a.get("/Subtype")) == "/Widget"]
        if page_widgets and str(page.obj.get("/Tabs", "")) != "/S":
            bad.append(f"p{pi+1} has widgets but no /Tabs /S: the tab order is not the structure order")
        for a in page_widgets:
            widgets[str(a.get("/T", ""))] = (pi, a)
            sp = a.get("/StructParent")
            if sp is None:
                bad.append(f"p{pi+1} widget without /StructParent")
                continue
            forms = [v for v in objs(tree.get(int(sp))) if getattr(v, "get", lambda k, d=None: None)("/S") == pikepdf.Name.Form]
            if not forms:
                bad.append(f"p{pi+1} widget /StructParent {sp} does not resolve to a /Form element")
                continue
            objr = forms[0].get("/K")
            obj = objr.get("/Obj") if hasattr(objr, "get") else None
            if obj is None or obj.objgen != a.objgen:
                bad.append(f"p{pi+1} {str(a.get('/T',''))}: the /Form element's OBJR does not point at this widget")

    for f in (want or []):
        got = widgets.get(f["name"])
        if got is None:
            bad.append(f"field {f['name']!r} missing (has {sorted(widgets)})")
            continue
        pi, a = got
        if pi != f["page"]:
            bad.append(f"field {f['name']!r} on p{pi+1}, expected p{f['page']+1}")
        rect = [float(v) for v in a["/Rect"]]
        if any(abs(x - y) > 1.5 for x, y in zip(rect, f["rect"])):
            bad.append(f"field {f['name']!r} rect {[round(v) for v in rect]} != spec {[round(v) for v in f['rect']]}")
    if want:
        extra = sorted(set(widgets) - {f["name"] for f in want})
        if extra:
            bad.append(f"undeclared fields {extra}")

    for f in fields:
        tu = str(f.get("/TU", ""))
        if not tu or not any("\u0600" <= ch <= "\u06ff" for ch in tu):
            bad.append("field without an Arabic /TU")
        if not str(f.get("/DA", "")).strip():
            bad.append("field without /DA")
    dr = pdf.Root.AcroForm.get("/DR", {})
    if not dr.get("/Font", {}):
        bad.append("AcroForm /DR has no embedded font")
    for _, f in (dr.get("/Font", {}) or {}).items():
        base = str(f.get("/BaseFont", ""))
        # A page font is a subset of the words printed on that page and carries no ToUnicode: a field that
        # borrows one cannot display a letter the page never used (the reader types «ملاحظات» and sees boxes).
        if "+" in base:
            bad.append(f"/DR font {base} is a subset: typed letters may be missing")
        if "/ToUnicode" not in f:
            bad.append(f"/DR font {base} has no ToUnicode: the value cannot be copied")
        if not f.get("/DescendantFonts"):
            bad.append(f"/DR font {base} is not a Type0/CID font")
    return bad


def link_tagging_problems(pdf) -> list[str]:
    bad, count = [], 0
    try:
        nums = list(pdf.Root.StructTreeRoot["/ParentTree"]["/Nums"])
        tree = {int(str(nums[i])): nums[i + 1] for i in range(0, len(nums), 2)}
    except (AttributeError, KeyError):
        tree = {}
    for i, page in enumerate(pdf.pages):
        for a in page.obj.get("/Annots", []):
            if str(a.get("/Subtype")) != "/Link":
                continue
            count += 1
            c = str(a.get("/Contents", ""))
            if not c or not any("\u0600" <= ch <= "\u06ff" for ch in c):
                bad.append(f"p{i+1} link without an Arabic /Contents")
            sp = a.get("/StructParent")
            if sp is None:
                bad.append(f"p{i+1} link without /StructParent")
                continue
            val = tree.get(int(sp))
            elems = list(val) if isinstance(val, pikepdf.Array) else ([val] if val is not None else [])
            ok = False
            for e in elems:
                if getattr(e, "get", lambda k, d=None: None)("/S") != pikepdf.Name.Link:
                    continue
                objr = e.get("/K")
                obj = objr.get("/Obj") if hasattr(objr, "get") else None
                if obj is not None and obj.objgen == a.objgen:
                    ok = True
            if not ok:
                bad.append(f"p{i+1} link /StructParent {sp} does not resolve to a /Link element holding this annot")
    if count != NS.EXPECTED_LINKS:
        bad.append(f"{count} links, expected {NS.EXPECTED_LINKS}")
    # A generic name on every row is a label in name only: the destination must be announced per row.
    for pi, key in ((NS.CONTENTS, "CONTENTS_LABELS"), (NS.REF_PAGE, "REF_LABELS")):
        want = getattr(NS, key, None)
        if not want:
            continue
        h = float(pdf.pages[pi].obj["/MediaBox"][3])
        rows = sorted([a for a in pdf.pages[pi].obj.get("/Annots", []) if str(a.get("/Subtype")) == "/Link"
                       and float(a["/Rect"][3]) <= h - 70],
                      key=lambda a: -float(a["/Rect"][3]))
        got = [str(a.get("/Contents", "")) for a in rows]
        if got != list(want):
            bad.append(f"p{pi+1} link names {got[:2]}... != spec {list(want)[:2]}...")
    return bad


def gate(doc) -> list[str]:
    fails: list[str] = []               # local: two gates may run in one process
    ran: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        print(("PASS " if ok else "FAIL ") + name + " - " + detail)
        ran.append(name)
        if not ok:
            fails.append(name)

    def final_count() -> None:
        # The gate counts its own checks against the declared number, so adding a check without updating
        # nav_spec and the printed page cannot pass unnoticed (H9).
        declared = set(spec_base.CHECK_NAMES)
        here = set(ran) | {"gate-count"}
        drift = sorted(here ^ declared)
        check("gate-count", not drift, f"{len(ran) + 1} checks (declared {len(declared)})"
              + ("; the set drifted: " + ", ".join(drift[:4]) if drift else "; same set"))

    # 1. page count = intended build
    check("pages", doc.page_count == NS.PAGES, f"{doc.page_count} (expected {NS.PAGES})")
    if doc.page_count != NS.PAGES:
        final_count()
        return fails  # every later check maps by page index; stop rather than report noise

    # 2. viewer preferences: single page + right-to-left reading
    layout = doc.xref_get_key(doc.pdf_catalog(), "PageLayout")[1]
    check("single-page", layout == "/SinglePage", layout)
    vp = " ".join(catalog_value(doc, "ViewerPreferences").split())
    check("rtl-direction", "/Direction/R2L" in vp.replace(" ", ""), vp[:70])

    # 3. nav buttons: each slot -> its own expected target; no self-links; no strip links elsewhere
    bad = []
    for i, page in enumerate(doc):
        strip = [l for l in goto_links(page) if abs(l["from"].y0 - NS.NAV_Y0) < 2]
        if i not in NS.NAV_PAGES:
            if strip:
                bad.append(f"p{i+1}: {len(strip)} unexpected nav links")
            continue
        for role, x in NS.SLOTS.items():
            hits = [l for l in strip if abs(l["from"].x0 - x) < 2]
            want = NS.nav_target(role, i)
            if len(hits) != 1:
                bad.append(f"p{i+1} {role}: {len(hits)} links in slot")
            elif hits[0]["page"] != want:
                bad.append(f"p{i+1} {role}: ->{hits[0]['page']+1} want {want+1}")
            elif want == i:
                bad.append(f"p{i+1} {role}: self-link")
        if len(strip) != len(NS.SLOTS):
            bad.append(f"p{i+1}: {len(strip)} strip links, want {len(NS.SLOTS)}")
    check("nav-buttons", not bad, "; ".join(bad[:4]) or f"{len(NS.NAV_PAGES)} pages x {len(NS.SLOTS)} slots")

    # 3b. render: every nav slot must show ink ON THE PAGE, and the icon the source draws there.
    # A missing source icon is a FAILURE, never a silent pass: a check that lost its input would otherwise
    # print "shape IoU 0.00-0.00" inside a PASS (H2).
    if not getattr(NS, "NAV_VISIBLE", True):
        # A print copy must draw no icon. Proven FROM THE PAGE, not from the markup this gate derives:
        # that derivation removes the strip by construction, so a check on it could never fail.
        drawn = slot_drawings(doc)
        check("render", not drawn, "; ".join(drawn[:4]) or
              f"print copy: {doc.page_count} pages, no drawing or image inside a strip slot")
    else:
        dead, seen, ious = [], [], []
        order = sorted(NS.SLOTS, key=NS.SLOTS.get)  # the HTML lists a strip's icons left to right
        try:
            icons = source_icons()
        except Exception as e:                      # a check that cannot read what it needs fails
            icons = []; dead.append(f"cannot render the source icons: {e}")
        want_strips, want_slots = NS.EXPECTED["source_strips"], NS.EXPECTED["slots_per_strip"]
        if not icons:
            dead.append(f"source icons not found in {NS.SOURCE_HTML}: the gate cannot verify the button shapes")
        elif (len(icons), {len(r) for r in icons}) != (want_strips, {want_slots}):
            dead.append(f"source HTML has {[len(r) for r in icons]} icons per strip, expected {want_strips} x {want_slots}")
            icons = []
        for n, i in enumerate(NS.NAV_PAGES):
            for role, x in NS.SLOTS.items():
                clip = fitz.Rect(x + 2, NS.NAV_Y0 + 2, x + NS.NAV_W - 2, NS.NAV_Y1 - 2)
                pm = doc[i].get_pixmap(dpi=300, clip=clip, colorspace=fitz.csGRAY)
                px = pm.samples
                bg = statistics.median(px)
                on = [k for k, v in enumerate(px) if abs(v - bg) > NS.SLOT_INK_CONTRAST]
                ink = len(on) / len(px)
                seen.append(ink)
                if not NS.SLOT_INK_MIN <= ink <= NS.SLOT_INK_MAX:
                    dead.append(f"p{i+1} {role}: ink {ink:.2f}")
                    continue
                # the right icon, not just some ink: ink share, centre of mass and spread against the icon's signature
                xs = [k % pm.stride for k in on]; ys = [k // pm.stride for k in on]
                sig = (ink, statistics.fmean(xs) / pm.width - 0.5, statistics.fmean(ys) / pm.height - 0.5,
                       statistics.pstdev(xs) / pm.width, statistics.pstdev(ys) / pm.height)
                if any(abs(a - b) > NS.SLOT_SHAPE_TOL for a, b in zip(sig, NS.SLOT_SHAPE[role])):
                    dead.append(f"p{i+1} {role}: not its icon - " + " ".join(f"{a:+.2f}" for a in sig) +
                                " vs " + " ".join(f"{b:+.2f}" for b in NS.SLOT_SHAPE[role]))
                    continue
                # the same shape as the icon the source draws there (the signature alone is five numbers: a striped
                # rectangle can match them all). With no source icons the check has already failed above: never
                # compare against nothing, and never let that path reach a PASS.
                if icons:
                    iou = icon_iou(pm, icons[n][order.index(role)]); ious.append(iou)
                    if iou < NS.SLOT_ICON_MIN_IOU:
                        dead.append(f"p{i+1} {role}: shape differs from the source icon (IoU {iou:.2f}, min {NS.SLOT_ICON_MIN_IOU})")
        check("render", not dead, "; ".join(dead[:6]) or
              f"{len(NS.NAV_PAGES)} pages x {len(NS.SLOTS)} slots: each icon drawn in its own slot (ink {min(seen):.2f}-{max(seen):.2f}, shape IoU {min(ious):.2f}-{max(ious):.2f})")


    # 3c. images: the page must carry the images it is supposed to carry (H3). A divider whose art vanished
    # while its text survived passes every text check — only an inventory of the page can see it.
    img_bad = []
    for i, page in enumerate(doc):
        n_img, cover = image_inventory(page)
        want_n, want_cover = NS.IMAGE_PAGES.get(i, (0, 0.0))
        if n_img != want_n:
            img_bad.append(f"p{i+1}: {n_img} images, expected {want_n}")
        elif abs(cover - want_cover) > NS.IMAGE_COVER_TOL:
            img_bad.append(f"p{i+1}: image cover {cover:.3f}, expected {want_cover:.3f}")
    check("page-images", not img_bad, "; ".join(img_bad[:4]) or
          ", ".join(f"p{i+1} {NS.IMAGE_PAGES[i][0]} img ({NS.IMAGE_PAGES[i][1]:.0%})" for i in sorted(NS.IMAGE_PAGES)))

    # 3d. ink: the page as a whole (H1). Reads every pixel of all 12 pages at 72 dpi against a measured
    # table (scalar + grid). A whiteout, a lost cover, a dropped divider: all of them change this.
    ink_bad, worst, retention = [], 0.0, 1.0
    for i, page in enumerate(doc):
        frac, cells = page_ink(page)
        want = NS.PAGE_INK.get(i)
        if want is None:
            ink_bad.append(f"p{i+1}: no measured baseline (run scripts/calibrate.py)")
            continue
        want_frac, want_cells = want
        d = abs(frac - want_frac)
        worst = max(worst, d)
        if d > NS.PAGE_INK_TOL:
            ink_bad.append(f"p{i+1} ink {frac:.4f} vs {want_frac:.4f}")
            continue
        for k, (got, want) in enumerate(zip(cells, want_cells)):
            if abs(got - want) > NS.PAGE_INK_TOL:
                ink_bad.append(f"p{i+1} cell {k//NS.PAGE_INK_GRID},{k%NS.PAGE_INK_GRID} {got:.3f} vs {want:.3f}")
                break
            if want >= NS.PAGE_INK_CELL_FLOOR:
                r = got / want
                retention = min(retention, r)
                if r < NS.PAGE_INK_MIN_RETENTION:
                    ink_bad.append(f"p{i+1} cell {k//NS.PAGE_INK_GRID},{k%NS.PAGE_INK_GRID} kept {r:.0%} of {want:.3f}")
                    break
    check("page-ink", not ink_bad, "; ".join(ink_bad[:4]) or
          f"{NS.PAGES} pages, max |d| {worst:.4f} (tol {NS.PAGE_INK_TOL}), min cell retention {retention:.2f}")

    # 4. outline = spec (titles, levels, pages)
    toc = doc.get_toc()
    check("outline", toc == NS.TOC, f"{len(toc)} entries (expected {len(NS.TOC)})")

    # 5. contents page: clickable rows top-to-bottom -> spec targets, and printed page numbers equal them
    rows = sorted(goto_links(doc[NS.CONTENTS]), key=lambda l: l["from"].y0)
    got = [l["page"] for l in rows]
    check("contents-links", got == NS.TOC_ROWS, f"{[g+1 for g in got]} (expected {[t+1 for t in NS.TOC_ROWS]})")
    printed = printed_page_numbers(doc[NS.CONTENTS])
    want = [t + 1 for t in NS.TOC_ROWS]
    outline_pages = {e[2] for e in NS.TOC}
    check("contents-numbers", printed == want and set(want) <= outline_pages,
          f"printed {printed} vs links/outline {want}" if printed else "could not parse printed numbers")

    # 5b. footers: the printed page number = the page's own index (H8). The guide DECLARES Latin footer
    # numbers; a declaration with no check is a claim that rots silently. The value comes from the drawn
    # position of each digit (B4), not from which token happens to appear in another reader's text.
    texts = pdfium_texts(doc)
    foot_bad = []
    for i, page in enumerate(doc):
        got_nums = footer_numbers(page, limit=doc.page_count)
        want_num = NS.FOOTER.get(i)
        if want_num is None:
            if got_nums:
                foot_bad.append(f"p{i+1}: unexpected footer {got_nums}")
        elif got_nums != [want_num]:
            foot_bad.append(f"p{i+1}: footer {got_nums or 'missing'} vs {want_num}")
    check("footer-numbers", not foot_bad, "; ".join(foot_bad[:5]) or
          f"{len(NS.FOOTER)} pages print their own number, {len(NS.PAGE_INK) - len(NS.FOOTER)} print none")

    # 5c. stage-5 features (features.toml): every declared feature must exist and be right. A feature
    # that was never checked is a feature that can vanish in the next refactor.
    try:
        pdf = pikepdf_open(doc)
    except Exception as e:
        pdf = None
        for name in ("page-labels", "named-destinations", "xmp", "output-intent", "attachments"):
            check(name, False, f"could not open with pikepdf: {e}")
    if pdf is not None:
        # page labels: derive what a reader will show, from the RAW /Nums
        want_labels = []
        for i in range(NS.PAGES):
            rule = None
            for start, style, value in NS.PAGE_LABELS:
                if start <= i:
                    rule = (start, style, value)
            if rule is None:
                want_labels.append(str(i + 1))
            elif rule[1] is None:
                want_labels.append(rule[2])
            else:
                want_labels.append(str(rule[2] + i - rule[0]))
        got_labels = derived_page_labels(pdf)
        check("page-labels", got_labels == want_labels,
              f"labels {got_labels[:3]}...{got_labels[-2:]}" if got_labels else "no /PageLabels")

        dests = named_destination_pages(pdf)
        dest_bad = [f"{n}: {dests.get(n, 'missing')} vs {p}" for n, p in NS.DEST_NAMES if dests.get(n) != p]
        check("named-destinations", not dest_bad and len(dests) == len(NS.DEST_NAMES),
              "; ".join(dest_bad[:4]) or f"{len(dests)} names resolve to their pages")

        x = xmp_values(pdf)
        lang = x.get("dc:language")
        langs = [str(v).lower() for v in (lang if isinstance(lang, (list, tuple, set)) else [lang])]
        x_bad = [k for k, ok in (
            ("dc:title", bool(x.get("dc:title")) and NS.GUIDE_VERSION_AR in str(x.get("dc:title"))),
            ("dc:creator", bool(x.get("dc:creator"))),
            ("dc:language", NS.XMP_LANGUAGE in langs),
            ("xmp:CreatorTool", bool(x.get("xmp:CreatorTool"))),
            ("pdf:Producer", bool(x.get("pdf:Producer"))),
            ("xmpMM:DocumentID", bool(x.get("xmpMM:DocumentID"))),
        ) if not ok]
        check("xmp", not x_bad, "missing/wrong: " + ", ".join(x_bad) if x_bad else
              f"6 fields, language {sorted(langs)}")

        oi_bad = output_intent_problems(pdf)
        check("output-intent", not oi_bad, "; ".join(oi_bad[:4]) or
              f"GTS_PDFA1 sRGB, Trim/Bleed inside MediaBox on {len(pdf.pages)} pages")

        att_bad = attachment_problems(pdf)
        check("attachments", not att_bad, "; ".join(att_bad[:4]) or
              ", ".join(f"{n} ({len(s.get_file().read_bytes())} B)" for n, s in pdf.attachments.items()))
        art_bad = art_dpi_problems(doc)
        check("art-dpi", not art_bad, "; ".join(art_bad[:4]) or
              f"page art <= {NS.ART_MAX_DPI} dpi, declared pages match")

        ua_bad = pdfua_problems(pdf)
        claim = getattr(NS, "CONFORMANCE", None)
        detail = (f"claim {claim} checked against an empty 3b baseline" if claim
                  else "no conformance claim") + "; ParentTree, Lang, MarkInfo, DisplayDocTitle"
        check("pdfua", not ua_bad, "; ".join(ua_bad[:4]) or detail)

        form_bad = acroform_problems(pdf)
        n_fields = len(getattr(NS, "ACROFORM_FIELDS", [1]))
        check("acroform", not form_bad, "; ".join(form_bad[:3]) or
              f"{n_fields} field(s): Arabic /TU, /DA, embedded font in /DR, /StructParent -> /Form")

        link_bad = link_tagging_problems(pdf)
        check("link-tagging", not link_bad, "; ".join(link_bad[:4]) or
              f"{NS.EXPECTED_LINKS} links: Arabic /Contents, /StructParent, /Link element")
        pdf.close()


    # 6. external links on the references page
    uris = [l.get("uri") for l in sorted(doc[NS.REF_PAGE].get_links(), key=lambda l: l["from"].y0)
            if l.get("kind") == fitz.LINK_URI]
    check("ref-links", uris == NS.REF_URLS, f"{len(uris)} URIs")

    # 7. fonts: house family only; the basmala page may add the macOS vocalisation face
    foreign = []
    vocalised_pages = set(getattr(NS, "VOCALISED_PAGES", {NS.BASMALA}))
    for i, page in enumerate(doc):
        allowed_extra = NS.BASMALA_FACES if i in vocalised_pages else set()
        for f in page.get_fonts():
            name = f[3].split("+")[-1]
            if not name:
                foreign.append(f"p{i+1}:<unnamed {f[1]}>")
            elif not name.startswith(NS.HOUSE_FONT_PREFIX) and not any(name.startswith(a) for a in allowed_extra):
                foreign.append(f"p{i+1}:{name}")
    check("fonts", not foreign, ", ".join(sorted(set(foreign))[:6]) or f"only {NS.HOUSE_FONT_PREFIX}* (+ {'/'.join(sorted(NS.BASMALA_FACES))} on the basmala page)")

    # 8. title metadata carries the guide version, and the cover prints the same one
    # (the PDFium texts were read once at 5b — same call, not a second extraction)
    title = (doc.metadata or {}).get("title", "")
    ver = f"الإصدار {NS.GUIDE_VERSION_AR}"
    want_title = f"{getattr(NS, 'DOC_TITLE', 'معيار إنتاج ملفات PDF — دليل المعيار')} · {ver}"
    cover = " ".join(texts[NS.COVER].split()) if texts else ""
    on_cover = ver in cover
    check("title", title.strip() == want_title and on_cover,
          title[:70] + ("" if title.strip() == want_title else f" - != «{want_title}»")
          + ("" if on_cover else f" - cover does not print «{ver}»"))

    # 8b. version consistency: EVERY place the version is printed carries the same value (H7). The cover was
    # guarded; the back cover was not, so a stale back cover could ship next to a current cover.
    src_versions = version_spots_in_source()
    want_versions = [NS.GUIDE_VERSION_AR] * len(NS.VERSION_SPOTS)
    ver_bad = []
    if src_versions != want_versions:
        ver_bad.append(f"source prints {src_versions}, expected {want_versions}")
    for name, page in NS.VERSION_SPOTS:
        if texts is None:
            ver_bad.append(f"{name}: could not read the page with PDFium")
        elif ver not in " ".join(texts[page].split()):
            ver_bad.append(f"{name} (p{page+1}) does not print «{ver}»")
    check("version-consistency", not ver_bad, "; ".join(ver_bad[:4]) or
          f"{len(NS.VERSION_SPOTS)} spots print «{ver}» (source and PDF)")

    # 8c. provenance: the file says which source it was built from, and that is the source this gate compares with
    name, digest = source_stamp()
    got_name = got_digest = got_rendered = got_chrome = ""
    stray = 0
    try:
        import hashlib
        import json as _json
        px = pikepdf_open(doc)
        with px.open_metadata() as m:
            doc_id = str(m.get("xmpMM:DocumentID", ""))
        got_digest = doc_id.split("sha256:")[-1] if doc_id.startswith("sha256:") else ""
        if "manifest.json" in px.attachments:      # the file carries its own manifest: source + hashes
            man = _json.loads(px.attachments["manifest.json"].get_file().read_bytes())
            got_name = man.get("source", "")
            got_rendered = man.get("rendered_sha256", "")
            got_chrome = man.get("chrome_version", "")
        # Page furniture must not be structure content. A /P element directly under /Document is a
        # paragraph the post-processor invented for a run that belonged to no section — a reader then
        # reads the running head once per page, after the last section.
        root = px.Root.get("/StructTreeRoot")
        if root is not None:
            kids = root.get("/K")
            for k in (list(kids) if isinstance(kids, pikepdf.Array) else [kids]):
                if str(k.get("/S")) == "/Document":
                    ch = k.get("/K")
                    stray += sum(1 for x in (list(ch) if isinstance(ch, pikepdf.Array) else [ch])
                                 if str(x.get("/S")) == "/P")
        px.close()
    except Exception:
        got_name = got_digest = ""
    # 8c continued — the manifest names the markup this build handed to Chrome, and the gate derives it
    # again from this spec and this source. There is no sidecar to read: the copy was the stale thing.
    # A missing key is a FAIL, not a skip: a manifest without it binds the file to nothing.
    try:
        want_rendered = render_markup.markup_sha256(source_markup())
        derive_err = ""
    except Exception as e:
        want_rendered, derive_err = "", f"the gate cannot derive the markup this document was built from: {type(e).__name__}: {e}"
    got_rendered = str(got_rendered or "")
    if derive_err:
        rendered_why = derive_err
    elif not got_rendered:
        rendered_why = "the manifest carries no rendered_sha256: the build that made this file did not record its markup"
    elif got_rendered != want_rendered:
        rendered_why = (f"manifest rendered_sha256 {got_rendered[:12]} is not the markup this spec derives "
                        f"from {name} ({want_rendered[:12]})")
    else:
        rendered_why = ""
    ok = (got_name, got_digest) == (name, digest) and not rendered_why
    check("provenance", ok,
          f"{name} sha256 {digest[:12]} · rendered {want_rendered[:12]}" if ok else
          (rendered_why or ("no source stamp" if not got_digest else
           f"built from {got_name} {got_digest[:12]}, gate truth is {name} {digest[:12]}")))
    # 8d. the engine that printed it: Skia decides the text layer this repo patches and measures, so the
    #     manifest carries the binary's own version and the gate holds it to the pin — by name, not a warning.
    pin = chrome_pin.CHROME_VERSION
    check("chrome-version", got_chrome == pin,
          f"printed by Chrome {got_chrome}" if got_chrome == pin else
          f"manifest says «{got_chrome or 'nothing'}», the pipeline is pinned to {pin}")
    check("tagged-structure", stray == 0,
          "no paragraph sits directly under /Document" if stray == 0 else
          f"{stray} paragraph(s) under /Document — page furniture tagged as content")

    # 9. no blank / overflow pages: far below the median text (cover + contents excluded) and not excused by image cover
    blank, low, med = blank_pages(doc, [i for i in range(doc.page_count) if i not in (NS.COVER, NS.CONTENTS)])
    check("no-blank-pages", not blank, ", ".join(blank) or
          f"median {med:.0f} chars; low-text pages excused by image cover: " + (", ".join(f"p{i+1} {c:.0%}" for i, c in low.items()) or "none"))

    # 9b. tagged PDF, as README declares: language, marked content, structure tree
    lang = catalog_value(doc, "Lang").strip("()")
    markinfo = catalog_value(doc, "MarkInfo")
    marked = bool(re.search(r"/Marked\s+true", markinfo))
    tree = doc.xref_get_key(doc.pdf_catalog(), "StructTreeRoot")[0] == "xref"
    missing = [n for n, ok in ((f"Lang={NS.LANG}", lang == NS.LANG), ("MarkInfo/Marked", marked), ("StructTreeRoot", tree)) if not ok]
    check("tagged", not missing, "missing: " + ", ".join(missing) if missing else f"Lang={lang}, Marked, structure tree")

    # 9c. what a pagination artifact carries: /Pagination is where a screen reader stops reading, so every
    #     text show inside one must sit in the band the spec declares. The producer refuses at build time;
    #     this is the same rule on the file, which is where a mutation can be seen.
    bands = list(getattr(NS, "FURNITURE_BANDS", []))
    swept, inventory = [], {}
    try:
        xp = pikepdf_open(doc)
        try:
            for pi, page in enumerate(xp.pages, 1):
                instr = list(pikepdf.parse_content_stream(page))
                resolve, props = form_resolver(page), props_of(page)
                # every artifact that carries text — typed, bare, named, nested, inside a form — is judged
                for kind, n in artifact_shows(instr, resolve, props).items():
                    inventory[kind] = inventory.get(kind, 0) + n
                swept += [f"p{pi} {kind} y={y:.0f}" for kind, y in outside_bands(instr, bands, resolve, props)]
        finally:
            xp.close()
    except GateInput:
        raise
    except Exception as exc:                 # an unreadable content stream is a failure, not a crash
        swept = [f"cannot read the page content: {exc}"]
    check("furniture-band", not swept,
          "; ".join(swept[:4]) or f"{len(bands)} band(s) · {inventory or 'no artifact text'}, every show inside")

    # 9d. the declared model: the structures this pipeline produces, and nothing else. A form is followed
    #     for its own sake in 9c; here the FORM ITSELF is the subject — text inside one, a form inside a
    #     form's resources, a text rise, artifact text under a rotated matrix. Interpreting deeper is how
    #     every adversarial round found another hole; refusing by name closes the class.
    model_bad, mstats = [], {}
    try:
        xp = pikepdf_open(doc)
        try:
            model_bad, mstats = model_stats(xp)
        finally:
            xp.close()
    except GateInput:
        raise
    except Exception as exc:
        model_bad = [f"cannot read the model: {exc}"]
    check("pdf-model", not model_bad,
          "; ".join(model_bad[:4]) or
          f"{mstats.get('forms', 0)} form(s) at depth 1 · no text inside · no nesting · no Ts · no rotated artifact text")

    # 10. text layer: every glyph carries ONE base code point (scripts/fix_text_layer.py). Presentation Forms or
    #     multi-letter entries are what makes readers reverse letters inside ligatures (لأ→ال، في→يف).
    bad_tu = text_layer_violations(doc)
    check("text-layer", not bad_tu, "; ".join(bad_tu[:3]) or "one base code point per glyph")

    # 11. copy fidelity, measured with PDFium (Chrome/Edge's engine) against the words of the source HTML
    plain = "\n".join(texts) if texts else None
    rec, seq = copy_fidelity(doc, text=plain)
    ok = rec is not None and rec >= NS.COPY_MIN_RECALL and seq >= NS.COPY_MIN_SEQUENCE
    check("copy-fidelity", ok, f"recall {rec:.3f} / sequence {seq:.3f} (min {NS.COPY_MIN_RECALL} / {NS.COPY_MIN_SEQUENCE})"
          if rec is not None else "could not read source HTML or PDF text")

    # 12. line order for stream-order readers: MuPDF (PyMuPDF, RAG extractors) must return each line's words in order
    _, mseq = copy_fidelity(doc, engine="mupdf")
    # Per document, calibrated: the ratchet is what THIS document's layer can do, minus drift, and never
    # below the historical floor. A single 0.75 for three documents let Najd hide 0.18 of headroom.
    if not hasattr(NS, "LINE_ORDER_MIN"):
        raise GateInput("the spec declares no LINE_ORDER_MIN: the floor is not optional")
    if float(NS.LINE_ORDER_MIN) < LINE_ORDER_FLOOR:
        raise GateInput(f"LINE_ORDER_MIN {NS.LINE_ORDER_MIN} is below the {LINE_ORDER_FLOOR} floor: refused, not clamped")
    mmin = float(NS.LINE_ORDER_MIN)
    check("line-order", mseq is not None and mseq >= mmin,
          f"MuPDF sequence {mseq:.3f} (min {mmin:.3f})" if mseq is not None else "could not read source HTML or PDF text")

    # 13. vocalised text: the basmala must copy exactly, marks on their letters (PDFium and MuPDF)
    import unicodedata as _ud
    ctrl = re.compile("[\u2060\u200b\u200e\u200f\u202a-\u202e\u2066-\u2069]")
    norm = lambda t: _ud.normalize("NFC", ctrl.sub("", t))
    claimed = getattr(NS, "VOCALISED_CLAIM", True)
    want_v = _ud.normalize("NFC", NS.VOCALISED) if claimed else None

    got = {} if not claimed else {"MuPDF": norm(doc[NS.BASMALA].get_text()),
                                  "PDFium": norm(texts[NS.BASMALA]) if texts else ""}
    missing = [] if not claimed else [k for k, t in got.items() if want_v not in t]
    detail = ("not claimed — " + getattr(NS, "VOCALISED_REASON", "no reason declared")) if not claimed else (
        f"basmala not exact in {missing}" if missing else "basmala exact in PDFium and MuPDF")
    check("vocalised", not missing, detail)

    # 14. words per page (H5): aggregate ratios are blind below ~2.4% of the corpus — 18 words can vanish and
    #     every ratio still passes. Per-page counts make a lost paragraph break the build.
    if texts is None:
        check("page-words", False, "could not read the text with PDFium")
    else:
        per = [len(source_words(t)) for t in texts]
        w_bad = [f"p{i+1} {n} vs {NS.PAGE_WORDS[i]}" for i, n in enumerate(per)
                 if i in NS.PAGE_WORDS and abs(n - NS.PAGE_WORDS[i]) > NS.PAGE_WORDS_TOL]
        w_bad += [f"p{i+1}: no measured word count" for i in range(len(per)) if i not in NS.PAGE_WORDS]
        check("page-words", not w_bad, "; ".join(w_bad[:4]) or
              f"{NS.PAGES} pages within +-{NS.PAGE_WORDS_TOL} words (total {sum(per)})")

    # 15. the document's own claim about this gate (H9): the printed counts must equal the live ones.
    claims = printed_counts(doc[NS.PRINTED_COUNTS_PAGE])
    want_claims = {"checks": NS.GATE_CHECKS, "mutations": NS.GATE_MUTATIONS}
    if getattr(NS, "PRINTS_LINK_COUNT", False):      # only where the document actually prints the number
        want_claims["links"] = NS.EXPECTED_LINKS
    claim_bad = [f"{k}: printed {claims.get(k, 'not found')} vs actual {v}" for k, v in want_claims.items() if claims.get(k) != v]
    detail = f"printed {claims.get('checks')} checks / {claims.get('mutations')} mutations"
    if "links" in want_claims:
        detail += f" / {claims.get('links')} links"
    check("gate-claims", not claim_bad, "; ".join(claim_bad) or detail + " = actual")

    final_count()
    if os.environ.get("VERIFY_DUMP_CHECKS"):
        print("CHECKS_DUMP:", " ".join(sorted(set(ran))))
    return fails


PRES_FORM = lambda ch: 0xFB50 <= ord(ch) <= 0xFDFF or 0xFE70 <= ord(ch) <= 0xFEFF


def text_layer_violations(doc) -> list[str]:
    import unicodedata
    out, seen = [], set()
    for page in doc:
        for xref, *_ in page.get_fonts():
            if xref in seen:
                continue
            seen.add(xref)
            kind, tu = doc.xref_get_key(xref, "ToUnicode")
            if kind != "xref":
                continue
            data = doc.xref_stream(int(tu.split()[0])).decode("latin1")
            pairs = []
            for blk in re.findall(r"beginbfchar(.*?)endbfchar", data, re.S):
                pairs += re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk)
            # ranges map codes too: <lo> <hi> <dst> (dst counts up) and <lo> <hi> [<d1> <d2> ...]
            for blk in re.findall(r"beginbfrange(.*?)endbfrange", data, re.S):
                for lo, hi, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]+>|\[[^\]]*\])", blk):
                    if dst.startswith("["):
                        pairs += [(f"{int(lo, 16) + k:04X}", h) for k, h in enumerate(re.findall(r"<([0-9A-Fa-f]+)>", dst))]
                    else:
                        h = dst.strip("<>")
                        pairs += [(f"{c:04X}", h[:-4] + f"{int(h[-4:], 16) + c - int(lo, 16):04X}") for c in range(int(lo, 16), int(hi, 16) + 1)]
            for cid, hx in pairs:
                txt = bytes.fromhex(hx).decode("utf-16-be", "replace")
                letters = [c for c in txt if unicodedata.category(c) != "Mn"]
                if any(PRES_FORM(c) for c in txt) or len(letters) > 1:
                    out.append(f"xref {xref} cid {cid}: {txt!r}")
    return out


def sequence_ratio(truth: list[str], got: list[str]) -> float:
    """How much of `truth` appears in `got` in the same order — one definition, one number."""
    import difflib
    sm = difflib.SequenceMatcher(None, truth, got, autojunk=False)
    return sum(b.size for b in sm.get_matching_blocks()) / len(truth)


def truth_words() -> list[str]:
    """The markup's words in source order — what copy-fidelity and the line-order report both compare to."""
    import html
    src = source_markup()
    stripped = re.sub(r"<(style|script|svg)\b.*?</\1>", " ", src, flags=re.S | re.I)
    return source_words(html.unescape(re.sub(r"<[^>]+>", " ", stripped)))


def copy_fidelity(doc, engine="pdfium", text=None):
    """(recall, sequence) of the source words in the engine's extraction; sequence counts words in order.

    The reference is the markup the producer ACTUALLY handed to Chrome — derived here from the same
    spec and source, never read from a copy beside the file. For the print variant the navigation
    strip is removed from that markup itself, so comparing against the original template would count
    words the PDF was never asked to carry: the gate would be measuring a decision, not a defect.
    """
    import collections
    import difflib
    try:
        truth = truth_words()
    except Exception:
        return None, None
    if text is not None:                # text extracted by another reader (PDFium, or Preview's PDFKit)
        got = source_words(text)
    elif engine == "mupdf":
        got = source_words("\n".join(p.get_text() for p in doc))
    else:
        texts = pdfium_texts(doc)
        if texts is None:
            return None, None
        got = source_words("\n".join(texts))
    if not truth or not got:
        return None, None
    ct, cg = collections.Counter(truth), collections.Counter(got)
    recall = sum(min(ct[w], cg[w]) for w in ct) / len(truth)
    return recall, sequence_ratio(truth, got)


def printed_page_numbers(page) -> list[int]:
    """Page numbers printed in the contents table, top to bottom.

    Chrome's text layer is visual-order, so multi-digit numbers come out reversed in plain text
    («١٠» -> «٠١»). Read digit glyphs with positions, group them into numbers by line, rebuild each
    number left-to-right, and keep the LEFT column (the page column in an RTL table)."""
    nums = []
    for b in page.get_text("rawdict")["blocks"]:
        for line in b.get("lines", []):
            for s in line["spans"]:
                ds = [c for c in s["chars"] if c["c"].isdigit()]
                if ds and len(ds) == len("".join(c["c"] for c in s["chars"]).strip()):
                    ds.sort(key=lambda c: c["bbox"][0])
                    val = int("".join(str(int(c["c"])) for c in ds))   # int() reads Arabic-Indic digits
                    nums.append((round(ds[0]["bbox"][1]), ds[0]["bbox"][0], val))
    if not nums:
        return []
    xs = sorted({round(x) for _, x, _ in nums})
    gaps = [(xs[k + 1] - xs[k], k) for k in range(len(xs) - 1)]
    if not gaps:
        return []
    cut = xs[max(gaps)[1]] + max(gaps)[0] / 2       # split the two columns at the widest x gap
    left = sorted((y, v) for y, x, v in nums if x < cut)
    return [v for _, v in left]


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "out.pdf"
    try:
        doc = open_for_gate(pdf)
        failed = gate(doc)
    except GateInput as e:            # a rule refused its input: by name, like every other gate failure
        print(f"FAIL input - {e}")
        raise SystemExit(1)
    if failed:
        print(f"\n{len(failed)} gate(s) FAILED: {failed}")
        raise SystemExit(1)
    print("\nALL GATES PASSED")
