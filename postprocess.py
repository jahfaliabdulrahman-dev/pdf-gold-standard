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


def feature_page_labels(pdf, spec) -> None:
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


def feature_named_destinations(pdf, spec) -> None:
    """A name -> page map, so a target is an identity, not an index that shifts when a page is added."""
    import spec_loader
    NS = spec_loader.load()
    names = pikepdf.Array()
    for name, page in NS.DEST_NAMES:
        names.append(pikepdf.String(name))
        names.append(pikepdf.Dictionary(D=pikepdf.Array([pdf.pages[page].obj, pikepdf.Name.Fit])))
    pdf.Root.Names = pikepdf.Dictionary(Dests=pikepdf.Dictionary(Names=names))


def feature_xmp(pdf, spec) -> None:
    """XMP is what archive/search tools read; Info alone is invisible to them."""
    import spec_loader
    NS = spec_loader.load()
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


def feature_output_intent(pdf, spec) -> None:
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


def feature_attachments(pdf, spec) -> None:
    """The file carries its own source and a manifest of hashes: reproduction is content, not a claim.

    The file list lives in the spec (`ATTACHMENT_FILES`: name, repo-relative path, mime, /AFRelationship), so a
    second document adds evidence without touching this code. A name with no path is generated here (the
    manifest), which is how the hashes always describe the file that was actually built.
    """
    import spec_loader
    NS = spec_loader.load()
    src_path = os.path.join(PROJ, NS.SOURCE_HTML)
    data = open(src_path, "rb").read()
    manifest = {
        "source": NS.SOURCE_HTML,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "guide_version": NS.GUIDE_VERSION,
        "pages": NS.PAGES,
    }
    declared = getattr(NS, "ATTACHMENT_FILES", None) or [
        ("source.html", NS.SOURCE_HTML, "text/html", "Source"),
        ("manifest.json", None, "application/json", "Source"),
    ]
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


def feature_acroform(pdf, spec) -> None:
    """Real text fields with an Arabic /TU and an embedded house font in /DR.

    The fields live in the spec (`ACROFORM_FIELDS`: name, /TU, page, rect in PDF points, optional multiline),
    so the report can carry three and the guide one. Each widget is borderless (/BS W 0) and moves no pixel;
    /Q 2 asks for right alignment (bidi is the reader's job — Acrobat is not automatable here).
    """
    import spec_loader
    NS = spec_loader.load()
    fields = getattr(NS, "ACROFORM_FIELDS", None) or [
        {"name": "applicant_name", "tu": "الاسم الكامل لمقدم الطلب", "page": NS.PAGES - 1,
         "rect": [60, 80, 360, 112]},
    ]
    fonts = pdf.pages[0].obj["/Resources"]["/Font"]
    key = next(iter(fonts.keys()))
    da = pikepdf.String(f"{key} 10 Tf 0 g")
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
        ap["/Resources"] = pikepdf.Dictionary(Font=pikepdf.Dictionary({key: fonts[key]}))
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
        DR=pikepdf.Dictionary(Font=pikepdf.Dictionary({key: fonts[key]})),
        DA=da)


def feature_link_tagging(pdf, spec) -> None:
    """Every Link annotation gets a /Link structure element, an OBJR and an Arabic /Contents.

    A screen reader announces the label; without it the link is silent. Geometry comes from the document's spec.
    """
    import spec_loader
    NS = spec_loader.load()
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


def apply(src: str, dst: str, profile: str = "web", features_path: str = None) -> list[str]:
    """Apply every declared stage-5 feature allowed in `profile`; returns the names applied, in order."""
    if profile not in SUPPORTED_PROFILES:
        raise SystemExit(f"postprocess: profile {profile!r} is not implemented (supported: {sorted(SUPPORTED_PROFILES)})")
    spec = tomllib.load(open(features_path or os.path.join(PROJ, "features.toml"), "rb"))
    applied = []
    with pikepdf.open(src) as pdf:
        for name, f in spec.get("features", {}).items():
            if f.get("stage") != 5 or profile not in f.get("profiles", []):
                continue
            if name not in STAGE5:
                raise SystemExit(f"postprocess: feature {name!r} is declared but has no implementation")
            STAGE5[name](pdf, f)
            applied.append(name)
        for k in ("/SourceFile", "/SourceSHA256"):
            if k in pdf.docinfo:
                del pdf.docinfo[k]
        assert "/SourceFile" not in pdf.docinfo and "/SourceSHA256" not in pdf.docinfo
        normalise(pdf)
        pdf.save(dst)
    return applied


if __name__ == "__main__":
    import sys
    print(apply(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "web"))
