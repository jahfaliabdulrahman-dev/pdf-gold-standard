#!/usr/bin/env python3
"""Stage-5 post-processing: metadata and structure that must not change the drawing.

Applied AFTER fix_text_layer (which rewrites content) and BEFORE the gate. The feature list and its
order live in features.toml, not in this file: build.py knows nothing about features, and the gate
verifies the file against the same declaration.

Why a separate stage: PageLabels, named destinations, XMP, the output intent and attachments are
catalog-level objects. Adding them cannot move a glyph, so the 300-dpi pixel proof still holds; doing
them inside build.py's PyMuPDF pass would mix drawing and metadata in one place.
"""
import hashlib
import json
import os
import tomllib

import pikepdf

import pdfops

PROJ = os.path.dirname(os.path.abspath(__file__))


def _srgb_icc() -> bytes:
    """A full sRGB ICC profile. The system profile is 3.1 KB; Pillow's littlecms fallback is a
    588-byte minimal profile, which a print check must not accept as an output intent."""
    system = "/System/Library/ColorSync/Profiles/sRGB Profile.icc"
    if os.path.exists(system):
        data = open(system, "rb").read()
        if len(data) > 1024:
            return data
    from PIL import ImageCms
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def feature_page_labels(pdf, spec, ctx=None) -> None:
    """Printed numbering lives in the design; /PageLabels governs what the READER shows.

    PDF supports only D/r/R/a/A styles (no Arabic-Indic), so the cover is a prefix-only label («غ») and
    the body counts 1..11 — the same numbers the pages print.
    """
    import spec_loader
    NS = spec_loader.load()
    nums = pikepdf.Array()
    for start, style, value in NS.PAGE_LABELS:
        d = pikepdf.Dictionary()
        if value:
            d["/P"] = pikepdf.String(value) if isinstance(value, str) else pikepdf.String(str(value))
        if style:
            d["/S"] = pikepdf.Name("/" + style)
            # decimal numbering starts at `start_value`; the rule's start page is separate
        nums.append(start)
        nums.append(d)
    # decimal start values, per the measured spec (cover = label only, body = 1..)
    for k, (start, style, value) in enumerate(NS.PAGE_LABELS):
        if style and isinstance(value, int):
            nums[2 * k + 1]["/St"] = value
    pdf.Root.PageLabels = pikepdf.Dictionary(Nums=nums)


def feature_named_destinations(pdf, spec, ctx=None) -> None:
    """A name -> page map, so a target is an identity, not an index that shifts when a page is added."""
    import spec_loader
    NS = spec_loader.load()
    names = pikepdf.Array()
    for name, page in NS.DEST_NAMES:
        names.append(pikepdf.String(name))
        names.append(pikepdf.Dictionary(D=pikepdf.Array([pdf.pages[page].obj, pikepdf.Name.Fit])))
    pdf.Root.Names = pikepdf.Dictionary(Dests=pikepdf.Dictionary(Names=names))


from pdfops import PAINT_OPS, TEXT_OPS, model_boundary, text_shows, outside_bands  # noqa: E402  (one definition, shared with the gate)


def _wrap_untagged(instructions, bands=None, page_no=0):
    """Wrap untagged painting runs in an artifact; return (new list, blocks added).

    Text inside a run is judged before it is wrapped (B1): a show outside every declared band is body text
    Chrome failed to tag, and wrapping it as /Pagination would hide it from a screen reader while the file
    still passes veraPDF — it stops the build by name instead. A run that carries text becomes a TYPED
    /Pagination artifact; a run of pure painting (backgrounds, rules, icons) stays a bare /Artifact BMC.

    Only painting operators enter the block. Every container operator — BMC/BDC/EMC, q/Q, BT/ET, colour
    and text state — closes the block first, so an artifact can never hold a tagged sequence (7.1-2) and
    can never straddle a state container.
    """
    # untagged shows that sit OUTSIDE every marked-content block — the only ones this function wraps
    shows = [s for s in text_shows(instructions) if s[0] is None and s[4] == 0]
    pending = iter(shows)
    out, buf, buf_text, added = [], [], False, 0

    def flush():
        nonlocal buf, buf_text, added
        if not buf:
            return
        wrapper = ([pikepdf.Name("/Artifact"), pikepdf.Dictionary(Type=pikepdf.Name("/Pagination"))]
                   if buf_text else [pikepdf.Name("/Artifact")])
        out.append(pikepdf.ContentStreamInstruction(wrapper, pikepdf.Operator("BDC" if buf_text else "BMC")))
        out.extend(buf)
        out.append(pikepdf.ContentStreamInstruction([], pikepdf.Operator("EMC")))
        added += 1
        buf, buf_text = [], False

    mc = 0                       # marked-content depth: only painting OUTSIDE every block is wrapped
    for ins in instructions:
        op = str(ins.operator)
        if op in ("BMC", "BDC"):
            flush()
            out.append(ins)
            mc += 1
        elif op == "EMC":
            flush()
            out.append(ins)
            mc = max(0, mc - 1)
        elif op in ("q", "Q", "BT", "ET"):
            flush()
            out.append(ins)
        elif op in PAINT_OPS and mc == 0:
            if op in TEXT_OPS:
                _kind, _x, y, _size, _depth = next(pending)
                # bands is None inside a Form XObject: its coordinates are the form's, and the page-level
                # check follows Do to judge them in page space.
                # both ends of the drawn glyph: a 300 pt line with its origin in the band still reaches out
                if bands is not None and not any(lo <= y <= hi and lo <= y + _size <= hi for lo, hi in bands):
                    raise ValueError(f"page {page_no}: untagged text at y={y:.0f} (top {y + _size:.0f}) is outside "
                                     f"the declared furniture band {list(bands)} — marking it /Pagination would "
                                     "hide it from a screen reader")
                buf_text = True
            buf.append(ins)
        elif mc > 0:
            out.append(ins)       # inside a tag: not ours to wrap
        else:
            flush()
            out.append(ins)
    flush()
    return out, added


