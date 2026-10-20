"""Experiment 46: a reproducible random sample of links for a hand check (printed string beside the target)."""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common46 import connect, marc  # noqa: E402

PLAN = [("catalogue", "catalogue-fts", 25), ("catalogue", "catalogue-about", 4), ("work", "backref-author", 6),
        ("work", "backref-author-title", 6), ("work", "backref-previous", 8), ("work", "backref-title", 5)]


def main():
    con, m = connect(), marc()
    rnd = random.Random(2026)
    out = []
    for tk, meth, n in PLAN:
        q = "SELECT * FROM citation_links WHERE target_kind = ?" + (" AND method = ?" if meth else "") + \
            " ORDER BY from_kind, from_id, target_id"
        rows = con.execute(q, (tk, meth) if meth else (tk,)).fetchall()
        for l in rnd.sample(rows, min(n, len(rows))):
            ev = json.loads(l["evidence"] or "{}")
            item = dict(from_kind=l["from_kind"], from_id=l["from_id"], target_kind=tk, target_id=l["target_id"],
                        method=l["method"], score=l["score"])
            if l["from_kind"] == "work":
                w = con.execute("SELECT * FROM works WHERE work_id = ?", (l["from_id"],)).fetchone()
                item["cited"] = dict(authors=w["authors"], title=w["article_title"] or w["chapter_title"],
                                     source=w["source_title"], year=w["year"], type=w["pub_type"],
                                     printed=(w["printed"] or "")[:400])
            else:
                b = con.execute("SELECT * FROM back_references WHERE backref_id = ?", (l["from_id"],)).fetchone()
                item["cited"] = dict(note=(b["printed"] or "")[:300])
            if tk == "catalogue":
                r = m.execute("SELECT title, subtitle, year_int, journal, type FROM records WHERE rec = ?",
                              (int(l["target_id"]),)).fetchone()
                au = [a[0] for a in m.execute("SELECT name FROM authors WHERE rec = ? ORDER BY seq",
                                              (int(l["target_id"]),))]
                item["target"] = dict(title=r["title"], subtitle=r["subtitle"], year=r["year_int"],
                                      journal=r["journal"], type=r["type"], authors=au)
            elif tk == "article":
                a = con.execute("SELECT title, pub_year FROM articles WHERE stem = ?", (l["target_id"],)).fetchone()
                au = [x[0] for x in con.execute("SELECT printed_name FROM article_authors WHERE stem = ?",
                                                (l["target_id"],))]
                item["target"] = dict(title=a["title"], year=a["pub_year"], authors=au)
            else:
                w = con.execute("SELECT * FROM works WHERE work_id = ?", (l["target_id"],)).fetchone()
                item["target"] = dict(authors=w["authors"], title=w["article_title"] or w["chapter_title"],
                                      source=w["source_title"], year=w["year"], note=w["container_id"],
                                      printed=(w["printed"] or "")[:250])
            out.append(item)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
