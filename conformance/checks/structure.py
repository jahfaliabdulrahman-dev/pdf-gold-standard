"""The general structural checks — what the file is supposed to say, and what it is tagged as saying.

Every check returns `{"id", "status": pass|fail|na, "reason"}`. Three rules:

  · **A check that cannot read its input fails**, never passes by default (the pipeline's own rule).
  · **Text is compared as a word multiset, not as a sequence.** Attribution — *which* text is under *which*
    element — is this module's subject; *order* is the readers' metric (`order`, `exact`), and each reader is
    scored separately. A structure check that also demanded order would report the same defect twice, once
    without naming the reader that caused it.
  · **`n/a` carries its reason.** The model boundary applies only when our post-processing ran; on another
    engine's raw output it is `n/a` with that sentence, not a pass.

The anchors are the published ones: tagging and language are PDF/UA-1 requirements (Matterhorn 01, 09, 11,
14, 15), the font rules are Matterhorn 31-027 (ToUnicode) and 31-030 (`.notdef`), and the profile verdicts
come from veraPDF's own rule set at clause-testNumber granularity.
"""
import os
import re
import unicodedata
from collections import Counter

import pikepdf

from . import mcid_text, verapdf as verapdf_mod
from . import metrics

HEADING_TAGS = {f"/H{i}": i for i in range(1, 7)}
BLOCK_TAGS = set(HEADING_TAGS) | {"/P", "/L", "/Table", "/Figure", "/Sect", "/Div"}
WRAPPERS = {"/NonStruct", "/Span", "/Link", "/Lbl", "/LBody", "/Annot", "/Form", "/Document", "/Part"}


class Node:
    __slots__ = ("tag", "page", "mcids", "children")

    def __init__(self, tag, page=None):
        self.tag, self.page, self.mcids, self.children = tag, page, [], []

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def text_slots(self):
        for page, mcid in self.mcids:
            yield page, mcid
        for child in self.children:
            yield from child.text_slots()


def read_tree(pdf) -> Node:
    """The structure tree as Nodes, with /Pg inherited and MCIDs resolved to (page, mcid)."""
    root = pdf.Root.get("/StructTreeRoot")
    if root is None:
        raise ValueError("no /StructTreeRoot")
    page_of = {page.objgen: i + 1 for i, page in enumerate(pdf.pages)}
    top = Node("/StructTreeRoot")

    def fill(node, elem, inherited_page):
        pg = elem.get("/Pg") or inherited_page
        page_no = page_of.get(pg.objgen) if pg is not None else None
        node.page = page_no
        k = elem.get("/K")
        if k is None:
            return
        items = list(k) if isinstance(k, pikepdf.Array) else [k]
        for item in items:
            if isinstance(item, int):
                node.mcids.append((page_no, int(item)))
            elif isinstance(item, pikepdf.Dictionary) and str(item.get("/Type")) == "/MCR":
                # a marked-content reference (Word, Acrobat): /MCID + /Pg, and no /S
                mref = item.get("/Pg") or pg
                mpage = page_of.get(mref.objgen) if mref is not None else page_no
                if item.get("/MCID") is not None:
                    node.mcids.append((mpage, int(item.get("/MCID"))))
            elif isinstance(item, pikepdf.Dictionary) and str(item.get("/Type")) == "/OBJR":
                continue                       # an object reference carries no text
            elif isinstance(item, pikepdf.Dictionary):
                tag = str(item.get("/S", ""))
                child = Node(tag)
                node.children.append(child)
                fill(child, item, pg)

    kids = root.get("/K")
    for item in (list(kids) if isinstance(kids, pikepdf.Array) else [kids]):
        if isinstance(item, pikepdf.Dictionary):
            tag = str(item.get("/S", ""))
            child = Node(tag)
            top.children.append(child)
            fill(child, item, None)
    return top


ARABIC = re.compile("[\u0600-\u06FF\u0750-\u077F]")
LATIN_OR_DIGIT = re.compile("[A-Za-z0-9]")


