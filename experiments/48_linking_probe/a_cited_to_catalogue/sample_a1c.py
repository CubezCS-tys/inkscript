"""Third draw (seed 4801, after the first two): 20 fresh accepted links under decide.py v3."""
import json, random
OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
W = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")}
M = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "matches.jsonl", encoding="utf-8")}
D = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "decisions.jsonl", encoding="utf-8")}
seen = {s["cited_work_pk"] for s in json.load(open(OUT + "a1_sample.json"))} | {s["cited_work_pk"] for s in json.load(open(OUT + "a1b_sample.json"))}
rng = random.Random(4801); rng.random(); rng.random()
acc = sorted(k for k, d in D.items() if d["decision"] == "accept" and k not in seen)
S = rng.sample(acc, 20)
with open(OUT + "a1c_sample.txt", "w", encoding="utf-8") as f:
    for i, k in enumerate(S):
        w, m, d = W[k], M[k], D[k]
        rep = max(w["members"], key=lambda x: len(x["printed"] or ""))
        t = next(t for t in m["top"] if t["c999"] == d["c999"])
        f.write(f"#{i} {m['cls']} {w['cited_work_id']} {rep['stem']} p{rep['page']} {rep['container_id']} {d['why']}\n  CITED: {rep['printed']}\n")
        f.write(f"  -> c999={t['c999']} T={t['s_title']} A={d['author_cross']} Y={t['s_year']} J={t['s_journal']} V={t['s_vip']}: {t['title']} | {t['subtitle']} | {t['authors'][:3]} {t['year']} {t['journal']} [{t['type']}]\n\n")
json.dump([dict(i=i, cited_work_pk=k) for i, k in enumerate(S)], open(OUT + "a1c_sample.json", "w"))
print(len(acc))
