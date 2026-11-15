#!/usr/bin/env python3
"""End-to-end test of the fill surface: HTTP in, built PDF out — one process, one command.

    .venv/bin/python scripts/test_fill_surface.py [out.pdf]

Binds an ephemeral port (never 8765), POSTs a real Arabic form, checks the PDF it gets back, and saves it
for visual inspection. Exits non-zero on the first broken link in the chain (status, magic, pages, no
widgets left behind, the name present as page text).
"""
import os
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import fitz                       # noqa: E402
import pikepdf                    # noqa: E402

import fill_server                # noqa: E402

VALUES = {
    "name": "عبدالرحمن جحفلي",
    "email": "almohalhel1408@gmail.com",
    "note": "نصٌّ عربيٌّ كتبه المالك في نموذج الويب، ثم شكّله محرّك البناء: لاحظ اتصال الحروف، "
            "واتجاهها من اليمين إلى اليسار، والتفاف السطر الطويل بلا انقطاع.",
}


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Downloads", "filled.pdf")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), fill_server.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        body = urllib.parse.urlencode(VALUES).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/build", data=body, method="POST")
        with urllib.request.urlopen(req, timeout=600) as r:
            pdf = r.read()
            status = r.status
            ctype = r.headers.get("Content-Type")
    finally:
        srv.shutdown()

    print("status:", status, "| type:", ctype, "| bytes:", len(pdf))
    assert status == 200 and ctype == "application/pdf" and pdf[:5] == b"%PDF-", "bad response"
    open(out, "wb").write(pdf)

    doc = fitz.open(out)
    # the rebuilt text layer separates words with tabs/zero-width marks; compare on normalised text
    text = " ".join(doc[14].get_text().split())
    with pikepdf.open(out) as p:
        has_form = "/AcroForm" in p.Root
    print("pages:", doc.page_count, "| widgets left:", has_form)
    assert doc.page_count == 17, "page count changed"
    assert not has_form, "a filled copy must not leave a /AcroForm behind"
    assert "عبدالرحمن جحفلي" in text, "the name is not in the page text"
    assert "almohalhel1408@gmail.com" in text, "the address is not in the page text"
    assert "محرّك البناء" in text.replace("\u200c", "").replace("\u200f", ""), "the note is not in the page text"
    print("OK — saved:", out)
    doc[14].get_pixmap(dpi=110).save(out[:-4] + "-p15.png")


if __name__ == "__main__":
    main()
