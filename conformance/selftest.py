"""Planted mutations: every check must be seen catching its own defect, on a file it is given.

The rule the pipeline already lives by, applied to this gate: a check never seen failing is unverified, and a
comparison that cannot fail is decoration. Each mutation is applied to a **fresh build of a fixture case**, the
baseline is measured first (the checks must be green on it), and the mutation must move exactly the named
quantity:

  · a metric drops (order, digit_runs, exact)
  · a counter rises (presentation forms, direction marks the file carries)
  · a structural check turns from pass to fail (/Lang, TH, outline, ToUnicode)

Mutations are edits to the PDF, not to the case: the truth never changes, so a mutation that the gate misses is
a hole in the gate, not a disagreement about the text. `N/A` is declared and printed with its reason; it never
counts as a catch.
"""
import os
import shutil
import sys
import tempfile

import pikepdf
import pymupdf

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
if os.path.join(REPO, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "scripts"))

import pdfops


class _NA(Exception):
    """The fixture does not carry what this mutation needs — declared, never counted as caught."""


# Four fixtures, each chosen by measurement (2026-11-19) so its baseline is green where the mutation needs a
# head start: `text` and `digits` are exact=1 in PDFium, `marked` is exact=1 with 8 marks in the layer, and
# `struct` passes the structural checks (its PDFium exact is 0 — the table — which the structure does not read).
FIXTURES = {
    "text": {
        "id": "selftest-text", "category": "shaping", "lang": "ar", "font": "plex", "note": "selftest fixture",
        "blocks": [{"type": "heading", "level": 1, "text": "كشف الحساب"},
                   {"type": "paragraph", "text": "ألف باء جيم دال."}],
    },
    "digits": {
        "id": "selftest-digits", "category": "digits", "lang": "ar", "font": "plex", "note": "selftest fixture",
        "blocks": [{"type": "paragraph", "text": "المبلغ 6060 ريال سعودي."}],
    },
    "marked": {
        "id": "selftest-marked", "category": "vocalisation", "lang": "ar", "font": "amiri", "note": "selftest fixture",
        "blocks": [{"type": "heading", "level": 1, "text": "بسم الله"},
                   {"type": "paragraph", "text": "الْحَمْدُ لِلَّهِ"}],
    },
    "struct": {
        "id": "selftest-struct", "category": "tables", "lang": "ar", "font": "plex", "note": "selftest fixture",
        "blocks": [{"type": "heading", "level": 1, "text": "كشف الحساب"},
                   {"type": "table", "header": ["البند", "الوصف"], "rows": [["رسوم", "إدارية"]]}],
    },
}


def _text_ops(instr):
    return [i for i, ins in enumerate(instr)
            if str(ins.operator) in ("Tj", "TJ") and ins.operands and len(_raw(ins.operands[0])) > 0]


def _raw(obj) -> bytes:
    try:
        return obj.read_bytes()
    except Exception:
        pass
    try:
        return bytes(obj)
    except Exception:
        return b""


def _is_digit(code: int) -> bool:
    return 0x30 <= code <= 0x39 or 0x660 <= code <= 0x669 or 0x6F0 <= code <= 0x6F9


def _drawn_codes(pdf) -> set:
    """Every 2-byte code drawn on page 1 — a mutation that changes a code nobody draws proves nothing."""
    codes = set()
    for ins in pikepdf.parse_content_stream(pdf.pages[0]):
        if str(ins.operator) in ("Tj", "TJ"):
            for o in (ins.operands if str(ins.operator) == "TJ" else ins.operands[:1]):
                raw = _raw(o)
                for k in range(0, len(raw) - 1, 2):
                    codes.add(int.from_bytes(raw[k:k + 2], "big"))
    return codes


def _rewrite(src: str, dst: str, fn) -> None:
    with pikepdf.open(src) as pdf:
        page = pdf.pages[0]
        instr = list(pikepdf.parse_content_stream(page))
        if not fn(instr, pdf):
            raise _NA("the fixture has nothing of that kind on page 1")
        page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(instr))
        pdf.save(dst)