def _tag_orphan_runs(pdf, page, instructions, bands=(), page_no=0):
    """Mark every top-level marked-content run Chrome left unlinked as page furniture — inside the band only.

    Chrome wraps reversed RTL text in a bare `BMC /ReversedChars … EMC` with no MCID. At depth 0 those runs
    are the running head/footer, which a screen reader should skip: they become /Artifact /Pagination. The
    text stays where it is; only its ownership changes.

    A run outside the band the spec declares is NOT furniture — it is body text Chrome failed to tag, and
    marking it /Pagination would hide it from a screen reader while the file still passes veraPDF. It stops
    the build by name instead.
    """
    st = pdf.Root.get("/StructTreeRoot")
    if st is None or "/ParentTree" not in st:
        return instructions
    sp = page.obj.get("/StructParents")
    if sp is None:
        return instructions
    nums = st.ParentTree.get("/Nums")
    table = {}
    if nums is not None:
        for i in range(0, len(nums) - 1, 2):
            table[int(nums[i])] = nums[i + 1]
    arr = table.get(int(sp))
    if arr is None:
        return instructions
    document = st.get("/K")
    if isinstance(document, pikepdf.Array):
        document = document[0] if len(document) else None
    if document is None:
        return instructions

    out, depth, added = [], 0, 0
    for ins in instructions:
        op = str(ins.operator)
        if op in ("BMC", "BDC"):
            if depth == 0 and op == "BMC" and str(ins.operands[0]) != "/Artifact":
                # Outside every marked-content block sits page furniture: the printed once-per-page head,
                # footer and number. Chrome leaves them untagged, and turning them into /P paragraphs made
                # a screen reader read the running head twelve times AFTER the last section. They are what
                # they are — pagination artifacts, not reading order.
                out.append(pikepdf.ContentStreamInstruction(
                    [pikepdf.Name("/Artifact"), pikepdf.Dictionary(Type=pikepdf.Name("/Pagination"))],
                    pikepdf.Operator("BDC")))
                depth += 1
                added += 1
                continue
            depth += 1
            out.append(ins)
        elif op == "EMC":
            depth = max(0, depth - 1)
            out.append(ins)
        else:
            out.append(ins)

    # A run outside every marked-content block is page furniture ONLY if it sits in a declared band. Wrapping
    # body text as /Pagination hides it from a screen reader while the file still passes veraPDF, so a run
    # outside the band stops the build by name instead of being swept along.
    stray = outside_bands(out, bands)
    if stray:
        raise ValueError(f"page {page_no}: untagged text at y={stray[0][1]:.0f} is outside the declared furniture "
                         f"band {list(bands)} — marking it /Pagination would hide it from a screen reader")
    return out


