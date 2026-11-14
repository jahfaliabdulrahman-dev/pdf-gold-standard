#!/usr/bin/env python3
"""Rebuild the text layer of a Chrome/Skia-printed PDF so every glyph carries exactly ONE code point.

Why: Skia stores RTL runs in visual order and gives ligature glyphs (لأ، في، بي…) their two letters via
/ActualText in logical order. Extractors disagree on how to read that: poppler/MuPDF/PDFium reverse the run
character by character (letters inside the ligature flip), PDFKit keeps the stored order, pdf.js ignores
ActualText. One glyph -> one base code point is the only convention all of them read the same way.

What it does (painting is unchanged: verified pixel-identical at 300 dpi on the guide):
  * single-letter spans: ToUnicode gets the base letter (not the Presentation Form); the span is unwrapped
  * ligature glyph with n letters: kept as drawn, re-addressed through an alias CID that maps to the LAST
    logical letter, followed by n-1 INVISIBLE copies (Tr 3) of the same outline, one per remaining letter,
    each taking an equal share of the advance — every glyph now carries exactly one code point
  * kerning gaps inside a word (0.10–0.25 em) get an alias width so readers do not invent a space
  * each line's per-word text objects are merged into one BT..ET, spaces are drawn with a blank glyph of the
    neighbouring word's font, redundant Tf are dropped and /ReversedChars regions are joined across spaces, so
    MuPDF (direction reset at every BT) and pdf.js (new item at every Tf / marked-content boundary) see whole runs
  * a Latin phrase inside an Arabic line gets invisible zero-width direction marks where its isolate edges were
    (LRM outside its brackets, RLM outside sentence punctuation at the line edge): Preview then keeps
    «(Business Process» and «Model and Notation).» in order
  * vocalised text (tashkeel): the DRAWN mark glyphs move to a text object of their own before the line (same
    positions) and map to an invisible joiner; each letter gets invisible copies of its marks on the baseline, just
    left of it, so the line reads letter+marks in order (basmala exact in Preview, PDFium and MuPDF)
  * mark clusters (tashkeel): each glyph gets its own letter/mark; unmapped base glyphs are resolved from ActualText
  * a glyph that needs different text in different places gets alias CIDs (CIDToGIDMap), never a shared mapping
Usage: fix_text_layer.py in.pdf out.pdf
Measured on guide v2.1 (word sequence vs source): Preview 80.8→98.8%, PDFium 37.0→95.7%, poppler 78.3→95.1%,
MuPDF 13.5→80.0%, pdf.js 12.3→58.7%.
"""
import collections, io, re, sys, unicodedata
import pikepdf
from fontTools.ttLib import TTFont

PRES = lambda ch: 0xFB50 <= ord(ch) <= 0xFDFF or 0xFE70 <= ord(ch) <= 0xFEFF
is_mark = lambda ch: unicodedata.category(ch) == "Mn"


def parse_tu(data):
    m = {}
    for blk in re.findall(r"beginbfchar(.*?)endbfchar", data, re.S):
        for a, b in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            m[int(a, 16)] = bytes.fromhex(b).decode("utf-16-be")
    for blk in re.findall(r"beginbfrange(.*?)endbfrange", data, re.S):
        for line in blk.strip().splitlines():
            t = re.findall(r"<([0-9A-Fa-f]+)>", line)
            if "[" in line:
                for j, b in enumerate(t[2:]):
                    m[int(t[0], 16) + j] = bytes.fromhex(b).decode("utf-16-be")
            else:
                lo, hi, b = int(t[0], 16), int(t[1], 16), int(t[2], 16)
                for j in range(hi - lo + 1):
                    m[lo + j] = chr(b + j)
    return m


def write_tu(m):
    items, out = sorted(m.items()), []
    for i in range(0, len(items), 100):
        chunk = items[i:i + 100]
        out.append(f"{len(chunk)} beginbfchar\n" + "\n".join(
            f"<{c:04X}> <{s.encode('utf-16-be').hex().upper()}>" for c, s in chunk) + "\nendbfchar")
    return ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo\n<< /Registry (Adobe)\n"
            "/Ordering (UCS)\n/Supplement 0\n>> def\n/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n" + "\n".join(out) +
            "\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend").encode()


def parse_w(W):
    w, i, W = {}, 0, list(W)
    while i < len(W):
        c = int(W[i])
        if isinstance(W[i + 1], pikepdf.Array):
            for j, v in enumerate(W[i + 1]):
                w[c + j] = float(v)
            i += 2
        else:
            for k in range(c, int(W[i + 1]) + 1):
                w[k] = float(W[i + 2])
            i += 3
    return w


