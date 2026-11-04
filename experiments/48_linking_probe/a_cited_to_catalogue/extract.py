"""Step 1: dump every active cited work with its members, authors, mention counts and link47 outcome."""
import json, sqlite3, collections
from q import pv
OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/works.jsonl"
con = pv(); con.row_factory = sqlite3.Row
nm = {r[0]: (r[1], r[2], r[3]) for r in con.execute(
    "select cited_work_pk, count(*), count(distinct citing_pub_id), sum(kind='full') from v_mention_work where cited_work_pk is not null group by 1")}
authors = collections.defaultdict(list)
for r in con.execute("select cited_work_pk, seq, printed, latin, authority_id from cited_work_authors order by 1,2"):
    authors[r[0]].append(dict(printed=r[2], latin=r[3], authority_id=r[4]))
members = collections.defaultdict(list)
for r in con.execute("""select m.cited_work_pk, c.mention_pk, c.mention_id, v.stem, c.page, c.container_kind, c.container_id,
        c.printed, c.parsed from cited_work_members m join citation_mentions c on c.mention_pk=m.full_mention_pk
        join versions v using(version_id) where v.is_current=1 order by c.mention_id"""):
    members[r[0]].append(dict(mention_pk=r[1], mention_id=r[2], stem=r[3], page=r[4], container_kind=r[5],
                              container_id=r[6], printed=r[7], parsed=json.loads(r[8]) if r[8] else None))
links = collections.defaultdict(list)
for r in con.execute("""select l.cited_work_pk, l.status, l.best, l.score, l.method, l.target_pub_id, p.c999, l.evidence
        from citation_links l left join publications p on p.pub_id=l.target_pub_id"""):
    links[r[0]].append(dict(status=r[1], best=r[2], score=r[3], method=r[4], target_pub_id=r[5], c999=r[6]))
rels = collections.defaultdict(list)
for r in con.execute("select subject_cited_work_pk, relation, object_pub_id, score from work_relations"):
    rels[r[0]].append(dict(relation=r[1], object_pub_id=r[2], score=r[3]))
n = 0
with open(OUT, "w", encoding="utf-8") as f:
    for r in con.execute("select * from cited_works where status='active'"):
        d = dict(r); pk = d["cited_work_pk"]
        d["n_mentions"], d["n_citing"], d["n_full"] = nm.get(pk, (0, 0, 0))
        d["authors"] = authors[pk]; d["members"] = members[pk]; d["links47"] = links[pk]; d["relations47"] = rels[pk]
        f.write(json.dumps(d, ensure_ascii=False) + "\n"); n += 1
print(n, "works;", sum(v[0] for v in nm.values()), "mentions on cards")
