"""The one ToUnicode CMap parser — shared by the writer (`scripts/fix_text_layer.py`) and the checker
(`conformance/checks/mcid_text.py`).

It was extracted from the writer so the checker no longer puts `scripts/` on `sys.path`, and so the
`CMapError`/`parse_tu_report` contract has one home. The parser reads `beginbfchar`/`beginbfrange` with
comments, multi-line arrays, multiple ranges on a line and multi-unit destinations; a failure is named,
never `{}`. ISO 32000-1 §9.10.3 is the law; Adobe TN #5014 is the overlap note.
"""
import re
import struct

class CMapError(ValueError):
    """A ToUnicode CMap that cannot be read completely — refused by name, never folded to `{}`."""


_WS = " \t\r\n\f\x00"
_DELIMS = "()<>[]{}/%"


def _literal(data: str, i: int, problems: list[str]) -> tuple[bytes, int, bool]:
    """A PDF literal string, parsed so its parentheses never become operators (the CMap header has `(Adobe)`)."""
    out, depth, fatal = bytearray(), 1, False
    i += 1
    escapes = {"n": 10, "r": 13, "t": 9, "b": 8, "f": 12}
    while i < len(data):
        ch = data[i]
        if ch == "\\":
            i += 1
            if i >= len(data):
                break
            e = data[i]
            if e in escapes:
                out.append(escapes[e])
                i += 1
            elif e in "()\\":
                out.append(ord(e))
                i += 1
            elif e in "\r\n":
                if e == "\r" and i + 1 < len(data) and data[i + 1] == "\n":
                    i += 1
                i += 1
            elif e.isdigit() and e in "01234567":
                digits = ""
                for _ in range(3):
                    if i < len(data) and data[i] in "01234567":
                        digits += data[i]
                        i += 1
                    else:
                        break
                out.append(int(digits or "0", 8) & 0xFF)
            else:
                out.append(ord(e) & 0xFF)
                i += 1
        elif ch == "(":
            depth += 1
            out.append(ord(ch))
            i += 1
        elif ch == ")":
            depth -= 1
            i += 1
            if depth == 0:
                return bytes(out), i, fatal
            out.append(ord(ch))
        else:
            out.append(ord(ch) & 0xFF)
            i += 1
    problems.append("unterminated literal string")
    return bytes(out), i, True


def _tokens(data: str) -> tuple[list[tuple[str, object]], list[str], bool]:
    """The CMap token stream: hex strings, names, numbers, literals, and the operators between them.

    Comments (`%` to end of line), `<<`/`>>`, `[]`, `{}` and literal strings are consumed so the CMap header
    — `/CIDSystemInfo << /Registry (Adobe) … >> def` — never reaches the bfchar/bfrange reader as junk.
    A token that cannot be consumed is a named problem and `fatal=True`; a malformed range is not thrown as
    an exception here, because the caller must be able to report it.
    """
    tokens: list[tuple[str, object]] = []
    problems: list[str] = []
    fatal = False
    i, n = 0, len(data)
    while i < n:
        ch = data[i]
        if ch in _WS:
            i += 1
            continue
        if ch == "%":
            j = data.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if data.startswith("<<", i):
            tokens.append(("<<", "<<")); i += 2; continue
        if data.startswith(">>", i):
            tokens.append((">>", ">>")); i += 2; continue
        if ch == "<":
            j = data.find(">", i + 1)
            if j < 0:
                problems.append("unterminated hex string")
                fatal = True
                break
            digits = re.sub(r"\s+", "", data[i + 1:j])
            if not re.fullmatch(r"[0-9A-Fa-f]*", digits):
                problems.append(f"malformed hex string <{digits[:24]}>")
                fatal = True
                i = j + 1
                continue
            if len(digits) % 2:
                problems.append("odd-length hex string — padded with 0 (ISO 32000-1 §7.3.4.3)")
                digits += "0"
            tokens.append(("hex", bytes.fromhex(digits)))
            i = j + 1
            continue
        if ch == "[":
            tokens.append(("[", "[")); i += 1; continue
        if ch == "]":
            tokens.append(("]", "]")); i += 1; continue
        if ch == "{":
            tokens.append(("{", "{")); i += 1; continue
        if ch == "}":
            tokens.append(("}", "}")); i += 1; continue
        if ch == "(":
            raw, i, bad = _literal(data, i, problems)
            tokens.append(("literal", raw))
            fatal = fatal or bad
            continue
        if ch == "/":
            j = i + 1
            while j < n and data[j] not in _WS and data[j] not in _DELIMS:
                j += 1
            tokens.append(("name", data[i:j])); i = j; continue
        if ch.isdigit() or (ch in "+-." and i + 1 < n and (data[i + 1].isdigit() or data[i + 1] == ".")):
            m = re.match(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)", data[i:])
            if m:
                text = m.group(0)
                tokens.append(("num", float(text) if "." in text else int(text)))
                i += len(text)
                continue
        j = i + 1
        while j < n and data[j] not in _WS and data[j] not in _DELIMS:
            j += 1
        tokens.append(("op", data[i:j]))
        i = j
    return tokens, problems, fatal


