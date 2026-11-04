"""C1f. Self-citation in the 600: platform v2's view v_author_self_citations (a cited work's author and a byline author
of the citing article share one person id), with the evidence to judge each: the byline as printed, the citation as
printed (stem, page, note), and how the cited author was linked. Read-only; writes c1_selfcite.json."""
import json
from common48c import RUNS600, pcon, save, progress
p = pcon()
rows = []
for r in p.execute(f"""SELECT DISTINCT s.citing_pub_id, s.person_id, s.cited_work_pk, d.stem, v.run, w.title, w.year_printed
                      FROM v_author_self_citations s JOIN documents d ON d.pub_id = s.citing_pub_id
                      JOIN versions v ON v.stem = d.stem AND v.is_current = 1 AND v.run IN {RUNS600}
                      JOIN cited_works w ON w.cited_work_pk = s.cited_work_pk ORDER BY d.stem"""):
    r = dict(r)
    r["byline"] = [x[0] for x in p.execute("""SELECT b.printed FROM authorships a JOIN authorship_mentions am USING (authorship_pk)
                     JOIN byline_mentions b USING (mention_pk) WHERE a.pub_id = ? AND a.person_id = ?""",
                                            (r["citing_pub_id"], r["person_id"]))]
    r["authorship_method"] = [x[0] for x in p.execute("SELECT method FROM authorships WHERE pub_id = ? AND person_id = ?",
                                                      (r["citing_pub_id"], r["person_id"]))]
    r["cited_authors"] = [dict(x) for x in p.execute("SELECT printed, match_method, person_id = ? same FROM cited_work_authors "
                                                     "WHERE cited_work_pk = ? ORDER BY seq", (r["person_id"], r["cited_work_pk"]))]
    c = p.execute("""SELECT c.printed, c.page, c.container_id, c.mention_id FROM cited_work_members m
                     JOIN citation_mentions c ON c.mention_pk = m.full_mention_pk JOIN versions v USING (version_id)
                     WHERE m.cited_work_pk = ? AND v.stem = ? AND v.is_current = 1 LIMIT 1""",
                  (r["cited_work_pk"], r["stem"])).fetchone()
    r["citation"] = dict(c) if c else None
    rows.append(r)
save("c1_selfcite.json", rows)
progress(f"- c1_selfcite.py: {len(rows)} self-citation rows in the 600, {len({(r['stem'], r['person_id']) for r in rows})} article-person pairs")
for i, r in enumerate(rows):
    print(i, r["stem"], "| byline:", r["byline"], r["authorship_method"], "| cited:", [(a["printed"], a["match_method"]) for a in r["cited_authors"] if a["same"]])
    print("    ", (r["citation"] or {}).get("page"), (r["citation"] or {}).get("container_id"), ((r["citation"] or {}).get("printed") or r["title"] or "")[:220])
