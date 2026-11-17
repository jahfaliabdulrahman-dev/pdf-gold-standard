"""Render the two generated appearances with an engine that only reads /AP.

PDFium's own on-screen form filler draws text fields itself and ignores the
generated appearance, so pdfium_test cannot show the difference. This turns
each file into a plain page whose only content is one field's /AP form
XObject, and renders it with MuPDF — the same stream a reader gets, drawn by a
different engine.

Run:  .venv/bin/python scripts/pdfium_fields/render_ap.py before.pdf after.pdf out
"""

from __future__ import annotations

import argparse
import pathlib

import pikepdf
import pymupdf
from pikepdf import Dictionary, Name


def only_appearance(source: pathlib.Path, field: str, target: pathlib.Path,
                    normalize_subtype: bool) -> float:
    """Rewrite `source` so its page draws only the field's appearance.

    Returns the appearance's width in points, for the right-margin check.
    """
    pdf = pikepdf.open(source)
    page = pdf.pages[0]
    for annot in page["/Annots"]:
        if str(annot["/T"]) != field:
            continue
        stream = annot["/AP"]["/N"]
        bbox = [float(v) for v in stream["/BBox"]]
        if normalize_subtype and "/Subtype" not in stream:
            # The baseline build writes an appearance without /Subtype /Form,
            # which strict readers reject. Adding it here makes the two shapes
            # comparable; the difference in the codes is what is being measured.
            stream["/Subtype"] = Name("/Form")
        xobjects = Dictionary()
        xobjects[Name("/Fm0")] = stream
        resources = Dictionary()
        resources[Name("/XObject")] = xobjects
        page["/Resources"] = resources
        page["/Contents"] = pdf.make_stream(b"q 1 0 0 1 10 10 cm /Fm0 Do Q")
        del page["/Annots"]
        pdf.save(target)
        return bbox[2] - bbox[0]
    raise SystemExit(f"field {field} not found in {source}")


def ink(image: pymupdf.Pixmap) -> tuple[int, int, tuple[int, int, int, int]]:
    """Ink pixels, separate ink shapes (4-connected), and the ink box."""
    samples, stride = image.samples, image.stride
    width, height = image.width, image.height
    grid = [[False] * width for _ in range(height)]
    count = 0
    for y in range(height):
        row = samples[y * stride:y * stride + width * 3]
        line = grid[y]
        for x in range(width):
            if min(row[3 * x], row[3 * x + 1], row[3 * x + 2]) < 200:
                line[x] = True
                count += 1

    min_x, max_x, min_y, max_y = width, -1, height, -1
    for y in range(height):
        for x in range(width):
            if grid[y][x]:
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
    shapes = 0
    for y in range(height):
        for x in range(width):
            if not grid[y][x]:
                continue
            shapes += 1
            stack = [(y, x)]
            grid[y][x] = False
            while stack:
                cy, cx = stack.pop()
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < height and 0 <= nx < width and grid[ny][nx]:
                        grid[ny][nx] = False
                        stack.append((ny, nx))
    return count, shapes, (min_x, min_y, max_x, max_y)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=pathlib.Path)
    parser.add_argument("after", type=pathlib.Path)
    parser.add_argument("out", type=pathlib.Path)
    parser.add_argument("--field", default="ar")
    parser.add_argument("--normalize-subtype", action="store_true")
    parser.add_argument("--no-margin-check", action="store_true",
                        help="for fields that are not right-aligned")
    parser.add_argument("--center-check", action="store_true",
                        help="the ink has to stay centred, for a centred field")
    args = parser.parse_args()

    results = {}
    for side, source in (("before", args.before), ("after", args.after)):
        page_pdf = args.out.with_name(f"{args.out.name}-{side}.pdf")
        width_pt = only_appearance(source, args.field, page_pdf,
                                   args.normalize_subtype)
        doc = pymupdf.open(page_pdf)
        page = doc[0]
        pix = page.get_pixmap(dpi=300, clip=page.rect)
        count, shapes, box = ink(pix)
        results[side] = (count, shapes, pix, box, width_pt)
        pix.save(args.out.with_name(f"{args.out.name}-{side}.png"))
        print(f"{side:6s} ink={count:6d} shapes={shapes} ink_right={box[2]}")

    # The appearance is drawn at x = 10 pt inside a page as wide as the
    # appearance itself plus 20 pt, so the right margin sits at
    # (10 + width) * dpi / 72 pixels. A shaped run that drifts off that margin
    # is a misplacement, not a shaping difference.
    scale = 300 / 72.0
    expected_right = (10 + results["after"][4]) * scale
    margin_ok = True
    for side in ("before", "after") if not args.no_margin_check else ():
        drift = abs(results[side][3][2] - expected_right)
        print(f"{side:6s} right margin drift {drift:.1f} px")
        if drift > 0.02 * results[side][4] * scale:
            margin_ok = False
            print(f"FAIL {side}: the text is not anchored at the right margin")
    same = results["before"][2].samples == results["after"][2].samples
    print("identical" if same else "different")
    center_ok = True
    if args.center_check:
        before_box = results["before"][3]
        after_box = results["after"][3]
        before_center = (before_box[0] + before_box[2]) / 2.0
        after_center = (after_box[0] + after_box[2]) / 2.0
        drift = abs(after_center - before_center)
        print(f"ink centre {before_center:.1f} -> {after_center:.1f} "
              f"(drift {drift:.1f} px)")
        center_ok = drift <= 0.01 * results["after"][2].width
    ok = (center_ok and margin_ok and not same and results["after"][0] > 0
          and results["after"][1] < results["before"][1])
    if args.field == "ar":
        # «لا» is two disconnected strokes before shaping and one ligature after.
        ok = ok and results["before"][1] == 2 and results["after"][1] == 1
    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
