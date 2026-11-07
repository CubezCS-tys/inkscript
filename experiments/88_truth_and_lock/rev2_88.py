"""Experiment 88, task 1: the owner's 20-page truth, rev2 — printed «» restored, nothing else changed.

    nice -n 19 python3 rev2_88.py

The owner's yardstick truth (experiment 34, out/gold/<page>.json, status done) reaches every scorer through
experiment 77's out/test/pages.json (built by test77.py; read by eval77/eval78/eval83 and quotes84).  It writes printed
«» as (( )) on 18 lines, carried over from Azure's draft.  Each of those 18 line crops was looked at (out/crops/,
cut from experiment 77's test tar): every mark on them is printed «».

Writes, never touching the original:
  ../77_scratch_reader/out/test/yardstick_truth_rev2_quotes.jsonl   one row per yardstick page: page_id, stem, page,
        truth (the rev2 lines, same order and count as pages.json's truth, so gold_pos still holds), changes
  ../77_scratch_reader/out/test/yardstick_truth_rev2_quotes.README.txt
  out/rev2_changes.json   per change: page, line key, truth position, old, new, evidence crop
"""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
TEST = E / "77_scratch_reader/out/test"
REV2 = TEST / "yardstick_truth_rev2_quotes.jsonl"
CROPS = HERE / "out/crops"

# The 18 lines, checked one by one against their crops on 2026-11-05 (all print « and », not parentheses).
CHECKED = """0005-055-003-004_p008_l014 0260-000-008-013_p005_l021 0260-000-008-013_p005_l023 0355-000-002-006_p017_l002
0382-016-063-013_p003_l011 0382-016-063-013_p003_l014 0382-016-063-013_p003_l015 0382-016-063-013_p003_l017
0382-016-063-013_p003_l018 0382-016-063-013_p003_l020 0382-016-063-013_p003_l021 0382-016-063-013_p003_l023
0382-016-063-013_p003_l025 0382-016-063-013_p003_l027 0408-002-010-007_p003_l021 0408-002-010-007_p003_l024
0408-002-010-007_p003_l025 0498-000-388-003_p006_l034""".split()

# Two lines carry a half-converted mark; the crop shows a plain « / » there (spacing left as the owner wrote it):
#   p008 l014 "( اليد فى العجينة))"  ->  "« اليد فى العجينة»"   (printed « اليد فى العجينة »)
#   p017 l002 "(( يوميات ...)»"     ->  "« يوميات ...»"         (printed « يوميات نائب في الارياف »)
SPECIAL = {"0005-055-003-004_p008_l014": [("( اليد", "« اليد")],
           "0355-000-002-006_p017_l002": [(")»", "»")]}


def fix(key: str, t: str) -> str:
    for a, b in SPECIAL.get(key, []):
        assert t.count(a) == 1, (key, a)
        t = t.replace(a, b)
    return t.replace("((", "«").replace("))", "»")


def main():
    pages = json.loads((TEST / "pages.json").read_text(encoding="utf-8"))
    CROPS.mkdir(parents=True, exist_ok=True)
    tar = tarfile.open(TEST / "test-0-000.tar")
    rows, changes = [], []
    for p in (p for p in pages if p["set"] == "yardstick"):
        inv = {v: int(k) for k, v in p["gold_pos"].items()}
        keys = {l["i"]: l["key"] for l in p["lines"]}
        new = list(p["truth"])
        ch = []
        for j, t in enumerate(p["truth"]):
            key = keys.get(inv.get(j))
            if key not in CHECKED:
                assert "((" not in t and "))" not in t, (p["page_id"], j, t)   # no unchecked (( )) left behind
                continue
            n = fix(key, t)
            assert n != t and "((" not in n and "))" not in n
            crop = CROPS / f"{key}.jpg"
            if not crop.exists():
                crop.write_bytes(tar.extractfile(tar.getmember(key + ".jpg")).read())
            new[j] = n
            c = dict(page_id=p["page_id"], key=key, truth_pos=j, old=t, new=n,
                     evidence=str(crop.relative_to(E.parent)), checked="looked at the crop, 2026-11-05: printed «»")
            ch.append(c)
            changes.append(c)
        rows.append(dict(page_id=p["page_id"], stem=p["stem"], page=p["page"], rev="rev2_quotes", truth=new,
                         changes=[{k: c[k] for k in ("key", "truth_pos", "old", "new")} for c in ch]))
    assert len(changes) == len(CHECKED), len(changes)
    assert not REV2.exists() or "rev2" in REV2.name
    with open(REV2, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (TEST / "yardstick_truth_rev2_quotes.README.txt").write_text(
        f"rev2 (lead, 2026-11-05, owner OK): printed «» restored on {len(changes)} lines; original untouched.\n"
        "The original truth is experiment 34's out/gold/*.json (status done), as carried into pages.json here.\n"
        "rev2 changes only (( )) (and two half-converted marks) to « » on lines whose crop prints « ».\n"
        "Each change, with its crop: experiments/88_truth_and_lock/out/rev2_changes.json.  Made by rev2_88.py.\n"
        "Select it in scoring with experiments/88_truth_and_lock/score88.py --truth rev2 (or yardstick_pages('rev2')).\n",
        encoding="utf-8")
    (HERE / "out/rev2_changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(changes), "lines changed on", sum(bool(r["changes"]) for r in rows), "pages ->", REV2)


if __name__ == "__main__":
    main()
