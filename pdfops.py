"""The one list of operators that PAINT — and the one way to read where text lands.

Shared by the producer (postprocess: what may be wrapped as an Artifact, and where its text sits) and the
gate (verify_pdf: the furniture band, and what counts as an artifact carrying text). Two copies would let one
side drift and quietly silence the other.

What counts as an artifact (B1, tightened after review):
  · ANY marked-content block whose tag is `/Artifact`, at any nesting depth — not only a depth-0 BDC with an
    inline `/Type /Pagination`. A named property list is resolved through the page's /Resources /Properties,
    and an `/Artifact` nested inside a `/Span` is still an artifact.
  · Text inside one is page furniture: it must sit in the document's declared band, whatever its `Type` says.
    An untyped block is not a licence.
  · `Do` is followed into Form XObjects (with the form's /Matrix), because Chrome may keep a page's text in a
    form; the text rise (`Ts`) is part of where a glyph is drawn.
"""

import pikepdf

PAINT_OPS = frozenset({
    "m", "l", "c", "v", "y", "h", "re",                    # path construction
    "S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n",   # path painting
    "Do", "sh",                                            # XObject / shading
    "Tj", "TJ", "'", '\"',                                  # text showing
})

TEXT_OPS = frozenset({"Tj", "TJ", "'", '\"'})

PAGINATION, ARTIFACT = "pagination", "artifact"


def _mul(m1, m2):
    """m1 × m2 in PDF's [a b c d e f] convention."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return [a1 * a2 + b1 * c2, a1 * b2 + b1 * d2,
            c1 * a2 + d1 * c2, c1 * b2 + d1 * d2,
            e1 * a2 + f1 * c2 + e2, e1 * b2 + f1 * d2 + f2]


def _xy(m, x, y):
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def _kind(tag, operand, props):
    """The artifact kind of a marked-content tag: pagination, artifact, or None (tagged content)."""
    if str(tag) != "/Artifact":
        return None
    d = operand
    if isinstance(d, str) and props:
        d = props.get(d)
    if not hasattr(d, "get"):
        return ARTIFACT          # a name we cannot resolve is still an artifact, just an untyped one
    try:
        return PAGINATION if str(d.get("/Type")) == "/Pagination" else ARTIFACT
    except Exception:
        return ARTIFACT


def text_shows(instructions, resolve=None, props=None):
    """(kind, x, y, size, marked_depth) for every text show: kind is None, 'artifact' or 'pagination'.

    `resolve` follows `Do` into a Form XObject: given the XObject's name it returns
    (its instructions, its /Matrix), or None. Without it, form text is invisible to the reader — the hole the
    review found. `size` is the font size in page units and `y` is the drawn baseline: the text matrix, the
    text rise (`Ts`) and the CTM (scaled by the form matrix) all take part.
    """
    return _walk(instructions, resolve, [1, 0, 0, 1, 0, 0], frozenset(), props)


def _walk(instructions, resolve, ctm0, seen, props=None, base=None):
    ctm = list(ctm0)
    stack, tm, tlm = [], [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 0, 0]
    size, leading, rise = 12.0, 0.0, 0.0
    frames = [base] if base else []   # one entry per BMC/BDC; `base` carries the caller's artifact context
    out = []
    for ins in instructions:
        op = str(ins.operator)
        o = ins.operands
        if op == "q":
            stack.append((list(ctm), rise, size, leading))   # text state is part of the graphics state
        elif op == "Q":
            if stack:
                ctm, rise, size, leading = stack.pop()
        elif op == "cm":
            ctm = _mul([float(v) for v in o], ctm)
        elif op == "BT":
            tm = tlm = [1, 0, 0, 1, 0, 0]
        elif op == "Tm":
            tm = tlm = [float(v) for v in o]
        elif op == "Td":
            tlm = _mul([1, 0, 0, 1, float(o[0]), float(o[1])], tlm)
            tm = tlm
        elif op == "TD":
            tlm = _mul([1, 0, 0, 1, float(o[0]), float(o[1])], tlm)
            leading = -float(o[1])
            tm = tlm
        elif op == "T*":
            tlm = _mul([1, 0, 0, 1, 0, -leading], tlm)
            tm = tlm
        elif op == "TL":
            leading = float(o[0])
        elif op == "Ts":
            rise = float(o[0])                      # text rise: where the glyph is drawn, not where the line is
        elif op == "Tf":
            size = float(o[1])
        elif op in ("Tj", "TJ", "'", '\"'):
            if op in ("'", '\"'):
                tlm = _mul([1, 0, 0, 1, 0, -leading], tlm)
                tm = tlm
            m = _mul(tm, ctm)
            x, y = _xy(m, 0, rise)
            out.append((_frame_kind(frames), x, y, size * (m[2] ** 2 + m[3] ** 2) ** 0.5, len(frames)))
        if op in ("BMC", "BDC"):
            if op == "BDC" and len(o) > 1:
                frames.append(_kind(o[0], o[1], props))
            else:
                frames.append(_kind(o[0], None, None) if o else None)
        elif op == "EMC":
            if frames:
                frames.pop()
        elif op == "Do" and resolve is not None and o:
            hit = resolve(str(o[0]))
            if hit is not None:
                sub, matrix = hit[0], hit[1]
                key = id(sub)
                if key not in seen and len(seen) < 8:      # a form cycle is not a reason to hang the gate
                    out.extend(_walk(sub, resolve, _mul(matrix, ctm), seen | {key}, props,
                                    _frame_kind(frames)))
    return out


def _frame_kind(frames):
    """The nearest enclosing artifact kind — a `/Span` inside an artifact does not cancel it."""
    return next((k for k in reversed(frames) if k), None)


def outside_bands(instructions, bands, resolve=None, props=None):
    """(kind, y) of every text show inside an artifact whose drawn baseline is outside every declared band.

    Empty means the rule holds. The producer refuses a build on it; the gate holds the file to it. An empty
    band list means the document declares no page furniture: any artifact text is then outside.
    """
    return [(kind, y) for kind, _x, y, _s, _d in text_shows(instructions, resolve, props)
            if kind is not None and not any(lo <= y <= hi for lo, hi in bands)]


def artifact_shows(instructions, resolve=None, props=None):
    """{kind: count} of the text shows inside artifacts — the inventory the review asked to print."""
    out = {}
    for kind, _x, _y, _s, _d in text_shows(instructions, resolve, props):
        if kind is not None:
            out[kind] = out.get(kind, 0) + 1
    return out


def props_of(page):
    """The page's /Resources /Properties: a named property list has to be resolved to be judged."""
    try:
        p = page.get("/Resources", {}).get("/Properties", {})
        return {str(k): v for k, v in p.items()}
    except Exception:
        return {}


