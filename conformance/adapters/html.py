"""case -> HTML. One template, uniform for every case and every engine that speaks HTML.

Every rule here that was chosen *because an engine misbehaves* is declared in `ENGINE_BEHAVIOURS` below, with
the case that reproduces the misbehaviour and the engine setting that shows it. `conformance/tests/
test_engine_behaviour.py` builds each declaration and asserts both halves: the defect appears where the table
says it appears, and the produced file does not carry it. A claim in this file with no witness is a bug.

Three decisions, all measured:

1. **A table at `width:auto`.** A table sized `width:100%` in a BARE fragment — no `@page`, no `line-height`, no
   body reset, which is what a customer hands over — makes Chrome paint the table as one run, and PDFium then
   returns its rows reversed (`خدمات ٢٠٠ رسوم ١٠٠`) with the heading shredded per glyph (3x2x2 measured: the
   conjunction is required; adding EITHER `@page` OR `line-height: 1.7` restores the order). `fix_text_layer`
   repairs it too. So the trigger is narrower than first written, the claim now names the conjunction, and
   `tbl-plain-fragment` is the case that reproduces it while `tbl-width-100` records the harmless twin.

2. **Tables do not repeat a header across a page break** (`thead { display: table-row-group }`). A repeated
   header is text the case declares once; a comparison against the truth would count it as invented content
   and punish an engine for a typographic convention. The case `tbl-page-break` measures whether the rows
   continue in order. This rule is a measurement decision, not a defect workaround, and `tbl-no-page-box`
   proves the header display is not what breaks the layer.

3. **Bold is real, never synthesised.** Both weights of each family are declared (@font-face 400 and 700), so a
   block marked `"bold": true` gets the real face. A synthesised bold is printed as a Type3 font whose glyphs
   carry no descriptor and whose ToUnicode can name presentation forms (measured earlier: three Type3 fonts and
   9 presentation forms on a two-row table). `test_engine_behaviour.py` asserts no Type3 font in a bold case.

The only styling input a case may carry is `align: justify` on a paragraph (justification is where an engine
adds kashida that is not in the source — `kash-justify`), `bold` on a block, and `page_box: false` on a case
(the HTML a customer writes when they hand over a plain fragment with no page declaration).
"""
import html as htmllib
import re
import unicodedata

from ..corpus.truth import arabic_indic
from . import fonts

# Each row: what the template does about an engine behaviour, the case that reproduces the behaviour, and how.
# `engine` names the setting in which the defect must appear; `expect` is what must be true of the produced file.
ENGINE_BEHAVIOURS = [
    {
        "id": "table-width-without-page-box",
        "rule": "table { width: auto } and a declared @page",
        "claim": "a width:100% table in a bare fragment (no @page, no line-height) makes Chrome paint it as one "
                 "run and PDFium return its rows reversed",
        "case": "tbl-plain-fragment",
        "engine": "chrome-raw",
        "expect": "the case's rows are NOT in reading order",
    },
    {
        "id": "table-width-with-page-box",
        "rule": "table { width: auto }",
        "claim": "in the template (declared page box + line-height), width:100% is harmless — same shape, in order",
        "case": "tbl-width-100",
        "engine": "chrome-raw",
        "expect": "the case's rows ARE in reading order",
    },
    {
        "id": "empty-cell-dropped",
        "rule": "an empty cell is written as one `&#160;`, never as `<td></td>`",
        "claim": "a cell with no content is dropped from the structure tree; the table's rows lose a column and "
                 "veraPDF UA-1 fails 7.2-43",
        "case": "tbl-empty-cell",
        "engine": "chrome",
        "expect": "rows lose a cell when the producer writes no space",
    },
    {
        "id": "identifier-own-line",
        "rule": "a composite identifier after Arabic starts on its own display line (`<br>`)",
        "claim": "the same text inline is read `-2026-0042INV` by PDFium and `0042-2026-INV` by PDFKit; the "
                 "line break makes both exact 1.0 and leaves the logical text (and the floors) unchanged",
        "case": "num-invoice-latn",
        "engine": "chrome",
        "expect": "the identifier is not in reading order when the break is absent",
    },
    {
        "id": "no-synthetic-bold",
        "rule": "both real weights declared per family",
        "claim": "a block asked for bold is set in the real 700 face, so no Type3 font appears",
        "case": "bld-word",
        "engine": "chrome",
        "expect": "no Type3 font in the file",
    },
]


