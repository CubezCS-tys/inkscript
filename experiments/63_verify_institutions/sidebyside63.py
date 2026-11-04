"""Experiment 63, step 2: after the blind answers are frozen, print each sampled item with my answer and exp 56's.

    python3 sidebyside63.py > out/sidebyside63.txt
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
E56 = HERE.parent / "56_librarian_institutions" / "out"
OUT = HERE / "out"

key = json.loads((OUT / "sample63_key.json").read_text(encoding="utf-8"))
mine = {}
for line in open(OUT / "mine63_frozen.jsonl", encoding="utf-8"):
    d = json.loads(line)
    mine[d["sid"]] = d  # a later line for the same sid (a blind revision) wins
dec = {}
for line in open(E56 / "decisions56.jsonl", encoding="utf-8"):
    d = json.loads(line)
    dec[d["decision_id"]] = d


def core(d):
    x = d["decision"]
    if d["level"] == "affiliation":
        return dict(status=x["status"], inst=[i["name_en"] or i["name_ar"] for i in x["institutions"]],
                    units=x.get("units"), faculty=x.get("faculty"), country=x["country"])
    return {k: v for k, v in x.items() if k not in ("names",)}


for sid in sorted(key):
    k = key[sid]
    d = dec[k["decision_id"]]
    print(f"=== {sid} {k['kind']} {k['confidence']} {k['basis']}  {d.get('printed', '')}")
    print(f"  63: {json.dumps({a: b for a, b in mine[sid].items() if a != 'sid'}, ensure_ascii=False)}")
    print(f"  56: {json.dumps(core(d), ensure_ascii=False)}")
    print(f"  56 reason: {d['reason']}")
    print()
