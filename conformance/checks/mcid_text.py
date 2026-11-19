"""What each marked-content sequence says — and what the fonts that draw it are.

Why this exists, measured: pdfplumber/pdfminer expose `mcid` per character, but the value is lost as soon as
Chrome nests a `/Span` inside a `/P` — the inner `EMC` resets the extractor's single `cur_mcid` slot, so
almost every character in our files comes back with `mcid=None` while the structure tree lists an MCID for
every leaf. Fixing a third-party library's stack is not our job; reading the content stream with a stack is.

The decoder is **not** new: `fix_text_layer.parse_tu` is the repository's ToUnicode reader, already used to
rebuild the layer. Reusing it here is deliberate — a second CMap parser would be a second opinion that can
drift. The risk that one reader hides a defect in both places is answered by a planted mutation (a character
changed in one heading's ToUnicode must be caught) and by never comparing this text against the pipeline's
own output: the comparison is against the case's truth.

Handled: inline `BDC` dictionaries, named property lists (`/Resources /Properties`), bare `BMC`, `Do` into
Form XObjects with their own resources, and `'` / `"` line moves. Code 0 in an Identity-H font is glyph 0 —
`.notdef` — and is counted, never silently decoded.
"""
import os
import sys

import pikepdf

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if os.path.join(REPO, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "scripts"))

from fix_text_layer import parse_tu          # noqa: E402  (the repository's ToUnicode reader)

TEXT_OPS = {"Tj", "TJ", "'", '"'}


class _Font:
    """code -> text for one font resource. Type0 uses two-byte codes; anything else, one byte."""

    def __init__(self, name: str, font):
        self.name = name
        self.two_byte = str(font.get("/Subtype")) == "/Type0"
        self.subtype = str(font.get("/Subtype"))
        desc = font.get("/FontDescriptor")
        if desc is None and self.two_byte:
            try:                                   # a Type0 font keeps its descriptor on the descendant
                desc = font["/DescendantFonts"][0].get("/FontDescriptor")
            except Exception:
                desc = None
        self.family = ""
        self.embedded = False
        try:
            if desc is not None:
                self.family = str(desc.get("/FontName", "")).lstrip("/").split("+")[-1]
                self.embedded = any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3"))
            if self.subtype == "/Type3":
                self.embedded = True        # the glyph procedures ARE the font: nothing external to embed
            base = str(font.get("/BaseFont", "")).lstrip("/")
            self.family = self.family or base.split("+")[-1]
        except Exception:
            pass
        tu = font.get("/ToUnicode")
        self.has_tounicode = tu is not None
        self.map = {}
        if tu is not None:
            try:
                self.map = parse_tu(tu.read_bytes().decode("latin-1"))
            except Exception:
                self.map = {}

    def decode(self, raw: bytes) -> tuple[str, int, int]:
        """(text, notdef_codes, codes_without_a_unicode_value). A code with no entry decodes to '' and is
        never invented — the count is what the font check reports."""
        width = 2 if self.two_byte else 1
        out, notdef, missing = [], 0, 0
        for i in range(0, len(raw) - width + 1, width):
            code = int.from_bytes(raw[i:i + width], "big")
            if code == 0:
                notdef += 1
            elif code not in self.map:
                missing += 1
            out.append(self.map.get(code, ""))
        return "".join(out), notdef, missing


def _string_bytes(obj) -> bytes:
    try:
        return obj.read_bytes()
    except Exception:
        pass
    try:
        return bytes(obj)
    except Exception:
        return b""


def _fonts(resources) -> dict:
    out = {}
    try:
        for name, font in (resources or {}).get("/Font", {}).items():
            out[str(name)] = _Font(str(name), font)
    except Exception:
        pass
    return out


