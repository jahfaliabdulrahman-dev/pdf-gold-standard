"""Category floors — the corpus is only as good as the shapes it refuses to go without.

The floors are the assignment's table, copied as data. `problems()` is called by the corpus test and by
`python -m conformance run` before it builds anything: a corpus that lost a case from a category at its floor
does not run. Deleting a case is therefore a decision with a reason in a commit message, not an edit.
"""
from collections import Counter

# category -> (minimum, the mandatory shapes it must contain, free text for the docs)
FLOORS = {
    "shaping":        (6, "لام-ألف بأشكالها الأربعة، «الله»، حروف لا تتصل يسارًا، كلمة من حرف واحد"),
    "vocalisation":   (5, "نص مشكول كاملًا، شدّة مع حركة، تنوين، حركات على لام-ألف"),
    "kashida":        (3, "تطويل في المصدر، فقرة مضبوطة لكشف كشيدة يضيفها المحرّك"),
    "digits":         (8, "هندية وغربية في جملة، تاريخ، نسبة، مادة (٢٥)، هاتف، رقم في قوسين"),
    "money":          (6, "-6,006.965 في خلية RTL، سالب بالهندية، U+20C1، «ر.س»، IBAN، فاصل آلاف"),
    "mixed":          (6, "كلمة لاتينية وسط جملة، جملة لاتينية، بريد ورابط، PDF/UA، أقواس"),
    "tables":         (6, "عمودان وخمسة، رأس من صفّين، خلية فارغة، خلية من سطرين، جدول عابر للصفحة"),
    "headings":       (4, "H1–H3 متداخلة، عنوان بأرقام، عنوان لاتيني"),
    "punctuation":    (4, "، ؛ ؟ على حافة سطر، اقتباس «»"),
    "lists":          (2, "مرقّمة بالهندية، ونقطية"),
}


def problems(cases: list[dict]) -> list[str]:
    counts = Counter(c["category"] for c in cases)
    unknown = sorted(set(counts) - set(FLOORS))
    out = [f"category {u!r} is not declared in FLOORS ({counts[u]} case(s))" for u in unknown]
    for cat, (floor, _shapes) in FLOORS.items():
        got = counts.get(cat, 0)
        if got < floor:
            out.append(f"category {cat}: {got} case(s), floor {floor}")
    return out


def summary(cases: list[dict]) -> str:
    counts = Counter(c["category"] for c in cases)
    rows = [f"{cat} {counts.get(cat, 0)}/{floor}" for cat, (floor, _) in FLOORS.items()]
    return f"{len(cases)} cases · " + " · ".join(rows)
