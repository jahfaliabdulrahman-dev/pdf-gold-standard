"""Hold the interactive editor's drawing against the appearance stream.

The editor (CPWL) draws a focused field itself; every other reader draws the
generated /AP. When the two disagree, a field looks right in one and wrong in
the other, so this stage renders both at 72 dpi and compares the ink they put on
the page: the horizontal extent of the ink. Two renderers put down different pixels for
the same glyphs, so the comparison is the span the ink occupies, not its shape.

Only fields whose value fits the editor's line are compared. The editor lays the
value out in a plate narrower than the field, so «الصفحة 5 من 10» wraps onto a
second line there while the appearance stream keeps it on one; that difference
is present before this change and is not what this stage measures.

The editor also draws a caret in the field it is editing; it sits inside the ink
the text already covers, so it does not move the span.

Run:  .venv/bin/python scripts/pdfium_fields/measure_editor.py fixture.pdf \
          --source after.pdf --pdfium-out ~/pdfium/pdfium/out/Release
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess

import numpy as np
import pymupdf

from measure_text import appearance_only

# field -> (click x, click y) that puts the caret in that field, in page points.
CLICKS = {
    "ar": (350.0, 710.0),
    "q0": (150.0, 310.0),
}

# field -> its rectangle on the page, and the offset an appearance stream's own
# origin has from that rectangle's corner.
FIELD_RECTS = {
    "ar": (260.0, 690.0, 560.0, 730.0),
    "q0": (140.0, 290.0, 560.0, 330.0),
}
AP_ORIGIN_INSET = 1.0
# The appearance-only page draws the form at this offset.
PAGE_INSET = 10.0

# How far the editor's ink may sit from the appearance stream's, in points.
MAX_INK_SHIFT = 2.5


def ink_extent(dark: np.ndarray) -> tuple[int, int]:
    """(first dark column, last dark column) of a boolean ink map."""
    columns = np.nonzero(dark.any(axis=0))[0]
    if len(columns) == 0:
        return (0, 0)
    return (int(columns.min()), int(columns.max()))


def editor_ink(fixture: pathlib.Path,
               out: pathlib.Path,
               click: tuple[float, float],
               field: str,
               probe: pathlib.Path) -> np.ndarray:
    bgra = out.with_suffix(".bgra")
    shown = subprocess.run(
        [str(probe), str(fixture), str(bgra), str(click[0]), str(click[1])],
        check=True, capture_output=True, text=True).stdout.strip()
    width, height = (int(v) for v in shown.split("=")[1].split("x"))
    data = np.frombuffer(bgra.read_bytes(), dtype=np.uint8).reshape(height, width, 4)
    grey = data[:, :, :3].min(axis=2)

    # Page y runs up from the bottom; the bitmap's rows run down from the top.
    left, bottom, right, top = FIELD_RECTS[field]
    rows = slice(height - int(top), height - int(bottom))
    return grey[rows, int(left):int(right)] < 200


def appearance_ink(ap_pdf: pathlib.Path) -> np.ndarray:
    pixmap = pymupdf.open(ap_pdf)[0].get_pixmap(dpi=72)
    data = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n)
    return data[:, :, :3].min(axis=2) < 200


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=pathlib.Path)
    parser.add_argument("--source", type=pathlib.Path, required=True,
                        help="the PDF whose generated appearances to compare")
    parser.add_argument("--pdfium-out", type=pathlib.Path, required=True)
    parser.add_argument("--work", type=pathlib.Path, default=None)
    args = parser.parse_args()

    editor_probe = args.pdfium_out / "form_render"
    if not editor_probe.exists():
        raise SystemExit(f"no form_render at {editor_probe}")
    work = args.work or args.fixture.parent
    work.mkdir(parents=True, exist_ok=True)

    failures = []
    for field, click in CLICKS.items():
        ap_pdf = work / f"{field}.appearance.pdf"
        appearance_only(args.source, field, ap_pdf)

        editor = editor_ink(args.fixture, work / f"{field}.editor.png", click, field,
                            editor_probe)
        appearance = appearance_ink(ap_pdf)
        left_e, right_e = ink_extent(editor)
        left_a, right_a = ink_extent(appearance)

        # Put both in the field's own coordinates: the editor's crop starts at the
        # field's left edge, the appearance page at PAGE_INSET.
        left_a = round(left_a - PAGE_INSET + AP_ORIGIN_INSET, 1)
        right_a = round(right_a - PAGE_INSET + AP_ORIGIN_INSET, 1)
        print(f"{field:4s} editor {left_e}..{right_e} | "
              f"appearance {left_a}..{right_a}")
        if abs(left_e - left_a) > MAX_INK_SHIFT or abs(right_e - right_a) > MAX_INK_SHIFT:
            failures.append(f"{field}: the ink moved between the editor and the AP "
                            f"({left_e}..{right_e} vs {left_a}..{right_a})")

    for failure in failures:
        print("FAIL", failure)
    print("RESULT", "PASS" if not failures else "FAIL")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
