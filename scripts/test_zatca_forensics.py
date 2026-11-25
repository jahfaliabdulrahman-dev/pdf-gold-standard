#!/usr/bin/env python3
"""PR-3's artifact must agree with itself, with its runs, and with the report's headline numbers.

The audit of 2026-11-25 (item 5) refused a deposited artifact with no producer and no head/dirty, and
(item 6) refused a verdict whose two standards were stated as one. This guard is the mechanical half:

  · the artifact names a tree (`head` + `dirty`) and at least two runs with ONE measurements digest — the
    digest is recomputed here, so a hand-edited number breaks it;
  · the totals are the sum of the rows, not a second count;
  · the report's headline holds in the artifact: presentation-forms is 16/16 in the LAYER and 11/16 by the
    reader majority, and PDFium's letter reversal set == the Type3 set == the /AF-absent set.
"""
import hashlib
import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ART = os.path.join(REPO, "docs", "checker-v0", "measurements", "pr3", "zatca-forensics.json")

passed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    if not condition:
        print(f"FAIL {name} — {detail}")
        raise SystemExit(1)
    passed += 1
    print(f"PASS {name}")


def digest(summary: dict, files: list) -> str:
    """The producer's canonical digest: measurements only, no timestamps."""
    payload = json.dumps({"summary": summary, "files": files}, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    art = json.load(open(ART, encoding="utf-8"))
    check("schema", art.get("schema_version") == "zatca-forensics/2", str(art.get("schema_version")))
    check("head-recorded", bool(re.fullmatch(r"[0-9a-f]{7,40}", art.get("head") or "")), str(art.get("head")))
    check("dirty-recorded", isinstance(art.get("dirty"), bool), str(art.get("dirty")))
    check("dirty-is-false", art.get("dirty") is False, "the artifact must come from a clean tree")
    check("reader-versions", len(art.get("reader_versions") or {}) == 6, str(art.get("reader_versions")))
    check("arafix-version-recorded", "arafix" in (art.get("reader_versions") or {}), str(art.get("reader_versions")))
    check("sdk-recorded", bool((art.get("sdk") or {}).get("declared")), str(art.get("sdk")))

    runs = art.get("runs") or []
    check("two-runs", len(runs) >= 2, str(len(runs)))
    digests = {r.get("measurements_sha256") for r in runs}
    live = digest(art["summary"], art["files"])
    check("runs-agree", len(digests) == 1, str(digests))
    check("runs-record-where-they-wrote", all(r.get("out") for r in runs), str([r.get("out") for r in runs]))
    check("digest-matches-the-artifact", digests == {live}, f"{sorted(digests)} vs {live}")

    files = art["files"]
    check("sixteen-files", len(files) == 16, str(len(files)))
    check("every-file-has-a-sha", all(re.fullmatch(r"[0-9a-f]{64}", f.get("sha256") or "") for f in files))
    check("every-file-has-five-readings", all(len(f["readers"]) == 5 for f in files))
    check("samples-are-bounded", all(len(r["sample"]) <= 3 for f in files for r in f["readers"].values()))

    s = art["summary"]
    check("codes-total-is-the-sum", s["drawn_codes_total"] == sum(f["codes"] for f in files),
          f"{s['drawn_codes_total']} vs {sum(f['codes'] for f in files)}")
    check("fonts-total-is-the-sum", s["fonts_total"] == sum(f["fonts"] for f in files),
          f"{s['fonts_total']} vs {sum(f['fonts'] for f in files)}")
    check("pf-positive-is-the-count", s["pf_file_positive"] == sum(1 for f in files if f["pf_file"] > 0),
          str(s["pf_file_positive"]))
    check("missing/notdef/pua are the sum",
          (s["missing_unicode_total"], s["notdef_total"], s["pua_total"])
          == (sum(f["missing_unicode"] for f in files), sum(f["notdef"] for f in files),
              sum(f["pua"] for f in files)))

    # item 6, as a number — ONE definition, the artifact's own: a reader «copies all forms» when
    # pf == pf_file > 0, and a file reaches a reader majority when >= 3 of the five do.
    layer = sum(1 for f in files if f["pf_file"] > 0)
    copying = {n: sum(1 for f in files if f["readers"][n]["pf"] == f["pf_file"] > 0) for n in art["readers"]}
    check("summary-readers-copying-all-forms-is-the-count", copying == s["readers_copying_all_forms"],
          f"{copying} vs {s['readers_copying_all_forms']}")
    by_majority = sum(1 for f in files
                      if sum(1 for n in art["readers"] if f["readers"][n]["pf"] == f["pf_file"] > 0) >= 3)
    check("layer-is-16/16", layer == 16, str(layer))
    check("majority-is-11/16 (>=3 of 5 readers copy all forms)", by_majority == 11, str(by_majority))
    check("the other five carry it in the layer only", layer - by_majority == 5, str(layer - by_majority))

    # the measured correlation, computed from the ROWS: pdfium's letter reversal == Type3 fonts == /AF absent.
    # The summary's two lists are only accepted when they equal what the rows say.
    reversed_letters = [f["index"] for f in files if f["readers"]["pdfium"]["visual"]]
    type3 = [f["index"] for f in files if f["type3_fonts"] > 0]
    af_absent = [f["index"] for f in files if not f["af_present"]]
    check("type3-set-is-the-rows", s["type3_samples"] == type3, f"{s['type3_samples']} vs {type3}")
    check("af-absent-set-is-the-rows", s["af_absent_samples"] == af_absent, f"{s['af_absent_samples']} vs {af_absent}")
    check("the three sets are equal", type3 == af_absent == reversed_letters,
          f"{type3} / {af_absent} / {reversed_letters}")
    check("producer-is-read-from-the-files", bool(s.get("producer")) and ", " not in s["producer"],
          str(s.get("producer")))

    # the report and the artifact are ONE claim: the headline numbers must be in both, and the removed claim
    # must be gone. A document that drifts from its artifact is the stale-line defect this repo keeps paying for.
    doc = os.path.join(REPO, "docs", "checker-v0", "09-pr3-zatca-forensics-2026-11-24.md")
    text = open(doc, encoding="utf-8").read()
    check("doc-states-both-standards", "11/16" in text and "16/16" in text)
    check("doc-names-the-correlation", "9، 11" in text or "9, 11" in text, "the Type3 set is not named")
    check("doc-drops-the-recovered-claim", "يستعيدها" not in text)

    print(f"\nZATCA FORENSICS PASSED — {passed} check(s); {len(runs)} runs, one digest, head {art['head']}, "
          f"dirty {art['dirty']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
