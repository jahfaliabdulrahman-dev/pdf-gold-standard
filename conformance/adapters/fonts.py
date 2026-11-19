"""The two fonts the corpus is allowed to use — resolved as files, pinned by sha256.

The case declares `font: plex|amiri`; this module turns that into one file path. The rule the assignment
sets: full TTF/OTF from the official release, the same bytes for every engine, and **not committed** —
a download script that refuses a byte that does not match the recorded sha256. (The owner's decision on
committing them into `fonts/full/` is still open; until it is taken, the default is download.)

Why the bytes matter, measured 2026-11-19: the repository's `fonts/IBMPlexSansArabic-Regular.ttf`
(`8e0f1046…`) is not the Google Fonts build (`6f611412…`), and **neither Plex nor Amiri carries U+20C1**
(`fontTools` cmap probe: 1065 and 1548 code points in the Bold faces, the riyal sign absent in both). The
U+20C1 case therefore had no owner: it was drawn by a system face and embedded, which is a licensing exposure
as much as a typographic one. The `riyal` entry is the declared last-resort answer — OFL-1.1, pinned, its cmap
verified for U+20C1 before pinning — and the `fonts` check refuses any embedded face outside this table.

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
#
# DECLARED DEVIATION from the assignment's C1 («TTF/OTF كاملة من الإصدار الرسمي»): these two URLs are the
# google/fonts OFL mirror, not IBM/plex and aliftype/amiri release assets. The reason is reproducibility, and
# it is the only reason: google/fonts gives a commit-pinned raw URL for a single file, while the official
# repositories publish their TTFs inside versioned releases (Amiri ships a zip, which would need unpacking and
# a second hash for the archive). The bytes are OFL in both cases and the sha256 is recorded, so the
# measurement is reproducible either way — but the provenance is a mirror, and the owner may prefer the
# official release with a zip step. That decision is open.
FONTS = {
    "plex": {
        "file": "IBMPlexSansArabic-Regular.ttf",
        "sha256": "6f611412270a132bbac838da9259d4c68569b4175f3b3b8fa3fa36a30b56dab9",
        "url": "https://raw.githubusercontent.com/google/fonts/2cf30108643373d19195f09bdba07de4317152ae"
               "/ofl/ibmplexsansarabic/IBMPlexSansArabic-Regular.ttf",
        "family": "IBM Plex Sans Arabic",
        "homepage": "https://github.com/IBM/plex",
    },
    "plex-bold": {
        "file": "IBMPlexSansArabic-Bold.ttf",
        "sha256": "691e0c891a38637ae6bbdb69700f8042cb0724a137bee615068ffdb92244f61f",
        "url": "https://raw.githubusercontent.com/google/fonts/2cf30108643373d19195f09bdba07de4317152ae"
               "/ofl/ibmplexsansarabic/IBMPlexSansArabic-Bold.ttf",
        "family": "IBM Plex Sans Arabic",
        "homepage": "https://github.com/IBM/plex",
        "weight": 700,
    },
    "amiri-bold": {
        "file": "Amiri-Bold.ttf",
        "sha256": "cfccb794268e7d573d857e6d6a67f89cf8a053e8ffd85dfa0c8ec1bb36fc4827",
        "url": "https://raw.githubusercontent.com/google/fonts/39d11bc313031c9f68e21a297ce5e4a15cc5365e"
               "/ofl/amiri/Amiri-Bold.ttf",
        "family": "Amiri",
        "homepage": "https://github.com/aliftype/amiri",
        "weight": 700,
    },
    # The declared LAST-RESORT face for U+20C1. Neither corpus font carries the riyal sign (measured: Plex 1065
    # and Amiri 1548 code points in the Bold faces, U+20C1 absent), so without this the sign is drawn by whatever
    # system font the OS offers — Apple's .SFCompact-Black on macOS, which is then EMBEDDED in a file we would
    # ship. That is a licensing question, not a typographic one. This face is OFL-1.1 (Reserved Font Name «Saudi
    # Riyal Font», so it is embedded unmodified and never renamed), written for this sign, and its cmap was
    # verified to carry U+20C1 before it was pinned.
    "riyal": {
        "file": "saudi_riyal.ttf",
        "sha256": "e3449bada8a339507601e76ad182ce408c20535afe768ced588b06512f705546",
        "url": "https://raw.githubusercontent.com/emran-alhaddad/Saudi-Riyal-Font/main/fonts/regular/saudi_riyal.ttf",
        "family": "Saudi Riyal",
        "homepage": "https://github.com/emran-alhaddad/Saudi-Riyal-Font",
        "weight": 400,
        "fallback": True,
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


BOLD = {"plex": "plex-bold", "amiri": "amiri-bold"}


def font_face_css(key: str) -> str:
    """Every declared face of the case's family, at its real weight — 400 and, where it exists, 700.

    A synthesised bold is not a style: Chrome prints it as a Type3 font whose ToUnicode can name presentation
    forms (measured earlier: three Type3 fonts and 9 presentation forms on a two-row table). Declaring the real
    700 face removes the reason to forbid bold, so `bold: true` on a block is honest emphasis, not an engine
    artifact — and `test_engine_behaviour.py` asserts no Type3 appears in a bold case.
    """
    faces = [key] + ([BOLD[key]] if key in BOLD else [])
    out = []
    for face in faces:
        entry = FONTS[face]
        url = "file://" + os.path.abspath(path(face))
        weight = entry.get("weight", 400)
        out.append(f"@font-face {{ font-family: '{entry['family']}'; font-style: normal; font-weight: {weight}; "
                   f"font-display: block; src: url('{url}') format('truetype'); }}")
    return "\n".join(out)


def fallback_css() -> str:
    """The declared last-resort face (U+20C1): declared, pinned, OFL — never the OS's. Empty if it is missing."""
    entry = FONTS["riyal"]
    try:
        url = "file://" + os.path.abspath(path("riyal"))
    except FontError:
        return ""
    return (f"@font-face {{ font-family: '{entry['family']}'; font-style: normal; font-weight: 400; "
            f"font-display: block; src: url('{url}') format('truetype'); }}")


def font_stack(key: str) -> str:
    """The case family, then the declared fallback — so a code point the family lacks has a named owner."""
    return f"'{FONTS[key]['family']}', '{FONTS['riyal']['family']}'"


def family(key: str) -> str:
    return FONTS[key]["family"]


def declared_families() -> set[str]:
    return {e["family"] for e in FONTS.values()}


def is_fallback(key: str) -> bool:
    return bool(FONTS[key].get("fallback"))
