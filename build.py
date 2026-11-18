#!/usr/bin/env python3
"""PDF Gold Standard — build pipeline.
HTML (designed pages) -> Chrome headless print -> PyMuPDF interactivity layer.

Usage:  python3 build.py [source.html] [output.pdf]
Defaults: guide-v2.html -> ./out.pdf
"""
import atexit
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

import fitz  # PyMuPDF

import spec_loader
from render_markup import rendered_markup

NS = spec_loader.load()

PROJ = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJ, NS.SOURCE_HTML)
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.getcwd(), "out.pdf")
# Build into a sibling .partial.pdf; only a gate PASS replaces OUT (a failed run never clobbers the last good file).
PARTIAL = OUT[:-4] + ".partial.pdf" if OUT.endswith(".pdf") else OUT + ".partial"
# Intermediate files live in a private directory of this run: two builds never collide, nothing stays in /tmp.
TMPDIR = tempfile.mkdtemp(prefix="gold-guide-")
atexit.register(shutil.rmtree, TMPDIR, ignore_errors=True)
TMP_HTML = os.path.join(TMPDIR, "final.html")
TMP_PDF = os.path.join(TMPDIR, "raw.pdf")

MM = 2.83465  # 1 mm in pt


def chrome_bin() -> str:
    # CHROME_PATH env first, then macOS app, then PATH lookups
    cands = [os.environ.get("CHROME_PATH", ""),
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             shutil.which("google-chrome") or "",
             shutil.which("google-chrome-stable") or "",
             shutil.which("chromium") or "",
             shutil.which("chromium-browser") or ""]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise SystemExit("Chrome not found - set CHROME_PATH to the Chrome/Chromium binary.")


CHROME = chrome_bin()


def build_html() -> None:
    """Write the markup Chrome will print — derived from the spec and the source, never from a copy."""
    html = rendered_markup(NS, open(SRC, encoding="utf-8").read(), PROJ)
    open(TMP_HTML, "w", encoding="utf-8").write(html)
    print("[1/4] html ready (QR embedded)")


def print_pdf() -> None:
    r = subprocess.run(
        [
            CHROME,
            "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
            "--virtual-time-budget=20000",
            f"--print-to-pdf={TMP_PDF}", "file://" + TMP_HTML,
        ],
        capture_output=True, text=True, timeout=240,
    )
    assert os.path.exists(TMP_PDF), f"chrome failed: {r.stderr[-400:]}"
    # Keep what Chrome actually produced: the only way to tell a Chrome text-layer defect from a
    # post-processing one is to measure the raw file before anything else touches it.
    try:
        # Keep Chrome's own output BESIDE the build, not in the run directory that atexit removes, so a
        # disputed text layer can be re-measured from the file that produced it.
        shutil.copyfile(TMP_PDF, os.path.splitext(OUT)[0] + ".raw.pdf")
    except OSError as exc:                      # keep building; only the diagnostic copy is lost
        print(f"[!] could not keep the raw Chrome PDF: {exc}")
    print("[2/4] chrome printed:", TMP_PDF)


