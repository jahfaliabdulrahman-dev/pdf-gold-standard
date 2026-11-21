"""Orientation detection — arafix's voted detector, imported (MIT), never re-written.

The assignment's signal text names «the share of words a lexicon reads forward vs reversed». arafix
implements a different, deterministic mechanism: three linguistic signals (final-only letters in word
initial position, joining forms, the definite article), weighted and voted, with a published threshold
(`DEFAULT_THRESHOLDS["visual_order"] = 0.30`). It is adopted because it was measured, not because it was
available: on a logical sentence it returns −1.0 and on the same sentence reversed +1.0
(`docs/checker-v0/measurements/arafix.md`), and the separation on the fixtures is recorded there too.

This wrapper is the ONLY place the checker's orientation metric may live: a detector written inside
`arabic_pdf_check/` would be a second opinion that can drift from the one the measurements were made with.
"""
from arafix import DEFAULT_THRESHOLDS, __version__ as ARAFIX_VERSION, diagnose
from arafix.types import Defect

THRESHOLD = float(DEFAULT_THRESHOLDS["visual_order"])
VERSION = ARAFIX_VERSION
SIGNALS = ("final_only_letters", "joining_forms", "definite_article")


def inspect(text: str) -> dict:
    """{'score', 'visual', 'confidence', 'evidence'} for one extracted text.

    `score` is arafix's own number in [−1, 1]: +1 certainly reversed, −1 certainly logical, 0 no evidence.
    It is evidence, not a quality ratio — the report never renders it as a percentage.
    """
    d = diagnose(text or "")
    score = d.metrics.get("order_score")
    evidence = [{"signal": e.name, "value": round(float(e.value), 3), "detail": e.detail}
                for e in d.evidence if e.name in SIGNALS]
    return {
        "score": None if score is None else round(float(score), 4),
        "visual": Defect.VISUAL_ORDER in d.defects,
        "confidence": d.defect_confidence.get(Defect.VISUAL_ORDER),
        "evidence": evidence,
    }