def _walk(instructions, resources, page_no, out: dict, stats: dict, depth=0, props=None):
    fonts = _fonts(resources)
    font = None
    frames: list = []                             # MCID (or None) per open marked-content sequence
    for ins in instructions:
        op, operands = str(ins.operator), ins.operands
        if op == "Tf" and operands:
            font = fonts.get(str(operands[0]))
        elif op in ("BMC", "BDC"):
            mcid = None
            if op == "BDC" and len(operands) > 1:
                d = operands[1]
                if isinstance(d, str) and props:
                    d = props.get(d)
                if hasattr(d, "get"):
                    try:
                        mcid = int(d.get("/MCID")) if d.get("/MCID") is not None else None
                    except Exception:
                        mcid = None
            frames.append(mcid)
        elif op == "EMC":
            if frames:
                frames.pop()
        elif op in TEXT_OPS and font is not None:
            current = next((m for m in reversed(frames) if m is not None), None)
            key = (page_no, current if current is not None else -1)
            # A `TJ` operand is ONE array (`[(...)-120(...)]TJ`), not a list of operands: iterating `operands`
            # handed the array itself to the decoder, which returned b"" and a silent empty string. Our own
            # pipeline writes `Tj`, so the gate never noticed; Typst and WeasyPrint write `TJ`, and every
            # tag-text check then accused their files of carrying no text (measured in E3).
            items = operands
            if op == "TJ" and len(operands) == 1 and type(operands[0]).__name__ in ("Object", "Array"):
                try:
                    items = list(operands[0])
                except Exception:
                    items = operands
            for o in (items if op == "TJ" else operands[:1]):
                if type(o).__name__ in ("int", "float"):
                    continue
                text, notdef, missing = font.decode(_string_bytes(o))
                if text or notdef or missing:
                    out.setdefault(key, []).append(text)
                    stats["notdef"] += notdef
                    stats["missing_unicode"] += missing
                    stats["codes"] += len(text) + notdef + missing
                    stats["fonts"][font.name] = {"family": font.family, "subtype": font.subtype,
                                                 "embedded": font.embedded,
                                                 "tounicode": font.has_tounicode}
        elif op == "Do" and operands and depth < 4:
            try:
                xo = (resources or {}).get("/XObject", {}).get(str(operands[0]))
            except Exception:
                xo = None
            if xo is None or str(xo.get("/Subtype")) != "/Form":
                continue
            try:
                sub = list(pikepdf.parse_content_stream(xo))
            except Exception:
                continue
            sub_res = xo.get("/Resources")
            sub_props = {}
            try:
                sub_props = {str(k): v for k, v in (sub_res or {}).get("/Properties", {}).items()}
            except Exception:
                pass
            _walk(sub, sub_res, page_no, out, stats, depth + 1, sub_props)


def scan(pdf_path: str) -> dict:
    """{'text': {(page, mcid): str}, 'fonts': {...}, 'notdef': n, 'codes': n} for one file."""
    out: dict = {}
    stats = {"notdef": 0, "missing_unicode": 0, "codes": 0, "fonts": {}}
    with pikepdf.open(pdf_path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            try:
                instructions = list(pikepdf.parse_content_stream(page))
            except Exception:
                continue
            # `/Resources` is INHERITABLE (PDF 32000-1 §7.7.3.4): a page may leave it to the /Pages node, and
            # most producers do. Reading only the page's own key found no fonts at all on Typst and WeasyPrint
            # output — every tag-text check then accused the file of carrying nothing, which was our bug, not
            # their defect (measured in E3: fonts {} and codes 0 while the page had 6 BDC /MCID).
            res = page.obj.get("/Resources")
            node = page.obj
            depth = 0
            while res is None and depth < 32:
                parent = node.get("/Parent")
                if parent is None:
                    break
                res = parent.get("/Resources")
                node = parent
                depth += 1
            props = {}
            try:
                props = {str(k): v for k, v in (res or {}).get("/Properties", {}).items()}
            except Exception:
                pass
            _walk(instructions, res, page_no, out, stats, 0, props)
    return {"text": {k: "".join(v) for k, v in out.items()}, **stats}


def mcid_text(pdf_path: str) -> dict:
    return scan(pdf_path)["text"]