def _utf16(raw: bytes, problems: list[str], where: str) -> str | None:
    """Decode a destination string as UTF-16BE; a bad destination is named, never silently dropped."""
    if not raw:
        problems.append(f"{where}: empty destination string")
        return None
    if len(raw) % 2:
        problems.append(f"{where}: odd-length UTF-16BE destination ({len(raw)} bytes)")
        return None
    try:
        return raw.decode("utf-16-be", errors="surrogatepass")
    except UnicodeDecodeError as exc:
        problems.append(f"{where}: destination is not valid UTF-16BE ({exc.reason})")
        return None


def _unit_increment(raw: bytes, k: int, problems: list[str], where: str) -> str | None:
    """Increment the LAST UTF-16 code unit by k (ISO 32000-1 §9.10.3's range rule, unit form).

    The clause increments the last byte and requires that byte to stay ≤ 255 − (src2 − src1); under that
    constraint the last byte and the last unit agree. The unit form is used here because it also gives a
    defined answer for the two out-of-spec shapes the audit sends (`<0000> <FFFF>` and the four-byte bomb):
    a carry beyond 0xFFFF is named, not wrapped into a broken surrogate.
    """
    if not raw or len(raw) % 2:
        problems.append(f"{where}: invalid destination string")
        return None
    units = list(struct.unpack(f">{len(raw) // 2}H", raw))
    last = units[-1] + k
    if last > 0xFFFF:
        problems.append(f"{where}: the last UTF-16 unit overflows at k={k} — mapping stops there")
        return None
    units[-1] = last
    try:
        return struct.pack(f">{len(units)}H", *units).decode("utf-16-be", errors="surrogatepass")
    except UnicodeDecodeError as exc:
        problems.append(f"{where}: incremented destination is not valid UTF-16BE ({exc.reason})")
        return None


