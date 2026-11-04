"""C1f-2. Self-citations the view misses: in each of the 600, a cited author whose given name and surname equal a
byline author's (both folded, «ال» ignored, «Surname, Given» turned round), but who is not linked to the same person."""
import json, re
from collections import defaultdict
from common48c import OUT, RUNS600, given_surname, pcon, save, progress
p = pcon()
def gs(n):
    g, s = given_surname(n or "")
    f = lambda x: re.sub(r"^ال", "", x or "")
    return (f(g), f(s)) if g and s else None
by = json.load(open(OUT / "c1_bylines.json"))
names = defaultdict(list)
for r in by:
    for n in r["printed"]:
        k = gs(n)
        if k: names[r["pub_id"]].append((k, r["person_id"], n))
view = {(r["stem"], r["person_id"]) for r in json.load(open(OUT / "c1_selfcite.json"))}
out = []
for r in p.execute(f"""SELECT DISTINCT d.pub_id, v.stem, ca.cited_work_pk, ca.printed, ca.person_id, w.title
                       FROM cited_work_authors ca JOIN cited_work_members m ON m.cited_work_pk = ca.cited_work_pk
                       JOIN citation_mentions c ON c.mention_pk = m.full_mention_pk
                       JOIN versions v ON v.version_id = c.version_id AND v.is_current = 1 AND v.run IN {RUNS600}
                       JOIN documents d ON d.stem = v.stem JOIN cited_works w ON w.cited_work_pk = ca.cited_work_pk"""):
    k = gs(r["printed"])
    if not k: continue
    for bk, pid, bn in names.get(r["pub_id"], []):
        if bk == k and r["person_id"] != pid:
            out.append(dict(stem=r["stem"], byline=bn, cited=r["printed"], title=r["title"], in_view=(r["stem"], pid) in view))
save("c1_selfcite_missed.json", out)
progress(f"- c1_selfcite_missed.py: {len(out)} name-equal cited authors not linked to the byline person")
for x in out: print(x)
