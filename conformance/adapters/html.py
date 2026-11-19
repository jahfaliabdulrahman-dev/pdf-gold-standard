"""case -> HTML. One template, uniform for every case and every engine that speaks HTML.

Two decisions, both measured rather than stylistic:

1. **Tables do not repeat a header across a page break** (`thead { display: table-row-group }`). A repeated
   header is text the case declares once; a comparison against the truth would count it as invented content
   and punish an engine for a typographic convention. Header repetition is a separate question and is not
   measured here — the case `tbl-page-break` measures whether the rows continue in order.

2. **Tables are laid out at their natural width (`width: auto`), never 100%.** Measured on CfT 157: an
   explicitly sized table (`width:100%`, `90%`, `min-width:100%`, `table-layout:fixed`) makes Chrome paint the
   whole table as ONE text run, and PDFium then returns its rows in reverse order (`خدمات ٢٠٠ رسوم ١٠٠` for
   rows 1 and 2), on a page that renders perfectly. With `width:auto` the same table yields the correct
   order. The corpus is measuring content shapes, not a CSS property — so the template uses the form whose
   text layer is sound, and the finding is recorded in `docs/conformance/metrics.md` as an engine behaviour
   the certificate cannot see (the file renders correctly and the structure tree is in order).
2. **No synthetic bold.** The corpus ships one weight per family, so a heading is told apart by size and by
   its tag. A synthesised face is an engine artifact that changes the glyph outline (and sometimes the text
   layer), and the corpus is not measuring bold.

The only styling input a case may carry is `align: justify` on a paragraph — justification is where an
engine adds kashida that is not in the source, which is a case of its own (`kash-justify`).
"""
import html as htmllib

from ..corpus.truth import arabic_indic
from . import fonts


def esc(text: str) -> str:
    return htmllib.escape(str(text), quote=True)


def render(case: dict) -> str:
    body = []
    for block in case["blocks"]:
        kind = block["type"]
        if kind == "heading":
            level = block["level"]
            body.append(f"<h{level}>{esc(block['text'])}</h{level}>")
        elif kind == "paragraph":
            cls = ' class="j"' if block.get("align") == "justify" else ""
            body.append(f"<p{cls}>{esc(block['text'])}</p>")
        elif kind == "list":
            tag = "ol" if block["ordered"] else "ul"
            items = "".join(f"<li>{esc(i)}</li>" for i in block["items"])
            body.append(f"<{tag}>{items}</{tag}>")
        elif kind == "table":
            header = block["header"]
            rows = [header] if header and not isinstance(header[0], list) else list(header)
            head = "".join("<tr>" + "".join(f"<th>{esc(c)}</th>" for c in r) + "</tr>" for r in rows)
            body_rows = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>"
                                for r in block["rows"])
            style = f' style="width: {esc(block["width"])}"' if block.get("width") else ""
            body.append(f"<table{style}><thead>{head}</thead><tbody>{body_rows}</tbody></table>")
    return template(case, "\n".join(body))


def template(case: dict, body: str) -> str:
    fam = fonts.family(case["font"])
    return f"""<!doctype html>
<html lang="{case['lang']}" dir="rtl"><head><meta charset="utf-8">
<title>{esc(case['id'])}</title>
<style>
{fonts.font_face_css(case['font'])}
@page {{ size: A4; margin: 20mm; }}
html, body {{ margin: 0; padding: 0; }}
body {{ font-family: '{fam}'; font-size: 12pt; line-height: 1.7; color: #000; }}
h1 {{ font-size: 20pt; font-weight: 400; margin: 0 0 8pt; }}
h2 {{ font-size: 16pt; font-weight: 400; margin: 6pt 0 6pt; }}
h3 {{ font-size: 13pt; font-weight: 400; margin: 6pt 0 4pt; }}
h4, h5, h6 {{ font-size: 12pt; font-weight: 400; margin: 4pt 0; }}
p {{ margin: 0 0 6pt; }}
p.j {{ text-align: justify; }}
table {{ border-collapse: collapse; width: auto; margin: 6pt 0; }}
thead {{ display: table-row-group; }}
th, td {{ border: 0.5pt solid #000; padding: 3pt; text-align: right; vertical-align: top; }}
/* No synthetic bold anywhere: Chrome prints a synthesised face as a Type3 font whose glyphs carry no
   descriptor, and its ToUnicode can name presentation forms (measured: three Type3 fonts and 9 presentation
   forms on a two-row table before this rule). Weights are chosen by the case, not by the UA stylesheet. */
th, b, strong {{ font-weight: 400; }}
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


__all__ = ["render", "outline", "esc", "arabic_indic"]
