"""Recall check on Arabic-script catalogue-type works with no link (seed 4801, after the other draws): for each, every
catalogue record carrying a rare word of the cited author's name, listed for a person (here: the agent) to read."""
import json, random, re, sys
sys.path.insert(0, "/home/appuser/inkscript/experiments/45_marc_db")
from build45 import fold
from q import marc
from match import toks, name_toks, COMMON, Matcher
OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
W = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")}
M = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "matches.jsonl", encoding="utf-8")}
D = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "decisions.jsonl", encoding="utf-8")}
seen = set()
for f in ("a1_sample.json", "a1b_sample.json", "a1c_sample.json"):
    seen |= {s["cited_work_pk"] for s in json.load(open(OUT + f))}
AR = re.compile(r"[؀-ۿ]")
pool = sorted(k for k, d in D.items() if d["decision"] == "none" and d["cls"] in ("journal_article", "thesis", "conference_paper")
              and k not in seen and AR.search(M[k]["title"] or "") and len(toks(M[k]["title"])) >= 3 and M[k]["authors"])
rng = random.Random(4801); [rng.random() for _ in range(3)]
S = rng.sample(pool, 20)
mt = Matcher(); m = mt.m
with open(OUT + "recall_ar.txt", "w", encoding="utf-8") as f:
    f.write(f"pool {len(pool)}\n")
    for i, k in enumerate(S):
        w = W[k]; rep = max(w["members"], key=lambda x: len(x["printed"] or ""))
        f.write(f"#{i} {M[k]['cls']} {w['cited_work_id']} {rep['stem']} p{rep['page']} {rep['container_id']}\n  CITED: {rep['printed']}\n")
        nts = sorted({t for a in M[k]["authors"][:2] for t in name_toks(a) if t not in COMMON and len(t) >= 3},
                     key=lambda t: mt.docfreq(t))
        nts = [t for t in nts if mt.docfreq(t) > 0][:2]
        if not nts:
            f.write("  (no rare author word)\n\n"); continue
        q = "authors: (" + " AND ".join('"%s"' % t for t in nts) + ")"
        recs = [r[0] for r in m.execute("select rowid from fts where fts match ? limit 60", (q,))]
        f.write(f"  query {q}: {len(recs)} records\n")
        tk = set(toks(M[k]["title"]))
        rows = []
        for rec in recs:
            r = m.execute("select c999,title,subtitle,year_int,journal,type from records where rec=?", (rec,)).fetchone()
            ov = len(tk & set(toks((r[1] or "") + " " + (r[2] or "")))) / max(1, len(tk))
            rows.append((ov, r))
        for ov, r in sorted(rows, key=lambda x: -x[0])[:4]:
            f.write(f"    {ov:.2f} {r}\n")
        f.write("\n")
print(len(pool))