class FontState:
    def __init__(self, F):
        self.F, self.D = F, F.DescendantFonts[0]
        self.old = parse_tu(F.ToUnicode.read_bytes().decode("latin1"))
        self.width = parse_w(self.D.get("/W", []))
        self.dw = float(self.D.get("/DW", 1000))
        tt = TTFont(io.BytesIO(self.D.FontDescriptor.FontFile2.read_bytes()), lazy=True)
        self.nglyphs = tt["maxp"].numGlyphs
        glyf, order = tt["glyf"], tt.getGlyphOrder()
        self.blank = next((g for g in range(1, self.nglyphs) if glyf[order[g]].numberOfContours == 0), None)
        self.map = {}                       # cid -> final text (1 code point, or marks only)
        self.gid = {}                       # alias cid -> gid
        self.alias = {}                     # (gid, text) -> cid
        self.next = max(self.nglyphs, max(self.old, default=0) + 1)
        self.neww = {}

    def base(self, cid):
        """Default text of a glyph: its ToUnicode entry with single Presentation Forms folded to the base letter."""
        s = self.old.get(cid, "")
        if len(s) == 1 and s != "\x00":
            n = unicodedata.normalize("NFKC", s)
            return n if len(n) == 1 else s
        return "" if s == "\x00" else s

    def want(self, cid, text, width=None):
        """Return a CID that draws glyph `cid` and maps to `text`."""
        if cid not in self.gid and self.map.setdefault(cid, text) == text and width is None:
            return cid
        key = (self.gid.get(cid, cid), text, width)
        if key not in self.alias:
            c = self.next; self.next += 1
            self.alias[key] = c; self.gid[c] = key[0]; self.map[c] = text
            self.neww[c] = self.width.get(cid, self.dw) if width is None else width
        return self.alias[key]

    def space_cid(self, width):
        """A blank glyph of this font mapped to U+0020 (None if the subset has no empty glyph)."""
        if self.blank is None: return None
        key = ("space", round(width, 3))
        if key not in self.alias:
            c = self.next; self.next += 1
            self.alias[key] = c; self.gid[c] = self.blank; self.map[c] = " "; self.neww[c] = width
        return self.alias[key]

    def other_gid(self, cid, k):
        """A different inked glyph of this font (for invisible companions: two identical glyphs side by side with the
        same letter look like fake bold to PDFium, which then drops one)."""
        gid = self.gid.get(cid, cid)
        if not hasattr(self, "inked"):
            tt = TTFont(io.BytesIO(self.D.FontDescriptor.FontFile2.read_bytes()), lazy=True); glyf, order = tt["glyf"], tt.getGlyphOrder()
            self.inked = {g: (glyf[order[g]].yMin, glyf[order[g]].yMax) for g in range(1, self.nglyphs) if glyf[order[g]].numberOfContours != 0}
        # nearest vertical extent first: Preview takes a companion that sits higher or lower (a mark, say) for another line
        lo, hi = self.inked.get(gid, (0, 0))
        pool = sorted((g for g in self.inked if g != gid), key=lambda g: (abs(self.inked[g][0] - lo) + abs(self.inked[g][1] - hi), g)) or [gid]
        return pool[(k - 2) % len(pool)]

    def filler_cid(self, width):
        """A blank glyph of the given width mapped to U+200B, to be shown hidden (None if the subset has no empty glyph)."""
        if self.blank is None: return None
        key = ("filler", round(width, 3))
        if key not in self.alias:
            c = self.next; self.next += 1
            self.alias[key] = c; self.gid[c] = self.blank; self.map[c] = WJ; self.neww[c] = width
        return self.alias[key]

    def mark_cid(self, text):
        """A zero-width blank glyph mapped to an invisible direction mark (None if the subset has no empty glyph)."""
        if self.blank is None: return None
        key = ("mark", text)
        if key not in self.alias:
            c = self.next; self.next += 1
            self.alias[key] = c; self.gid[c] = self.blank; self.map[c] = text; self.neww[c] = 0.0
        return self.alias[key]

    def finish(self, pdf):
        for cid, s in self.old.items():                 # glyphs never seen inside a span keep a folded default
            self.map.setdefault(cid, self.base(cid) or s)
        self.F.ToUnicode = pdf.make_stream(write_tu({c: s for c, s in self.map.items() if s and s != "\x00"}))
        if self.gid:
            top = self.next
            m = bytearray()
            for c in range(top):
                g = self.gid.get(c, c if c < self.nglyphs else 0)
                m += g.to_bytes(2, "big")
            self.D.CIDToGIDMap = pdf.make_stream(bytes(m))
            W = self.D.get("/W", pikepdf.Array())
            for c, w in sorted(self.neww.items()):
                W.append(c); W.append(pikepdf.Array([round(w, 4)]))
            self.D.W = W


SPAN = re.compile(rb"/Span<</ActualText <FEFF([0-9A-Fa-f]*)> >> BDC\n(.*?)EMC\n", re.S)
TJ = re.compile(rb"<([0-9A-Fa-f]+)> Tj")
TF = re.compile(rb"(/F\w+)\s+([\d.]+)\s+Tf")
ADJ = re.compile(rb"%%ADJ ([\d.]+)%%\n")
TD = re.compile(rb"(-?[\d.]+) (-?[\d.]+) Td")


HM = b"%%HM%%\n"                   # tag: a text object that holds only hoisted marks (removed by join_lines)
VM = b"%%VM%%"                      # tag: a DRAWN mark glyph (mapped to U+200B) that hoist_marks() moves out of the line
HT = re.compile(rb"(/F\w+)\s+([\d.]+)\s+Tf|(1 0 0 -1 -?[\d.]+ -?[\d.]+ Tm)|(-?[\d.]+) (-?[\d.]+) Td|<([0-9A-Fa-f]+)> Tj(%%VM%%)?")