def interactivize() -> None:
    doc = fitz.open(TMP_PDF)
    n = doc.page_count
    print("      pages:", n)

    doc.set_toc(NS.TOC)

    # nav buttons on content+divider pages — geometry and targets from nav_spec (one set of numbers)
    for i in NS.NAV_PAGES:
        pg = doc[i]
        for role, x in NS.SLOTS.items():
            pg.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(x, NS.NAV_Y0, x + NS.NAV_W, NS.NAV_Y1),
                            "page": NS.nav_target(role, i)})

    # contents rows -> section pages
    for k, target in enumerate(NS.TOC_ROWS):
        top = NS.toc_row_top(k)
        rect = fitz.Rect(NS.TOC_ROW_X0, top, NS.TOC_ROW_X1, top + NS.TOC_ROW_H)
        doc[NS.CONTENTS].insert_link({"kind": fitz.LINK_GOTO, "from": rect, "page": target})

    # references rows -> URI links
    for k, url in enumerate(NS.REF_URLS):
        top = (66 + k * 26) * MM
        rect = fitz.Rect(31.54 * MM, top, 189.54 * MM, top + 22 * MM)
        doc[NS.REF_PAGE].insert_link({"kind": fitz.LINK_URI, "from": rect, "uri": url})

    # Title/author/subject/keywords belong to the DOCUMENT (its spec), not to the pipeline: a second
    # document must not inherit the first one's identity.
    doc.set_metadata({
        "title": f"{getattr(NS, 'DOC_TITLE', 'معيار إنتاج ملفات PDF — دليل المعيار')} · الإصدار {NS.GUIDE_VERSION_AR}",
        "author": getattr(NS, "DOC_AUTHOR", "م. عبدالرحمن جحفلي"),
        "subject": getattr(NS, "DOC_SUBJECT", "معيار جودة إنتاج ملفات PDF التفاعلية العربية"),
        "keywords": getattr(NS, "DOC_KEYWORDS", "PDF, Arabic, RTL"),
        "creator": "Hermes PDF Gold Standard pipeline",
    })
    # Provenance: which source this file was built from. The gate refuses a file whose stamp is not its own truth.
    info = int(doc.xref_get_key(-1, "Info")[1].split()[0])
    doc.xref_set_key(info, "SourceFile", fitz.get_pdf_str(os.path.basename(SRC)))
    doc.xref_set_key(info, "SourceSHA256", fitz.get_pdf_str(hashlib.sha256(open(SRC, "rb").read()).hexdigest()))
    # Force single-page display in every compliant viewer — house standard:
    # pages must read as independent sheets (like the reference model).
    cat = doc.pdf_catalog()
    doc.xref_set_key(cat, "PageLayout", "/SinglePage")
    doc.xref_set_key(cat, "PageMode", "/UseNone")
    # Mirror the reference model's RTL reading direction + keep doc-title display.
    vpx = doc.get_new_xref()
    doc.update_object(vpx, "<< /Type /ViewerPreferences /Direction /R2L /DisplayDocTitle true >>")
    doc.xref_set_key(cat, "ViewerPreferences", f"{vpx} 0 R")
    doc.save(PARTIAL, deflate=True, garbage=3)
    print("[3/4] interactivity injected + saved:", PARTIAL, os.path.getsize(PARTIAL), "bytes")


if __name__ == "__main__":
    build_html()
    # The hash of the markup this build handed to Chrome. It is written into the manifest and
    # recomputed by the gate from the same spec and source: a file from another build cannot stand in.
    rendered_sha = hashlib.sha256(open(TMP_HTML, "rb").read()).hexdigest()
    print_pdf()
    interactivize()
    # rebuild the Arabic text layer (one code point per glyph) — drawing unchanged; see scripts/fix_text_layer.py
    sys.path.insert(0, os.path.join(PROJ, "scripts"))
    from fix_text_layer import process as fix_text_layer
    fixed = PARTIAL[:-4] + ".textfix.pdf"
    print("[4b] text layer rebuilt:", fix_text_layer(PARTIAL, fixed, strict_widths=True))
    os.replace(fixed, PARTIAL)
    # stage 5: metadata/structure declared in features.toml — applied after the text layer, before the gate
    from postprocess import apply as postprocess
    prof = os.environ.get("PDF_PROFILE", "web")
    post = PARTIAL[:-4] + ".post.pdf"
    print("[4c] postprocess:", ", ".join(postprocess(PARTIAL, post, prof, rendered_sha=rendered_sha)) or "none")
    os.replace(post, PARTIAL)
    # The gate is imported, not shelled out: it already returns the failing names, so no output format is
    # being parsed (a regex over stdout was one edit away from silently matching nothing).
    sys.path.insert(0, os.path.join(PROJ, "scripts"))
    import verify_pdf
    try:
        gate_doc = verify_pdf.open_for_gate(PARTIAL)
    except verify_pdf.GateInput as exc:
        print(f"FAIL input - {exc}")
        raise SystemExit(f"GATE FAILED — {OUT} left untouched; inspect {PARTIAL}")
    failing = set(verify_pdf.gate(gate_doc))
    if failing:
        raise SystemExit(f"GATE FAILED — {OUT} left untouched; inspect {PARTIAL}")
    os.replace(PARTIAL, OUT)
    print("[5/5] gate passed — published:", OUT)
