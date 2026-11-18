"""The two numbers the word-order gate is made of — in one place.

`calibrate --write` derives a document's floor as «measured − drift»; the gate refuses a spec that omits the
key or writes anything below the floor, so the rule cannot be bought down by editing one module. Written twice, the two sides can drift apart and the rule
becomes a comment; the same reason `pdfops` exists for the matrix maths.
"""

LINE_ORDER_FLOOR = 0.75     # nothing may sit below this, ever: it is the floor three documents once shared
LINE_ORDER_DRIFT = 0.02     # how far a build may fall before the ratchet calls it a regression