def hoist_marks(data, fontmap, st_of, stats):
    """Tashkeel glyphs are drawn above/below the letters, inside the line's glyph sequence; poppler and PDFium then
    cut the line at every mark. Paint the marks from a text object of their own BEFORE the line (same positions, so
    same pixels) and leave only letters and their invisible on-baseline mark copies in the line itself."""
    def one(m):
        body = m.group(0)
        if VM not in body: return body
        first = HT.search(body)
        if not first or not first.group(1): return body.replace(VM, b"")       # line must select its own font first
        font = tm = None; x = y = 0.0; marks = []; out = []; pos = 0
        for t in HT.finditer(body):
            if t.group(1): font = (t.group(1), t.group(2))
            elif t.group(3): tm = t.group(3); x = y = 0.0
            elif t.group(4): x += float(t.group(4)); y += float(t.group(5))
            elif t.group(7):
                F = fontmap.get(font[0].decode()); st = st_of(F); h = t.group(6).decode()
                adv = sum(st.neww.get(int(h[i:i + 4], 16), st.width.get(int(h[i:i + 4], 16), st.dw)) for i in range(0, len(h), 4))
                if adv == 0 and tm is not None:                                     # removing it must not move the pen
                    marks.append((font, tm, x, y, t.group(6)))
                    out.append(body[pos:t.start()]); pos = t.end(); continue
                out.append(body[pos:t.start()] + b"<" + t.group(6) + b"> Tj"); pos = t.end()
        out.append(body[pos:])
        if not marks: return b"".join(out)
        pre = [b"BT\n" + HM + MARKS_ACTUAL]; cur = None; cx = cy = 0.0
        for font, tm, x, y, h in marks:
            if (font, tm) != cur:
                pre.append(b"%s %s Tf\n%s\n" % (font[0], font[1], tm)); cur = (font, tm); cx = cy = 0.0
            pre.append(b"%.7f %.7f Td <%s> Tj\n" % (x - cx, y - cy, h)); cx, cy = x, y
        pre.append(b"EMC\nET\n"); stats["marks_hoisted"] += len(marks)
        line = b"".join(out)
        # MuPDF starts every BT with "no direction": a line that begins with a mark copy would leave that mark
        # outside the RTL run. Start the line with an invisible zero-width RLM.
        f1, tm1, tj1 = HT.search(line), re.search(rb"1 0 0 -1 -?[\d.]+ -?[\d.]+ Tm\n", line), re.search(rb"<([0-9A-Fa-f]{4})", line)
        if f1 and f1.group(1) and tm1 and tj1:
            st = st_of(fontmap.get(f1.group(1).decode())); c0 = int(tj1.group(1), 16)
            if all(is_mark(ch) for ch in st.map.get(c0, "x")):
                rl = st.want(c0, RLM, width=0.0)
                line = line[:tm1.end()] + b"3 Tr <%04X> Tj 0 Tr\n" % rl + line[tm1.end():]; stats["rlm_line_start"] += 1
        return b"".join(pre) + line
    return BLOCK.sub(one, data)


def split_units(text):
    """Logical units of a cluster: a base letter with its following marks."""
    units = []
    for ch in text:
        if is_mark(ch) and units:
            units[-1] += ch
        else:
            units.append(ch)
    return units


TOK = re.compile(rb"(/F\w+)\s+([\d.]+)\s+Tf|(-?[\d.]+) (-?[\d.]+) Td|<([0-9A-Fa-f]+)> Tj|\bET\b|\bTm\b")
STRICT_WIDTHS = False  # set by process(strict_widths=True): no drawn glyph may differ from the font's width
GAP_MIN, GAP_MAX = 0.10, 0.25      # em: a positive kern readers may read as a space; larger jumps are real gaps


def close_gaps(data, fontmap, st_of, stats):
    """Glyphs are placed by explicit Td, so /W only tells readers how wide a glyph is. Where the next letter on the
    same baseline starts further right than this glyph's width (kerning), poppler and pdf.js read a space into the
    word. A HIDDEN glyph gets an alias whose width is the real advance. A DRAWN glyph must keep the font's own width
    (PDF/A 6.2.11.5, PDF/UA 7.21.5) — but the two cannot both be had (measured on the guide, 5 gaps):
      * default: the drawn glyph gets the wider alias too. Best copy; the one class of drawn glyph left whose /W is
        not the font's (veraPDF: 1 failed check, down from 22).
      * STRICT_WIDTHS: the drawn glyph keeps its width and is followed by a hidden blank glyph as wide as the gap,
        mapped to U+200B. veraPDF: 0. Price: pdf.js skips that character and still reads a space into 3 words;
        MuPDF and poppler paste the invisible character inside 4 words; PDFium is unchanged.
    Drawing is unchanged either way."""
    st = None; size = 0.0; x = y = 0.0; seq = []
    for t in TOK.finditer(data):
        if t.group(1):
            F = fontmap.get(t.group(1).decode()); st = st_of(F) if F is not None and F.get("/Subtype") == "/Type0" else None
            size = float(t.group(2))
        elif t.group(3):
            x += float(t.group(3)); y += float(t.group(4))
        elif t.group(5):
            if st is not None and len(t.group(5)) == 4:
                seq.append((x, y, int(t.group(5), 16), st, size, t.start(5), id(st)))
            else:
                seq.append(None)
        else:
            x = y = 0.0; seq.append(None)
    edits = []
    for i, a in enumerate(seq):
        if a is None: continue
        for b in seq[i + 1:i + 6]:
            if b is None: break
            if b[6] != a[6] or abs(b[1] - a[1]) > 1e-6: continue          # marks sit on another baseline: skip them
            x0, _, cid, s, sz, pos, _ = a
            text = s.map.get(cid) or s.base(cid); nxt = b[3].map.get(b[2]) or b[3].base(b[2])
            w = s.neww.get(cid, s.width.get(cid, s.dw)) / 1000 * sz
            gap = (b[0] - x0 - w) / sz
            if GAP_MIN < gap < GAP_MAX and text and nxt and not text.isspace() and not nxt.isspace():
                hidden = data[pos - 6:pos - 1] == b"3 Tr "
                fill = s.filler_cid(round(gap * 1000, 4)) if STRICT_WIDTHS and not hidden else None
                if hidden or fill is None:
                    edits.append((pos, 4, b"%04X" % s.want(cid, text, width=round((b[0] - x0) / sz * 1000, 4))))
                    stats["gap_closed" if hidden else "gap_closed_by_width"] += 1
                else:
                    end = pos + 4 + len(b"> Tj")
                    edits.append((end, 0, b" 3 Tr <%04X> Tj 0 Tr" % fill)); stats["gap_filled"] += 1
            break
    out = bytearray(data)
    for pos, n, new in sorted(edits, reverse=True):
        out[pos:pos + n] = new
    return bytes(out)


