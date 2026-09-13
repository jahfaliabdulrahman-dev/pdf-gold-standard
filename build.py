#!/usr/bin/env python3
"""PDF Gold Standard — build pipeline.
HTML (designed pages) -> Chrome headless print -> PyMuPDF interactivity layer.

Usage:  python3 build.py [source.html] [output.pdf]
Defaults: guide-v2.html -> ./out.pdf
"""
import base64
import io
import os
import re
import shutil
import subprocess
import sys

import fitz  # PyMuPDF
import segno

PROJ = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PROJ, "guide-v2.html")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.getcwd(), "out.pdf")
TMP_HTML = "/tmp/gold-guide-final.html"
TMP_PDF = "/tmp/gold-guide-raw.pdf"

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


def qr_datauri(url: str) -> str:
    q = segno.make(url, error="m")
    buf = io.BytesIO()
    q.save(buf, kind="png", scale=10, border=2, dark="#3d1a9e", light="#ffffff")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def build_html() -> None:
    html = open(SRC, encoding="utf-8").read()
    # Local-first fonts: base64-embed the woff2 files so the print is
    # deterministic and offline; then drop the remote font links.
    fdir = os.path.join(PROJ, "fonts")
    if os.path.isdir(fdir):
        fcss = open(os.path.join(fdir, "fonts.css"), encoding="utf-8").read()

        def _embed(m):
            fp = os.path.join(fdir, m.group(1))
            return "url(data:font/woff2;base64," + base64.b64encode(open(fp, "rb").read()).decode() + ")"

        fcss = re.sub(r"url\('([^']+)'\)", _embed, fcss)
        html = html.replace("/*__FONTS__*/", fcss)
    html = re.sub(r"<link[^>]*fonts\.(?:googleapis|gstatic)\.com[^>]*>\s*", "", html)
    for ph, url in [
        ("{{QR_IBM}}", "https://github.com/IBM/plex"),
        ("{{QR_PYMUPDF}}", "https://pymupdf.readthedocs.io"),
        ("{{QR_PAGEDJS}}", "https://pagedjs.org"),
        ("{{QR_CHROME}}", "https://developer.chrome.com/docs/chromium/headless"),
    ]:
        html = html.replace(ph, qr_datauri(url))
    # v2 generated-art layer: base64-embed local art so the print stays
    # deterministic (Chrome renders from /tmp; relative paths would break).
    adir = os.path.join(PROJ, "art")
    for ph, fn in [
        ("{{ART_COVER}}", "embed-cover.jpg"),
        ("{{ART_DIVIDER}}", "embed-divider.jpg"),
        ("{{ART_BACK}}", "embed-back.jpg"),
    ]:
        fp = os.path.join(adir, fn)
        if os.path.exists(fp):
            payload = base64.b64encode(open(fp, "rb").read()).decode()
            html = html.replace(ph, "data:image/jpeg;base64," + payload)
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
    print("[2/4] chrome printed:", TMP_PDF)


def interactivize() -> None:
    doc = fitz.open(TMP_PDF)
    n = doc.page_count
    print("      pages:", n)

    doc.set_toc([
        [1, "الغلاف", 1],
        [1, "البسملة", 2],
        [1, "جدول المحتويات", 3],
        [1, "القسم الأول — الأساس", 4],
        [2, "لماذا هذا المعيار؟", 5],
        [2, "نظام التنقل الدائم", 6],
        [1, "القسم الثاني — البناء", 7],
        [2, "الهوية البصرية والتايبوغرافي", 8],
        [2, "الإيقاع الطباعي والمكونات", 9],
        [2, "دعم العربية والتحقق الآلي", 10],
        [1, "المراجع والأدوات", 11],
        [1, "الغلاف الخلفي", 12],
    ])

    # nav buttons on content+divider pages (0-based idx 3..10 = pages 4..11)
    XS = [58.0, 95.33, 132.67, 170.0]
    for i in range(3, 11):
        pg = doc[i]
        pg.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(XS[3], 37, XS[3] + 25, 62), "page": 0})      # home -> cover
        pg.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(XS[2], 37, XS[2] + 25, 62), "page": 2})      # toc
        pg.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(XS[1], 37, XS[1] + 25, 62), "page": i - 1})  # prev
        pg.insert_link({"kind": fitz.LINK_GOTO, "from": fitz.Rect(XS[0], 37, XS[0] + 25, 62), "page": i + 1})  # next

    # TOC rows (page idx 2) -> content pages 5,6,8,9,10,11 (0-based 4,5,7,8,9,10)
    for k, target in enumerate([4, 5, 7, 8, 9, 10]):
        top = (64 + k * 16.5) * MM
        rect = fitz.Rect(39.54 * MM, top, 189.54 * MM, top + 13 * MM)
        doc[2].insert_link({"kind": fitz.LINK_GOTO, "from": rect, "page": target})

    # references rows (page idx 10) -> URI links
    urls = [
        "https://github.com/IBM/plex",
        "https://pymupdf.readthedocs.io",
        "https://pagedjs.org",
        "https://developer.chrome.com/docs/chromium/headless",
    ]
    for k, url in enumerate(urls):
        top = (66 + k * 26) * MM
        rect = fitz.Rect(31.54 * MM, top, 189.54 * MM, top + 22 * MM)
        doc[10].insert_link({"kind": fitz.LINK_URI, "from": rect, "uri": url})

    doc.set_metadata({
        "title": "معيار إنتاج ملفات PDF — دليل المعيار · الإصدار الثاني",
        "author": "م. عبدالرحمن جحفلي",
        "subject": "معيار جودة إنتاج ملفات PDF التفاعلية العربية",
        "keywords": "PDF, Arabic, RTL, تفاعلي, معيار, Gold Standard",
        "creator": "Hermes PDF Gold Standard pipeline",
    })
    # Force single-page display in every compliant viewer — house standard:
    # pages must read as independent sheets (like the reference model).
    cat = doc.pdf_catalog()
    doc.xref_set_key(cat, "PageLayout", "/SinglePage")
    doc.xref_set_key(cat, "PageMode", "/UseNone")
    # Mirror the reference model's RTL reading direction + keep doc-title display.
    vpx = doc.get_new_xref()
    doc.update_object(vpx, "<< /Type /ViewerPreferences /Direction /R2L /DisplayDocTitle true >>")
    doc.xref_set_key(cat, "ViewerPreferences", f"{vpx} 0 R")
    doc.save(OUT, deflate=True, garbage=3)
    print("[3/4] interactivity injected + saved:", OUT, os.path.getsize(OUT), "bytes")


def verify() -> None:
    v = fitz.open(OUT)
    toc = v.get_toc()
    print("[4/4] VERIFY")
    print("      outline entries:", len(toc))
    total = 0
    for i, pg in enumerate(v):
        ls = pg.get_links()
        if ls:
            tgts = sorted({(l["kind"], l.get("page"), bool(l.get("uri"))) for l in ls})
            print(f"      p{i+1}: {len(ls)} links -> {tgts}")
            total += len(ls)
    print("      total links:", total)
    md = v.metadata
    print("      title:", md.get("title"))
    print("      pages:", v.page_count)


if __name__ == "__main__":
    build_html()
    print_pdf()
    interactivize()
    verify()