def feature_pdfua(pdf, spec=None) -> None:
    """Mark every untagged painting run as an Artifact, so the file reaches PDF/UA's 7.1 rule.

    Chrome tags the text it draws (BDC … EMC with an /MCID) but leaves backgrounds, rules, icons and the
    cover wall untagged; veraPDF reports each as «Content is neither marked as Artifact nor tagged as real
    content» (256 on Najd, 612 on the report). The fix is a container, not a redraw.

    Chrome also splits a page into Form XObjects, so the same treatment has to reach inside a form — but
    only when the form is invoked OUTSIDE any tagged sequence. A form invoked inside a BDC holds real
    content; marking its interior as an artifact there would violate 7.1-1. The usage map below decides,
    and a form used in both contexts is left alone (and reported) rather than guessed at.
    """
    import spec_loader
    # `spec` is the feature's entry from features.toml, not the document spec: only a module that carries
    # the document's own constants may override the loaded spec.
    import types
    NS = spec if isinstance(spec, types.ModuleType) else spec_loader.load()
    if not getattr(NS, "PDFUA", False):
        return

    pdf.Root["/MarkInfo"] = pikepdf.Dictionary(Type=pikepdf.Name("/MarkInfo"), Marked=True, Suspects=False)

    def resources(container):
        return container.get("/Resources", {}) if hasattr(container, "get") else {}

    # pass 1: which forms exist, and in which context each one is invoked
    import collections
    forms: dict = {}
    queue = collections.deque()
    for page in pdf.pages:
        queue.append((page.obj, page.obj, list(pikepdf.parse_content_stream(page))))
    while queue:
        _owner, container, instrs = queue.popleft()
        mc = 0
        for ins in instrs:
            op = str(ins.operator)
            if op in ("BMC", "BDC"):
                mc += 1
            elif op == "EMC":
                mc = max(0, mc - 1)
            elif op == "Do" and ins.operands:
                xo = resources(container).get("/XObject", {})
                target = xo.get(str(ins.operands[0]))
                if target is None or str(target.get("/Subtype")) != "/Form":
                    continue
                key = target.objgen
                rec = forms.setdefault(key, {"obj": target, "tagged": False, "artifact": False, "seen": False})
                rec["tagged" if mc > 0 else "artifact"] = True
                if not rec["seen"]:
                    rec["seen"] = True
                    try:
                        queue.append((target, target, list(pikepdf.parse_content_stream(target))))
                    except Exception:
                        pass

    # pass 2: inside artifact-only forms, the same wrap; forms used in tagged context are left untouched
    marks = 0
    skipped = 0
    for rec in forms.values():
        if rec["artifact"] and not rec["tagged"]:
            out, added = _wrap_untagged(pikepdf.parse_content_stream(rec["obj"]))
            if added:
                rec["obj"].write(pikepdf.unparse_content_stream(out))
                marks += added
        elif rec["tagged"] and rec["artifact"]:
            skipped += 1

    # pass 3: the pages themselves — wrap the untagged painting, then give the leftover runs an owner
    for page_no, page in enumerate(pdf.pages, 1):
        out, added = _wrap_untagged(pikepdf.parse_content_stream(page),
                                     getattr(NS, "FURNITURE_BANDS", []), page_no)
        out = _tag_orphan_runs(pdf, page, out, getattr(NS, "FURNITURE_BANDS", []), page_no)
        if added or out:
            page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(out))
            marks += added

    if marks:
        print(f"      pdfua: wrapped {marks} untagged run(s) as artifacts")
    if skipped:
        print(f"      pdfua: {skipped} form(s) used in both contexts were left alone")


_PDFUA_NS = (
    ("pdfaExtension", "http://www.aiim.org/pdfa/ns/extension/"),
    ("pdfaSchema", "http://www.aiim.org/pdfa/ns/schema#"),
    ("pdfaProperty", "http://www.aiim.org/pdfa/ns/property#"),
)

PDFUA_XMP_SCHEMA = (
    "<pdfaExtension:schemas><rdf:Bag><rdf:li rdf:parseType=\"Resource\">"
    "<pdfaSchema:schema>PDF/UA identification schema</pdfaSchema:schema>"
    "<pdfaSchema:namespaceURI>http://www.aiim.org/pdfua/ns/id/</pdfaSchema:namespaceURI>"
    "<pdfaSchema:prefix>pdfuaid</pdfaSchema:prefix>"
    "<pdfaSchema:property><rdf:Seq><rdf:li rdf:parseType=\"Resource\">"
    "<pdfaProperty:name>part</pdfaProperty:name>"
    "<pdfaProperty:valueType>Integer</pdfaProperty:valueType>"
    "<pdfaProperty:category>external</pdfaProperty:category>"
    "<pdfaProperty:description>Part of ISO 14289 standard</pdfaProperty:description>"
    "</rdf:li></rdf:Seq></pdfaSchema:property></rdf:li></rdf:Bag></pdfaExtension:schemas>"
)


def _pdfua_description() -> str:
    """A Description of its own: the schema's prefixes are declared here, not borrowed from a neighbour."""
    ns = " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in _PDFUA_NS)
    return f'<rdf:Description rdf:about="" {ns}>{PDFUA_XMP_SCHEMA}</rdf:Description>'