POS = re.compile(rb"(/F\w+)\s+([\d.]+)\s+Tf|1 0 0 -1 (-?[\d.]+) (-?[\d.]+) Tm|(-?[\d.]+) (-?[\d.]+) Td|<([0-9A-Fa-f]+)> Tj|\bET\b")
LRM, RLM = "\u200e", "\u200f"
MARK_W = 20.0          # width (1/1000 em) of an invisible on-baseline mark copy
DUP_W = 120            # 1/1000 em between a ligature's last hidden letter and the glyph's right edge (see letters_plan)
SEP_MIN, SEP_W = 0.1, 0.8   # invisible separator after hoisted marks: at least 0.1 em, or 0.8 x the next glyph's width, above the line
WJ = "\u200b"          # zero-width space: what a DRAWN mark maps to (Preview drops it; U+2060 was pasted at every line end)
# Readers that honour /ActualText get ONE tab for the whole block of drawn marks: PDFium then skips the block (nothing
# printable in it), poppler and MuPDF stop cutting the line at each mark. Preview ignores /ActualText (hence WJ above).
MARKS_ACTUAL = b"/Span <</ActualText <FEFF0009>>> BDC\n"
OPEN, CLOSE = "([{", ")]}"


def bidi_kind(txt):
    for ch in txt:
        t = unicodedata.bidirectional(ch)
        if t in ("R", "AL", "AN"): return "R"
        if t in ("L", "EN"): return "L"
    return "N"