def parse_tu_report(data: str) -> dict:
    """Parse a ToUnicode CMap into `{map, problems, unparsable, capped, src_widths, codespace_widths}`.

    This is the one parser. `parse_tu` is the strict wrapper the writer uses; `mcid_text` uses the report so a
    failed parse becomes a named signal instead of a silent `{}`. The reader follows the bfchar/bfrange syntax
    of ISO 32000-1 §9.10.3 and Adobe TN #5014: comments, multi-line arrays, multiple entries/ranges on one
    line, multi-code-unit destinations with the last unit incremented, and a per-range cap of 65,536 codes.
    """
    tokens, problems, fatal = _tokens(data)
    mapping: dict[int, str] = {}
    capped = 0
    src_widths: set[int] = set()
    codespace_widths: set[int] = set()
    overlaps = 0
    surrogate_hits = 0
    i = 0

    def _count_surrogates(text: str) -> None:
        nonlocal surrogate_hits
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
            surrogate_hits += 1

    def add(src: bytes, dst: bytes, where: str) -> bool:
        if not src:
            problems.append(f"{where}: empty source code")
            return False
        src_widths.add(len(src))
        code = int.from_bytes(src, "big")
        text = _utf16(dst, problems, where)
        if text is None:
            # A destination that cannot be decoded leaves a HOLE in the map. The old caller replaced the whole
            # map with {}; this parser keeps the valid entries, but the writer must not rewrite a layer from a
            # map it knows is short — so the hole is fatal, named, and the strict wrapper refuses.
            nonlocal fatal
            fatal = True
            return False
        _count_surrogates(text)
        if code in mapping and mapping[code] != text:
            nonlocal overlaps
            overlaps += 1
        mapping[code] = text
        return True

    while i < len(tokens):
        kind, value = tokens[i]
        if kind == "op" and value == "begincodespacerange":
            j = i + 1
            widths = []
            while j < len(tokens) and not (tokens[j] == ("op", "endcodespacerange")):
                if tokens[j][0] == "hex":
                    widths.append(len(tokens[j][1]))
                j += 1
            if j >= len(tokens):
                problems.append("missing endcodespacerange"); fatal = True
            else:
                if len(widths) != 2:
                    problems.append(f"codespace range carries {len(widths)} hex strings, not 2"); fatal = True
                elif widths[0] != widths[1]:
                    problems.append(f"codespace range widths differ ({widths[0]} and {widths[1]} bytes)"); fatal = True
                else:
                    codespace_widths.add(widths[0])
                j += 1
            i = j
            continue
        if kind == "op" and value in ("usecmap",) or (kind == "name" and value == "/UseCMap"):
            # The inherited map lives in another stream this parser does not open. Marking the map incomplete
            # is honest; silently returning only the local entries would lose every inherited code.
            problems.append("usecmap is declared; the inherited map is not resolved")
            fatal = True
            i += 1
            continue
        if not (kind == "op" and value in ("beginbfchar", "beginbfrange")):
            i += 1
            continue
        end = "endbfchar" if value == "beginbfchar" else "endbfrange"
        count = tokens[i - 1][1] if i > 0 and tokens[i - 1][0] == "num" else None
        if count is not None and not isinstance(count, int):
            count = None
        j = i + 1
        entries = 0
        closed = False
        while j < len(tokens):
            if tokens[j] == ("op", end):
                closed = True
                break
            if value == "beginbfchar":
                if tokens[j][0] != "hex":
                    problems.append(f"bfchar entry is {tokens[j][0]}, not a source hex string")
                    fatal = True
                    break
                src = tokens[j][1]
                j += 1
                if j >= len(tokens) or tokens[j][0] != "hex":
                    problems.append("bfchar source has no destination hex string")
                    fatal = True
                    break
                if add(src, tokens[j][1], f"bfchar {int.from_bytes(src, 'big'):04X}"):
                    entries += 1
                j += 1
            else:
                if tokens[j][0] != "hex":
                    problems.append(f"bfrange start is {tokens[j][0]}, not a hex string"); fatal = True; break
                lo = tokens[j][1]; j += 1
                if j >= len(tokens) or tokens[j][0] != "hex":
                    problems.append("bfrange start has no end hex string"); fatal = True; break
                hi = tokens[j][1]; j += 1
                if not lo or not hi:
                    problems.append("bfrange has an empty source bound"); fatal = True; break
                lo_i, hi_i = int.from_bytes(lo, "big"), int.from_bytes(hi, "big")
                if len(lo) != len(hi):
                    problems.append(f"bfrange bounds differ in width ({len(lo)} and {len(hi)} bytes)"); fatal = True; break
                if hi_i < lo_i:
                    problems.append(f"bfrange is reversed ({lo_i:04X} > {hi_i:04X})"); fatal = True; break
                width = hi_i - lo_i + 1
                if width > 65536:
                    problems.append(f"bfrange {lo_i:04X}-{hi_i:04X} is {width} codes; capped at 65,536")
                    capped += 1
                    width = 65536
                if tokens[j][0] == "[":
                    j += 1
                    dests = []
                    while j < len(tokens) and tokens[j][0] != "]":
                        if tokens[j][0] != "hex":
                            problems.append("bfrange array carries a non-hex destination"); fatal = True; break
                        dests.append(tokens[j][1]); j += 1
                    if j >= len(tokens) or tokens[j][0] != "]":
                        problems.append("bfrange array is not closed"); fatal = True; break
                    j += 1
                    if len(dests) != width:
                        problems.append(f"bfrange array has {len(dests)} destinations for {width} codes")
                        if len(dests) < width:
                            fatal = True
                    for k, dst in enumerate(dests[:width]):
                        src = (lo_i + k).to_bytes(len(lo), "big")
                        add(src, dst, f"bfrange {lo_i + k:04X}")
                    entries += 1
                else:
                    if tokens[j][0] != "hex":
                        problems.append(f"bfrange destination is {tokens[j][0]}, not a hex string"); fatal = True; break
                    dst = tokens[j][1]; j += 1
                    if width > 256:
                        problems.append(f"bfrange {lo_i:04X}-{hi_i:04X} is wider than 256 codes; "
                                        "last-byte increment is undefined (unit increment used)")
                    for k in range(width):
                        text = _unit_increment(dst, k, problems, f"bfrange {lo_i + k:04X}")
                        if text is None:
                            break
                        _count_surrogates(text)
                        src = (lo_i + k).to_bytes(len(lo), "big")
                        src_widths.add(len(src))
                        if (lo_i + k) in mapping and mapping[lo_i + k] != text:
                            overlaps += 1
                        mapping[lo_i + k] = text
                    entries += 1
            if fatal:
                break
        if not closed and not fatal:
            problems.append(f"missing {end}"); fatal = True
        if count is not None and count != entries:
            problems.append(f"{value}: count says {count}, read {entries} entries")
        if closed:
            i = j + 1
        else:
            i = j
    if overlaps:
        problems.append(f"{overlaps} overlapping mapping(s): the later entry supersedes (TN #5014)")
    if surrogate_hits:
        problems.append(f"{surrogate_hits} destination(s) contain a lone UTF-16 surrogate — "
                        "not a Unicode scalar (the code is mapped, and the writer must refuse it)")
    return {"map": mapping, "problems": problems, "unparsable": bool(fatal), "capped": capped,
            "src_widths": sorted(src_widths), "codespace_widths": sorted(codespace_widths)}


def parse_tu(data: str) -> dict[int, str]:
    """The strict wrapper: the map, or a named `CMapError` — never `{}` for a stream that did not parse."""
    report = parse_tu_report(data)
    if report["unparsable"]:
        raise CMapError("; ".join(report["problems"][:4]) or "unparsable ToUnicode CMap")
    return report["map"]


def write_tu(m):
    items, out = sorted(m.items()), []
    for i in range(0, len(items), 100):
        chunk = items[i:i + 100]
        out.append(f"{len(chunk)} beginbfchar\n" + "\n".join(
            f"<{c:04X}> <{s.encode('utf-16-be').hex().upper()}>" for c, s in chunk) + "\nendbfchar")
    return ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n/CIDSystemInfo\n<< /Registry (Adobe)\n"
            "/Ordering (UCS)\n/Supplement 0\n>> def\n/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n" + "\n".join(out) +
            "\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend").encode()
