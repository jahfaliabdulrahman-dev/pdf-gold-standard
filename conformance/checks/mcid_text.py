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

from conformance.cmap import parse_tu_report

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
        # The simple-font exception (Matterhorn 31-027) rests on the ENCODING carrying the mapping, so the
        # encoding has to be read: a custom /Differences or a non-standard base is not verifiable here.
        self.encoding = ""
        self.encoding_differences = False
        self.glyph_names = {}
        try:
            enc = font.get("/Encoding")
            if enc is not None:
                if hasattr(enc, "get"):
                    self.encoding = str(enc.get("/BaseEncoding", "") or "")
                    diffs = enc.get("/Differences")
                    if diffs is not None:
                        self.encoding_differences = True
                        code = 0
                        for item in diffs:
                            if isinstance(item, (int, float)):
                                code = int(item)
                            else:
                                self.glyph_names[code] = str(item).lstrip("/")
                                code += 1
                else:
                    self.encoding = str(enc)
        except Exception:
            self.encoding = ""
        self.map = {}
        self.unparsable = False
        self.width_mismatch = False
        self.capped = 0
        self.problem = ""
        self.problems = []
        if tu is not None:
            try:
                report = parse_tu_report(tu.read_bytes().decode("latin-1"))
                self.map = report["map"]
                self.capped = int(report.get("capped") or 0)
                self.problems = list(report.get("problems") or [])
                # The source codes must be as wide as the font's codes: `<41>` and `<0041>` are different
                # code spaces, and a map written for one cannot name the other. The codespace range says the
                # same thing from the other side; both are checked because either can be wrong alone. A
                # mismatch is a CONFORMANCE warning, not an unparsable map: the entries can still be usable
                # (a 2-byte codespace declaration over 1-byte keys was measured on a real owner file), so the
                # signal is medium, not the high of a parse failure.
                expected_bytes = 2 if self.two_byte else 1
                widths = set(report.get("src_widths") or [])
                codespace = set(report.get("codespace_widths") or [])
                # `/UseCMap` is legal inheritance the parser does not resolve. The strict writer wrapper still
                # refuses it (it cannot rebuild the inherited map), but the CHECKER must not call a conforming
                # file high: the local entries are used and the inheritance is named as a medium limitation.
                usecmap_only = bool(self.problems) and all("usecmap" in p for p in self.problems)
                if report.get("unparsable") and not usecmap_only:
                    self.unparsable = True
                    self.problem = "; ".join(report.get("problems") or [])[:300]
                elif widths and any(w != expected_bytes for w in widths):
                    self.width_mismatch = True
                    self.problem = (f"ToUnicode source codes are {sorted(widths)} byte(s); "
                                    f"the font uses {expected_bytes}")
                elif codespace and expected_bytes not in codespace:
                    self.width_mismatch = True
                    self.problem = (f"ToUnicode codespace is {sorted(codespace)} byte(s); "
                                    f"the font uses {expected_bytes}")
                elif usecmap_only:
                    self.problem = "; ".join(self.problems)[:300]
            except Exception as exc:
                # A /ToUnicode that is not a stream, or a stream that cannot be read: a named defect, never
                # the silent `{}` that made every code look unmapped and every report look the same.
                self.unparsable = True
                self.problem = f"ToUnicode could not be read: {type(exc).__name__}"
                self.map = {}

    def decode(self, raw: bytes) -> tuple[str, dict]:
        """(text, counts) — `counts` is per DRAWING of this string, keyed for aggregation.

        A code with no entry decodes to '' and is never invented — the count is what the font check
        reports. The mapped value is inspected character by character: a valid CMap can still map a code to
        the private use area (a glyph name, not a letter), to U+FFFD, to U+0000 (Matterhorn 31-028) or to
        U+FEFF/U+FFFE (31-029), and the reader then shows exactly that. Counting them here is the only place
        that sees the mapping itself rather than a reader's interpretation of it.
        """
        width = 2 if self.two_byte else 1
        out = []
        counts: dict = {"codes": 0, "notdef": 0, "missing_unicode": 0, "pua": 0, "replacement": 0,
                        "zero_value": 0, "bom": 0, "missing_in_word": 0}
        counts["missing_codes"] = {}
        codes = [int.from_bytes(raw[i:i + width], "big") for i in range(0, len(raw) - width + 1, width)]
        for idx, code in enumerate(codes):
            counts["codes"] += 1
            if code == 0:
                counts["notdef"] += 1
                continue
            if code not in self.map:
                counts["missing_unicode"] += 1
                counts["missing_codes"][code] = counts["missing_codes"].get(code, 0) + 1
                # A gap INSIDE a word destroys the word; a gap between words (a bullet, a tab, a rule) does
                # not. The neighbours are read from the same string: previous decoded character, and the
                # first character of the next code's mapping.
                prev = out[-1][-1] if out and out[-1] else ""
                nxt = ""
                if idx + 1 < len(codes):
                    nxt = (self.map.get(codes[idx + 1]) or "")[:1]
                if prev.isalpha() and nxt.isalpha():
                    counts["missing_in_word"] += 1
                continue
            value = self.map[code]
            out.append(value)
            for ch in value:
                cp = ord(ch)
                if 0xE000 <= cp <= 0xF8FF:
                    counts["pua"] += 1
                elif cp == 0xFFFD:
                    counts["replacement"] += 1
                elif cp == 0:
                    counts["zero_value"] += 1
                elif cp in (0xFEFF, 0xFFFE):
                    counts["bom"] += 1
        return "".join(out), counts


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
                text, counts = font.decode(_string_bytes(o))
                if counts["codes"]:
                    out.setdefault(key, []).append(text)
                    for k in ("notdef", "missing_unicode", "pua", "replacement", "zero_value", "bom", "codes",
                              "missing_in_word"):
                        stats[k] += counts[k]
                    # Keyed by resource name AND family: two pages can both name their font «/F1» while one
                    # of them carries a different program, and a merged row would hide the broken one.
                    fkey = f"{font.name}|{font.family or font.subtype}"
                    row = stats["fonts"].setdefault(fkey, {
                        "name": font.name, "family": font.family, "subtype": font.subtype,
                        "embedded": font.embedded, "tounicode": font.has_tounicode,
                        "two_byte": font.two_byte, "encoding": font.encoding,
                        "encoding_differences": font.encoding_differences, "codes": 0, "notdef": 0,
                        "missing_unicode": 0, "missing_in_word": 0, "missing_codes": {}, "glyph_names": {},
                        "pua": 0, "replacement": 0, "zero_value": 0, "bom": 0,
                        "unparsable": False, "capped": 0, "width_mismatch": False, "problem": "",
                        "problems": [],
                    })
                    row["unparsable"] = row["unparsable"] or font.unparsable
                    row["capped"] = max(row["capped"], font.capped)
                    row["width_mismatch"] = row["width_mismatch"] or font.width_mismatch
                    row["problem"] = row["problem"] or font.problem
                    row["problems"].extend(font.problems)
                    for k in ("codes", "notdef", "missing_unicode", "missing_in_word", "pua", "replacement",
                              "zero_value", "bom"):
                        row[k] += counts[k]
                    for c, n in counts["missing_codes"].items():
                        row["missing_codes"][c] = row["missing_codes"].get(c, 0) + n
                        if c in font.glyph_names:
                            row["glyph_names"][c] = font.glyph_names[c]
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
    """{'text': {(page, mcid): str}, 'fonts': {key: row}, 'notdef', 'missing_unicode', 'missing_in_word',
    'pua', 'replacement', 'zero_value', 'bom', 'codes'} for one file.

    The per-font rows are the numbers the checker reports: a composite font that draws codes its ToUnicode
    does not name is the failure ISO 32000-1 §14.8.2.4.2 forbids, and it is invisible in a merged total.
    """
    out: dict = {}
    stats = {"notdef": 0, "missing_unicode": 0, "missing_in_word": 0, "codes": 0, "pua": 0,
             "replacement": 0, "zero_value": 0, "bom": 0, "fonts": {}}
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
