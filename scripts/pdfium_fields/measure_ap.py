"""Read back the appearance streams PDFium generated, and hold them against
HarfBuzz and against a baseline build.

For each widget the `/AP /N` stream is parsed into the codes its `Tj`
operators show. The expected codes for an Arabic or mixed field are built by
shaping every bidi segment of the value with HarfBuzz — digits split the text
into segments, which is what the bidi algorithm does with them — and, for the
controls, the whole stream must be byte-identical to the baseline build.

Run:  .venv/bin/python scripts/pdfium_fields/measure_ap.py after.pdf \
          --source fixture.pdf --probe path/to/field_probe \
          --baseline before.pdf
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess

import pikepdf
import uharfbuzz as hb
from pikepdf import Name

ESCAPES = {
    ord("n"): b"\n", ord("r"): b"\r", ord("t"): b"\t", ord("b"): b"\b",
    ord("f"): b"\f", ord("("): b"(", ord(")"): b")", ord("\\"): b"\\",
}


def decode_pdf_string(raw: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(raw):
        byte = raw[i]
        if byte != 0x5C:  # backslash
            out.append(byte)
            i += 1
            continue
        i += 1
        if i >= len(raw):
            break
        escape = raw[i]
        if escape in ESCAPES:
            out += ESCAPES[escape]
            i += 1
        elif 0x30 <= escape <= 0x37:
            digits = bytearray()
            while i < len(raw) and len(digits) < 3 and 0x30 <= raw[i] <= 0x37:
                digits.append(raw[i])
                i += 1
            out.append(int(digits.decode(), 8) & 0xFF)
        else:
            out.append(escape)
            i += 1
    return bytes(out)


def shown_strings(content: bytes) -> list[bytes]:
    """The string operand of every `Tj`, decoded — literal or hexadecimal."""
    strings = []
    for match in re.finditer(rb"[)>]\s*Tj", content):
        end = match.start()
        if content[end] == 0x3E:  # '>' — a hexadecimal string
            start = content.rfind(b"<", 0, end)
            if start >= 0:
                strings.append(bytes.fromhex(content[start + 1:end].decode("ascii")))
            continue
        depth = 1
        i = end - 1
        while i >= 0 and depth:
            if content[i] == 0x29 and content[i - 1] != 0x5C:
                depth += 1
            elif content[i] == 0x28 and content[i - 1] != 0x5C:
                depth -= 1
            i -= 1
        strings.append(decode_pdf_string(content[i + 2:end]))
    return strings


def used_font(annot: pikepdf.Object, content: bytes) -> tuple[bytes | None, bool]:
    """The font the stream selects with `Tf`, and whether its codes are two bytes."""
    match = re.search(rb"/([A-Za-z0-9]+)\s+[\d.]+\s+Tf", content)
    if not match:
        return None, False
    fonts = annot.get("/AP", {}).get("/N", {}).get("/Resources", {}).get("/Font", {})
    ref = fonts.get("/" + match.group(1).decode())
    if ref is None or ref.get("/Subtype") != Name("/Type0"):
        return None, False
    descriptor = ref["/DescendantFonts"][0].get("/FontDescriptor")
    if descriptor is None or "/FontFile2" not in descriptor:
        return None, True
    return bytes(descriptor["/FontFile2"].read_bytes()), True


def shaped_glyphs(font_bytes: bytes, text: str) -> list[int]:
    face = hb.Face(font_bytes)
    font = hb.Font(face)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return [info.codepoint for info in buf.glyph_infos]


def expected_codes(font_bytes: bytes, value: str) -> list[int]:
    """HarfBuzz per bidi segment: digits split the text, everything else is one run."""
    codes: list[int] = []
    for segment in re.split(r"([0-9]+)", value):
        if segment:
            codes += shaped_glyphs(font_bytes, segment)
    return codes


def positions(content: bytes) -> list[float]:
    """The x each `Tj` is drawn at, following `Td` from the line matrix."""
    pen = [0.0, 0.0]
    xs = []
    for match in re.finditer(
            rb"(-?[\d.]+) (-?[\d.]+) (Td|Tm)|<([0-9A-Fa-f]+)>\s*Tj|\(([^)]*)\)\s*Tj",
            content):
        if match.group(3):
            if match.group(3) == b"Td":
                pen[0] += float(match.group(1))
                pen[1] += float(match.group(2))
            else:
                pen[0], pen[1] = float(match.group(1)), float(match.group(2))
        else:
            xs.append(round(pen[0], 2))
    return xs


def codes_of(strings: list[bytes], two_byte: bool) -> list[int]:
    joined = b"".join(strings)
    if two_byte:
        return [int.from_bytes(joined[i:i + 2], "big")
                for i in range(0, len(joined) - 1, 2)]
    return list(joined)


def streams(pdf: pikepdf.Pdf) -> dict[str, tuple[bytes, bytes | None, bool, str]]:
    """name -> (appearance bytes, font program, two-byte codes, field value)."""
    out = {}
    for annot in pdf.pages[0]["/Annots"]:
        stream = annot.get("/AP", {}).get("/N")
        content = bytes(stream.read_bytes()) if stream is not None else b""
        font_bytes, two_byte = used_font(annot, content)
        out[str(annot["/T"])] = (content, font_bytes, two_byte, str(annot["/V"]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=pathlib.Path)
    parser.add_argument("--probe", type=pathlib.Path)
    parser.add_argument("--source", type=pathlib.Path)
    parser.add_argument("--baseline", type=pathlib.Path,
                        help="a second run (another build) the controls must match")
    parser.add_argument("--expect", choices=["patch", "baseline"], default="patch",
                        help="what the shaped fields should look like")
    args = parser.parse_args()

    if args.probe:
        if not args.source:
            parser.error("--probe needs --source")
        subprocess.run([str(args.probe), str(args.source), str(args.pdf)], check=True)

    after = streams(pikepdf.open(args.pdf))
    before = streams(pikepdf.open(args.baseline)) if args.baseline else {}
    failures = []

    for name, (content, _, two_byte, _) in after.items():
        codes = codes_of(shown_strings(content), two_byte)
        print(f"{name:12s} tjs={len(shown_strings(content)):2d} codes={codes}")
        if args.expect == "patch" and two_byte and 0 in codes:
            failures.append(f"{name}: contains .notdef (CID 0)")

    # The shaped fields: every code, in order, must equal HarfBuzz on the same
    # font and text, segmented where the bidi algorithm splits on digits. The
    # baseline build must disagree — that disagreement is the defect.
    for name in ("ar", "mixed"):
        if name not in after or after[name][1] is None:
            failures.append(f"{name}: missing or not a Type0 field")
            continue
        want = expected_codes(after[name][1], after[name][3])
        got = codes_of(shown_strings(after[name][0]), True)
        print(f"{name:12s} expected={want}")
        if args.expect == "patch" and got != want:
            failures.append(f"{name}: {got} != harfbuzz {want}")
        if args.expect == "baseline":
            if got == want:
                failures.append(f"{name}: the baseline already shapes the run")
            elif name == "ar" and len(got) != 2:
                failures.append(f"{name}: expected one code per character before the patch, got {got}")

    # Placement: a run inside a left-to-right line must not push the text that
    # follows it, and a left-aligned field keeps its left edge.
    if args.expect == "patch" and "ltr_mixed" in after:
        xs = positions(after["ltr_mixed"][0])
        if any(b < a - 0.01 for a, b in zip(xs, xs[1:])):
            failures.append(f"ltr_mixed: the line runs backwards: {xs}")
        if before:
            tail_after = xs[-1]
            tail_before = positions(before["ltr_mixed"][0])[-1]
            if abs(tail_after - tail_before) > 1.0:
                failures.append(
                    f"ltr_mixed: the text after the run moved {tail_before} -> {tail_after}")
    if args.expect == "patch" and "q0" in after and before:
        left_after = min(positions(after["q0"][0]))
        left_before = min(positions(before["q0"][0]))
        if abs(left_after - left_before) > 1.0:
            failures.append(
                f"q0: the left margin moved {left_before} -> {left_after}")

    # The controls: a non-Identity CID font and a simple font must produce the
    # same bytes as the baseline build.
    if before:
        for name in ("latin", "nonidentity"):
            if before.get(name, (b"",))[0] != after.get(name, (b"",))[0]:
                failures.append(f"{name}: appearance changed against the baseline")

    for failure in failures:
        print("FAIL", failure)
    print("RESULT", "PASS" if not failures else "FAIL")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