def direction_marks(data, fontmap, st_of, stats):
    """A Latin phrase inside an Arabic line is an isolate in the HTML, but the PDF carries no isolate: readers attach
    its brackets (and the sentence punctuation next to it) to the wrong side. Put invisible, zero-width direction
    marks where the isolate's edges were: LRM outside a bracket that belongs to the Latin run, RLM outside
    sentence punctuation that sits between the run and the line edge. No ink, no advance."""
    st = None; x = y = 0.0; ox = oy = 0.0; glyphs = []            # (y, x, text, st, hex_start, index)
    for t in POS.finditer(data):
        if t.group(1):
            F = fontmap.get(t.group(1).decode()); st = st_of(F) if F is not None and F.get("/Subtype") == "/Type0" else None
        elif t.group(3): ox, oy = float(t.group(3)), float(t.group(4)); x = y = 0.0
        elif t.group(5): x += float(t.group(5)); y += float(t.group(6))
        elif t.group(7):
            if st is None: continue
            h = t.group(7).decode(); px = x
            for i in range(0, len(h), 4):
                c = int(h[i:i + 4], 16)
                glyphs.append((round(oy - y, 1), ox + px, st.map.get(c) or st.base(c) or "", st, t.start(7), i // 4, len(h) // 4, t.end()))
                px += st.neww.get(c, st.width.get(c, st.dw)) / 1000      # only ordering matters here
    lines = {}
    for g in glyphs: lines.setdefault(g[0], []).append(g)
    ins = []                                               # (hex_start, glyph index to insert before, st, mark)
    for line in lines.values():
        line.sort(key=lambda g: g[1])
        kinds = [bidi_kind(g[2]) if g[2].strip() else "S" for g in line]
        i, n = 0, len(line)
        while i < n:
            if kinds[i] != "L": i += 1; continue
            j = i
            while True:                                               # extend over letters, and neutrals/spaces followed by more letters
                k = j + 1
                while k < n and kinds[k] in ("N", "S"): k += 1
                if k < n and kinds[k] == "L": j = k
                else: break
            a, b = i, j
            left_attached = a > 0 and line[a - 1][2] in OPEN
            right_attached = b + 1 < n and line[b + 1][2] in CLOSE
            if left_attached: a -= 1
            if right_attached: b += 1
            if left_attached: ins.append((line[a], 0, LRM))
            if right_attached: ins.append((line[b], 1, LRM))
            if True:                                                  # punctuation between the run and the LEFT line edge
                k = a - 1
                while k >= 0 and kinds[k] in ("N", "S"): k -= 1
                if k < 0 and a > 0 and any(kinds[m] == "N" for m in range(a)):
                    first = next(m for m in range(a) if kinds[m] == "N")
                    ins.append((line[first], 0, RLM))
                    if not left_attached: ins.append((line[a], 0, LRM))
            i = j + 1
    edits = {}
    for g, after, mark in ins:
        c = g[3].mark_cid(mark)
        if c is None: continue
        edits.setdefault(g[4], []).append((g[5] + after, c)); stats["dir_marks"] += 1
    out = bytearray(data)
    for start in sorted(edits, reverse=True):
        end = out.index(b">", start); h = out[start:end].decode()
        cids = [h[i:i + 4] for i in range(0, len(h), 4)]
        for idx, c in sorted(edits[start], reverse=True): cids.insert(idx, "%04X" % c)
        out[start:end] = "".join(cids).encode()
    return bytes(out)


BLOCK = re.compile(rb"BT\n(?:(?!ET\n).)*?ET\n", re.S)
TM_Y = re.compile(rb"1 0 0 -1 [\d.]+ ([\d.]+) Tm")
ONE_TJ = re.compile(rb"<([0-9A-Fa-f]{4})> Tj")
# EMC, then one space drawn on its own (Tm + Td/Tj), then the next reversed run
RUN_GAP = re.compile(rb"EMC\n\s*((?:1 0 0 -1 [\d.]+ [\d.]+ Tm\n)?-?[\d.]+ -?[\d.]+ Td\s+(?:3 Tr )?<[0-9A-Fa-f]{4}> Tj(?: 0 Tr)?\n)\s*/ReversedChars BMC\n")


def join_lines(data, fontmap, st_of, stats):
    """Skia paints one BT..ET per word and per space, the space in a different (Latin) subset font.
      * pdf.js starts a new text item at every font change, so it never sees a whole Arabic line and returns its
        words in visual order -> draw each space with a blank glyph of the NEIGHBOURING word's font;
      * MuPDF forgets the text direction at every BT, so a space cannot inherit it and each word is reversed alone
        -> merge the adjacent text objects of a line into one BT..ET.
    Nothing is painted differently: a space has no ink and every block sets its own Tm."""
    out, pos, group = [], 0, []      # group: [block bytes, font at start, font at end, is_space, tm_y]
    font = (None, "0")

    def text_of(body, f):
        txt, cur = "", f
        for t in TOK.finditer(body):
            if t.group(1): cur = (t.group(1).decode(), t.group(2).decode())
            elif t.group(5):
                F = fontmap.get(cur[0]); st = st_of(F) if F is not None and F.get("/Subtype") == "/Type0" else None
                h = t.group(5).decode()
                for i in range(0, len(h), 4):
                    c = int(h[i:i + 4], 16); txt += (st.map.get(c) or st.base(c) or "?") if st else "?"
        return txt, cur

    def flush():
        if len(group) > 1:
            seen = [False]                                           # is the font in force known from a Tf inside this line?
            for g in group: seen.append(seen[-1] or bool(TF.search(g[0])))
            for i, g in enumerate(group):
                if not g[3]: continue
                pj = next((j for j in range(i - 1, -1, -1) if not group[j][3]), None)
                nj = next((j for j in range(i + 1, len(group)) if not group[j][3]), None)
                if pj is not None and seen[pj + 1]: nf = group[pj][2]
                elif nj is not None and TF.search(group[nj][0]) and TF.search(group[nj][0]).start() < TJ.search(group[nj][0]).start():
                    t = TF.search(group[nj][0]); nf = (t.group(1).decode(), t.group(2).decode())
                else: continue
                sf = g[2]
                if not seen[i + 1] or nf[0] == sf[0]: continue           # the space's own font must be known too
                Fn, Fs = fontmap.get(nf[0]), fontmap.get(sf[0])
                if Fn is None or Fs is None or Fn.get("/Subtype") != "/Type0": continue
                sn, ss = st_of(Fn), st_of(Fs)
                m = ONE_TJ.search(g[0]); cid = int(m.group(1), 16)
                adv = ss.neww.get(cid, ss.width.get(cid, ss.dw)) / 1000 * float(sf[1])
                sc = sn.space_cid(round(adv / float(nf[1]) * 1000, 4))
                if sc is None: continue
                body = TF.sub(b"", g[0])                               # the space no longer selects the Latin font
                k = ONE_TJ.search(body)
                g[0] = body[:k.start()] + b"%s %s Tf 3 Tr <%04X> Tj 0 Tr" % (nf[0].encode(), nf[1].encode(), sc) + body[k.end():]
                g.append(nf); stats["space_refont"] += 1
            # PDFium keeps consecutive objects on one line while they are vertically closer than a fraction of their
            # widths, then sorts that line by x: the last hoisted mark would land inside the line's first word. End the
            # marks with an invisible copy just far enough above the line (same glyph, Tr 3: no pixels).
            # Only for marks that open the line: in the middle of a line the separator would cut the line for MuPDF.
            for i, g in enumerate(group[:1]):
                if HM not in g[0] or HM in group[i + 1][0]: continue
                f, w, n = group[i + 1][1], 0.0, 0
                for t in TOK.finditer(group[i + 1][0]):
                    if t.group(1): f = (t.group(1).decode(), t.group(2).decode())
                    elif t.group(5):
                        F = fontmap.get(f[0])
                        if F is None or F.get("/Subtype") != "/Type0": break
                        st = st_of(F); c = int(t.group(5)[:4], 16); n += 1
                        w = max(w, st.neww.get(c, st.width.get(c, st.dw)) / 1000 * float(f[1]))
                        if n == 2: break
                size, y, last = 0.0, 0.0, None
                for t in HT.finditer(g[0]):
                    if t.group(1): size = float(t.group(2))
                    elif t.group(3): y = 0.0
                    elif t.group(4): y += float(t.group(5))
                    elif t.group(6): last = t.group(6)[:4]
                if last and size:
                    g[0] = g[0][:-7] + b"0 %.7f Td 3 Tr <%s> Tj 0 Tr\nEMC\nET\n" % (-max(SEP_MIN * size, SEP_W * w) - y, last)
            # every block must start in the font it originally started in, and the line must leave the font state
            # it originally left; then drop each Tf that changes nothing (pdf.js starts a new item at every Tf)
            parts, actual, changed = [], None, False
            for i, g in enumerate(group):
                first_tf, first_tj = TF.search(g[0]), TJ.search(g[0])
                own = first_tf and first_tj and first_tf.start() < first_tj.start()
                if changed and seen[i] and not own and actual != g[1]:
                    parts.append(b"%s %s Tf\n" % (g[1][0].encode(), g[1][1].encode())); actual = g[1]
                for t in TF.finditer(g[0]): actual = (t.group(1).decode(), t.group(2).decode())
                if len(g) > 5: changed = True
                parts.append(g[0])
            merged = b"".join(parts).replace(b"ET\nBT\n", b"")
            if changed and actual != group[-1][2]:
                merged = merged[:-3] + b"%s %s Tf\nET\n" % (group[-1][2][0].encode(), group[-1][2][1].encode())
            cur, keep, p = None, [], 0
            for t in TF.finditer(merged):
                f = (t.group(1).decode(), t.group(2).decode())
                keep.append(merged[p:t.start()]); p = t.end()
                if f != cur: keep.append(t.group(0)); cur = f
                elif merged[p:p + 1] == b"\n": p += 1
            keep.append(merged[p:]); merged = b"".join(keep)
            # one /ReversedChars region per run of Arabic words: a region boundary also starts a new pdf.js item
            merged, n = RUN_GAP.subn(lambda m: m.group(1), merged)
            out.append(merged); stats["lines_joined"] += 1; stats["rtl_runs_joined"] += n
        else:
            out.extend(g[0] for g in group)
        group.clear()

    for m in BLOCK.finditer(data):
        between = data[pos:m.start()]
        if between.strip(): flush()
        body = m.group(0); tm = TM_Y.search(body); y = tm.group(1) if tm else None
        txt, endfont = text_of(body, font)
        if group and (y is None or y != group[-1][4]): flush()
        if not group: out.append(between)
        is_space = bool(txt) and txt.isspace() and len(ONE_TJ.findall(body)) == 1 and len(TJ.findall(body)) == 1
        group.append([body, font, endfont, is_space, y]); font = endfont; pos = m.end()
        if y is None: flush()
    flush(); out.append(data[pos:])
    return b"".join(out).replace(HM, b"")


def drawn_width_mismatches(path):
    """Drawn glyphs (text render mode other than 3) whose width in the font dictionary differs from the embedded font
    program by more than 1/1000 em -> sorted [(base font, cid, dictionary width, font width)]. This is what PDF/A
    6.2.11.5 and PDF/UA 7.21.5 forbid; it counts every (font, cid) pair, veraPDF fewer (60 / 5 / 0 here against 22 / 1 / 0 on the same three builds of the
    guide - the difference is not explained); the two agree on which builds are clean."""
    tok = re.compile(rb"(/F\w+)\s+[\d.]+\s+Tf|\b([0-7]) Tr\b|<([0-9A-Fa-f]+)> Tj|\b(q|Q)\b")
    bad = set()
    with pikepdf.open(path) as pdf:
        cache = {}
        for page in pdf.pages:
            fonts = page.Resources.get("/Font", {})
            data = b"".join(c.read_bytes() + b"\n" for c in (page.Contents if isinstance(page.Contents, pikepdf.Array) else [page.Contents]))
            font, tr, stack = None, 0, []
            for t in tok.finditer(data):
                if t.group(1): font = t.group(1).decode()
                elif t.group(2): tr = int(t.group(2))
                elif t.group(4): 
                    if t.group(4) == b"q": stack.append((font, tr))
                    elif stack: font, tr = stack.pop()
                elif tr != 3 and font in fonts and fonts[font].get("/Subtype") == "/Type0":
                    F = fonts[font]; key = F.objgen
                    if key not in cache:
                        D = F.DescendantFonts[0]
                        tt = TTFont(io.BytesIO(D.FontDescriptor.FontFile2.read_bytes()), lazy=True)
                        m = D.get("/CIDToGIDMap"); gidmap = m.read_bytes() if isinstance(m, pikepdf.Stream) else None
                        cache[key] = (str(F.BaseFont)[1:], parse_w(D.get("/W", [])), float(D.get("/DW", 1000)), tt["hmtx"], tt.getGlyphOrder(), 1000 / tt["head"].unitsPerEm, gidmap)
                    name, W, dw, hmtx, order, k, gidmap = cache[key]
                    h = t.group(3).decode()
                    for i in range(0, len(h), 4):
                        cid = int(h[i:i + 4], 16)
                        gid = cid if gidmap is None else int.from_bytes(gidmap[2 * cid:2 * cid + 2], "big")
                        fw = hmtx[order[gid]][0] * k if gid < len(order) else 0.0
                        if abs(W.get(cid, dw) - fw) > 1: bad.add((name, cid, round(W.get(cid, dw), 2), round(fw, 2)))
    return sorted(bad)


def process(src, dst, strict_widths=False):
    global STRICT_WIDTHS
    STRICT_WIDTHS = strict_widths
    pdf = pikepdf.open(src)
    states, stats = {}, collections.Counter()

    def st_of(F):
        return states.setdefault(F.objgen, FontState(F))

    for page in pdf.pages:
        fontmap = {str(k): v for k, v in page.Resources.get("/Font", {}).items()}
        streams = [page.Contents] if isinstance(page.Contents, pikepdf.Stream) else list(page.Contents)
        for cs in streams:
            data = cs.read_bytes()
            tfs = [(m.start(), m.group(1).decode(), float(m.group(2))) for m in TF.finditer(data)]

            def font_at(pos):
                cur = (None, 0.0)
                for p, n, s in tfs:
                    if p <= pos: cur = (n, s)
                    else: break
                return cur

            def hexs(cids):
                return b"<" + b"".join(b"%04X" % c for c in cids) + b">"

            def split_in_cluster(st, body, shows, gids, assign, units, size):
                """One Tj holding mark glyphs + ONE glyph that stands for several letters: keep the marks where they are, then
                the letters left to right (lead glyph + hidden companions). Letters come out exact; marks may attach to a neighbour."""
                if len(shows) != 1 or len(gids) < 2 or [i for i in assign if len([c for c in assign[i] if not is_mark(c)]) > 1] != [len(gids) - 1]:
                    return None
                wid = [st.width.get(g, st.dw) / 1000 * size for g in gids]
                off = [sum(wid[:i]) for i in range(len(gids))]
                vis = units[::-1]                                   # leftmost unit first
                letters = [u[0] for u in vis]; marks = [u[1:] for u in vis]
                if "".join(letters[::-1]) != "".join(c for c in assign[len(gids) - 1] if not is_mark(c)): return None
                mark_glyphs = list(range(len(gids) - 1)); k = 0; pre = []
                for j, u in enumerate(vis):
                    if marks[j]:
                        if k >= len(mark_glyphs) or sorted(assign[mark_glyphs[k]]) != sorted(marks[j]): return None
                        i = mark_glyphs[k]; k += 1
                        pre.append((off[i], st.want(gids[i], WJ), False))
                plan = letters_plan(st, gids[-1], off[-1], letters, marks, size)
                plan = pre + plan            # marks first, then letters left to right: positions never jump backwards
                if k != len(mark_glyphs): return None
                head = body[:shows[0].start()]; cur = 0.0; out = head
                for o, cid, hidden in plan:
                    if out is not head: out += b"%.6f 0 Td " % (o - cur); cur = o   # Td also resets the pen to the line origin
                    elif abs(o) > 1e-9: out += b"%.6f 0 Td " % o; cur = o
                    out += (b"3 Tr " if hidden else b"") + hexs([cid]) + b" Tj" + (b" 0 Tr\n" if hidden else (VM + b"\n" if (o, cid, hidden) in pre else b"\n"))
                return out + body[shows[0].end():].lstrip(b"\n") + (b"%%%%ADJ %.6f%%%%\n" % cur if cur else b"")

            def letters_plan(st, g, at, letters, marks, size):
                """One drawn glyph `g` at offset `at` that stands for several letters (leftmost first), each with its
                marks -> [(offset, cid, hidden)], left to right.

                The DRAWN glyph keeps the font's own width (PDF/A 6.2.11.5, PDF/UA 7.21.5: a rendered glyph's width
                must match the font program) and carries the SECOND-TO-LAST letter (the only letter of two = the first).
                Everything before it — earlier letters, and the marks of each — is hidden 0.02 em copies just left of
                the glyph, where a letter's mark copies always sit. The LAST letter and its marks are hidden copies
                against the glyph's right edge, DUP_W short of it: the next glyph may be the same letter (سس، لل) and
                MuPDF drops a repeated character closer than 0.1 em as fake bold. pdf.js starts a new item when x
                jumps back more than 0.2 em, so the jump from the glyph's end to that pack must stay under it:
                0.12 + 0.02 per hidden copy (three letters of «لله» in the pack measured 0.32 and cut the line)."""
                w = st.width.get(g, st.dw); d = MARK_W / 1000 * size; v = max(0, len(letters) - 2); nth = 0

                def hidden(ch, mk, wd):
                    nonlocal nth
                    if mk: return st.want(g, ch, width=wd)
                    nth += 1
                    return st.want(g if nth == 1 else st.other_gid(g, nth), ch, width=wd)
                before = []
                for j in range(v + 1):
                    before += [(mk, True) for mk in reversed(marks[j])] + ([(letters[j], False)] if j < v else [])
                plan = [(at - (len(before) - i) * d, hidden(ch, mk, MARK_W), True) for i, (ch, mk) in enumerate(before)]
                plan.append((at, st.want(g, letters[v]), False))
                after = []
                for j in range(v + 1, len(letters)):
                    after += [(mk, True) for mk in reversed(marks[j])] + [(letters[j], False)]
                x = at + (w - DUP_W - MARK_W * len(after)) / 1000 * size
                for i, (ch, mk) in enumerate(after):
                    # the last copy reaches the glyph's edge: no gap is left for a reader (or close_gaps) to take for a space
                    plan.append((x, hidden(ch, mk, MARK_W + (DUP_W if i == len(after) - 1 else 0)), True)); x += d
                return plan

            def split_multi(st, body, shows, gids, assign, units, size):
                """Mark glyphs drawn on their own (any number of Tj) + a LAST glyph that stands for several letters (لَا لْآ لْأُ لًّا):
                the drawn marks stay where they are (mapped to U+200B, hoisted later); the ligature becomes its letters left to
                right, each preceded by hidden copies of its own marks."""
                lig = len(gids) - 1
                if [i for i in assign if len([c for c in assign[i] if not is_mark(c)]) > 1] != [lig]: return None
                if any(is_mark(c) for c in assign[lig]): return None
                vis = units[::-1]; letters = [u[0] for u in vis]; marks = [u[1:] for u in vis]
                if "".join(letters[::-1]) != assign[lig]: return None
                if sorted("".join(assign[i] for i in range(lig))) != sorted("".join(marks)): return None
                out, pos, k = b"", 0, 0
                for sh in shows[:-1]:
                    n = len(sh.group(1)) // 4
                    out += body[pos:sh.start()] + hexs([st.want(gids[i], WJ) for i in range(k, k + n)]) + b" Tj" + VM
                    pos = sh.end(); k += n
                last = shows[-1]; out += body[pos:last.start()]
                pre = list(range(k, lig)); base = sum(st.width.get(gids[i], st.dw) for i in pre) / 1000 * size
                if pre: out += hexs([st.want(gids[i], WJ) for i in pre]) + b" Tj" + VM + b"\n"
                plan = letters_plan(st, gids[lig], base, letters, marks, size)
                cur, first = 0.0, not pre
                for o, cid, hidden in plan:
                    if not first or abs(o) > 1e-9: out += b"%.6f 0 Td " % (o - cur); cur = o
                    first = False
                    out += (b"3 Tr " if hidden else b"") + hexs([cid]) + b" Tj" + (b" 0 Tr\n" if hidden else b"\n")
                return out + body[last.end():].lstrip(b"\n") + (b"%%%%ADJ %.6f%%%%\n" % cur if cur else b"")

            def repl(m):
                text = bytes.fromhex(m.group(1).decode()).decode("utf-16-be")
                body = m.group(2)
                inner = TF.search(body)
                fname, size = (inner.group(1).decode(), float(inner.group(2))) if inner else font_at(m.start())
                F = fontmap.get(fname)
                if F is None or F.get("/Subtype") != "/Type0":
                    stats["kept_unknown_font"] += 1; return m.group(0)
                st = st_of(F)
                shows = list(TJ.finditer(body))
                gids = [int(s.group(1)[i:i + 4], 16) for s in shows for i in range(0, len(s.group(1)), 4)]
                units = split_units(text)
                # --- one glyph
                if len(gids) == 1:
                    g = gids[0]
                    if len(text) == 1:
                        c = st.want(g, text); stats["single"] += 1
                        return body if c == g else TJ.sub(hexs([c]) + b" Tj", body)
                    chars = list(text)                               # ligature / base+mark in one glyph
                    plan = letters_plan(st, g, 0.0, chars[::-1], [""] * len(chars), size)   # leftmost = last logical
                    new = b""; cur = 0.0
                    for o, cid, hidden in plan:
                        new += (b"%.6f 0 Td " % (o - cur) if o != cur or new else b"") + (b"3 Tr " if hidden else b"") + hexs([cid]) + b" Tj" + (b" 0 Tr\n" if hidden else b"\n"); cur = o
                    stats["ligature_split"] += 1
                    return TJ.sub(lambda _: new.rstrip(b"\n"), body) + (b"%%%%ADJ %.6f%%%%\n" % cur if cur else b"")
                # --- several glyphs (mark cluster): give every glyph its own text
                left = collections.Counter(text); assign = {}
                for i, g in enumerate(gids):
                    b = st.base(g)
                    if b and all(left[ch] > 0 for ch in b):
                        assign[i] = b
                        for ch in b: left[ch] -= 1
                rest = [ch for ch in text if left[ch] > 0 and not left.subtract({ch: 1})]
                unknown = [i for i in range(len(gids)) if i not in assign]
                if unknown:
                    bases = [ch for ch in rest if not is_mark(ch)]; marks = [ch for ch in rest if is_mark(ch)]
                    if len(unknown) == 1:
                        assign[unknown[0]] = "".join(bases + marks)
                    else:                                            # base letter is the last glyph drawn; marks come first
                        assign[unknown[-1]] = "".join(bases)
                        per = [""] * (len(unknown) - 1)
                        for k, ch in enumerate(marks): per[min(k, len(per) - 1)] += ch
                        for i, s in zip(unknown[:-1], per): assign[i] = s
                elif rest:
                    stats["kept_cluster_leftover"] += 1; return m.group(0)
                for i in assign:
                    if len(assign[i]) > 1 and all(is_mark(c) for c in assign[i]):
                        assign[i] = "".join(sorted(assign[i], key=unicodedata.combining))
                multi = [i for i in assign if len([c for c in assign[i] if not is_mark(c)]) > 1]
                if multi:
                    out = split_in_cluster(st, body, shows, gids, assign, units, size)
                    if out is None: out = split_multi(st, body, shows, gids, assign, units, size)
                    if out is None:
                        stats["kept_cluster_ambiguous"] += 1; return m.group(0)
                    stats["cluster_split"] += 1; return out
                for i in assign:                                     # marks in canonical order, so equal sets share one mapping
                    if len(assign[i]) > 1 and all(is_mark(c) for c in assign[i]):
                        assign[i] = "".join(sorted(assign[i], key=unicodedata.combining))
                if any(not assign[i] or (len(assign[i]) > 1 and not all(is_mark(c) for c in assign[i])) for i in assign):
                    stats["kept_cluster_ambiguous"] += 1; return m.group(0)
                base_idx = [i for i in assign if any(not is_mark(c) for c in assign[i])]
                if len(units) == 1 and len(base_idx) == 1 and len(units[0]) > 1:
                    # Marks are drawn above/below the line, where readers take them for separate lines. Keep them
                    # drawn but mapped to an invisible joiner, and give the letter invisible zero-width copies of
                    # its marks on the baseline (stream order = reversed logical order, like the rest of the run).
                    bi = base_idx[0]
                    new = [st.want(g, assign[i] if i == bi else WJ) for i, g in enumerate(gids)]
                    mk_l = units[0][1:]; d = MARK_W / 1000 * size
                    inv = b"%.6f 0 Td 3 Tr " % (-len(mk_l) * d)
                    for mk in reversed(mk_l):
                        inv += hexs([st.want(gids[bi], mk, width=MARK_W)]) + b" Tj %.6f 0 Td " % d
                    inv += b"0 Tr\n"
                    out, pos, k = b"", 0, 0
                    for sh in shows:
                        n = len(sh.group(1)) // 4; cids = new[k:k + n]
                        out += body[pos:sh.start()]; pos = sh.end()
                        if k <= bi < k + n:
                            if bi > k: out += hexs(cids[:bi - k]) + b" Tj" + VM + b"\n"
                            out += inv + hexs(cids[bi - k:]) + b" Tj"
                        else:
                            out += hexs(cids) + b" Tj" + VM
                        k += n
                    stats["cluster_marks_on_baseline"] += 1
                    return out + body[pos:]
                new = [st.want(g, assign[i]) for i, g in enumerate(gids)]
                it = iter(new)
                out = TJ.sub(lambda s: hexs([next(it) for _ in range(len(s.group(1)) // 4)]) + b" Tj", body)
                stats["cluster"] += 1
                return out

            new = SPAN.sub(repl, data)
            # shift the next relative move after each split so later glyphs stay exactly where they were
            pos, out, pending = 0, [], 0.0
            for t in re.finditer(rb"%%ADJ ([\d.]+)%%\n|(-?[\d.]+) (-?[\d.]+) Td|\bET\b|\bTm\b", new):
                out.append(new[pos:t.start()]); pos = t.end()
                if t.group(1):
                    pending += float(t.group(1))                     # marker removed from the stream
                elif t.group(2):
                    out.append(b"%.6f %s Td" % (float(t.group(2)) - pending, t.group(3)) if pending else t.group(0)); pending = 0.0
                else:
                    out.append(t.group(0)); pending = 0.0            # ET / Tm reset the line origin
            out.append(new[pos:])
            cs.write(join_lines(direction_marks(close_gaps(hoist_marks(b"".join(out), fontmap, st_of, stats), fontmap, st_of, stats), fontmap, st_of, stats), fontmap, st_of, stats))
    for st in states.values():
        st.finish(pdf)
    pdf.save(dst)
    return dict(stats)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--strict-widths"]
    print(process(args[0], args[1], strict_widths="--strict-widths" in sys.argv))