def _replace(instr, index, operands, operator):
    instr[index] = pikepdf.ContentStreamInstruction(operands, operator)


# ---------------------------------------------------------------- content-stream mutations
def m_swap_runs(src, dst):
    _rewrite(src, dst, _swap_runs)


def _swap_runs(instr, pdf):
    idx = _text_ops(instr)
    if len(idx) < 2:
        raise _NA("fewer than two text runs")
    a, b = idx[0], idx[-1]
    if _raw(instr[a].operands[0]) == _raw(instr[b].operands[0]):
        raise _NA("the two runs carry the same bytes")
    _replace(instr, a, [pikepdf.String(_raw(instr[b].operands[0]))], instr[a].operator)
    _replace(instr, b, [pikepdf.String(_raw(instr[a].operands[0]))], instr[b].operator)
    return True


def m_swap_digits(src, dst):
    _rewrite(src, dst, _swap_digits)


def _swap_digits(instr, pdf):
    """Swap the glyphs of two digits. The layer draws one glyph per run, so the digits are found by DECODING
    each run (a code is a glyph id, not a character) and then two runs' operands are exchanged."""
    from .checks.mcid_text import _Font
    fonts = {}
    for name, font in (pdf.pages[0].get("/Resources", {}).get("/Font", {}) or {}).items():
        fonts[str(name)] = _Font(str(name), font)
    current, digits = None, []
    for i, ins in enumerate(instr):
        op = str(ins.operator)
        if op == "Tf":
            current = str(ins.operands[0])
        elif op in ("Tj", "TJ") and current in fonts:
            text = fonts[current].decode(_raw(ins.operands[0]))[0]
            if len(text) == 1 and text.isdigit():
                digits.append((i, current))       # the font at the run, not «whatever came last»
    for (a, fa), (b, fb) in zip(digits, digits[1:]):
        if fa != fb:
            continue
        ta = fonts[fa].decode(_raw(instr[a].operands[0]))[0]
        tb = fonts[fb].decode(_raw(instr[b].operands[0]))[0]
        if ta != tb:
            _replace(instr, a, [pikepdf.String(_raw(instr[b].operands[0]))], instr[a].operator)
            _replace(instr, b, [pikepdf.String(_raw(instr[a].operands[0]))], instr[b].operator)
            return True
    raise _NA("fewer than two distinct digit glyphs on page 1")


def _tu_fonts(pdf):
    out = {}
    for page in pdf.pages:
        for name, font in (page.get("/Resources", {}).get("/Font", {}) or {}).items():
            if font.get("/ToUnicode") is not None:
                out[str(name)] = font
    return out


def _rewrite_tu(pdf, font, mapping_fn) -> bool:
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts")))
    from fix_text_layer import parse_tu, write_tu
    cmap = parse_tu(font["/ToUnicode"].read_bytes().decode("latin-1"))
    new = mapping_fn(cmap)
    if new is None:
        return False
    font["/ToUnicode"] = pdf.make_stream(write_tu(new))
    return True


def m_presentation_form(src, dst):
    with pikepdf.open(src) as pdf:
        drawn = _drawn_codes(pdf)
        for font in _tu_fonts(pdf).values():
            done = _rewrite_tu(pdf, font, lambda m: _to_form(m, drawn))
            if done:
                pdf.save(dst)
                return
    raise _NA("no drawn code maps to an Arabic letter")


def _to_form(cmap, drawn):
    for code in sorted(set(cmap) & drawn):
        text = cmap[code]
        if len(text) == 1 and 0x0621 <= ord(text) <= 0x064A:
            out = dict(cmap)
            out[code] = "\uFE91"          # ARABIC LETTER BEH INITIAL FORM — a presentation form, not a letter
            return out
    return None


def m_insert_bidi(src, dst):
    with pikepdf.open(src) as pdf:
        for font in _tu_fonts(pdf).values():
            def add(m):
                for code, text in sorted(m.items()):
                    if text == " ":
                        out = dict(m)
                        out[code] = "\u200F"      # RIGHT-TO-LEFT MARK where a space was
                        return out
                return None
            if _rewrite_tu(pdf, font, add):
                pdf.save(dst)
                return
    raise _NA("no ToUnicode CMap maps a space")


