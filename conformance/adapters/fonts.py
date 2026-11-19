"""The two fonts the corpus is allowed to use — resolved as files, pinned by sha256.

The case declares `font: plex|amiri`; this module turns that into one file path. The rule the assignment
sets: full TTF/OTF from the official release, the same bytes for every engine, and **not committed** —
a download script that refuses a byte that does not match the recorded sha256. (The owner's decision on
committing them into `fonts/full/` is still open; until it is taken, the default is download.)

Why the bytes matter, measured 2026-11-19: the repository's `fonts/IBMPlexSansArabic-Regular.ttf`
(`8e0f1046…`) is not the Google Fonts build (`6f611412…`), and **neither Plex nor Amiri carries U+20C1**
(`fontTools` cmap probe: 1032 and 1699 code points, the riyal sign absent in both). The U+20C1 case is
therefore a measured limit of the fonts, not of an engine — which is exactly how the report states it.

The Chrome-only woff2 chunks in `fonts/` stay what they are: the pipeline's shipping format for the four
documents. The corpus does not use them, because a unicode-range split silently falls back to a system
face for any code point outside every range — and a fallback face is not the font the case declared.
"""
import hashlib
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
FULL_DIR = os.path.join(HERE, "..", "..", "fonts", "full")

# Pinned to the commit that last changed each file in google/fonts, so the URL cannot move under us.
FONTS = {
    "plex": {
        "file": "IBMPlexSansArabic-Regular.ttf",
        "sha256": "6f611412270a132bbac838da9259d4c68569b4175f3b3b8fa3fa36a30b56dab9",
        "url": "https://raw.githubusercontent.com/google/fonts/2cf30108643373d19195f09bdba07de4317152ae"
               "/ofl/ibmplexsansarabic/IBMPlexSansArabic-Regular.ttf",
        "family": "IBM Plex Sans Arabic",
        "homepage": "https://github.com/IBM/plex",
    },
    "amiri": {
        "file": "Amiri-Regular.ttf",
        "sha256": "ab391c4147d054c48976e98322ad0eefe1427aa0e0502a12a4c75d80a70cfcd7",
        "url": "https://raw.githubusercontent.com/google/fonts/39d11bc313031c9f68e21a297ce5e4a15cc5365e"
               "/ofl/amiri/Amiri-Regular.ttf",
        "family": "Amiri",
        "homepage": "https://github.com/aliftype/amiri",
    },
}

LICENCE = "SIL Open Font License 1.1 (OFL) — see the upstream repository named in FONTS[*]['homepage']"


class FontError(RuntimeError):
    """The font is missing and could not be fetched, or its bytes are not the pinned ones."""


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def path(key: str, fetch: bool = True) -> str:
    """The pinned file for `key`, downloading it once if needed. A wrong hash is refused, never accepted."""
    if key not in FONTS:
        raise FontError(f"unknown font {key!r} (corpus allows {sorted(FONTS)})")
    entry = FONTS[key]
    os.makedirs(FULL_DIR, exist_ok=True)
    target = os.path.join(FULL_DIR, entry["file"])
    if not os.path.exists(target):
        if not fetch:
            raise FontError(f"{entry['file']} is not in fonts/full/ — run `python -m conformance.adapters.fetch_fonts`")
        with urllib.request.urlopen(entry["url"], timeout=120) as r:
            data = r.read()
        with open(target, "wb") as fh:
            fh.write(data)
    got = sha256_of(target)
    if got != entry["sha256"]:
        raise FontError(f"{entry['file']}: sha256 {got[:12]} is not the pinned {entry['sha256'][:12]} — "
                        f"refused (delete fonts/full/{entry['file']} to re-fetch)")
    return target


def font_face_css(key: str) -> str:
    """One @font-face, weight 400 only. No synthetic bold: a case that needs emphasis uses size, not weight."""
    entry = FONTS[key]
    url = "file://" + os.path.abspath(path(key))
    return (f"@font-face {{ font-family: '{entry['family']}'; font-style: normal; font-weight: 400; "
            f"font-display: block; src: url('{url}') format('truetype'); }}")


def family(key: str) -> str:
    return FONTS[key]["family"]


def declared_families() -> set[str]:
    return {e["family"] for e in FONTS.values()}