def feature_xmp(pdf, spec, ctx=None) -> None:
    """XMP is what archive/search tools read; Info alone is invisible to them."""
    import spec_loader
    # `spec` is the feature's entry from features.toml, not the document spec: only a module that carries
    # the document's own constants may override the loaded spec.
    import types
    NS = spec if isinstance(spec, types.ModuleType) else spec_loader.load()
    sha = pdf.docinfo.get("/SourceSHA256", "")
    title = getattr(NS, "XMP_TITLE", None) or f"معيار إنتاج ملفات PDF — دليل المعيار · الإصدار {NS.GUIDE_VERSION_AR}"
    description = getattr(NS, "XMP_DESCRIPTION", None) or "معيار جودة إنتاج ملفات PDF التفاعلية العربية"
    with pdf.open_metadata() as m:
        m["dc:title"] = title
        m["dc:creator"] = [getattr(NS, "XMP_CREATOR", "م. عبدالرحمن جحفلي")]
        m["dc:description"] = description
        m["dc:language"] = ["ar"]
        m["xmp:CreatorTool"] = "Hermes PDF Gold Standard pipeline"
        m["pdf:Producer"] = str(pdf.docinfo.get("/Producer", "PyMuPDF + pikepdf"))
        m["xmpMM:DocumentID"] = f"sha256:{sha}" if sha else "urn:pdf-gold-standard"
        # A conformance identifier only when the spec declares it; the gate refuses a claim whose baseline
        # still lists failures, so this line cannot turn into decoration.
        for key, value in (getattr(NS, "CONFORMANCE", None) or {}).items():
            m[key] = value
        if "dc:source" in m:
            del m["dc:source"]
    # PDF/A and PDF/UA together need more than the identifier: PDF/A 6.6.2.3.1 accepts a foreign XMP
    # property only if its schema is described in pdfaExtension. pikepdf merges nested dictionaries, so
    # the description is written as XMP text, not through the mapping API (measured: merging produced a
    # malformed schema and four 6.6.2.3.3 failures).
    if any(k.startswith("pdfuaid:") for k in (getattr(NS, "CONFORMANCE", None) or {})):
        xmp = pdf.Root.Metadata.read_bytes().decode("utf-8")
        if "pdfaExtension:schemas" not in xmp:
            # a description of its own: the identifier's namespace is not declared on any existing element,
            # so merging the schema into one of them would attach it to a foreign subject
            patched = xmp.replace("</rdf:RDF>", _pdfua_description() + "</rdf:RDF>", 1)
            if patched == xmp:
                raise SystemExit("postprocess: XMP has no rdf:RDF to carry the pdfuaid schema, "
                                 "so PDF/A 6.6.2.3.1 cannot pass")
            pdf.Root.Metadata.write(patched.encode("utf-8"))
            with pdf.open_metadata() as check:
                if check.get("pdfuaid:part") in (None, ""):
                    raise SystemExit("postprocess: the pdfuaid schema block did not survive the XMP write")


def feature_output_intent(pdf, spec, ctx=None) -> None:
    """sRGB output intent + Trim/Bleed boxes. No design change: boxes equal MediaBox (no bleed)."""
    icc = _srgb_icc()
    profile = pdf.make_stream(icc)
    profile["/N"] = 3          # RGB
    intent = pikepdf.Dictionary(
        Type=pikepdf.Name.OutputIntent,
        S=pikepdf.Name("/GTS_PDFA1"),
        OutputConditionIdentifier=pikepdf.String("sRGB IEC61966-2.1"),
        Info=pikepdf.String("sRGB IEC61966-2.1"),
        DestOutputProfile=pdf.make_indirect(profile),
    )
    pdf.Root.OutputIntents = pikepdf.Array([pdf.make_indirect(intent)])
    for page in pdf.pages:
        box = page.obj.get("/MediaBox")
        page.obj["/TrimBox"] = box
        page.obj["/BleedBox"] = box


def feature_attachments(pdf, spec, ctx=None) -> None:
    """The file carries its build data and a manifest of hashes: reproduction is content, not a claim.

    The file list lives in the spec (`ATTACHMENT_FILES`: name, repo-relative path, mime, /AFRelationship), so a
    second document adds evidence without touching this code. A name with no path is generated here (the
    manifest), which is how the hashes always describe the file that was actually built. A spec without the
    list is refused by name: the code no longer keeps a default that only one document happens to satisfy.
    `rendered_sha` is passed in by `apply()` — no module state stands between the producer and the manifest.
    """
    import spec_loader
    NS = spec_loader.load()
    rendered_sha = (ctx or {}).get("rendered_sha")
    chrome_version = (ctx or {}).get("chrome_version")
    declared = getattr(NS, "ATTACHMENT_FILES", None)
    if not declared:
        raise SystemExit("postprocess: the spec declares no ATTACHMENT_FILES — the file list is a contract, not a default")
    if not rendered_sha:
        raise SystemExit("postprocess: manifest.json needs the hash of the markup handed to Chrome; "
                         "none was passed to apply(rendered_sha=...)")
    if not chrome_version:
        raise SystemExit("postprocess: manifest.json needs the version of the binary that printed the file; "
                         "none was passed to apply(chrome_version=...)")
    src_path = os.path.join(PROJ, NS.SOURCE_HTML)
    data = open(src_path, "rb").read()
    manifest = {
        "source": NS.SOURCE_HTML,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "rendered_sha256": rendered_sha,
        "chrome_version": chrome_version,
        "guide_version": NS.GUIDE_VERSION,
        "pages": NS.PAGES,
    }
    payloads = []
    for name, rel, mime, relationship in declared:
        if rel is None:
            payloads.append((name, json.dumps(manifest, ensure_ascii=False, indent=1).encode(), mime, relationship))
        else:
            payloads.append((name, open(os.path.join(PROJ, rel), "rb").read(), mime, relationship))
    for name, payload, mime, relationship in payloads:
        spec_obj = pikepdf.AttachedFileSpec(pdf, payload, mime_type=mime, filename=name)
        spec_obj.obj["/AFRelationship"] = pikepdf.Name("/" + relationship)
        spec_obj.obj["/Params"] = pikepdf.Dictionary(ModDate=pikepdf.String("D:20261114210000+03'00'"))
        pdf.attachments[name] = spec_obj
    # /AF on the document lists the associated files (PDF/A-3 asks for it)
    pdf.Root.AF = pikepdf.Array([pdf.attachments[name].obj for name, *_ in payloads])