def m_drop_mark(src, dst):
    """Remove one Arabic diacritic from the drawn layer: exact must fall, skeleton_exact must stay."""
    with pikepdf.open(src) as pdf:
        fonts = _tu_fonts(pdf)
        mark_codes = {}
        for name, font in fonts.items():
            import sys
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts")))
            from fix_text_layer import parse_tu
            for code, text in parse_tu(font["/ToUnicode"].read_bytes().decode("latin-1")).items():
                if len(text) == 1 and 0x064B <= ord(text) <= 0x0652:
                    mark_codes.setdefault(name, set()).add(code)
        if not mark_codes:
            raise _NA("no diacritic in any ToUnicode CMap")
        page = pdf.pages[0]
        instr = list(pikepdf.parse_content_stream(page))
        current = None
        for i, ins in enumerate(instr):
            if str(ins.operator) == "Tf":
                current = str(ins.operands[0])
            elif str(ins.operator) in ("Tj", "TJ") and current in mark_codes:
                raw = bytearray(_raw(ins.operands[0]))
                for k in range(0, len(raw) - 1, 2):
                    if int.from_bytes(raw[k:k + 2], "big") in mark_codes[current]:
                        del raw[k:k + 2]
                        _replace(instr, i, [pikepdf.String(bytes(raw))], ins.operator)
                        page.Contents = pdf.make_stream(pikepdf.unparse_content_stream(instr))
                        pdf.save(dst)
                        return
    raise _NA("no drawn diacritic on page 1")


# ---------------------------------------------------------------- document mutations
def m_drop_lang(src, dst):
    with pikepdf.open(src) as pdf:
        if "/Lang" not in pdf.Root:
            raise _NA("no /Lang to drop")
        del pdf.Root["/Lang"]
        pdf.save(dst)


def m_th_to_td(src, dst):
    with pikepdf.open(src) as pdf:
        root = pdf.Root.get("/StructTreeRoot")
        if root is None:
            raise _NA("no structure tree")
        changed = []

        def walk(node):
            if isinstance(node, pikepdf.Array):
                for x in node:
                    walk(x)
                return
            if not hasattr(node, "get"):
                return
            if str(node.get("/S")) == "/TH":
                node["/S"] = pikepdf.Name("/TD")
                changed.append(1)
                return
            k = node.get("/K")
            for x in (list(k) if isinstance(k, pikepdf.Array) else [k] if k is not None else []):
                walk(x)

        walk(root.get("/K"))
        if not changed:
            raise _NA("no /TH element")
        pdf.save(dst)


def m_outline_mismatch(src, dst):
    doc = pymupdf.open(src)
    toc = doc.get_toc()
    if not toc:
        raise _NA("no outline")
    toc[0][1] = toc[0][1] + " (معدّل)"
    doc.set_toc(toc)
    doc.save(dst, garbage=3, deflate=True)
    doc.close()


def m_drop_tounicode(src, dst):
    with pikepdf.open(src) as pdf:
        for font in _tu_fonts(pdf).values():
            del font["/ToUnicode"]
            pdf.save(dst)
            return
    raise _NA("no font with /ToUnicode")


def m_foreign_font(src, dst):
    """Rename every embedded face to one that is not the case's font nor the declared fallback.

    The `fonts` check is the gate's only defence against shipping an OEM face we have no licence to embed
    (the review's P2-3: Apple's .SFCompact-Black was embedded in a distributable file). It was widened to allow
    the declared OFL fallback — so it now needs a mutation that proves it still refuses a stranger.
    """
    renamed = 0
    with pikepdf.open(src) as pdf:
        for obj in pdf.objects:
            if not isinstance(obj, pikepdf.Dictionary):
                continue
            if "/BaseFont" in obj and "/Subtype" in obj and "/ToUnicode" in obj or "/BaseFont" in obj:
                try:
                    obj["/BaseFont"] = pikepdf.Name("/AAAAAA+SFCompact-Black")
                    renamed += 1
                except Exception:
                    continue
            if "/FontName" in obj:
                try:
                    obj["/FontName"] = pikepdf.Name("/AAAAAA+SFCompact-Black")
                    renamed += 1
                except Exception:
                    continue
        pdf.save(dst)
    if not renamed:
        raise _NA("no font object to rename")


