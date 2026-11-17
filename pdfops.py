"""The one list of operators that PAINT.

Shared by the producer (postprocess: what gets wrapped as an Artifact) and the gate (verify_pdf: what
counts as an untagged run). Two copies would let one side drift and quietly silence the other.
"""

PAINT_OPS = frozenset({
    "m", "l", "c", "v", "y", "h", "re",                    # path construction
    "S", "s", "f", "F", "f*", "B", "B*", "b", "b*", "n",   # path painting
    "Do", "sh",                                            # XObject / shading
    "Tj", "TJ", "'", '"',                                  # text showing
})
