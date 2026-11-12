# Hardening a PDF delivery gate (recipes)

Depth for the "Hardening the gate itself" rules in SKILL.md. Every recipe is a
shape that was measured against a real Chrome-printed Arabic report; adapt the
constants, keep the discipline.

## 0. Build-time auto-fit loop (the harness the gate plugs into)

```python
for per_page in CANDIDATES:                 # appendix lines per page, widest first
    for step in range(len(TIGHT_STEPS) + 1):  # section tightening steps
        for attempt in (1, 2):              # contents-page convergence
            pages, sections, chunks = rebuild(toc_pages, per_page)
            if pages == toc_pages:
                break
            toc_pages = pages
        over = measure_overflow()           # from inside the browser, see §2
        bad = {p: v for p, v in over.items() if 3 <= p < first_appendix_page}
        if not bad:
            break
        if step >= len(TIGHT_STEPS):
            raise SystemExit(f"overflow unresolved on {sorted(bad)} — refusing to ship")  # split the section instead
        for p in bad:
            tight[p - 3] = TIGHT_STEPS[step]
        toc_pages = None
    if coverage_ok() and not appendix_overflow():
        break
else:
    raise SystemExit("no layout found without clipping — refuse to ship")
```

Two properties matter: the loop REFUSES rather than shipping a clipped or
overlapped page, and `sections` is re-bound from the rebuild return value —
keeping it in an outer variable that the rebuild does not refresh produces a
build with no bookmarks and a contents page full of dashes.

## 1. Mutation self-test (the gate must be seen failing)

```python
# gate: accept a mutation flag, apply it to the in-memory doc BEFORE the checks
try:
    k = sys.argv.index("--mutate")
    MUTATION = sys.argv[k + 1]
except ValueError:
    MUTATION = None
POSITIONAL = [a for a in sys.argv[1:] if not a.startswith("--") and a != MUTATION]  # valeur ≠ path

if MUTATION == "buttons":            # swap two nav destinations (same rects, same labels)
    pg = doc[page]                   # a content page
    ls = sorted([l for l in pg.get_links() if l["kind"] == fitz.LINK_GOTO],
                key=lambda l: -fitz.Rect(l["from"]).x1)
    for l, t in ((ls[0], ls[1]["page"]), (ls[1], ls[0]["page"])):
        pg.delete_link(l); pg.insert_link({**l, "page": t})
elif MUTATION == "clip":             # simulate a clipped line in the appendix
    pg = doc[appendix_page_index]
    b = [b for b in pg.get_text("blocks") if b[6] == 0 and arabic_chars(b[4]) >= 40][1]
    pg.add_redact_annot(fitz.Rect(b[0], b[1], b[2], b[3])); pg.apply_redactions()
else:
    raise SystemExit(f"unknown mutation: {MUTATION}")
```

Driver: run the gate three times (baseline, `buttons`, `clip`); require exit 0 on
the baseline and exit≠0 WITH the expected `FAIL <check-name>` on each mutation.
Parse the failing names from stdout — an exit code alone may come from an
unrelated check crashing.

## 2. Overflow: measure the layout, not the PDF

Clipped text does not exist in the PDF, so no PDF-side check can detect it.
Measure the layout in the engine that clips it.

```html
<!-- injected into the print HTML -->
<div id="ovf" hidden></div>
<script>
/* braces doubled because the template is an f-string */
document.addEventListener('DOMContentLoaded', function () {{
  var out = [];
  document.querySelectorAll('.page-inner').forEach(function (el, i) {{
    var ov = el.scrollHeight - el.clientHeight;
    if (ov > 0) out.push((i + 1) + ':' + Math.round(ov));
  }});
  document.getElementById('ovf').textContent = out.length ? out.join(',') : 'none';
}});
</script>
```

```python
out = subprocess.run([chrome, "--headless=new", "--disable-gpu",
                      "--virtual-time-budget=12000", "--dump-dom", uri],
                     capture_output=True, text=True).stdout
m = re.search(r'id="ovf"[^>]*>([^<]*)<', out)
if not m:
    raise SystemExit("overflow measurement unreadable — stop instead of assuming safety")
over = {} if m.group(1).strip() in ("", "none") else {
    int(p) + 1: int(v) for p, v in (i.split(":") for i in m.group(1).split(","))}
```

CSS that makes the box clip instead of overlapping, and tightening that the
measurement can actually see:

