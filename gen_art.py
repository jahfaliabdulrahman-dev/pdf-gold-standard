#!/usr/bin/env python3
"""Art generation for PDF covers via the OpenRouter Image API.

Usage:
    export OPENROUTER_API_KEY=sk-or-...
    python3 gen_art.py cover 4K

Modes: cover | divider | back        Resolutions: 1K | 2K | 4K
Also reads a local `.env` next to this script (KEY=VALUE lines).

The divider/back modes reuse the cover as a style reference, so the whole
family stays consistent (same materials, palette, lighting).
"""
import base64
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
API = "https://openrouter.ai/api/v1/images"
MODEL = "google/gemini-3-pro-image"
NO_TEXT = ("Artwork only: absolutely no text, no typography, no letters, "
           "no words, no watermark, no logos. ")

PROMPTS = {
    "cover": ("Premium vertical 3:4 3D render for a luxury technology document. " + NO_TEXT +
              "An isometric stack of five floating translucent glass panels in royal violet "
              "#4928b5 and deep purple, arranged diagonally over a softly glowing circular "
              "pedestal; thin teal #79e9e0 light lines trace the panel edges; tiny glass cubes "
              "and sparkles float nearby; deep cosmic navy #1a0b70 background with a soft "
              "vertical light beam. The glass stack occupies the lower two thirds; the top "
              "third is calm, dark, empty space."),
    "divider": ("Using the attached image only as a STYLE REFERENCE (glass material, "
                "violet-teal palette, cosmic dark background, lighting mood) - create a "
                "brand-new minimal artwork in the same family for a section divider page: "
                "THREE floating translucent violet glass panels arranged in a graceful "
                "vertical flow with generous dark empty space above and below; a few small "
                "glowing particles; soft teal edge glow. Vertical 3:4 premium 3D render. "
                + NO_TEXT + "Centered composition, large calm dark areas."),
    "back": ("Using the attached image only as a STYLE REFERENCE - create a new minimal "
             "closing artwork in the same family for a back cover: a SINGLE centered "
             "translucent violet glass panel hovering above a small softly glowing base, "
             "seen at a gentle angle, with a faint teal rim light and sparse sparkles; the "
             "rest is vast calm dark cosmic space. Vertical 3:4 premium 3D render. " + NO_TEXT),
}


def style_ref() -> str:
    for cand in ("embed-cover.jpg", "final-cover-4K.png"):
        p = os.path.join(ROOT, "art", cand)
        if os.path.exists(p):
            return p
    return ""


def load_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        envf = os.path.join(ROOT, ".env")
        if os.path.exists(envf):
            for line in open(envf):
                m = re.match(r"OPENROUTER_API_KEY=(.+)", line.strip())
                if m:
                    key = m.group(1).strip().strip('"').strip("'")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY missing - export it or add ./.env")
    return key


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in PROMPTS:
        raise SystemExit("usage: gen_art.py <cover|divider|back> [1K|2K|4K]")
    mode = sys.argv[1]
    res = sys.argv[2] if len(sys.argv) > 2 else "2K"
    body = {
        "model": MODEL,
        "prompt": PROMPTS[mode],
        "resolution": res,
        "aspect_ratio": "3:4",
        "provider": {"only": ["google-ai-studio"], "allow_fallbacks": False},
    }
    ref = style_ref()
    if mode in ("divider", "back") and ref:
        b64 = base64.b64encode(open(ref, "rb").read()).decode()
        body["input_references"] = [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}
        ]
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + load_key(),
                 "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=540))
    out = os.path.join(ROOT, "art", f"final-{mode}-{res}.png")
    open(out, "wb").write(base64.b64decode(r["data"][0]["b64_json"]))
    cost = (r.get("usage") or {}).get("cost")
    print(f"{out}  cost={cost}")


if __name__ == "__main__":
    main()