def _resolve_from(res):
    """`Do` resolver for a Resources dictionary: name -> (instructions, /Matrix, Resources)."""
    try:
        xo = res.get("/XObject") if res is not None else None
    except Exception:
        xo = None
    cache = {}

    def resolve(name):
        if xo is None:
            return None
        try:
            target = xo.get(name)
        except Exception:
            return None
        if target is None or str(target.get("/Subtype")) != "/Form":
            return None
        key = target.objgen if hasattr(target, "objgen") else id(target)
        if key not in cache:
            try:
                matrix = [float(v) for v in target.get("/Matrix", [1, 0, 0, 1, 0, 0])]
                cache[key] = (pikepdf.parse_content_stream(target), matrix, target.get("/Resources"))
            except Exception:
                cache[key] = None
        return cache[key]

    return resolve


def form_resolver(page):
    """A `Do` resolver for a page: name -> (instructions, /Matrix, Resources), forms only, parsed once each."""
    try:
        return _resolve_from(page.get("/Resources"))
    except Exception:
        return None


def _form_names(res):
    """Names of the Form XObjects a Resources dictionary carries — invoked or not."""
    try:
        xo = res.get("/XObject") if res is not None else None
        if xo is None:
            return []
        return [str(k) for k, v in xo.items()
                if hasattr(v, "get") and str(v.get("/Subtype")) == "/Form"]
    except Exception:
        return []


def _axis_aligned(m, eps=1e-6):
    return abs(m[1]) <= eps and abs(m[2]) <= eps


# --- the model boundary (review P2, second round) --------------------------------------------------
# The gate MODELS a page: it follows `Do`, keeps text state across q/Q, and judges a glyph where it is
# drawn. Every structure it can model is another structure an attacker — or a Chrome upgrade — can hide
# text in, and each adversarial round found one more. So the pipeline stops interpreting and declares a
# boundary instead, measured on what it actually produces (scripts/constructs.py): Form XObjects at depth
# 1 with no text inside them, no nesting, no text rise, no artifact text under a rotated matrix. Anything
# else is REFUSED BY NAME by the producer and by the gate's `pdf-model` check — not interpreted.

