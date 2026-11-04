"""Seeded judging sample for A1 (seed 4801): 45 catalogue-type works across 5 score bands + 15 other-type works ≥ 0.7."""
import json, random
OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
W = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")}
M = [json.loads(l) for l in open(OUT + "matches.jsonl", encoding="utf-8")]
rng = random.Random(4801)
HOLD = {"journal_article", "thesis", "conference_paper"}
BANDS = [(0.85, 9), (0.75, 0.85), (0.65, 0.75), (0.55, 0.65), (-1, 0.55)]
BANDS = [(0.85, 9.0), (0.75, 0.85), (0.65, 0.75), (0.55, 0.65), (-1.0, 0.55)]
def tot(m): return m["top"][0]["total"] if m["top"] else -1
sample = []
for lo, hi in BANDS:
    pool = sorted([m for m in M if m["cls"] in HOLD and lo <= tot(m) < hi], key=lambda m: m["cited_work_pk"])
    for m in rng.sample(pool, 9):
        sample.append(dict(m, band=f"{lo}-{hi}", stratum="holdable"))
pool = sorted([m for m in M if m["cls"] not in HOLD and tot(m) >= 0.7], key=lambda m: m["cited_work_pk"])
for m in rng.sample(pool, 15):
    sample.append(dict(m, band=">=0.7", stratum="other-type"))
with open(OUT + "a1_sample.txt", "w", encoding="utf-8") as f:
    for i, m in enumerate(sample):
        w = W[m["cited_work_pk"]]
        rep = max(w["members"], key=lambda x: len(x["printed"] or ""))
        f.write(f"#{i} [{m['stratum']} {m['band']}] {m['cls']} {w['cited_work_id']}  {rep['stem']} p{rep['page']} {rep['container_id']}\n")
        f.write(f"  CITED: {rep['printed']}\n  parsed title={m['title']!r} src={m['source']!r} authors={m['authors'][:3]} years={m['years']}\n")
        f.write(f"  link47: {[(l['status'], l['c999']) for l in w['links47']]} rel47: {[(r['relation'], r['object_pub_id']) for r in w['relations47']]}\n")
        for j, t in enumerate(m["top"][:2]):
            f.write(f"  CAND{j} total={t['total']} T={t['s_title']} A={t['s_author']} Y={t['s_year']} J={t['s_journal']} V={t['s_vip']} c999={t['c999']} rec={t['rec']}\n")
            f.write(f"     {t['title']} | {t['subtitle']} | {t['title_en']}\n     {t['authors']} {t['year']} {t['journal']} [{t['type']}]\n")
        f.write("\n")
json.dump([dict(i=i, cited_work_pk=m["cited_work_pk"], stratum=m["stratum"], band=m["band"], cls=m["cls"]) for i, m in enumerate(sample)],
          open(OUT + "a1_sample.json", "w"), indent=0)
print(len(sample))
