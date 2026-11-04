"""Second draws for A1 (seed 4801, after the first sample): 30 accepted links under decide.py (fresh, not in the first
sample), 10 candidates, 20 'no link' works of catalogue types with ≥ 3-word titles (recall check: searched by hand),
and 30 of link47's accepted links."""
import json, random, sys
from match import toks
from q import marc
MC = marc()
OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
W = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")}
M = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "matches.jsonl", encoding="utf-8")}
D = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "decisions.jsonl", encoding="utf-8")}
first = {s["cited_work_pk"] for s in json.load(open(OUT + "a1_sample.json"))}
rng = random.Random(4801); rng.random()
HOLD = {"journal_article", "thesis", "conference_paper"}
acc = sorted(k for k, d in D.items() if d["decision"] == "accept" and k not in first)
cand = sorted(k for k, d in D.items() if d["decision"] == "candidate" and k not in first)
none = sorted(k for k, d in D.items() if d["decision"] == "none" and d["cls"] in HOLD and k not in first
              and len(toks(M[k]["title"])) >= 3)
l47 = sorted(k for k, w in W.items() if any(l["status"] == "accepted" for l in w["links47"]))
S = [("accept", k) for k in rng.sample(acc, 30)] + [("candidate", k) for k in rng.sample(cand, 10)] + \
    [("none", k) for k in rng.sample(none, 20)] + [("link47", k) for k in rng.sample(l47, 30)]
with open(OUT + "a1b_sample.txt", "w", encoding="utf-8") as f:
    for i, (g, k) in enumerate(S):
        w, m, d = W[k], M[k], D[k]
        rep = max(w["members"], key=lambda x: len(x["printed"] or ""))
        f.write(f"#{i} [{g}] {m['cls']} {w['cited_work_id']} {rep['stem']} p{rep['page']} {rep['container_id']} -> mine: {d['decision']} {d['c999']} {d['why']}\n")
        f.write(f"  CITED: {rep['printed']}\n  title={m['title']!r} authors={m['authors'][:2]} years={m['years']}\n")
        if g == "link47":
            l = [l for l in w["links47"] if l["status"] == "accepted"][0]
            r = MC.execute("select rec, title, subtitle, year_int, journal, type from records where c999=?", (l['c999'],)).fetchone()
            au = [a[0] for a in MC.execute("select name from authors where rec=? order by seq", (r[0],))][:3]
            f.write(f"  LINK47 -> c999={l['c999']} score={l['score']}: {r[1]} | {r[2]} | {au} {r[3]} {r[4]} [{r[5]}]\n")
        for t in m["top"][:2]:
            f.write(f"  CAND c999={t['c999']} total={t['total']} T={t['s_title']} A={t['s_author']} Y={t['s_year']} J={t['s_journal']} V={t['s_vip']}\n")
            f.write(f"     {t['title']} | {t['subtitle']} | {(t['title_en'] or '')[:90]}\n     {t['authors'][:3]} {t['year']} {t['journal']} [{t['type']}]\n")
        f.write("\n")
json.dump([dict(i=i, group=g, cited_work_pk=k) for i, (g, k) in enumerate(S)], open(OUT + "a1b_sample.json", "w"), indent=0)
print(len(S), len(acc), len(cand), len(none), len(l47))
