"""Experiment 54 step 2: which journals does journal 0130 cite? Read-only on platform_v2.db.
(a) accepted best citation_links from 0130 articles to catalogued articles -> target journal code;
(b) the parsed 'source' of every full journal-like reference, counted by name. -> out/cited_by_0130.json"""
import collections, json, sqlite3, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
DB = sys.argv[1] if len(sys.argv) > 1 else "/home/appuser/data/platform_v2/platform_v2.db"
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
vers = [v for (v,) in c.execute("select version_id from versions where stem like '0130-%' and is_current = 1")]
print(len(vers), "current 0130 versions")
q = ",".join("?" * len(vers))
links = collections.Counter(); link_arts = collections.defaultdict(set)
for stem, jid, cr in c.execute(f"""
    select v.stem, p.journal_id, p.c999 from citation_mentions m join versions v on v.version_id = m.version_id
    join cited_work_members w on w.full_mention_pk = m.mention_pk
    join citation_links l on l.cited_work_pk = w.cited_work_pk and l.status = 'accepted' and l.best = 1
    join publications p on p.pub_id = l.target_pub_id
    where m.version_id in ({q}) and m.kind = 'full'""", vers):
    code = (jid or "")[1:] or "-"
    links[code] += 1; link_arts[code].add(stem)
sources = collections.Counter(); n_full = 0
for (parsed,) in c.execute(f"select parsed from citation_mentions where version_id in ({q}) and kind = 'full'", vers):
    n_full += 1
    try: d = json.loads(parsed or "{}")
    except Exception: continue
    if d.get("pub_type") == "journal" and d.get("source_title"):
        sources[str(d["source_title"]).strip()] += 1
out = dict(db=DB, versions=len(vers), full_mentions=n_full,
           links_by_journal={k: dict(links=v, articles=len(link_arts[k])) for k, v in links.most_common()},
           sources_top=sources.most_common(400))
(HERE / "out/cited_by_0130.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(n_full, "full;", sum(links.values()), "links", links.most_common(40))
print(sources.most_common(60))