# ---------------------------------------------------------------- house keys (the private-key rule)
def m_private_key(src, dst):
    """The incident: the text layer's own key left on a delivered font dictionary."""
    with pikepdf.open(src) as pdf:
        for obj in pdf.objects:
            if isinstance(obj, pikepdf.Dictionary) and obj.get("/Subtype") == "/Type0":
                obj[pdfops.MARK_CIDS_KEY] = pikepdf.Array([1])
                pdf.save(dst)
                return
    raise _NA("no Type0 font to carry the key")


def m_private_key_stream(src, dst):
    """The edge the old filter missed: a key on a STREAM dictionary (pikepdf reports it as Object, not Dictionary)."""
    with pikepdf.open(src) as pdf:
        contents = pdf.pages[0].Contents
        if isinstance(contents, pikepdf.Array):        # a page may carry an array of content streams
            contents = contents[0] if contents else None
        if contents is None or not hasattr(contents, "stream_dict"):
            raise _NA("page 1 has no content stream")
        contents.stream_dict[pdfops.HOUSE_KEY_PREFIX + "Probe"] = pikepdf.String("probe")
        pdf.save(dst)


def m_private_key_direct(src, dst):
    """The other edge: a key on a DIRECT dictionary nested in the catalog — `pdf.objects` never lists it."""
    with pikepdf.open(src) as pdf:
        pdf.Root["/ProbeHolder"] = pikepdf.Dictionary({pdfops.HOUSE_KEY_PREFIX + "Direct": 1})
        pdf.save(dst)


# ---------------------------------------------------------------- harness
def _build(fixture: str, outdir: str, engine: str) -> str:
    from .adapters import chrome
    pdf = os.path.join(outdir, f"{fixture}.pdf")
    chrome.render_case(FIXTURES[fixture], pdf, "chrome-raw" if engine == "chrome-raw" else "chrome")
    return pdf


def _measure(pdf: str, fixture: str) -> dict:
    from .checks import metrics, mcid_text, structure
    from .readers import text_many
    case = FIXTURES[fixture]
    scan = mcid_text.scan(pdf)
    file_text = "\n".join(scan["text"].values())
    out = text_many("pdfium", [pdf])[0]
    m = metrics.measure(out, _truth(case))
    checks = {c["id"]: c["status"] for c in structure.evaluate(pdf, case, {"postprocess": True}, run_verapdf=False)}
    file_m = metrics.measure(file_text, _truth(case))
    return {"metrics": m["metrics"], "defects": m["defects"], "checks": checks,
            "file_metrics": file_m["metrics"], "file_defects": file_m["defects"],
            "file_bidi": metrics.bidi_count(file_text)}


def _truth(case: dict) -> str:
    from .corpus.truth import truth
    return truth(case)


