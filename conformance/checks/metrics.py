"""The metrics — one normalization, six numbers, five defect counters, all defined once.

`N(s)` is the only normalization, and it is the same function for the truth and for every reader:
  NFC  ->  drop bidi controls (U+200E/200F/061C, U+202A–202E, U+2066–2069)  ->  collapse every run of
  whitespace (space, tab, newline, CR) to one space  ->  trim.

What `N` deliberately does NOT do, because each of them hides a defect the gate exists to see:
  * it does not drop Arabic diacritics (that is `skeleton`, reported as its own metric),
  * it does not drop tatweel (U+0640): a kashida the engine added is a difference,
  * it does not map digits between scripts (٢٠٢٦ is not 2026),
  * it does not reorder anything.

`digit_runs` — a digit run is a **signed number with its internal separators**, not a bare digit sequence:
the pattern is `[+-]?` followed by one digit of any script and then any of digit / `,` / `.` / `٫` (U+066B) /
`٬` (U+066C). This is what makes the incident behind the corpus measurable: `-6,006.965` moved its sign in an
RTL table cell and the run `6,006.965-` no longer contains the run `-6,006.965`. A run-level definition that
kept only digits would call the moved sign a match and only `exact` would notice.

Defect counters are properties of the output that no normalization may erase. `bidi` is measured **against the
truth's own count**, never against zero: `fix_text_layer.direction_marks` inserts LRM/RLM on purpose, so a
zero floor would fail every pipeline build by design, and a disabled counter would miss the mutation that
inserts a stray U+200F. `tatweel` is likewise the excess over the truth.
"""
import re
import unicodedata
from collections import Counter

BIDI = re.compile("[\u200e\u200f\u061c\u202a-\u202e\u2066-\u2069]")
# Invisible format characters the producer inserts on purpose: `fix_text_layer` maps a drawn mark and a gap
# glyph to U+200B / U+2060 (its own comment: «Preview, PDFium, MuPDF and poppler paste the invisible U+2060
# inside those words»). The assignment's `N` removes direction controls and NOTHING else, so these are KEPT:
# they are characters in the file, a copy-paste carries them, and the gate must not normalize away a
# producer's own insertion. They are counted (`zero_width`) and the file-level check `invisible-format` names
# them. (An earlier version dropped them in `N`; the review was right that it flattered the pipeline.)
ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060]")
# Arabic diacritics (harakat, tanween, shadda, sukun, superscript alef, and the Quranic marks).
MARKS = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06dc\u06df-\u06e4\u06e7\u06e8\u06ea-\u06ed]")
WS = re.compile(r"\s+")
DIGIT = "0-9\u0660-\u0669\u06f0-\u06f9"
RUN = re.compile(f"[+-]?[{DIGIT}][{DIGIT},.\u066b\u066c]*")
PRESENTATION_FORM = (0xFB50, 0xFDFF, 0xFE70, 0xFEFF)      # the two Arabic presentation-forms blocks
ARABIC = re.compile("[\u0600-\u06FF\u0750-\u077F]")        # the base Arabic letters (not the forms)


def is_presentation_form(ch: str) -> bool:
    cp = ord(ch)
    return PRESENTATION_FORM[0] <= cp <= PRESENTATION_FORM[1] or PRESENTATION_FORM[2] <= cp <= PRESENTATION_FORM[3]


def pf_count(s: str) -> int:
    return sum(1 for ch in (s or "") if is_presentation_form(ch))


def arabic_count(s: str) -> int:
    return len(ARABIC.findall(s or ""))


def pf_share(s: str) -> float:
    """Presentation forms over the Arabic characters that could be base letters (a layer of only forms = 1)."""
    arabic, forms = arabic_count(s), pf_count(s)
    return forms / (arabic + forms) if (arabic + forms) else 0.0
PUA = (0xE000, 0xF8FF)


def N(s: str) -> str:
    """The one normalization (documented above, and in docs/conformance/metrics.md)."""
    s = unicodedata.normalize("NFC", s or "")
    s = BIDI.sub("", s)
    return WS.sub(" ", s).strip()


def bidi_count(s: str) -> int:
    return len(BIDI.findall(s or ""))


