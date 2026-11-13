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
GAP_MIN, GAP_MAX = 0.10, 0.25      # em: a positive kern readers may read as a space; larger jumps are real gaps


def close_gaps(data, fontmap, st_of, stats):
    """Glyphs are placed by explicit Td, so /W only tells readers how wide a glyph is. Where the next letter on the
    same baseline starts further right than this glyph's width (kerning), give this occurrence an alias whose width
    is the real advance. Drawing is unchanged."""
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
                edits.append((pos, s.want(cid, text, width=round((b[0] - x0) / sz * 1000, 4)))); stats["gap_closed"] += 1
            break
    out = bytearray(data)
    for pos, cid in edits:
        out[pos:pos + 4] = b"%04X" % cid
    return bytes(out)


POS = re.compile(rb"(/F\w+)\s+([\d.]+)\s+Tf|1 0 0 -1 (-?[\d.]+) (-?[\d.]+) Tm|(-?[\d.]+) (-?[\d.]+) Td|<([0-9A-Fa-f]+)> Tj|\bET\b")
LRM, RLM = "\u200e", "\u200f"
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
RUN_GAP = re.compile(rb"EMC\n\s*((?:1 0 0 -1 [\d.]+ [\d.]+ Tm\n)?-?[\d.]+ -?[\d.]+ Td\s+<[0-9A-Fa-f]{4}> Tj\n)\s*/ReversedChars BMC\n")


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
                g[0] = body[:k.start()] + b"%s %s Tf <%04X> Tj" % (nf[0].encode(), nf[1].encode(), sc) + body[k.end():]
                g.append(nf); stats["space_refont"] += 1
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
    return b"".join(out)


def process(src, dst):
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
                mark_glyphs = list(range(len(gids) - 1)); k = 0; plan = []; pre = []
                part_w = st.width.get(gids[-1], st.dw) / len(vis); part = part_w / 1000 * size
                for j, u in enumerate(vis):
                    if marks[j]:
                        if k >= len(mark_glyphs) or sorted(assign[mark_glyphs[k]]) != sorted(marks[j]): return None
                        i = mark_glyphs[k]; k += 1
                        pre.append((off[i], st.want(gids[i], assign[i]), False))
                    plan.append((off[-1] + j * part, st.want(gids[-1], letters[j], width=round(part_w, 4)), j > 0))
                plan = pre + plan            # marks first, then letters left to right: positions never jump backwards
                if k != len(mark_glyphs): return None
                head = body[:shows[0].start()]; cur = 0.0; out = head
                for o, cid, hidden in plan:
                    if out is not head: out += b"%.6f 0 Td " % (o - cur); cur = o   # Td also resets the pen to the line origin
                    elif abs(o) > 1e-9: out += b"%.6f 0 Td " % o; cur = o
                    out += (b"3 Tr " if hidden else b"") + hexs([cid]) + b" Tj" + (b" 0 Tr\n" if hidden else b"\n")
                return out + body[shows[0].end():].lstrip(b"\n") + (b"%%%%ADJ %.6f%%%%\n" % cur if cur else b"")

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
                    n = len(chars); w = st.width.get(g, st.dw); part = w / n
                    lead = st.want(g, chars[-1], width=round(part, 4))
                    out = TJ.sub(hexs([lead]) + b" Tj", body)
                    h = part / 1000 * size
                    for ch in reversed(chars[:-1]):                  # visual order: last logical letter is leftmost
                        comp = st.want(g, ch, width=round(part, 4))   # same outline, invisible (Tr 3): no pixel changes
                        out += b"%.6f 0 Td 3 Tr " % h + hexs([comp]) + b" Tj 0 Tr\n"
                    stats["ligature_split"] += 1
                    return out + b"%%%%ADJ %.6f%%%%\n" % (h * (n - 1))
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
                    if out is None:
                        stats["kept_cluster_ambiguous"] += 1; return m.group(0)
                    stats["cluster_split"] += 1; return out
                for i in assign:                                     # marks in canonical order, so equal sets share one mapping
                    if len(assign[i]) > 1 and all(is_mark(c) for c in assign[i]):
                        assign[i] = "".join(sorted(assign[i], key=unicodedata.combining))
                if any(not assign[i] or (len(assign[i]) > 1 and not all(is_mark(c) for c in assign[i])) for i in assign):
                    stats["kept_cluster_ambiguous"] += 1; return m.group(0)
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
            cs.write(join_lines(direction_marks(close_gaps(b"".join(out), fontmap, st_of, stats), fontmap, st_of, stats), fontmap, st_of, stats))
    for st in states.values():
        st.finish(pdf)
    pdf.save(dst)
    return dict(stats)


if __name__ == "__main__":
    print(process(sys.argv[1], sys.argv[2]))