MUTATIONS = [
    # (name, fixture, callable, the named witness, the assertion on (baseline, mutated))
    ("swap-two-runs", "text", m_swap_runs,
     "pdfium order", lambda b, m: m["metrics"]["order"] < b["metrics"]["order"] - 0.05),
    ("swap-two-digits", "digits", m_swap_digits,
     "file digit_runs", lambda b, m: m["file_metrics"]["digit_runs"] < b["file_metrics"]["digit_runs"]),
    ("presentation-form", "text", m_presentation_form,
     "check presentation-forms", lambda b, m: b["checks"]["presentation-forms"] == "pass"
     and m["checks"]["presentation-forms"] == "fail"),
    # The witness must be something a VERDICT consumes: `tagged-text` fails because the mark replaces a space
    # and glues two words (measured). A raw counter that no check reads caught nothing (review F2/S3).
    ("insert-U+200F", "text", m_insert_bidi,
     "check tagged-text", lambda b, m: b["checks"]["tagged-text"] == "pass"
     and m["checks"]["tagged-text"] == "fail"),
    ("drop-lang", "struct", m_drop_lang,
     "check lang", lambda b, m: b["checks"]["lang"] == "pass" and m["checks"]["lang"] == "fail"),
    ("TH-to-TD", "struct", m_th_to_td,
     "check tables", lambda b, m: b["checks"]["tables"] == "pass" and m["checks"]["tables"] == "fail"),
    ("outline-mismatch", "struct", m_outline_mismatch,
     "check outline", lambda b, m: b["checks"]["outline"] == "pass" and m["checks"]["outline"] == "fail"),
    ("drop-ToUnicode", "struct", m_drop_tounicode,
     "check tounicode-coverage", lambda b, m: b["checks"]["tounicode-coverage"] == "pass"
     and m["checks"]["tounicode-coverage"] == "fail"),
    ("foreign-font", "struct", m_foreign_font,
     "check fonts", lambda b, m: b["checks"]["fonts"] == "pass" and m["checks"]["fonts"] == "fail"),
    ("drop-one-haraka", "marked", m_drop_mark,
     "exact falls, skeleton stays", lambda b, m: m["metrics"]["exact"] == 0.0
     and m["metrics"]["skeleton_exact"] == 1.0 and b["metrics"]["exact"] == 1.0),
    # One per place a key can live. The rule says "any object"; each mutation is the witness for one clause
    # of that claim (indirect dictionary · stream dictionary · direct dictionary).
    ("private-key-leak", "struct", m_private_key,
     "check private-keys", lambda b, m: b["checks"]["private-keys"] == "pass"
     and m["checks"]["private-keys"] == "fail"),
    ("private-key-on-stream", "struct", m_private_key_stream,
     "check private-keys", lambda b, m: b["checks"]["private-keys"] == "pass"
     and m["checks"]["private-keys"] == "fail"),
    ("private-key-direct", "struct", m_private_key_direct,
     "check private-keys", lambda b, m: b["checks"]["private-keys"] == "pass"
     and m["checks"]["private-keys"] == "fail"),
]


def run(engine: str = "chrome") -> list[str]:
    tmp = tempfile.mkdtemp(prefix="conf-selftest-")
    missed, applied, na = [], 0, []
    try:
        baseline = {}
        for fixture in {m[1] for m in MUTATIONS}:
            pdf = _build(fixture, tmp, engine)
            baseline[fixture] = _measure(pdf, fixture)
            print(f"baseline {fixture:<8} checks "
                  f"{sum(1 for v in baseline[fixture]['checks'].values() if v == 'pass')} pass · "
                  f"pdfium exact {baseline[fixture]['metrics']['exact']:.0f} · "
                  f"order {baseline[fixture]['metrics']['order']:.3f}")
        for name, fixture, fn, witness, assertion in MUTATIONS:
            src = os.path.join(tmp, f"{fixture}.pdf")
            dst = os.path.join(tmp, f"{name}.pdf")
            try:
                fn(src, dst)
            except _NA as exc:
                # A declared mutation that cannot be planted is a MISS, not a skip: "N/A never counts as a
                # catch" was in this file's prose while the code returned success on an all-N/A run (review F4).
                print(f">>> {name:22s} MISSED — the mutation could not be planted: {exc}")
                na.append(name)
                missed.append(name)
                continue
            got = _measure(dst, fixture)
            ok = assertion(baseline[fixture], got)
            applied += 1
            print(f">>> {name:22s} expect {witness:26s} -> {'CAUGHT' if ok else 'MISSED'}")
            if not ok:
                missed.append(name)
        print(f"\n{applied} mutations applied · {len(na)} could not be planted · {len(missed)} missed")
        if missed:
            print(f"SELFTEST FAILED — not caught: {missed}")
        else:
            print("SELFTEST PASSED — every planted mutation was caught by its named check")
        return missed
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