def esc(text: str) -> str:
    return htmllib.escape(str(text), quote=True)


def _cls(block: dict, extra: str = "") -> str:
    parts = [p for p in (extra, "b" if block.get("bold") else "") if p]
    return f' class="{" ".join(parts)}"' if parts else ""


# ---- money, and why it is isolated ---------------------------------------------------------------
# Incident #157375: in an RTL paragraph or cell, the minus sign of `-6,006.965` takes the run's direction and
# the amount prints as `6,006.965-`. The digits themselves are fine — UAX#9 gives a number LTR direction — but a
# LEADING SIGN in an RTL run does not inherit it. So the amount is isolated as one LTR run and the sign becomes
# its leftmost character, in display and in every reader. Owner decision, 19 Nov 2026: the sign goes on the
# left (`-6,006.965`); acceptance is a PASS certificate on `mon-negative-table` and `mon-negative-hindi` and the
# sign on the left on the page. Isolation applies to (a) a cell that is nothing but an amount and (b) an inline
# token that begins with a sign — the two places the defect exists; a bare positive number is already LTR.
_AMOUNT = r"[0-9\u0660-\u0669\u06f0-\u06f9][0-9\u0660-\u0669\u06f0-\u06f9,./%\u066b\u066c]*"
# A composite identifier — the owner's invoice/IBAN class — is either an UPPERCASE **hyphen-separated** token with
# a digit (`INV-2026-0042`) or an IBAN-like uppercase prefix with six or more digits (`SA0380…`). The hyphen (not
# slash) is required: `PDF/UA-1` and `PDF/A-3` are standard names, not identifiers, and must not take a line of
# their own (measured: the slash form matched them in `mix-acronym`). In an RTL paragraph the readers reorder the
# identifier (PDFium `-2026-0042INV`, PDFKit `0042-2026-INV`); isolation in the source (`bdi`/`span`/LRM) did not
# fix both. The producer starts it on its own display line (a `<br>` before it) while the case's logical text stays
# the source text — both tier-1 readers exact 1.0, and the line break is whitespace to `metrics.N`, so the truth
# and the other readers' floors are unchanged. Lowercase versions (`v2.3.6`, `mix-version`) and pure digits
# (VAT/CR/phone) are NOT matched: they read correctly and a break changes a case that was never broken (measured:
# mix-version digit_runs 0.67 -> 0.33 with the broad form).
_IDENT = re.compile(r"(?<![A-Za-z0-9/-])(?=[A-Z0-9-]*\d)(?:[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+|[A-Z]{2}\d{6,})"
                    r"(?![A-Za-z0-9/-])")
_INLINE = re.compile(rf"(?P<sign>(?<![^\s(])[-−]\s?{_AMOUNT})|(?P<ident>{_IDENT.pattern})")
_ARABIC = re.compile(r"[\u0600-\u06FF]")
# Only a NEGATIVE amount is isolated: a positive number already reads left-to-right (UAX#9 gives digits
# EN direction), so isolating it changes a case that was never broken — measured on `dig-phone`, whose `+966`
# lost word_f1 1.0 -> 0.875 the moment it was wrapped.
_CELL_AMOUNT = re.compile(r"^\s*[-\u2212]\s?" + _AMOUNT + r"\s*$|^\s*" + _AMOUNT + r"\s*$")


def _ltr(inner: str) -> str:
    """One isolated LTR run (`bdi` + `unicode-bidi:isolate`)."""
    return f'<bdi dir="ltr" style="unicode-bidi:isolate">{inner}</bdi>' 


def _inline(text: str) -> str:
    """Escape a paragraph, isolating a signed amount and starting a composite identifier on its own line."""
    out, last = [], 0
    for m in _INLINE.finditer(text):
        prefix = text[last:m.start()]
        out.append(esc(prefix))
        if m.group("ident") is not None and _ARABIC.search(prefix):
            out.append("<br>")
        out.append(_ltr(esc(m.group(0))))
        last = m.end()
    out.append(esc(text[last:]))
    return "".join(out)


