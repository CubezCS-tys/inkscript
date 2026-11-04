"""Experiment 64, step 4: the institution numbers of a release, measured the way experiment 56 measured its "after"
(finalize56.py: every organisation-level link of an affiliation counts; gate 1 = journal J0130 against 20 random sets
of its size, seed 5250), and the way the Desk's index pages show them (desk.index_pages: overview, /institutions,
gate 1 with experiment 52's measure52, which counts an affiliation's first organisation only). Read-only.

    cd experiments/49_correction_desk
    .venv/bin/python ../64_apply_institutions/measure64.py BEFORE.db AFTER.db [--out out/numbers64.json]
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "49_correction_desk"))
from desk import index_pages  # noqa: E402

GATE1 = "J0130"
E56 = HERE.parent / "56_librarian_institutions" / "out"


def measure(path: Path) -> dict:
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    stems = {r[0]: dict(run=r[1], level=r[2], journal_id=r[3]) for r in c.execute(
        """SELECT v.stem, v.run, d.level, p.journal_id FROM versions v JOIN documents d ON d.stem = v.stem
           LEFT JOIN publications p ON p.pub_id = d.pub_id WHERE v.is_current = 1""")}
    tw = (" WHERE am.twin_of_aff_pk IS NULL" if "twin_of_aff_pk" in   # experiment 68: twins are not counted twice
          {r[1] for r in c.execute("PRAGMA table_info(affiliation_mentions)")} else "")
    affs = c.execute("""SELECT am.aff_pk, v.stem FROM affiliation_mentions am JOIN byline_mentions b USING (mention_pk)
                        JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1""" + tw).fetchall()
    links = defaultdict(lambda: defaultdict(list))
    for a, i, lvl in c.execute("SELECT aff_pk, inst_id, level FROM affiliation_links"):
        links[a][lvl].append(i)
    country = {r[0]: r[1] for r in c.execute("SELECT inst_id, country_code FROM institutions")}

    def m(keep):
        arts = defaultdict(set)
        linked = 0
        for a, s in affs:
            if s not in keep:
                continue
            os_ = links[a]["org"]
            linked += bool(os_)
            for o in os_:
                arts[o].add(s)
        return arts, linked
    allst = set(stems)
    arts, linked = m(allst)
    with_c = sum(1 for i in arts if country.get(i))
    aff_c = sum(1 for a, s in affs if any(country.get(o) for o in links[a]["org"]))
    jst = {s for s, x in stems.items() if x["journal_id"] == GATE1}
    runs = sorted({x["run"] for s, x in stems.items() if x["journal_id"] != GATE1 and x["level"] == "final"})
    pool = sorted(s for s, x in stems.items() if x["run"] in runs)
    rnd = random.Random(5250)
    draws = [set(rnd.sample(pool, len(jst))) for _ in range(20)]

    def two(keep):
        a, _ = m(keep)
        return sum(1 for v in a.values() if len(v) >= 2)
    rs = [two(d) for d in draws]
    out = dict(articles=len(stems), affiliations=len(affs), institutions=len(arts),
               institutions_2plus_articles=sum(1 for v in arts.values() if len(v) >= 2),
               affiliations_with_institution=linked, institutions_with_country=with_c,
               share_institutions_with_country=round(with_c / max(1, len(arts)), 3),
               affiliations_with_country=aff_c,
               links_former=sum(len(v["former"]) for v in links.values()),
               links_educated_at=sum(len(v["educated_at"]) for v in links.values()),
               gate1=dict(journal=two(jst), random_same_size=round(sum(rs) / len(rs), 2), random_range=[min(rs), max(rs)],
                          journal_distinct=len(m(jst)[0])))
    # the index pages, as the Desk shows them
    ov = index_pages.overview(path)
    nums = {n["key"]: n["value"] for n in ov.get("numbers", ov.get("nums", []))} if isinstance(ov, dict) else {}
    g = index_pages.gate1(path)
    row = {r["key"]: r for r in g["rows"]}["insts2"]
    out["index_pages"] = dict(overview_institutions=nums.get("institutions"),
                              institutions_list=len(index_pages.institutions(path, 1000)),
                              gate1_insts2=dict(journal=row["journal"], random=row["random"],
                                                random_same_size=row["random_same_size"]))
    return out, set(arts)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--out", default=str(HERE / "out" / "numbers64.json"))
    a = ap.parse_args(argv)
    b, bset = measure(Path(a.before))
    f, fset = measure(Path(a.after))
    e56 = json.loads((E56 / "numbers56.json").read_text(encoding="utf-8"))
    # which linked institutions the authority does not hold (the machine's rows the 10 unsure affiliations keep)
    con = sqlite3.connect(f"file:{a.after}?mode=ro", uri=True)
    lab = {}
    for i, n in con.execute("SELECT inst_id, name FROM institution_names ORDER BY (type = 'label') DESC, n_seen DESC"):
        lab.setdefault(i, n)
    desk_rows = {r[0] for r in con.execute("SELECT DISTINCT inst_id FROM institution_names WHERE source = 'desk'")}
    res = dict(before=dict(release=Path(a.before).name, **b), after=dict(release=Path(a.after).name, **f),
               exp56_after=e56["after"], exp56_before=e56["before"],
               after_rows_without_librarian_record=sorted((i, lab.get(i)) for i in fset - desk_rows))
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