FORM_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "IBMPlexSansArabic-Regular.ttf")
FORM_FONT_KEY = "/PlexForm"


def form_font(pdf):
    """A COMPLETE Arabic font for form fields — never a page subset.

    Chrome writes each page font as a subset with no ToUnicode: the glyphs of the words on that page and
    nothing else. A field that borrows one can only ever display those glyphs, so typing «ملاحظات» gives
    empty boxes. This embeds the full IBM Plex Sans Arabic (OFL) as Type0/Identity-H, CIDToGIDMap
    /Identity, with a ToUnicode CMap so the value can also be copied out.
    """
    from fontTools.ttLib import TTFont
    ttf = TTFont(FORM_FONT_PATH)
    upem = ttf["head"].unitsPerEm
    order = ttf.getGlyphOrder()
    hmtx, head, hhea = ttf["hmtx"], ttf["head"], ttf["hhea"]
    scale = lambda v: round(v * 1000 / upem)
    widths = [scale(hmtx[g][0]) for g in order]
    data = open(FORM_FONT_PATH, "rb").read()

    ff = pdf.make_stream(data)
    ff["/Length1"] = len(data)
    descriptor = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.FontDescriptor, FontName=pikepdf.Name("/IBMPlexSansArabic-Regular"),
        Flags=4, FontBBox=pikepdf.Array([scale(v) for v in (head.xMin, head.yMin, head.xMax, head.yMax)]),
        ItalicAngle=0, Ascent=scale(hhea.ascent), Descent=scale(hhea.descent),
        CapHeight=scale(getattr(ttf["OS/2"], "sCapHeight", hhea.ascent)), StemV=80, FontFile2=ff))
    cid = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.CIDFontType2,
        BaseFont=pikepdf.Name("/IBMPlexSansArabic-Regular"),
        CIDSystemInfo=pikepdf.Dictionary(Registry=pikepdf.String("Adobe"),
                                         Ordering=pikepdf.String("Identity"), Supplement=0),
        FontDescriptor=descriptor, DW=600, W=pikepdf.Array([0, pikepdf.Array(widths)]),
        CIDToGIDMap=pikepdf.Name.Identity))

    # ToUnicode: one entry per glyph that has a character — without it the value cannot be copied or read.
    reverse = {}
    for cp, name in ttf.getBestCmap().items():
        reverse.setdefault(ttf.getGlyphID(name), cp)
    lines = ["/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
             "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
             "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def", "1 begincodespacerange",
             "<0000> <FFFF>", "endcodespacerange"]
    pairs = sorted((gid, cp) for gid, cp in reverse.items() if cp <= 0xFFFF)
    for i in range(0, len(pairs), 100):
        chunk = pairs[i:i + 100]
        lines.append(f"{len(chunk)} beginbfchar")
        lines += [f"<{gid:04X}> <{cp:04X}>" for gid, cp in chunk]
        lines.append("endbfchar")
    lines += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    tu = pdf.make_stream("\n".join(lines).encode("ascii"))

    font = pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type0,
        BaseFont=pikepdf.Name("/IBMPlexSansArabic-Regular"), Encoding=pikepdf.Name("/Identity-H"),
        DescendantFonts=pikepdf.Array([cid]), ToUnicode=tu))
    return font, FORM_FONT_KEY

def _space_gid(font):
    """The glyph id the embedded font maps U+0020 to, or None when it cannot be read.

    Conservative on purpose: the rewrite is only safe when the glyph really is the font's space. A face
    that maps U+0020 elsewhere, or a subset whose cmap is unreadable, keeps its original mapping.
    """
    try:
        from fontTools.ttLib import TTFont
        import io as _io
        desc = font["/DescendantFonts"][0]["/FontDescriptor"]
        stream = desc.get("/FontFile2") or desc.get("/FontFile3")
        if stream is None:
            return None
        font = TTFont(_io.BytesIO(stream.read_bytes()))
        name = (font.getBestCmap() or {}).get(0x20)
        # getBestCmap returns a GLYPH NAME; the /W array and the ToUnicode map are keyed by glyph ID
        return font.getGlyphID(name) if name else None
    except Exception:
        return None


def _cid_widths(font) -> dict:
    """CID -> width (1000-unit em) from a Type0 font's /W array; {} when the array is absent."""
    try:
        desc = font["/DescendantFonts"][0]
        arr = desc.get("/W")
        if arr is None:
            return {}
        out, items, i = {}, list(arr), 0
        while i < len(items):
            first = int(items[i])
            if i + 1 < len(items) and isinstance(items[i + 1], pikepdf.Array):
                for k, w in enumerate(items[i + 1]):
                    out[first + k] = float(w)
                i += 2
            else:
                last, w = int(items[i + 1]), float(items[i + 2])
                for cid in range(first, last + 1):
                    out[cid] = w
                i += 3
        return out
    except Exception:
        return {}


