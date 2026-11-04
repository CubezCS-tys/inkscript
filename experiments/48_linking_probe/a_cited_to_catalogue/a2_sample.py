"""A2: match rates by source and group, and a seeded judging sample (seed 4802, 40 rows with a hit)."""
import json, random, collections
OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
W = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")}
R = [json.loads(l) for l in open(OUT + "external.jsonl", encoding="utf-8")]
seen = {}
for r in R: seen[(r["cited_work_pk"], r["source"])] = r
R = list(seen.values())
T = collections.defaultdict(collections.Counter)
for r in R:
    t = r["hits"][0]["total"] if r["hits"] else -1
    g = (r["source"], r["group"])
    T[g]["n"] += 1
    for th in (0.9, 0.8, 0.7):
        if t >= th: T[g][f">={th}"] += 1
    if r["hits"] and r["hits"][0].get("doi") and t >= 0.8: T[g]["doi>=0.8"] += 1
for g in sorted(T): print(g, dict(T[g]))
rng = random.Random(4802)
pool = sorted([r for r in R if r["hits"] and r["hits"][0]["total"] >= 0.6], key=lambda r: (r["cited_work_pk"], r["source"]))
S = rng.sample(pool, 40)
with open(OUT + "a2_sample.txt", "w", encoding="utf-8") as f:
    for i, r in enumerate(S):
        w = W[r["cited_work_pk"]]; rep = max(w["members"], key=lambda x: len(x["printed"] or ""))
        h = r["hits"][0]
        f.write(f"#{i} [{r['source']} {r['group']}] total={h['total']} T={h['s_title']} A={h['s_author']} Y={h['s_year']} V={h['s_venue']}\n  CITED: {rep['printed'][:260]}\n")
        f.write(f"  HIT: {h['title']} | {h.get('authors', [])[:3]} {h.get('year')} {h.get('venue')} doi={h.get('doi')} id={h.get('id')}\n\n")
json.dump(dict(rates={f"{a}|{b}": dict(v) for (a, b), v in T.items()},
               sample=[dict(i=i, cited_work_pk=r["cited_work_pk"], source=r["source"]) for i, r in enumerate(S)]),
          open(OUT + "a2_sample.json", "w"), indent=0)
