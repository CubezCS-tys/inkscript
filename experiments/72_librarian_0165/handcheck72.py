"""Experiment 72: the stratified hand-check sample (every applied kind the random 40 under-covers), printed to read.

    python handcheck72.py PART      (40 items per part) -> out/handcheck72_extra_sample.json
"""
import json
import random
import sys
sys.path.insert(0, '.')
from common72 import E62, add_paths  # noqa: E402
add_paths(E62)
from common72 import OUT, jl
import tools62
tools62.OUT = OUT / "works"
C = tools62.cards()
P = jl(OUT / "plan72.jsonl")
aff = {p["key"]: p for p in jl(OUT / "inst" / "aff0165.jsonl")}
allp = {p["key"]: p for p in jl(OUT / "inst" / "packets56.jsonl")}
pick = json.load(open(OUT / "handcheck72_sample.json"))
taken = {p["source_id"] for p in pick}
strata = [("librarian:opus:same_work", 10), ("librarian:opus:edition_of", 5), ("librarian:opus:relation", 6),
          ("librarian:opus:relation+D43", 4), ("librarian:opus:not_a_work_drop", 5), ("librarian:opus:not_a_work_retitle", 5),
          ("librarian:opus:not_a_work_drop+C1", 3), ("librarian:opus:not_a_work_retitle+C1", 2),
          ("librarian:flash:split_card", 10), ("librarian:flash:card_ok", 5), ("librarian:flash:links_to_publication", 5),
          ("librarian:opus:resolved", 10), ("librarian:opus:resolved+review72", 8), ("librarian:flash:same", 17),
          ("librarian:flash:not_institution", 3), ("librarian:P6+D43", 1), ("librarian:P6", 3), ("librarian:persons72", 1),
          ("librarian:reanchor68", 3)]
rnd = random.Random(7241)
out = []
for rc, n in strata:
    pool = [p for p in P if p["reason_code"] == rc and p["source_id"] not in taken]
    out += rnd.sample(pool, min(n, len(pool)))
json.dump(out, open(OUT / "handcheck72_extra_sample.json", "w"), ensure_ascii=False, indent=1)
from verify72 import _pub_title
part = int(sys.argv[1]) if len(sys.argv) > 1 else 0
for i, p in enumerate(out):
    if part and not ((part - 1) * 40 <= i < part * 40):
        continue
    print(f"=== X{i+1:03d} {p['source_id']} {p['op']} {p['reason_code']}")
    print("    note:", (p["note"] or "")[:260])
    for k in p["subject_keys"]:
        kind, v = k.split(":", 1)
        if kind == "aff":
            a = aff.get(k) or allp.get(k)
            if a: print("    printed:", a["printed"], "| journal", a["journal_id"])
        elif kind == "work" and v in C:
            c = C[v]; print(f"    card {v} «{c['title']}» {c['pub_type']}")
            for j, m in enumerate(c["members"][:8]): print(f"       {j+1}. [{m['stem']}] {(m['printed'] or '')[:230]}")
        elif kind == "inst":
            print("    inst", v)
    if p["op"] in ("link_publication", "relate_publication"):
        rec = p["payload"].get("record") or {}
        print(f"    record: «{rec.get('title') or _pub_title(p['subject_keys'][1])}» {[a.get('name') for a in rec.get('authors', [])][:3]} {rec.get('year')} {rec.get('type')} {rec.get('journal')} rel={p['payload'].get('relation')} as={p['payload'].get('as')}")
    if p["op"] == "link_affiliation":
        print("    bodies:", [(x["authority"], x["role"], x["country"], x.get("inferred")) for x in p["payload"]["institutions"]])
    if p["op"] in ("split_work",):
        print("    groups:", [[C[p['subject_keys'][0][5:]]['members'].index(next(m for m in C[p['subject_keys'][0][5:]]['members'] if m['mention_id']==x))+1 for x in g['members']] for g in p["payload"]["groups"]])
    if p["op"] == "not_a_work":
        print("    action:", p["payload"]["action"], "titles:", list((p["payload"].get("titles") or {}).values())[:2])
    if p["op"] == "same_institution":
        import sqlite3
        c = sqlite3.connect("file:/home/appuser/data/desk/releases/R20261103T023001.db?mode=ro", uri=True)
        for k in p["subject_keys"]:
            r = c.execute("SELECT i.inst_id, i.kind, i.parent_id, (SELECT group_concat(name,' | ') FROM institution_names n WHERE n.inst_id=i.inst_id), (SELECT group_concat(name,' | ') FROM institution_names n WHERE n.inst_id=i.parent_id) FROM institutions i WHERE inst_id=?", (k[5:],)).fetchone()
            print("    row:", r)
    print()