def feature_bidi_space(pdf) -> None:
    """Repair the space glyph's Unicode mapping — a producer defect, fixed where it occurs.

    Chrome maps the glyph it uses for a space to U+200F (RLM) when the face also maps a bidi control to
    that glyph. Readers that trust /ToUnicode (MuPDF, and the RAG extractors built on it) then read every
    word boundary as a control character, so a page copies as «سبعة‌مداخل» instead of «سبعة مداخل».
    Measured on Najd: repairing two fonts moved one page's word order from 0.14 to 0.83.

    This is a mapping correction, not a text edit: no glyph, position or word changes — only what the glyph
    is called. A bidi control a reader cannot see has no business owning a visible space's width, so the rule
    is exactly that: a glyph that occupies width is a space, and a glyph our text layer published in
    `/PLMarkCids` is never renamed (it is a mark we placed on purpose).
    """
    import re as _re
    seen, repaired, blind = set(), 0, 0
    for page in pdf.pages:
        for _key, font in (page.obj.get("/Resources", {}).get("/Font", {}) or {}).items():
            # The CIDs the text layer created for direction marks, published by it in `/PLMarkCids` (see
            # fix_text_layer.FontState.finish). A mark is a decision, not an accident: it is never renamed.
            ours = {int(c) for c in (font.get(pdfops.MARK_CIDS_KEY) or [])}
            # Consumed here, then removed: a house key is our bookkeeping, not the customer's document. It was
            # shipping inside the delivered font dict (measured on mon-negative-table.pdf), and an unregistered
            # private key does not belong in a PDF/A-3b file.
            if pdfops.MARK_CIDS_KEY in font:
                del font[pdfops.MARK_CIDS_KEY]

            tu = font.get("/ToUnicode")
            if tu is None or font.objgen in seen:
                continue
            seen.add(font.objgen)
            src = tu.read_bytes().decode("latin-1")
            widths = _cid_widths(font)

            # The glyph the FACE itself calls U+0020, read from its cmap. Needed as its own branch: a subset whose
            # /W cannot be read still names its space, and before the width rule that was the case the repair
            # still worked on (a silent change the review caught — the repair must not depend on ONE reading of
            # the font when a second one is available).
            space_gid = _space_gid(font)

            def _remap(m):
                cid = int(m.group(2), 16)
                if cid in ours:
                    return m.group(3)                       # a mark we placed: not a space, whatever its width
                if space_gid is not None and cid == space_gid:
                    is_space = True                         # this CID *is* the font's space, misnamed a control
                else:
                    # A glyph that occupies width is a space, whatever the ToUnicode calls it: a real bidi control
                    # has zero advance. No threshold, no reference glyph — a page that draws the misnamed space
                    # ONCE is repaired too (measured: a single-word caption).
                    is_space = (widths or {}).get(cid, 0) > 0
                return m.group(1) + ("<0020>" if is_space else m.group(3))

            dst = _re.sub(r"(<([0-9A-Fa-f]{4})>\s*)(<200[EF]>)", _remap, src)
            if not widths and space_gid is None:
                blind += 1                                  # neither reading available: no rule can be applied
            if dst != src:
                # never install something that stopped being a CMap: a silent break here would pass every
                # structural gate and only fail in the reader
                if ("beginbfchar" in dst and "endbfchar" in dst and "endcmap" in dst
                        and len(_re.findall(r"<[0-9A-Fa-f]{4}>\s*<0020>", dst)) >
                        len(_re.findall(r"<[0-9A-Fa-f]{4}>\s*<0020>", src))):
                    font["/ToUnicode"] = pdf.make_stream(dst.encode("latin-1"))
                    repaired += 1
    if repaired:
        print(f"      bidi-space: repaired the space mapping in {repaired} font(s)")
    if blind:
        print(f"      bidi-space: {blind} font(s) with no readable widths and no named space — left as they are")