def _cell(text: str) -> str:
    """A table cell: an empty one keeps its cell with ONE non-breaking space.

    Chrome drops a `<td></td>` with no content from the structure tree (measured: the table's rows become
    3,2,2 and veraPDF UA-1 fails 7.2-43 "rows span different number of columns"). U+00A0 is whitespace:
    `metrics.N` collapses it, so it adds no word, and the grader still sees three cells. A cell holding only
    spaces or only format characters (RLM/LRM/ZWSP/ZWNJ/ZWJ/WJ) loses its `/TD` the same way, so the test is
    "no character of substance", not `text.strip()`.
    """
    if _no_substance(text):
        return "&#160;"
    if _CELL_AMOUNT.match(text) and re.match(r"^\s*[-\u2212]", text):
        return _ltr(esc(text.strip()))
    return _inline(text)


def _no_substance(text: str) -> bool:
    """True when every character is whitespace, a format control, or a control char (nothing a reader shows)."""
    return all(unicodedata.category(ch) in ("Zs", "Zl", "Zp", "Cf", "Cc") for ch in text)


def render(case: dict) -> str:
    body = []
    for block in case["blocks"]:
        kind = block["type"]
        if kind == "heading":
            level = block["level"]
            body.append(f"<h{level}{_cls(block)}>{esc(block['text'])}</h{level}>")
        elif kind == "paragraph":
            body.append(f"<p{_cls(block, 'j' if block.get('align') == 'justify' else '')}>"
                        f"{_inline(block['text'])}</p>")
        elif kind == "list":
            tag = "ol" if block["ordered"] else "ul"
            items = "".join(f"<li>{_inline(i)}</li>" for i in block["items"])
            body.append(f"<{tag}>{items}</{tag}>")
        elif kind == "table":
            header = block["header"]
            rows = [header] if header and not isinstance(header[0], list) else list(header)
            attr = ' class="b"' if block.get("bold") else ""
            head = "".join("<tr>" + "".join(f"<th{attr}>{_cell(c)}</th>" for c in r) + "</tr>" for r in rows)
            body_rows = "".join("<tr>" + "".join(f"<td>{_cell(c)}</td>" for c in r) + "</tr>"
                                for r in block["rows"])
            style = f' style="width: {esc(block["width"])}"' if block.get("width") else ""
            body.append(f"<table{style}><thead>{head}</thead><tbody>{body_rows}</tbody></table>")
    return template(case, "\n".join(body))


def template(case: dict, body: str) -> str:
    stack = fonts.font_stack(case["font"])
    plain = bool(case.get("plain"))
    page = "" if plain else "@page { size: A4; margin: 20mm; }\n"
    reset = "" if plain else "html, body { margin: 0; padding: 0; }\n"
    leading = "" if plain else "line-height: 1.7;\n"
    return f"""<!doctype html>
<html lang="{case['lang']}" dir="rtl"><head><meta charset="utf-8">
<title>{esc(case['id'])}</title>
<style>
{fonts.font_face_css(case['font'])}
{fonts.fallback_css()}
{page}{reset}body {{ font-family: {stack}; font-size: 12pt; {leading}color: #000; }}
h1 {{ font-size: 20pt; font-weight: 400; margin: 0 0 8pt; }}
h2 {{ font-size: 16pt; font-weight: 400; margin: 6pt 0 6pt; }}
h3 {{ font-size: 13pt; font-weight: 400; margin: 6pt 0 4pt; }}
h4, h5, h6 {{ font-size: 12pt; font-weight: 400; margin: 4pt 0; }}
p {{ margin: 0 0 6pt; }}
p.j {{ text-align: justify; }}
/* A block marked `bold` gets the family's real 700 face — the weights are declared above, so this is not a
   synthesised bold and produces no Type3 font (asserted by test_engine_behaviour.py on `bld-word`). */
.b, b, strong {{ font-weight: 700; }}
table {{ border-collapse: collapse; width: auto; margin: 6pt 0; }}
thead {{ display: table-row-group; }}
th, td {{ border: 0.5pt solid #000; padding: 3pt; text-align: right; vertical-align: top; }}
ol {{ list-style-type: arabic-indic; margin: 0 0 6pt; padding-inline-start: 2.2em; }}
ul {{ list-style-type: disc; margin: 0 0 6pt; padding-inline-start: 1.6em; }}
li {{ margin: 0 0 2pt; }}
</style></head>
<body>
{body}
</body></html>
"""


def outline(case: dict) -> list[tuple[int, str]]:
    """(level, title) for every heading, in reading order — the outline the case declares."""
    return [(b["level"], b["text"]) for b in case["blocks"] if b["type"] == "heading"]


__all__ = ["render", "outline", "esc", "arabic_indic", "ENGINE_BEHAVIOURS"]
