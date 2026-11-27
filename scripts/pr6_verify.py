#!/usr/bin/env python3
"""PR-6 conditions أ-و, read from the artifacts — the same discipline as pr5c_verify.

  docs/checker-v0/measurements/pr6/verdicts-mac6.json     (after: visual-order out of the jury, six readers)
  docs/checker-v0/measurements/pr6/verdicts-linux4.json   (after, four readers — condition هـ)
  docs/checker-v0/measurements/pr5d/verdicts-mac6.json    (before, same six readers)

  أ  the only file whose level moves (before -> after, same jury) is planted-mupdf-logical, and downward
  ب  no clean file is `high`
  ج  the other five planted files keep their level and their named signal
  د  `copy_order` is present in every report (`scripts/test_copy_order.py` proves it equals a re-measurement)
  هـ mac6 and linux4 agree on the LEVEL of every file, and differ in the table rows (else the table is a constant)
  و  no owner text in any artifact: labels are `owner-NN`, and the name guard passes
"""
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MEAS = os.path.join(REPO, "docs/checker-v0/measurements")
RANK = {"low": 0, "medium": 1, "high": 2}
PLANTED = {"planted-chrome-raw": "presentation-forms", "planted-presentation-forms": "presentation-forms",
           "planted-no-tounicode": "tounicode-gaps", "planted-letter-swap": "lexical-validity",
           "planted-lam-alef": "lam-alef-transposition"}
OTHER_PLANTED = ("planted-chrome-raw", "planted-presentation-forms", "planted-no-tounicode",
                 "planted-letter-swap", "planted-lam-alef")
EXPECTED_MOVE = {"planted-mupdf-logical": "low"}


def load(name: str) -> dict:
    with open(os.path.join(MEAS, name), encoding="utf-8") as fh:
        return {row["label"]: row for row in json.load(fh)["files"] if not row.get("missing")}


def main() -> int:
    after = load("pr6/verdicts-mac6.json")
    before = load("pr5d/verdicts-mac6.json")
    fails = []

    def check(name, ok, detail=""):
        print(f"{'PASS' if ok else 'FAIL'} {name}{(' — ' + detail) if detail and not ok else ''}")
        if not ok:
            fails.append(name)

    moved = sorted(lbl for lbl in after
                   if before.get(lbl) and before[lbl]["ship"]["level"] != after[lbl]["level"])
    check("أ only planted-mupdf-logical moves", moved == ["planted-mupdf-logical"], str(moved))
    check("أ the movement is downward",
          RANK[after["planted-mupdf-logical"]["level"]] < RANK[before["planted-mupdf-logical"]["ship"]["level"]]
          and after["planted-mupdf-logical"]["level"] == EXPECTED_MOVE["planted-mupdf-logical"],
          f'before {before["planted-mupdf-logical"]["ship"]["level"]} after '
          f'{after["planted-mupdf-logical"]["level"]}')

    clean_high = sorted(lbl for lbl, row in after.items() if row["group"] == "clean" and row["level"] == "high")
    check("ب no clean file is high", not clean_high, str(clean_high))

    # Condition ج: the five other planted files keep their level and their NAMED signal. The literal reading
    # «signals exactly as they were» cannot hold for any file, because §1 requires `visual-order` to stop being
    # a file cause — so the check is: level unchanged, named signal still present, and the ONLY signal that ever
    # disappears anywhere is `visual-order` itself (proved below over all 149 files).
    for lbl in OTHER_PLANTED:
        same_level = after[lbl]["level"] == before[lbl]["ship"]["level"]
        named = PLANTED[lbl]
        keeps_named = named in (after[lbl]["signals"] or [])
        check(f"ج {lbl} keeps level and its named signal", same_level and keeps_named,
              f'level {before[lbl]["ship"]["level"]}->{after[lbl]["level"]} '
              f'signals {before[lbl]["ship"]["signals"]}->{after[lbl]["signals"]} named={named}')
    vanished = {s for lbl in after if before.get(lbl)
                for s in set(before[lbl]["ship"]["signals"]) - set(after[lbl]["signals"])}
    check("ج the only signal that disappears is visual-order", vanished <= {"visual-order"}, str(vanished))

    no_table = sorted(lbl for lbl, row in after.items() if not (row.get("copy_order") or {}).get("rows"))
    check("د every report carries copy_order", not no_table, str(no_table[:5]))
    wrong_rows = sorted(lbl for lbl, row in after.items()
                        if {r["reader"] for r in (row.get("copy_order") or {}).get("rows") or []}
                        != set(row.get("readers") or []))
    check("د a row per reader that read", not wrong_rows, str(wrong_rows[:5]))
    blame = sorted(lbl for lbl, row in after.items() if "visual-order" in (row.get("signals") or []))
    check("د no file-level visual accusation survives", not blame, str(blame[:5]))

    linux = load("pr6/verdicts-linux4.json")
    differ = sorted(lbl for lbl in after if lbl in linux and after[lbl]["level"] != linux[lbl]["level"])
    check("هـ mac6 and linux4 agree on level", not differ, str(differ[:8]))
    table_differs = sorted(lbl for lbl in after if lbl in linux
                           and after[lbl]["copy_order"] != linux[lbl]["copy_order"])
    check("هـ the tables do differ between juries", bool(table_differs),
          f"{len(table_differs)} file(s) — a table that never changes is a constant")

    keys = [lbl for lbl in after if not (lbl.startswith("owner-") or lbl.startswith("calibration-")
                                         or lbl.startswith("planted-") or lbl.startswith("doc:")
                                         or lbl.startswith("case:") or lbl.startswith("lo-arabic")
                                         or lbl.endswith(".pdf"))]
    check("و labels only, no owner text", not keys, str(keys[:5]))
    guard = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "test_no_owner_names.py")],
                           capture_output=True, text=True)
    check("و the name guard passes", guard.returncode == 0, guard.stdout[-200:])

    print(f"\nfiles: {len(after)} · levels moved: {moved} · signals dropped by the change: "
          f"{sorted({s for lbl in after if before.get(lbl) for s in set(before[lbl]['ship']['signals']) - set(after[lbl]['signals'])})}")
    print(f"\nPR-6 CONDITIONS {'PASSED' if not fails else 'FAILED'} — {14 - len(fails)}/14 check(s)")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