def _token(token: str) -> str:
    """One token of a LAYER text, in the order a comparison can use.

    NFKC first, so an Arabic presentation form reads as its base letter: the form itself is a defect of the
    layer, not a disagreement about which text is tagged, and it has its own check (`presentation-forms`).

    Then: the layer stores an RTL run in **visual** order (the glyphs are drawn right to left), so an
    RTL-only token is reversed before comparison. A token carrying Latin letters or digits is left alone —
    those are stored in reading order inside the run. This is a property of reading the *file*, never a
    normalization of a reader's output (readers are compared with `metrics.N` untouched).
    """
    # Invisible joiners are stripped FOR ATTRIBUTION ONLY: whether the producer inserted them is the separate
    # check `invisible-format`, and counting the same defect twice would hide which one it is. `exact` keeps
    # them (metrics.N is literal), so the product metric still prices them.
    token = metrics.ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", token))
    if ARABIC.search(token) and not LATIN_OR_DIGIT.search(token):
        # sorted characters, not a reversal: a vocalised token stores its marks beside the base letter in an
        # order a naive reversal would corrupt (measured on «الْحَمْدُ»). Within one token the characters are
        # what attribution needs; the order of tokens and of characters is the readers' metric.
        return "".join(sorted(token))
    return token


def words_multi(text: str) -> Counter:
    """The word multiset of a layer text under `_token` — attribution, not order."""
    return Counter(_token(t) for t in metrics.N(text).split())


def same_words(a: str, b: str) -> bool:
    return words_multi(a) == words_multi(b)


def layer_seq(text: str) -> list[str]:
    """The tokens of a LAYER text in reading order — a run stored in visual order is reversed as a sequence.

    Only a layer is reversed; the truth is already logical, and reversing both sides would cancel the very
    difference the check exists to see (measured: the heading check failed on a clean file because of it).
    A run carrying Latin or digits is left alone: its order is the readers' metric, not this module's. Per-token
    characters are sorted in `_token`, so a vocalised token whose marks sit beside the base letter survives.
    """
    norm = metrics.N(text)
    tokens = [_token(t) for t in norm.split()]
    if norm and not LATIN_OR_DIGIT.search(norm):
        tokens = list(reversed(tokens))
    return tokens


def truth_seq(text: str) -> list[str]:
    return [_token(t) for t in metrics.N(text).split()]


def same_sequence(got_layer: str, want_truth: str) -> bool:
    return layer_seq(got_layer) == truth_seq(want_truth)


def _block_tags(case: dict) -> list[str]:
    out = []
    for block in case["blocks"]:
        if block["type"] == "heading":
            out.append(f"/H{block['level']}")
        elif block["type"] == "paragraph":
            out.append("/P")
        elif block["type"] == "list":
            out.append("/L")
        elif block["type"] == "table":
            out.append("/Table")
    return out


def _collapse(tags: list[str]) -> list[str]:
    out = []
    for t in tags:
        if not out or out[-1] != t:
            out.append(t)
    return out


def _case_cells(block: dict) -> list[list[str]]:
    header = block["header"]
    rows = [header] if header and not isinstance(header[0], list) else list(header)
    return [list(map(str, r)) for r in rows] + [list(map(str, r)) for r in block["rows"]]


