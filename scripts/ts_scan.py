#!/usr/bin/env python3
"""Which documents carry text rise (`Ts`)?

Our post-processing model refuses a raised glyph ("outside the declared model"), so a document with `Ts` cannot
go through the shipping stages at all. WeasyPrint positions combining marks and superscripts with `Ts`; Chrome
and Typst do not in this corpus. This counts it per file, from the file itself.

Usage: python3 scripts/ts_scan.py /tmp/e3/weasyprint-r1
"""
import glob
import json
import os
import sys

import pikepdf


def count(path: str) -> int:
    n = 0
    with pikepdf.open(path) as pdf:
        for page in pdf.pages:
            for ins in pikepdf.parse_content_stream(page):
                if str(ins.operator) == "Ts":
                    n += 1
    return n


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "/tmp/e3/weasyprint-r1"
    files = sorted(f for f in glob.glob(os.path.join(root, "*.pdf")) if ".a3b." not in f)
    if not files:
        print(f"no PDFs in {root}")
        return 2
    counts = {os.path.basename(f)[:-4]: count(f) for f in files}
    refused = sorted(k for k, v in counts.items() if v)
    accepted = sorted(k for k, v in counts.items() if not v)
    print(f"{len(files)} files · with Ts: {len(refused)} · without: {len(accepted)}")
    print("refused:", ", ".join(refused) or "none")
    out = os.path.join(os.path.dirname(root.rstrip("/")), "ts-scan.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"root": root, "refused": refused, "accepted": accepted, "counts": counts}, fh,
                  ensure_ascii=False, indent=1)
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
