"""truth(case) — the text a case declares, in logical (reading) order.

One function, one input: the case file. No PDF is opened here, and no reader's output is ever copied into
a truth "to make it agree" — that is the assignment's hard rule, and it is also the only way the metrics
mean anything: a truth derived from a reader measures agreement between readers, not fidelity to the source.

The order is the reading order of the source:
  · headings and paragraphs in the order they are declared;
  · a table row by row, header rows first, cells in logical order (the FIRST cell is the rightmost in RTL —
    that is the order the source declares, and the order a reader must reproduce);
  · a list item by item, with its marker for an ordered list: the marker is drawn by the engine, so it is
    text the file contains. It is derived here from the item's index (Arabic-Indic digit + «.»), never read
    from a PDF. If an engine writes the marker in another form, the metric says so — that is a result.

Blocks are joined by a newline; `metrics.N` collapses whitespace, so the join character is not load-bearing.
"""
import unicodedata

ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"


def arabic_indic(n: int) -> str:
    """1 -> «١». Above 99 the digits concatenate, which is how the numeral is written."""
    return "".join(ARABIC_INDIC[int(d)] for d in str(n))


def truth(case: dict) -> str:
    lines: list[str] = []
    for block in case["blocks"]:
        kind = block["type"]
        if kind in ("heading", "paragraph"):
            lines.append(block["text"])
        elif kind == "list":
            for i, item in enumerate(block["items"], 1):
                lines.append(f"{arabic_indic(i)}. {item}" if block["ordered"] else item)
        elif kind == "table":
            header = block["header"]
            rows = ([header] if header and not isinstance(header[0], list) else list(header)) + list(block["rows"])
            for row in rows:
                lines.extend(str(cell) for cell in row)
        else:                                    # unreachable: cases.validate refuses unknown types
            raise ValueError(f"case {case.get('id')}: block type {kind!r} has no truth rule")
    return unicodedata.normalize("NFC", "\n".join(lines))


def truth_words(case: dict) -> list[str]:
    """The truth as words, for the order/token metrics — the whitespace of a cell break is not a word."""
    return truth(case).split()