def evaluate(pdf_path: str, case: dict, producer: dict, run_verapdf: bool = True) -> list[dict]:
    checks: list[dict] = []

    def add(cid: str, ok: bool | None, reason: str) -> None:
        checks.append({"id": cid, "status": "na" if ok is None else ("pass" if ok else "fail"), "reason": reason})

    scan = mcid_text.scan(pdf_path)
    # Joined with a NEWLINE: MCID boundaries are line/element boundaries, and gluing them with "" merges the
    # last word of one element with the first of the next (measured: «ةمدقملوألا»). N collapses it to a space.
    file_text = "\n".join(scan["text"].values())

    with pikepdf.open(pdf_path) as pdf:
        mark = pdf.Root.get("/MarkInfo")
        marked = bool(mark is not None and mark.get("/Marked") is True)
        add("markinfo", marked, "/MarkInfo /Marked true" if marked else "no /MarkInfo with /Marked true")
        lang = str(pdf.Root.get("/Lang", "")).strip("()")
        add("lang", lang.lower().startswith("ar"), f"/Lang {lang!r}" if lang else "no /Lang")

        try:
            tree = read_tree(pdf)
        except ValueError as exc:
            add("tagged", False, str(exc))
            tree = None
        nodes = list(tree.walk()) if tree is not None else []

        # --- every character is tagged (no text outside any MCID) -----------------------------------
        untagged = {k: v for k, v in scan["text"].items() if k[1] < 0}
        untagged_words = sum(len(metrics.N(v).split()) for v in untagged.values())
        add("all-text-tagged", untagged_words == 0,
            "every text show carries an MCID" if untagged_words == 0 else
            f"{untagged_words} word(s) sit outside every marked-content sequence")

        # --- the tagged words are the case's words (attribution, not order) -------------------------
        want_text = _truth_text(case)
        ok_text = same_words(file_text, want_text)
        add("tagged-text", ok_text,
            f"{len(metrics.N(file_text).split())} tagged words match the case" if ok_text else
            f"tagged words differ: missing {_missing(file_text, want_text)[:60]} · "
            f"extra {_extra(file_text, want_text)[:60]}")

        # --- headings: one element per heading, same level, same words ------------------------------
        heads = [n for n in nodes if n.tag in HEADING_TAGS]
        want_heads = [(b["level"], b["text"]) for b in case["blocks"] if b["type"] == "heading"]
        got_levels = [HEADING_TAGS[n.tag] for n in heads]
        got_texts = [_node_text(n, scan) for n in heads]
        levels_ok = got_levels == [lvl for lvl, _ in want_heads]
        text_ok = len(got_texts) == len(want_heads) and all(
            same_sequence(g, w) for g, (_, w) in zip(got_texts, want_heads))
        add("headings", levels_ok and text_ok,
            f"{len(heads)} heading element(s), levels {got_levels}"
            + ("" if levels_ok else f" — the case declares {[lvl for lvl, _ in want_heads]}")
            + ("" if text_ok else " — heading text does not match the case"))

        # --- tables: Table > TR > (TH…|TD…), same shape and same cells -------------------------------
        tables = [n for n in nodes if n.tag == "/Table"]
        want_tables = [b for b in case["blocks"] if b["type"] == "table"]
        table_problems = []
        if len(tables) != len(want_tables):
            table_problems.append(f"{len(tables)} /Table element(s) for {len(want_tables)} table(s) in the case")
        for k, (node, block) in enumerate(zip(tables, want_tables)):
            cells = _case_cells(block)
            rows = [c for c in node.children if c.tag == "/TR"]
            if len(rows) != len(cells):
                table_problems.append(f"table {k+1}: {len(rows)} TR for {len(cells)} rows")
                continue
            for r, (row, want) in enumerate(zip(rows, cells)):
                cs = [c for c in row.children if c.tag in ("/TH", "/TD")]
                if len(cs) != len(want):
                    table_problems.append(f"table {k+1} row {r+1}: {len(cs)} cells for {len(want)}")
                    continue
                if r < _header_rows(block) and any(c.tag != "/TH" for c in cs):
                    table_problems.append(f"table {k+1} row {r+1}: header cells not /TH")
                texts = [_node_text(c, scan) for c in cs]
                if not all(same_sequence(t, w) for t, w in zip(texts, want)):
                    table_problems.append(f"table {k+1} row {r+1}: cell text differs from the case")
        add("tables", not table_problems, "; ".join(table_problems[:3]) or
            f"{len(tables)} table(s) · TR/TH/TD match the case cell by cell")

        # --- block order: the document's own children follow the case's blocks -----------------------
        expected = _block_tags(case)
        top = [c for c in (tree.children if tree is not None else [])]
        doc = next((c for c in top if c.tag == "/Document"), None)
        seq = [n.tag for n in (doc.children if doc is not None else top) if n.tag in BLOCK_TAGS]
        add("block-order", seq == expected,
            f"top-level tags {seq}" + ("" if seq == expected else f" — the case declares {expected}"))

        # --- fonts: embedded, named ToUnicode, and only the family the case declares ----------------
        declared = _family(case["font"])
        bad_fonts = []
        for name, info in scan["fonts"].items():
            if not info["embedded"]:
                bad_fonts.append(f"{info['family'] or name}: not embedded")
            if not info["tounicode"]:
                bad_fonts.append(f"{info['family'] or name}: no /ToUnicode")
            if not (info["family"] or "").startswith(declared.split()[0]):
                bad_fonts.append(f"{info['family'] or name}: not the case's font ({declared})")
        add("fonts", not bad_fonts, "; ".join(sorted(set(bad_fonts))[:4]) or
            f"{len(scan['fonts'])} font(s) used for text, all embedded with /ToUnicode")
        add("notdef", scan["notdef"] == 0,
            "no glyph 0 drawn" if scan["notdef"] == 0 else f"{scan['notdef']} .notdef glyph(s) drawn")
        invisible = sum(1 for ch in file_text if 0x200B <= ord(ch) <= 0x200D or ord(ch) == 0x2060)
        add("invisible-format", invisible == 0,
            "no invisible joiner in the text layer" if invisible == 0 else
            f"{invisible} U+200B/200C/200D/2060 in the layer — the producer inserted them and a copy-paste "
            f"carries them")
        forms = sum(1 for ch in file_text
                    if 0xFB50 <= ord(ch) <= 0xFDFF or 0xFE70 <= ord(ch) <= 0xFEFF)
        add("presentation-forms", forms == 0,
            "no presentation form in the text layer" if forms == 0 else
            f"{forms} presentation-form character(s) in the layer — a reader that trusts the CMap shows a glyph "
            f"name, not a letter")
        add("tounicode-coverage", _tu_gaps(scan) == 0,
            "every drawn code has a Unicode value" if _tu_gaps(scan) == 0 else
            f"{_tu_gaps(scan)} code(s) with no /ToUnicode entry (readers would invent U+<glyph id>)")

        # --- the outline says what the headings say -------------------------------------------------
        import pymupdf
        doc_ = pymupdf.open(pdf_path)
        toc = doc_.get_toc()
        doc_.close()
        want_toc = [(lvl, unicodedata.normalize("NFC", t)) for lvl, t in
                    [(b["level"], b["text"]) for b in case["blocks"] if b["type"] == "heading"]]
        ok_toc = len(toc) == len(want_toc) and all(
            int(entry[0]) == lvl and metrics.N(entry[1]) == metrics.N(text)
            for entry, (lvl, text) in zip(toc, want_toc))
        add("outline", ok_toc, f"{len(toc)} entr(y/ies)" + ("" if ok_toc else
            f" — the case declares {[(l, t[:16]) for l, t in want_toc]}"))

    if run_verapdf:
        for flavour, cid in (("ua1", "verapdf-ua1"), ("3b", "verapdf-pdfa3b")):
            try:
                fails = verapdf_mod.failing(pdf_path, flavour)
            except Exception as exc:
                add(cid, False, f"veraPDF could not judge the file: {type(exc).__name__}: {exc}")
                continue
            add(cid, not fails, "no failing rule" if not fails else
                f"{len(fails)} failing rule(s): " + ", ".join(k for k, _ in fails[:6]))

    if producer.get("postprocess"):
        with pikepdf.open(pdf_path) as pdf:
            problems = __import__("pdfops").model_boundary(pdf)
        add("model-boundary", not problems, "; ".join(problems[:3]) or "inside the declared model")
    else:
        add("model-boundary", None, "n/a — our post-processing did not run, and the boundary is its guard")
    return checks


def _family(key: str) -> str:
    from ..adapters import fonts
    return fonts.family(key)


def _header_rows(block: dict) -> int:
    header = block["header"]
    return 1 if (header and not isinstance(header[0], list)) else len(header)


def _truth_text(case: dict) -> str:
    from ..corpus.truth import truth
    return truth(case)


def _node_text(node: Node, scan: dict) -> str:
    return "".join(scan["text"].get(slot, "") for slot in node.text_slots())


def _missing(got: str, want: str) -> str:
    return repr(" ".join((words_multi(want) - words_multi(got)).elements()))


def _extra(got: str, want: str) -> str:
    return repr(" ".join((words_multi(got) - words_multi(want)).elements()))


def _tu_gaps(scan: dict) -> int:
    """Codes drawn with no ToUnicode entry — the ones a reader turns into U+<glyph id> (measured behaviour)."""
    return int(scan.get("missing_unicode", 0))