def feature_acroform(pdf, spec, ctx=None) -> None:
    """Real text fields with an Arabic /TU and the COMPLETE house font in /DR.

    The fields live in the spec (`ACROFORM_FIELDS`: name, /TU, page, rect in PDF points, optional multiline),
    so the report can carry three and the guide one. Each widget is borderless (/BS W 0) and moves no pixel;
    /Q 2 asks for right alignment (bidi is the reader's job — Acrobat is not automatable here).
    """
    import spec_loader
    NS = spec_loader.load()
    import spec_loader as _sl
    if _sl.declares_no_acroform(NS):
        return                       # a filled copy typesets the values; nothing is left to type
    fields = getattr(NS, "ACROFORM_FIELDS", None) or [
        {"name": "applicant_name", "tu": "الاسم الكامل لمقدم الطلب", "page": NS.PAGES - 1,
         "rect": [60, 80, 360, 112]},
    ]
    font, key = form_font(pdf)
    da = pikepdf.String(f"{key} 11 Tf 0 g")
    st = pdf.Root.StructTreeRoot
    pt = st["/ParentTree"]
    nums = pt.get("/Nums", pdf.make_indirect(pikepdf.Array()))
    n = int(st.get("/ParentTreeNextKey", 0))
    widgets = []
    for f in fields:
        page = pdf.pages[f["page"]]
        rect = [float(v) for v in f["rect"]]
        widget = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Annot, Subtype=pikepdf.Name.Widget, FT=pikepdf.Name.Tx,
            T=pikepdf.String(f["name"]), TU=pikepdf.String(f["tu"]),
            Q=2, DA=da, Rect=pikepdf.Array(rect), F=4,
            BS=pikepdf.Dictionary(W=0), P=page.obj,
        ))
        if f.get("multiline"):
            widget["/Ff"] = 4096                       # bit 13: multiline
        ap = pdf.make_stream(b"")
        ap["/Type"] = pikepdf.Name.XObject
        ap["/Subtype"] = pikepdf.Name.Form
        ap["/BBox"] = pikepdf.Array([0, 0, rect[2] - rect[0], rect[3] - rect[1]])
        ap["/Resources"] = pikepdf.Dictionary(Font=pikepdf.Dictionary({key: font}))
        widget["/AP"] = pikepdf.Dictionary(N=pdf.make_indirect(ap))
        ann = page.obj.get("/Annots", pikepdf.Array())
        ann.append(widget)
        page.obj["/Annots"] = ann
        page.obj["/Tabs"] = pikepdf.Name("/S")        # tab order follows the structure tree
        # 7.18.4: a Widget must be nested in a /Form structure element with an OBJR and a StructParent
        form = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.StructElem, S=pikepdf.Name.Form, Pg=page.obj,
            K=pikepdf.Dictionary(Type=pikepdf.Name.OBJR, Obj=widget, Pg=page.obj)))
        form["/P"] = st          # 7.1-12: every structure element carries its parent
        nums.append(n); nums.append(form)
        widget["/StructParent"] = n
        n += 1
        k = st.get("/K")
        if isinstance(k, pikepdf.Array):
            k.append(form)
        elif k is None:
            st["/K"] = pikepdf.Array([form])
        else:
            st["/K"] = pikepdf.Array([k, form])
        widgets.append(widget)
    pt["/Nums"] = nums
    st["/ParentTreeNextKey"] = n

    pdf.Root.AcroForm = pikepdf.Dictionary(
        Fields=pikepdf.Array(widgets),
        DR=pikepdf.Dictionary(Font=pikepdf.Dictionary({key: font})),
        DA=da)


def feature_link_tagging(pdf, spec, ctx=None) -> None:
    """Every Link annotation gets a /Link structure element, an OBJR and an Arabic /Contents.

    A screen reader announces the label; without it the link is silent. Geometry comes from the document's spec.
    """
    import spec_loader
    import types
    NS = spec if isinstance(spec, types.ModuleType) else spec_loader.load()
    st = pdf.Root.StructTreeRoot
    n = int(st.get("/ParentTreeNextKey", 0))
    pt = st["/ParentTree"]
    nums = pt.get("/Nums", pdf.make_indirect(pikepdf.Array()))
    for pi, page in enumerate(pdf.pages):
        h = float(page.obj["/MediaBox"][3])
        links = [a for a in page.obj.get("/Annots", []) if a.get("/Subtype") == pikepdf.Name.Link]
        rows = sorted([a for a in links if float(a["/Rect"][3]) <= h - 70],   # the nav strip is not a row
                      key=lambda a: -float(a["/Rect"][3]))
        row_of = {a.objgen: k for k, a in enumerate(rows)}
        for annot in links:
            r = [float(v) for v in annot["/Rect"]]
            if r[3] > h - 70:                                   # nav strip (top of page in PDF space)
                role = min(NS.SLOTS, key=lambda k: abs(NS.SLOTS[k] - r[0]))
                label = NS.LINK_LABELS[role]
            elif pi == NS.CONTENTS:
                labels = getattr(NS, "CONTENTS_LABELS", [])
                k = row_of.get(annot.objgen, len(labels))
                label = labels[k] if k < len(labels) else "قسم من جدول المحتويات"
            elif pi == NS.REF_PAGE:
                labels = getattr(NS, "REF_LABELS", [])
                k = row_of.get(annot.objgen, len(labels))
                label = labels[k] if k < len(labels) else "مرجع خارجي"
            else:
                label = "رابط"
            annot["/Contents"] = pikepdf.String(label)
            elem = pdf.make_indirect(pikepdf.Dictionary(
                Type=pikepdf.Name.StructElem, S=pikepdf.Name.Link, P=st, Pg=page.obj,
                K=pikepdf.Dictionary(Type=pikepdf.Name.OBJR, Obj=annot, Pg=page.obj)))
            nums.append(n); nums.append(elem)
            annot["/StructParent"] = n; n += 1
            k = st.get("/K")
            if isinstance(k, pikepdf.Array):
                k.append(elem)
            elif k is None:
                st["/K"] = pikepdf.Array([elem])
            else:
                st["/K"] = pikepdf.Array([k, elem])
    pt["/Nums"] = nums
    st["/ParentTreeNextKey"] = n