```css
/* a bottom padding reserves space but does NOT stop overflow — the box must clip */
.page-inner { height: <content_h - footer_reserve>pt; overflow: hidden; }
/* real tightening: line-height / font-size. `zoom` does NOT change scrollHeight,
   so the measurement stays blind to it. */
.page-inner.tight   { line-height: 1.50; font-size-adjust: none; }
.page-inner.tight   .mono, .page-inner.tight .term { font-size: 7.0pt; }
.page-inner.tighter { line-height: 1.38; }
.page-inner.tighter .mono, .page-inner.tighter .term { font-size: 6.5pt; }
.page-inner.tight   figure img { max-height: 165pt; object-fit: contain; }
```

A section that still overflows after the bounded steps is a STRUCTURE problem:
split it into two sections (move half its blocks into a new `sec(...)`) rather
than squeezing further — at ~20 % overflow no amount of tightening reads well.

## 3. Content coverage that is not blind

```python
squash = lambda s: "".join(s.split())        # Chrome inserts a space inside `->`
                                             # and breaks long tokens when wrapping
def appendix_pages(doc):
    """Pages whose header carries the file name AND a line range — not every page
    that merely names the file (the files table in the body does too)."""
    ...

# (1) declared ranges are contiguous and end at the real line count
# (2) each ASCII content line appears on ITS declared page, whitespace-insensitively
# (3) per-page Arabic budget: arabic_chars(page) >= arabic_chars(source[a:b]) * 1.02
#     (headers add Arabic to every page, so the ratio must exceed 1)
```

Measure (1) and (3) in addition to (2): an ASCII filter can cover a third of an
Arabic-heavy appendix while printing "N/N lines visible".

## 4. Buttons and footers: positions, not sets

```python
SLOTS = {"next": 0, "prev": 1, "home": 2, "toc": 3}   # mirrored from the builder CSS
def slot_of(rect, right_edge, pitch):
    k = round((right_edge - rect.x1) / pitch)
    return k if abs((right_edge - k * pitch) - rect.x1) <= 1.5 else None

for link in links:
    exp = expected_target(page_index, slot, page_count)   # next/prev/home/toc
    assert link["page"] == exp                            # per-link, never a sorted multiset
    drawn = page.get_text("text", clip=fitz.Rect(link["from"]))
    assert sorted("".join(drawn.split())) == sorted("".join(label_for(slot).split()))
```

The label comparison uses a character MULTISET (order-independent) because the
Arabic text layer is visual-order — it still catches "this rect carries someone
else's label" and "a caption bled into the button strip".

Slot indexes must be assigned BY NAME in the builder too: numbering the drawn
buttons sequentially puts a link where no label is painted (a phantom hit area)
whenever a page omits one button.

## 5. Footer page numbers

`صفحة ١٢ من ١٩` extracts as one span containing both numbers, so a span-level x
cannot order them. Use char-level positions and the observed convention (a
multi-character Arabic-Indic run is extracted in visual order, i.e. REVERSED —
recover the value by reversing the run before `int()`):

```python
for b in page.get_text("rawdict")["blocks"]:
    for line in b.get("lines", []):
        for span in line["spans"]:
            # group consecutive Arabic-Indic chars, take bbox[0] of the first char
```

Guard the degenerate case: on the last page the page number equals the total, so
require two runs with that value and skip the ordering assertion.

## 6. Images prove nothing by count alone

```python
# unique 1-to-1 mapping via a downsampled signature: catches a duplicated image
# and an image swapped for a different file. Tolerate re-encoding (JPEG in PDF).
for pix in embedded: match = min(files, key=lambda f: mad(sig(pix), sig(f)))
assert unique(match) and mad < threshold
```

Also hash consecutive screenshots and FAIL on duplicates: if the delay before a
"live" capture exceeds the command's runtime, the live shot is byte-identical to
the finished one and evidences nothing.

## 7. Evidence index (so the report's numbers are checkable)

```
evidence/
  <raw logs>.log                 # untouched stdout of the measuring run
  stability_raw/run_1..N.json    # one file per run, each embedding:
                                 #   code_sha256 (hashlib of the producing file)
                                 #   timestamp
  measurement_summary.json       # derived aggregates the report text is built from
  README.md                      # what each artifact proves + the reproduce command
```

Regenerate the evidence immediately before the final build, and never edit the
code between the measurement batch and the summary — a code hash inside each run
record is what makes "one code revision produced all N runs" a fact rather than a
claim.

## 8. Publishing

Build to `<name>.partial.pdf` in the same directory and `os.replace` only after
all checks pass; return the gate's exit code from the builder so a failed gate
cannot produce a deliverable at all.
