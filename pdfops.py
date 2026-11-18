"""The one list of operators that PAINT — and the one way to read where text lands.

Shared by the producer (postprocess: what gets wrapped as an Artifact) and the gate (verify_pdf: what
counts as an untagged run, and where a pagination artifact's text sits). Two copies would let one side
drift and quietly silence the other.
"""

PAINT_OPS = frozenset({
    "m", "l", "c", "v", "y", "h", "re",                    # path construction
    "S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n",   # path painting
    "Do", "sh",                                            # XObject / shading
    "Tj", "TJ", "'", '"',                                  # text showing
})


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


def text_shows(instructions):
    """(is_pagination, x, y, size) in page space for every text show, matrices tracked.

    `is_pagination` is True when the show sits inside a top-level `/Artifact` whose `/Type` is
    `/Pagination` — the block the producer creates for page furniture. Chrome writes text in CSS pixels
    under a `cm` scale and one tall coordinate space, so `Tm` alone is not a page coordinate: the CTM and
    the q/Q stack are part of the answer. `y` is the baseline; `size` is the font size in page units.
    """
    ctm = [1, 0, 0, 1, 0, 0]
    stack, tm, tlm = [], [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 0, 0]
    size, leading, depth, art = 12.0, 0.0, 0, False
    out = []
    for ins in instructions:
        op = str(ins.operator)
        o = ins.operands
        if op == "q":
            stack.append(list(ctm))
        elif op == "Q":
            ctm = stack.pop() if stack else ctm
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
        elif op == "Tf":
            size = float(o[1])
        elif op in ("Tj", "TJ", "'", '"'):
            if op in ("'", '"'):                      # these also move to the next line first
                tlm = _mul([1, 0, 0, 1, 0, -leading], tlm)
                tm = tlm
            x, y = _xy(_mul(tm, ctm), 0, 0)
            out.append((art, x, y, size * abs(ctm[3] * tm[3])))
        if op in ("BMC", "BDC"):
            if depth == 0:
                art = False
                if op == "BDC" and str(o[0]) == "/Artifact" and len(o) > 1:
                    try:
                        art = str(o[1].get("/Type")) == "/Pagination"
                    except Exception:
                        art = False
            depth += 1
        elif op == "EMC":
            depth = max(0, depth - 1)
    return out
