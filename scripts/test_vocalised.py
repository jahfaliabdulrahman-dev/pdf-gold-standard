#!/usr/bin/env python3
"""Fully vocalised paragraphs must copy exactly — and the test must be able to fail.

Usage: python3 scripts/test_vocalised.py

tests/vocalised_raw.pdf is Chrome's untouched output for two paragraphs of fully vocalised text (Surah 93, GeezaPro,
printed on macOS); tests/vocalised_truth.txt is the text of one paragraph. The raw file must score BELOW the bar
(a test never seen failing is unverified); after scripts/fix_text_layer.py every word must come back with its marks,
in order, from PDFium and MuPDF, and not one pixel may change.
"""
import difflib
import os
import re
import sys
import tempfile
import unicodedata

import pikepdf
import pymupdf
import pypdfium2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fix_text_layer  # noqa: E402

RAW = os.path.join(HERE, "..", "tests", "vocalised_raw.pdf")
TRUTH = os.path.join(HERE, "..", "tests", "vocalised_truth.txt")
CTRL = re.compile("[⁠‎‏‪-‮⁦-⁩؜ـ\x00]")
norm = lambda t: unicodedata.normalize("NFC", CTRL.sub("", t))


def extract(path):
    doc = pypdfium2.PdfDocument(path)
    return {"PDFium": "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc))),
            "MuPDF": "\n".join(p.get_text() for p in pymupdf.open(path))}


def exact(text, want):
    got = norm(text).split()
    return sum(b.size for b in difflib.SequenceMatcher(None, want, got, autojunk=False).get_matching_blocks()) / len(want)


# Measured on the checked-in fixture tests/vocalised_raw.pdf (Chrome, GeezaPro): PDFium copies the joiner at
# character 103 (the end of the first RTL line), MuPDF at character 1 (right after its leading tab). A
# structural rule («any line end», «any tab») accepted a joiner anywhere along a line; the index does not.
GAP_SEAT = {"PDFium": 103, "MuPDF": 1}


def gap_seam(engine, strict_text, loose_text):
    """The fill's text AND its seat: ONE U+2060 at the measured index, and nothing else copied differently.

    A fill that is counted but never read is how a wrong character stays invisible; a fill read but not
    placed is how a wrong POSITION stays invisible (review P2).
    """
    n = strict_text.count("\u2060")
    if n != 1:
        return False, f"{n} U+2060 in the copied text (must be exactly 1)"
    i = strict_text.index("\u2060")
    want = GAP_SEAT.get(engine)
    if want is not None and i != want:
        return False, f"U+2060 at {i}; the measured seat for {engine} is {want} — {strict_text[max(0, i - 8):i + 8]!r}"
    if norm(strict_text) != norm(loose_text):
        return False, "the fill changed the copied text beyond the one invisible joiner"
    return True, f"U+2060 at {i}, the rest of the copy unchanged"


def r2l(src, dst):
    """build.py declares the document right-to-left; PDFium orders a line by that flag."""
    with pikepdf.open(src) as pdf:
        pdf.Root.ViewerPreferences = pikepdf.Dictionary(Direction=pikepdf.Name.R2L)
        pdf.save(dst)


def with_gap(src, dst, em=0.15):
    """Move one glyph right by `em` so it kerns away from its neighbour — the gap class the fix fills.

    GAP_MIN/GAP_MAX are 0.10/0.25 em; this fixture sits at 0.15, i.e. inside the band the code claims to
    handle. Without such a gap the strict branch never runs and the test proves nothing about it.
    """
    with pikepdf.open(src) as pdf:
        page = pdf.pages[0]
        data = bytes(page.Contents.read_bytes())
        m = list(re.finditer(rb"<([0-9A-Fa-f]+)>\s*Tj", data))
        if len(m) < 2:
            raise SystemExit("fixture: fewer than two <...> Tj glyph runs")
        size = float(re.findall(rb"/\w+\s+([\d.]+)\s+Tf", data)[0])
        shift = (f"{em * size:.3f} 0 Td\n").encode()
        pos = m[1].start()
        page.Contents = pdf.make_stream(data[:pos] + shift + data[pos:])
        pdf.save(dst)