STAGE5 = {
    "link-tagging": feature_link_tagging,
    "acroform": feature_acroform,
    "page-labels": feature_page_labels,
    "named-destinations": feature_named_destinations,
    "xmp": feature_xmp,
    "output-intent": feature_output_intent,
    "attachments": feature_attachments,
}

# Profiles this build can actually produce. secure/signed are NOT implemented: refusing them by name is
# better than producing a file that omits declared features while the gate still demands them.
SUPPORTED_PROFILES = {"web", "print", "archive"}


def normalise(pdf) -> None:
    """PDF/A hygiene owned by the file, not by a feature. Measured causes, not guesses:
    - 6.9: the OC configuration dictionary must carry /Name and must NOT carry /AS (PDF/A forbids it).
    - 6.6.4/6.7.3: Info must not carry keys XMP cannot mirror (SourceFile/SourceSHA256)."""
    for page in pdf.pages:                     # 6.3.2: every annotation prints
        for a in page.obj.get("/Annots", []):
            if a.get("/Subtype") in (pikepdf.Name.Link, pikepdf.Name.Widget):
                a["/F"] = 4
    oc = pdf.Root.get("/OCProperties")
    if oc is not None:
        ocgs = list(oc.get("/OCGs", []))
        pdf.Root["/OCProperties"] = pikepdf.Dictionary(
            OCGs=pikepdf.Array(ocgs),
            D=pikepdf.Dictionary(Name=pikepdf.String("الطبقات"),
                                 BaseState=pikepdf.Name.On,
                                 Order=pikepdf.Array(ocgs)))
    for k in ("/SourceFile", "/SourceSHA256"):
        if k in pdf.docinfo:
            del pdf.docinfo[k]
    assert "/SourceFile" not in pdf.docinfo and "/SourceSHA256" not in pdf.docinfo


def apply(src: str, dst: str, profile: str = "web", features_path: str = None,
          rendered_sha: str | None = None, chrome_version: str | None = None,
          doc_spec=None) -> list[str]:
    """Apply every declared stage-5 feature allowed in `profile`; returns the names applied, in order.

    `rendered_sha` is the hash of the markup this build handed to Chrome. The producer passes it; the
    manifest carries it, and the gate recomputes it from the same spec and source. This file is never
    read back from disk, so no copy beside the output can go stale.

    `doc_spec` is a module-like object that replaces the loaded document spec. The conformance gate
    (`conformance/`) has no document spec — its cases are the document — so it passes a case spec instead
    of letting the default load a calibrated one. `None` is the pipeline's own path, unchanged.
    """
    if doc_spec is not None and not isinstance(doc_spec, __import__("types").ModuleType):
        raise SystemExit("postprocess: doc_spec must be a module object — anything else would fall back to the "
                         "loaded document spec silently, which is the leak this parameter exists to close")
    if profile not in SUPPORTED_PROFILES:
        raise SystemExit(f"postprocess: profile {profile!r} is not implemented (supported: {sorted(SUPPORTED_PROFILES)})")
    spec = tomllib.load(open(features_path or os.path.join(PROJ, "features.toml"), "rb"))
    applied = []
    with pikepdf.open(src) as pdf:
        # The model boundary, BEFORE anything is tagged: the pipeline refuses the structures it does not
        # model instead of growing an interpreter for them (review P2, second round). A Chrome upgrade that
        # starts emitting nested forms or text inside a form stops the build here, by name.
        outside = model_boundary(pdf)
        if outside:
            raise SystemExit("postprocess: the document is outside the declared model — refused, not interpreted:\n  "
                             + "\n  ".join(outside[:8]))
        for name, f in spec.get("features", {}).items():
            if f.get("stage") != 5 or profile not in f.get("profiles", []):
                continue
            if name not in STAGE5:
                raise SystemExit(f"postprocess: feature {name!r} is declared but has no implementation")
            # One signature for every feature; only `attachments` reads the build context.
            STAGE5[name](pdf, doc_spec or f, {"rendered_sha": rendered_sha, "chrome_version": chrome_version})
            applied.append(name)
        for k in ("/SourceFile", "/SourceSHA256"):
            if k in pdf.docinfo:
                del pdf.docinfo[k]
        assert "/SourceFile" not in pdf.docinfo and "/SourceSHA256" not in pdf.docinfo
        normalise(pdf)
        feature_bidi_space(pdf)
        feature_pdfua(pdf, doc_spec)
        pdf.save(dst)
    return applied


if __name__ == "__main__":
    import sys
    print(apply(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "web",
                rendered_sha=sys.argv[4] if len(sys.argv) > 4 else None,
                chrome_version=sys.argv[5] if len(sys.argv) > 5 else None))
