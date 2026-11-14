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
    import nav_spec as NS
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
    import nav_spec as NS
    names = pikepdf.Array()
    for name, page in NS.DEST_NAMES:
        names.append(pikepdf.String(name))
        names.append(pikepdf.Dictionary(D=pikepdf.Array([pdf.pages[page].obj, pikepdf.Name.Fit])))
    pdf.Root.Names = pikepdf.Dictionary(Dests=pikepdf.Dictionary(Names=names))


def feature_xmp(pdf, spec) -> None:
    """XMP is what archive/search tools read; Info alone is invisible to them."""
    import nav_spec as NS
    sha = pdf.docinfo.get("/SourceSHA256", "")
    with pdf.open_metadata() as m:
        m["dc:title"] = f"معيار إنتاج ملفات PDF — دليل المعيار · الإصدار {NS.GUIDE_VERSION_AR}"
        m["dc:creator"] = ["م. عبدالرحمن جحفلي"]
        m["dc:description"] = "معيار جودة إنتاج ملفات PDF التفاعلية العربية"
        m["dc:language"] = ["ar"]
        m["xmp:CreatorTool"] = "Hermes PDF Gold Standard pipeline"
        m["pdf:Producer"] = "PyMuPDF + pikepdf"
        m["xmpMM:DocumentID"] = f"sha256:{sha}" if sha else "urn:pdf-gold-standard"


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
    """The file carries its own source and a manifest of hashes: reproduction is content, not a claim."""
    import nav_spec as NS
    src_path = os.path.join(PROJ, NS.SOURCE_HTML)
    data = open(src_path, "rb").read()
    manifest = {
        "source": NS.SOURCE_HTML,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "guide_version": NS.GUIDE_VERSION,
        "pages": NS.PAGES,
    }
    files = {
        "source.html": (data, "text/html"),
        "manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=1).encode(), "application/json"),
    }
    for name, (payload, mime) in files.items():
        spec_obj = pikepdf.AttachedFileSpec(pdf, payload, mime_type=mime, filename=name)
        spec_obj.obj["/AFRelationship"] = pikepdf.Name.Source
        pdf.attachments[name] = spec_obj
    # /AF on the document lists the associated files (PDF/A-3 asks for it)
    pdf.Root.AF = pikepdf.Array([pdf.attachments[n].obj for n in files])


STAGE5 = {
    "page-labels": feature_page_labels,
    "named-destinations": feature_named_destinations,
    "xmp": feature_xmp,
    "output-intent": feature_output_intent,
    "attachments": feature_attachments,
}


def apply(src: str, dst: str, profile: str = "web", features_path: str = None) -> list[str]:
    """Apply every declared stage-5 feature allowed in `profile`; returns the names applied, in order."""
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
        pdf.save(dst)
    return applied


if __name__ == "__main__":
    import sys
    print(apply(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "web"))