def _scan_model(instructions, res, page_no, depth, frames, seen, out, stats, props):
    ctm = [1, 0, 0, 1, 0, 0]
    stack, tm, tlm = [], [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 0, 0]
    rise, size, leading = 0.0, 12.0, 0.0
    frames = list(frames)
    resolve = _resolve_from(res)
    for ins in instructions:
        op, o = str(ins.operator), ins.operands
        if op == "q":
            stack.append((list(ctm), rise, size, leading))
        elif op == "Q":
            if stack:
                ctm, rise, size, leading = stack.pop()
        elif op == "cm":
            m = [float(v) for v in o]
            ctm = _mul(m, ctm)
            if depth == 0 and not _axis_aligned(m):
                stats["rotated_cm"] += 1
        elif op == "BT":
            tm = tlm = [1, 0, 0, 1, 0, 0]
        elif op == "Tm":
            tm = tlm = [float(v) for v in o]
        elif op == "Td":
            tlm = _mul([1, 0, 0, 1, float(o[0]), float(o[1])], tlm)
            tm = tlm
        elif op == "TD":
            tlm = _mul([1, 0, 0, 1, float(o[0]), float(o[1])], tlm)
            leading = -float(o[1])
            tm = tlm
        elif op == "T*":
            tlm = _mul([1, 0, 0, 1, 0, -leading], tlm)
            tm = tlm
        elif op == "TL":
            leading = float(o[0])
        elif op == "Ts":
            rise = float(o[0])
            if abs(rise) > 1e-9:
                stats["rise"] += 1
                out.append(f"p{page_no}: text rise {rise:g} (Ts) — a glyph off its baseline is not modelled")
        elif op == "Tf":
            size = float(o[1])
        elif op in TEXT_OPS:
            if op in ("'", '"'):
                tlm = _mul([1, 0, 0, 1, 0, -leading], tlm)
                tm = tlm
            if depth >= 1:
                stats["text_in_form"] += 1
                out.append(f"p{page_no}: text inside a Form XObject (depth {depth})")
            if _frame_kind(frames) and not _axis_aligned(_mul(tm, ctm)):
                out.append(f"p{page_no}: artifact text under a non-axis-aligned matrix")
        if op in ("BMC", "BDC"):
            if op == "BDC" and len(o) > 1:
                frames.append(_kind(o[0], o[1], props))
            else:
                frames.append(_kind(o[0], None, None) if o else None)
        elif op == "EMC":
            if frames:
                frames.pop()
        elif op == "Do" and o:
            hit = resolve(str(o[0]))
            if hit is None:
                continue
            if depth >= 1:
                stats["nested"] += 1
                out.append(f"p{page_no}: Do inside a Form XObject (depth {depth + 1})")
            sub, matrix, subres = hit
            nested = _form_names(subres)
            if nested:
                stats["nested"] += len(nested)
                out.append(f"p{page_no}: a Form XObject inside a form's /Resources ({', '.join(nested[:2])})")
            key = id(sub)
            if key in seen:
                continue
            _scan_model(sub, subres, page_no, depth + 1, frames, seen | {key}, out, stats,
                        {str(k): v for k, v in (subres or {}).get("/Properties", {}).items()} if subres else {})


def model_stats(pdf):
    """(violations, stats) for a whole file — the boundary the pipeline declares, measured."""
    out, stats = [], {"forms": 0, "nested": 0, "text_in_form": 0, "rise": 0, "rotated_cm": 0}
    for pi, page in enumerate(pdf.pages, 1):
        try:
            instr = list(pikepdf.parse_content_stream(page))
        except Exception as exc:
            out.append(f"p{pi}: cannot read the page content ({exc})")
            continue
        res = page.get("/Resources")
        stats["forms"] += len(_form_names(res))
        _scan_model(instr, res, pi, 0, [], frozenset(), out, stats, props_of(page))
    seen, uniq = set(), []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq, stats


def model_boundary(pdf):
    """Every structure outside the declared model, by name. Empty means the file is inside the boundary."""
    return model_stats(pdf)[0]
