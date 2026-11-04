"""Experiment 63, step 3b: an OPEN (not blind) review list of every standing decision NOT in the blind sample, one
line each, so the rest of the 908 can be read through after the blind pass (out/openreview63.txt).

    python3 openreview63.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
E56 = HERE.parent / "56_librarian_institutions" / "out"
OUT = HERE / "out"
key = json.loads((OUT / "sample63_key.json").read_text(encoding="utf-8"))
sampled = {v["decision_id"] for v in key.values()}
latest = {}
for line in open(E56 / "decisions56.jsonl", encoding="utf-8"):
    d = json.loads(line)
    latest[d["qkey"]] = d
S = [d for d in latest.values() if d["kind"] != "retired" and d["decision_id"] not in sampled]
P = {json.loads(l)["key"]: json.loads(l) for l in open(E56 / "packets56.jsonl", encoding="utf-8")}
I = {json.loads(l)["inst_id"]: json.loads(l) for l in open(E56 / "institutions56.jsonl", encoding="utf-8")}
order = ["affiliation_institution", "not_an_institution", "unit_kept_apart", "unsure", "set_country", "set_parent",
         "same_institution", "not_same_institution", "set_type"]
S.sort(key=lambda d: (order.index(d["kind"]), d["confidence"], d["basis"], d.get("printed", "")))
lines = []
for n, d in enumerate(S, 1):
    x = d["decision"]
    tag = f"O{n:03d} {d['kind'][:12]} {d['confidence'][:1]} {d['basis'][:5]}"
    if d["level"] == "affiliation":
        p = P[d["subject_keys"][0]]
        inst = "; ".join(i["name_en"] or i["name_ar"] for i in x["institutions"]) or x["status"]
        lines.append(f"{tag} | {p['printed'][:140]} | {p['journal_id']} {p['year']} => {inst} [{x['country']}]")
    elif d["kind"] == "set_country":
        r = I[x["machine_row"]]
        ex = [P[k]["printed"][:70] for k in r["affiliations"][:2] if k in P]
        lines.append(f"{tag} | {x['names']} {ex} => {x['country']} (was {x['was']})")
    elif d["kind"] == "set_parent":
        ex = [P[k]["printed"][:90] for k in x.get("affiliations", [])[:2] if k in P]
        lines.append(f"{tag} | {x['names']} {ex} => parent {x['parent_name']}")
    elif d["kind"] == "same_institution":
        lines.append(f"{tag} | {list(x['machine_rows'].values())} => {x['name_en']}")
    elif d["kind"] == "not_same_institution":
        lines.append(f"{tag} | {x['names']} => {x.get('group_names')}")
    elif d["kind"] == "set_type":
        lines.append(f"{tag} | {x['names']} {x['was']} => {x['type']} ({x['institution']})")
    else:
        lines.append(f"{tag} | {x} | {d['reason'][:120]}")
(OUT / "openreview63.txt").write_text("\n".join(lines), encoding="utf-8")
print(len(lines))
