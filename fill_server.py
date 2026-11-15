#!/usr/bin/env python3
"""Local fill surface for «الحرف المقلوب» — the answer to Arabic inside AcroForm.

No reader on the market shapes Arabic inside a form field (Chromium 385699043 is open; Adobe's own
community says Fill & Sign does not support Arabic; only Acrobat Pro ME types Arabic into a PDF). The
sustainable fix is not a trick in the file: it is to stop asking the reader to lay out Arabic.

    python fill_server.py            # http://127.0.0.1:8765
    open http://127.0.0.1:8765

The browser form collects the values, this server runs the SAME pipeline with `report_fill_spec`
(values become page text), and returns a PDF whose Arabic was shaped once, at build time, by Chrome.
Works the same on a phone, on Windows, in any reader, and in print.

Binds 127.0.0.1 on purpose: this is a single-user local surface, not a service. Do not put it on a
network interface without adding authentication and a CSRF token to the form.
"""
import html
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJ = os.path.dirname(os.path.abspath(__file__))
FILL_PAGE = os.path.join(PROJ, "fill.html")
MAX_BODY = 8 * 1024           # a name, an address and a note; nothing here needs more
LIMITS = {"name": 60, "email": 80, "note": 480}      # 480 fills the 39 mm box; more would clip silently


def clean(values: dict) -> dict:
    out = {}
    for key, limit in LIMITS.items():
        raw = (values.get(key) or "").strip()[:limit]
        if "\x00" in raw:
            raise ValueError("NUL in a value")
        out[key] = raw
    if not out["name"]:
        raise ValueError("the name is required")
    return out


def build(values: dict) -> bytes:
    with tempfile.TemporaryDirectory(prefix="fill-") as tmp:
        spec = os.path.join(tmp, "values.json")
        out = os.path.join(tmp, "filled.pdf")
        with open(spec, "w", encoding="utf-8") as fh:
            json.dump(values, fh, ensure_ascii=False)
        env = dict(os.environ, PDF_SPEC="report_fill_spec", FILL_JSON=spec)
        run = subprocess.run([sys.executable, os.path.join(PROJ, "build.py"),
                              os.path.join(PROJ, "report-v1.html"), out],
                             cwd=PROJ, env=env, capture_output=True, text=True)
        if run.returncode != 0 or not os.path.exists(out):
            tail = (run.stdout + run.stderr).strip().splitlines()[-6:]
            raise RuntimeError("the build failed:\n" + "\n".join(tail))
        return open(out, "rb").read()


class Handler(BaseHTTPRequestHandler):
    server_version = "FillSurface/1.0"

    def log_message(self, format, *args):      # noqa: A002 — the base class names it `format`
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def do_GET(self):
        if self.path.split("?")[0] not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = open(FILL_PAGE, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.split("?")[0] != "/api/build":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self.send_error(413, "body too large")
            return
        try:
            form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
            values = clean({k: v[0] for k, v in form.items() if v})
            pdf = build(values)
        except Exception as exc:              # the browser shows this text; never a stack trace
            # mask the home directory: the browser needs the reason, not the machine's layout
            text = html.escape(str(exc)).replace(os.path.expanduser("~"), "~")
            msg = text[:1200].encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return
        name = "الحرف-المقلوب-مُعبّأ.pdf"
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(pdf)))
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''%s" % urllib.parse.quote(name))
        self.send_header("X-Filename", urllib.parse.quote(name))
        self.end_headers()
        self.wfile.write(pdf)


def main() -> None:
    port = int(os.environ.get("FILL_PORT", "8765"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"fill surface: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
