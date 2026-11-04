"""Dump every active cited-work card with its members and the mentions that count for it (read-only)."""
import json
from collections import defaultdict
from db import con, OUT
c = con()
cards = {r["cited_work_pk"]: dict(r) for r in c.execute("select * from cited_works where status='active'")}
mem = defaultdict(list)
for r in c.execute("""select cm.cited_work_pk, cm.method, cm.evidence, m.mention_pk, m.mention_id, m.kind, m.printed,
                      m.parsed, m.container_kind, m.container_id, m.page, v.stem, v.run
                      from cited_work_members cm join citation_mentions m on m.mention_pk = cm.full_mention_pk
                      join versions v using(version_id)"""):
    mem[r["cited_work_pk"]].append(dict(r))
pk2card = {m["mention_pk"]: k for k, ms in mem.items() for m in ms}
extra = defaultdict(lambda: defaultdict(int))
for r in c.execute("""select m.full_mention_pk, m.kind from citation_mentions m join versions v using(version_id)
                      where v.is_current=1 and m.full_mention_pk is not null and m.full_mention_pk <> m.mention_pk"""):
    k = pk2card.get(r[0])
    if k: extra[k][r[1]] += 1
out = []
for k, cd in cards.items():
    ms = mem.get(k, [])
    cd["members"] = ms
    cd["n_members"] = len(ms)
    cd["n_pubs"] = len({m["stem"] for m in ms})
    cd["n_resolved_to"] = dict(extra[k])
    cd["n_mentions"] = len(ms) + sum(extra[k].values())
    out.append(cd)
json.dump(out, open(f"{OUT}/cards_dump.json", "w"), ensure_ascii=False)
print(len(out), sum(x["n_members"] for x in out))