def zero_width_count(s: str) -> int:
    return len(ZERO_WIDTH.findall(s or ""))


def tatweel_count(s: str) -> int:
    return (s or "").count("\u0640")


def words(s: str) -> list[str]:
    return N(s).split()


def digit_runs(s: str) -> list[str]:
    return RUN.findall(N(s))


def exact(out: str, truth: str) -> float:
    return 1.0 if N(out) == N(truth) else 0.0


def word_f1(out: str, truth: str) -> float:
    a, b = Counter(words(out)), Counter(words(truth))
    if not a and not b:
        return 1.0
    overlap = sum((a & b).values())
    if overlap == 0:
        return 0.0
    precision, recall = overlap / sum(a.values()), overlap / sum(b.values())
    return 2 * precision * recall / (precision + recall)


def lcs(a: list[str], b: list[str]) -> int:
    """Length of the longest common subsequence — the order a reader actually returns words in."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def order(out: str, truth: str) -> float:
    """LCS of the two word sequences, as a fraction of the truth's length."""
    t = words(truth)
    return lcs(words(out), t) / len(t) if t else 1.0


def digit_runs_ratio(out: str, truth: str) -> float:
    """Fraction of the truth's digit runs present in the output, COUNTED per run.

    Counted, not «is this string a substring somewhere»: a page that prints ٢٠٢٦ twice and loses one copy
    still contains the substring, and a presence test would call it intact. `Counter` intersection is the
    honest form and it keeps duplicates meaningful.
    """
    want = Counter(digit_runs(truth))
    if not want:
        return 1.0
    have = Counter(digit_runs(out))
    return sum((want & have).values()) / sum(want.values())


def strip_marks(s: str) -> str:
    return MARKS.sub("", s or "")


def skeleton_exact(out: str, truth: str) -> float:
    """`exact` after removing diacritics — separates a mark defect from a letter defect."""
    return 1.0 if N(strip_marks(out)) == N(strip_marks(truth)) else 0.0


def defects(out: str, truth: str, floor_bidi: int | None = None) -> dict:
    """Countable defects in the output, each with the truth as its reference where that matters.

    `floor_bidi` is the number of direction marks the FILE itself carries (read from its text layer). The
    reader's excess is measured above that floor, never above zero: the pipeline inserts LRM/RLM on purpose,
    and a zero floor would fail every build by design while a disabled counter would miss a stray mark. The
    file's own count is judged separately, as its own number.
    """
    counts = Counter()
    for ch in out or "":
        cp = ord(ch)
        if PRESENTATION_FORM[0] <= cp <= PRESENTATION_FORM[1] or PRESENTATION_FORM[2] <= cp <= PRESENTATION_FORM[3]:
            counts["presentation_forms"] += 1
        elif PUA[0] <= cp <= PUA[1]:
            counts["pua"] += 1
        elif cp == 0xFFFD:
            counts["replacement"] += 1
    floor = bidi_count(truth) if floor_bidi is None else max(bidi_count(truth), int(floor_bidi))
    counts["bidi"] = max(0, bidi_count(out) - floor)
    counts["zero_width"] = max(0, zero_width_count(out) - zero_width_count(truth))
    counts["tatweel_excess"] = max(0, tatweel_count(out) - tatweel_count(truth))
    return {k: counts.get(k, 0) for k in
            ("presentation_forms", "pua", "replacement", "bidi", "zero_width", "tatweel_excess")}


METRICS = ("exact", "word_f1", "order", "digit_runs", "skeleton_exact")


def measure(out: str, truth: str, floor_bidi: int | None = None) -> dict:
    """Every metric and every defect counter for one (reader, case) pair."""
    return {
        "metrics": {
            "exact": exact(out, truth),
            "word_f1": round(word_f1(out, truth), 6),
            "order": round(order(out, truth), 6),
            "digit_runs": round(digit_runs_ratio(out, truth), 6),
            "skeleton_exact": skeleton_exact(out, truth),
        },
        "defects": defects(out, truth, floor_bidi),
        "chars": {"truth": len(N(truth)), "out": len(N(out))},
        "digit_runs": {"truth": digit_runs(truth), "out": digit_runs(out)},
    }
