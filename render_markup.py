"""The markup handed to Chrome — one producer for the build and the gate.

A copy of what Chrome printed used to sit beside every build (`<out>.source.html`). A copy can go
missing, go stale, or belong to another build, and then the gate judges a document against text that
is not its own. This module derives that markup from the spec and the source template instead, so
both sides compute the same string: the build hashes it into `manifest.json` ("rendered_sha256") and
the gate recomputes it and compares.

Pure by design: no argv, no globals, no writes. `proj` defaults to this file's directory, so a
caller in `scripts/` gets the repository root without repeating the path.
"""
import base64
import functools
import io
import os
import re

_AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def arabic_digits(n: int) -> str:
    """The numeral as the documents print it (Arabic-Indic), so a spec never writes the count twice."""
    return str(int(n)).translate(_AR_DIGITS)


def _mime(path: str) -> str:
    return {".woff2": "font/woff2", ".ttf": "font/ttf", ".otf": "font/otf"}.get(
        os.path.splitext(path)[1], "font/ttf")


def _embed_css(css: str, font_dir: str) -> str:
    """Base64-embed every `url('file')` of a font stylesheet, so the print is offline and deterministic."""
    def _embed(m):
        fp = os.path.join(font_dir, m.group(1))
        with open(fp, "rb") as fh:
            payload = base64.b64encode(fh.read()).decode()
        return "url(data:" + _mime(fp) + ";base64," + payload + ")"
    return re.sub(r"url\('([^']+)'\)", _embed, css)


def _qr_datauri(url: str) -> str:
    import segno
    q = segno.make(url, error="m")
    buf = io.BytesIO()
    q.save(buf, kind="png", scale=10, border=2, dark="#3d1a9e", light="#ffffff")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _art_for_print(path: str) -> bytes:
    """The art as embedded: capped at 300 dpi for its printed size. Source files stay untouched."""
    from PIL import Image
    target = (round(21.0 / 2.54 * 300), round(29.7 / 2.54 * 300))     # A4 at 300 dpi = 2480 x 3508
    im = Image.open(path)
    if im.width <= target[0] and im.height <= target[1]:
        with open(path, "rb") as fh:
            return fh.read()
    im = im.convert("RGB").resize(target, Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85, dpi=(300, 300))
    return buf.getvalue()


def markup_sha256(markup: str) -> str:
    """The hash the manifest carries and the gate recomputes — one function, one encoding.

    Hashing the string (not the bytes of a file written in text mode) keeps the two sides independent of
    newline translation on the platform that produced the file.
    """
    import hashlib
    return hashlib.sha256(markup.encode("utf-8")).hexdigest()


# The pure, expensive steps are cached by their arguments. A file replaced inside one process is out of
# scope: a build reads each font/art file once, and nothing rewrites them mid-run.
_embed_css = functools.lru_cache(maxsize=8)(_embed_css)
_qr_datauri = functools.lru_cache(maxsize=64)(_qr_datauri)
_art_for_print = functools.lru_cache(maxsize=16)(_art_for_print)


def rendered_markup(spec, source_html: str, proj: str | None = None) -> str:
    """The exact markup this spec asks Chrome to print.

    The order of the substitutions is the order the build has always used; changing it would change
    the bytes, and the gate's whole job is to compare those bytes with the manifest's hash.
    """
    proj = proj or os.path.dirname(os.path.abspath(__file__))
    html = source_html
    fdir = os.path.join(proj, "fonts")
    if os.path.isdir(fdir):
        fcss = open(os.path.join(fdir, "fonts.css"), encoding="utf-8").read()
        html = html.replace("/*__FONTS__*/", _embed_css(fcss, fdir))
    ndir = os.path.join(proj, "najd")
    if "/*__FONTS_NAJD__*/" in html and os.path.isdir(ndir):
        ncss = open(os.path.join(ndir, "fonts.css"), encoding="utf-8").read()
        html = html.replace("/*__FONTS_NAJD__*/", _embed_css(ncss, ndir))
    html = re.sub(r"<link[^>]*fonts\.(?:googleapis|gstatic)\.com[^>]*>\s*", "", html)
    for ph, url in getattr(spec, "QR_FIXED", []):
        html = html.replace(ph, _qr_datauri(url))
    if "{{LINKS_CLAIM}}" in html:
        if not hasattr(spec, "LINKS_CLAIM"):
            raise ValueError("the source prints {{LINKS_CLAIM}} but the spec declares no LINKS_CLAIM")
        html = html.replace("{{LINKS_CLAIM}}", spec.LINKS_CLAIM)
    if "{{MUTATIONS_CLAIM}}" in html:
        # The mutation count is a claim about THIS variant: a print copy carries fewer applicable
        # mutations, and the printed number must be its own. Derived from the spec, never typed twice.
        if not hasattr(spec, "GATE_MUTATIONS"):
            raise ValueError("the source prints {{MUTATIONS_CLAIM}} but the spec declares no GATE_MUTATIONS")
        html = html.replace("{{MUTATIONS_CLAIM}}", arabic_digits(spec.GATE_MUTATIONS))
    if "{{ATTACHMENTS_CLAIM}}" in html:
        # The number of attached files is not a claim to be read back: it is derived from the list the
        # producer actually attaches, so it cannot disagree with the file.
        if not getattr(spec, "ATTACHMENT_FILES", None):
            raise ValueError("the source prints {{ATTACHMENTS_CLAIM}} but the spec declares no ATTACHMENT_FILES")
        html = html.replace("{{ATTACHMENTS_CLAIM}}", arabic_digits(len(spec.ATTACHMENT_FILES)))
    if not getattr(spec, "NAV_VISIBLE", True):
        # A print copy carries no navigation chrome: the icons are ink on paper and take four click
        # targets that can never be clicked. Stripping the markup (not hiding it with CSS) removes both.
        cls = getattr(spec, "NAV_CLASS", None)
        if not cls:
            raise ValueError("the spec hides the navigation strip but declares no NAV_CLASS")
        html = re.sub(r'\s*<div class="%s">.*?</div>' % re.escape(cls), "", html, flags=re.S)
    for k, url in enumerate(getattr(spec, "REF_URLS", []), start=1):
        html = html.replace("{{QR_%d}}" % k, _qr_datauri(url))
    # v2 generated-art layer: base64-embed local art so the print stays deterministic (Chrome renders
    # from a temp dir; relative paths would break).
    art = getattr(spec, "ART_FILES", None)
    if not art:
        raise ValueError("ART FILES: the spec declares none — every document names its own plates")
    for ph, fn in art:
        fp = fn if os.path.isabs(fn) else os.path.join(proj, "art", fn)
        # A declared plate that is absent used to be skipped in silence, leaving the placeholder in the
        # markup and failing much later as a blank page. The declaration is a contract: break it loudly.
        if not os.path.exists(fp):
            raise ValueError(f"ART FILES: {fn} is declared by the spec but missing at {fp}")
        if ph not in html:
            raise ValueError(f"ART FILES: placeholder {ph} for {fn} is not in the source HTML")
        payload = base64.b64encode(_art_for_print(fp)).decode()
        html = html.replace(ph, "data:image/jpeg;base64," + payload)
    if "{{ART_" in html:
        raise ValueError("ART FILES: an ART placeholder survived the substitution")
    if "{{QR_" in html:
        raise ValueError("QR: a QR placeholder survived — the spec declares fewer QR_FIXED / REF_URLS than the source prints")
    return html