if __name__ == "__main__":
    one = norm(open(TRUTH, encoding="utf-8").read()).split()
    want = one + one                                     # the fixture prints the paragraph twice
    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        raw, mid, fixed = (os.path.join(tmp, n) for n in ("raw.pdf", "mid.pdf", "fixed.pdf"))
        r2l(RAW, raw)
        stats = fix_text_layer.process(RAW, mid, strict_widths=True); r2l(mid, fixed)
        print(f"fix_text_layer: {stats}")
        for engine, text in extract(raw).items():
            s = exact(text, want); ok = s < 0.5
            print(f"{'PASS' if ok else 'FAIL'} raw-must-fail/{engine} - {s:.3f} (must be < 0.5)")
            if not ok: failed.append(f"raw-must-fail/{engine}")
        for engine, text in extract(fixed).items():
            s = exact(text, want); ok = s == 1.0
            print(f"{'PASS' if ok else 'FAIL'} vocalised-paragraphs/{engine} - {s:.3f} of {len(want)} words exact with their marks, in order")
            if not ok: failed.append(f"vocalised-paragraphs/{engine}")
        # nothing but the text may be pasted: no invisible filler for the drawn marks, no lines made of it
        for engine, text in extract(fixed).items():
            extra = sorted({f"U+{ord(c):04X}" for c in text if not ("\u0600" <= c <= "\u06ff") and c not in " \t\r\n\u200f"})
            lines = [l for l in text.splitlines() if l.strip()]
            ok = not extra and len(lines) == 8
            print(f"{'PASS' if ok else 'FAIL'} clean-paste/{engine} - {len(lines)} text lines (8 printed), foreign characters: {extra or 'none'}")
            if not ok: failed.append(f"clean-paste/{engine}")
        # a drawn glyph keeps the width of the font program (PDF/A 6.2.11.5, PDF/UA 7.21.5); hidden copies are exempt
        bad = fix_text_layer.drawn_width_mismatches(fixed)
        print(f"{'PASS' if not bad else 'FAIL'} drawn-widths - {len(bad)} drawn glyph(s) whose /W differs from the font program {bad[:3] if bad else ''}")
        if bad: failed.append("drawn-widths")
        a, b = pymupdf.open(RAW), pymupdf.open(fixed)
        diff = sum(a[i].get_pixmap(dpi=150).samples != b[i].get_pixmap(dpi=150).samples for i in range(len(a)))
        print(f"{'PASS' if not diff else 'FAIL'} pixels - {diff} page(s) differ at 150 dpi")
        if diff: failed.append("pixels")
        # The strict branch itself: a fixture whose glyphs kern 0.15 em apart must be filled, and the same
        # fixture under strict_widths=False must not fill it — otherwise the test never enters the branch
        # it claims to cover (a test never seen failing is unverified).
        gap_src, gap_strict, gap_loose, gap_wrong = (
            os.path.join(tmp, n) for n in ("gap.pdf", "gap-fixed.pdf", "gap-loose.pdf", "gap-wrong.pdf"))
        with_gap(RAW, gap_src)
        st_strict = fix_text_layer.process(gap_src, gap_strict, strict_widths=True)
        st_loose = fix_text_layer.process(gap_src, gap_loose, strict_widths=False)
        filled = st_strict.get("gap_filled", 0)
        ok = filled >= 1
        print(f"{'PASS' if ok else 'FAIL'} gap-filled/strict - {filled} gap(s) inside "
              f"{fix_text_layer.GAP_MIN}–{fix_text_layer.GAP_MAX} em filled by the strict branch")
        if not ok: failed.append("gap-filled/strict")
        ok = st_loose.get("gap_filled", 0) == 0
        print(f"{'PASS' if ok else 'FAIL'} gap-filled/counter - strict_widths=False fills "
              f"{st_loose.get('gap_filled', 0)} (must be 0: the fill is the strict branch's alone)")
        if not ok: failed.append("gap-filled/counter")
        # What the fill PUT in the text, not only that it ran: one joiner at the seam and no other change.
        strict_text, loose_text = extract(gap_strict), extract(gap_loose)
        for engine in ("PDFium", "MuPDF"):
            ok, why = gap_seam(engine, strict_text[engine], loose_text[engine])
            print(f"{'PASS' if ok else 'FAIL'} gap-text/{engine} - {why}")
            if not ok: failed.append(f"gap-text/{engine}")
        # Counter: the same branch filled with another character must be caught (a check never seen failing
        # is unverified). U+200B is not stripped by norm(), so it also alters the copy — both must show.
        keep = fix_text_layer.GAP_JOINER
        try:
            fix_text_layer.GAP_JOINER = "\u200b"
            fix_text_layer.process(gap_src, gap_wrong, strict_widths=True)
        finally:
            fix_text_layer.GAP_JOINER = keep
        # Counter on the SEAT: the same joiner, moved to the head of the text, must be refused.
        moved = {e: ("\u2060" + t.replace("\u2060", "", 1)) for e, t in strict_text.items()}
        seat_bad = {e: gap_seam(e, moved[e], loose_text[e])[0] for e in moved}
        ok = not any(seat_bad.values())
        print(f"{'PASS' if ok else 'FAIL'} gap-text/counter-seat - a U+2060 at the wrong index is refused: {seat_bad}")
        if not ok: failed.append("gap-text/counter-seat")

        wrong_text = extract(gap_wrong)
        verdicts = {e: gap_seam(e, wrong_text[e], loose_text[e])[0] for e in wrong_text}
        ok = not any(verdicts.values())
        print(f"{'PASS' if ok else 'FAIL'} gap-text/counter - filling with U+200B instead of U+2060 is "
              f"refused: {verdicts}")
        if not ok: failed.append("gap-text/counter")
    if failed:
        print(f"\nTEST FAILED: {failed}"); raise SystemExit(1)
    print("\nTEST PASSED")
