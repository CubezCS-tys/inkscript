"""Experiment 67, step 4: the numbers of a release, measured the way experiment 62's finalize62 measured its
"after" (so the two can be compared), and the index pages' own numbers on the same file (read-only).

- cited works: distinct cards the 780 articles' references land on (v_mention_work: Quran and hadith out);
- cited by 2+ / 3+ articles;
- gate 1: the journal's (J0130) works cited by 2+ of its articles vs 20 random same-size sets from the 600
  (seed 5250, as finalize62);
- held: references whose card has an accepted best link to a publication (all / the journal / the random 600).

    cd experiments/49_correction_desk
    .venv/bin/python ../67_apply_works/measure67.py BEFORE.db AFTER.db   -> out/numbers67.json
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESK = HERE.parent / "49_correction_desk"
E62O = HERE.parent / "62_librarian_works" / "out"
sys.path.insert(0, str(DESK))
GATE1 = "J0130"
RANDOM_RUNS = ("v33_300_final_lettersfix", "v33_300b_fix3_lettersfix")


def measure(path: str) -> dict:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    arts = json.loads((E62O / "articles62.json").read_text(encoding="utf-8"))
    rows = con.execute("SELECT stem, citing_pub_id, cited_work_pk FROM v_mention_work").fetchall()
    best = {r[0]: r[1] for r in con.execute("SELECT cited_work_pk, target_pub_id FROM citation_links WHERE status = "
                                            "'accepted' AND best = 1 AND target_kind = 'publication'")}
    title = {r[0]: (r[1], r[2]) for r in con.execute("SELECT cited_work_pk, cited_work_id, title FROM cited_works")}
    stems_j = {s for s, a in arts.items() if a["journal_id"] == GATE1}
    pool = sorted(s for s, a in arts.items() if a["run"] in RANDOM_RUNS)

    def works(stems):
        pubs = defaultdict(set)
        ment = Counter()
        for st, pub, w in rows:
            if st in stems and w is not None:
                pubs[w].add(pub)
                ment[w] += 1
        return pubs, ment

    def held(stems):
        ms = [r for r in rows if r[0] in stems]
        h = sum(1 for r in ms if r[2] is not None and r[2] in best)
        return dict(mentions=len(ms), held=h, share=round(h / max(1, len(ms)), 4))
    allst = set(arts)
    pubs, ment = works(allst)
    j = sum(1 for s in works(stems_j)[0].values() if len(s) >= 2)
    rnd = random.Random(5250)
    rs = [sum(1 for s in works(set(rnd.sample(pool, len(stems_j))))[0].values() if len(s) >= 2) for _ in range(20)]
    top = sorted(pubs, key=lambda w: (-len(pubs[w]), -ment[w], str(w)))[:15]
    return dict(release=Path(path).name, mentions=len(rows), cited_works=len(pubs),
                cited_by_2plus=sum(1 for s in pubs.values() if len(s) >= 2),
                cited_by_3plus=sum(1 for s in pubs.values() if len(s) >= 3),
                gate1=dict(journal=j, random_same_size=round(sum(rs) / len(rs), 2), random_range=[min(rs), max(rs)],
                           random_600=sum(1 for s in works(set(pool))[0].values() if len(s) >= 2),
                           ratio=round(j / max(0.01, sum(rs) / len(rs)), 1)),
                held=dict(all=held(allst), journal=held(stems_j), random600=held(set(pool))),
                top=[dict(id=title[w][0], title=title[w][1], articles=len(pubs[w]), mentions=ment[w]) for w in top])


def explain(path: str) -> dict:
    """Where this release's "after" differs from experiment 62's (which replayed every standing decision): the
    references whose card has an exp 62 link that was held (not K1c), the D44 same-text links, and the works the
    owner's rules and the one conflict changed."""
    sys.path.insert(0, str(E62O.parent))
    from finalize62 import standing
    from rules62 import _k1b, _venue_fits
    from desk.reading import Reading
    R = Reading(sqlite3.connect(f"file:{path}?mode=ro", uri=True))
    con = R.con
    best = {r[0] for r in con.execute("SELECT cited_work_pk FROM citation_links WHERE status = 'accepted' AND best = 1 "
                                      "AND target_kind = 'publication'")}
    refs = Counter(r[0] for r in con.execute("SELECT cited_work_pk FROM v_mention_work WHERE cited_work_pk IS NOT NULL"))
    arts = defaultdict(set)
    for w, pub in con.execute("SELECT cited_work_pk, citing_pub_id FROM v_mention_work WHERE cited_work_pk IS NOT NULL"):
        arts[w].add(pub)
    D = standing()

    def pk(cid):
        c = R.resolve_work(cid)[0]
        return R.card(c)["cited_work_pk"] if c else None
    held_links = {pk(d["subject_keys"][0]) for d in D if d["kind"] == "links_to_publication"
                  and not (_k1b(d) and _venue_fits(d))} - {None}
    out = dict(held_links_cards=len(held_links),
               held_links_refs_not_held_now=sum(refs[w] for w in held_links if w not in best),
               held_links_refs_held_by_another_link=sum(refs[w] for w in held_links if w in best))
    plan = [json.loads(l) for l in open(HERE / "out" / "plan67.jsonl", encoding="utf-8")]
    d44 = {pk(p["subject_keys"][0][5:]) for p in plan if p["reason_code"] == "librarian:D44"} - {None}
    out["d44_same_text_refs_held"] = sum(refs[w] for w in d44 if w in best)

    def works(*cids):
        return {c: dict(card=R.resolve_work(c)[0], articles=len(arts.get(pk(c), ())), references=refs.get(pk(c), 0))
                for c in cids}
    out["d40"] = works("C4EZV38PP2", "CMGAH5Y38J", "CPA8ZNRRSW")
    out["d42"] = works("C2BE7XGM7E", "C7TGVAC7QF")
    out["conflict_CF622F7PED"] = works("CF622F7PED", "CVSFVRG2E8")
    return out


def index_numbers(path: str) -> dict:
    from desk import index_pages
    o = index_pages.overview(Path(path))
    nums = {n["key"]: dict(value=n["value"], sub=n.get("sub")) for n in o["numbers"]}
    return dict(cited_works=nums["cited_works"], held=nums["held"],
                top_works=[(w["title"], w["times_cited"]) for w in o["top_works"]])


def main():
    before, after = sys.argv[1], sys.argv[2]
    n62 = json.loads((E62O / "numbers62.json").read_text(encoding="utf-8"))
    out = dict(before=measure(before), after=measure(after),
               exp62=dict(before={k: v for k, v in n62["before"].items() if k != "top"},
                          after={k: v for k, v in n62["after"].items() if k != "top"}, held=n62["held"]["after"]),
               index_after=index_numbers(after), explain=explain(after))
    (HERE / "out" / "numbers67.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    show = {k: ({x: y for x, y in v.items() if x != "top"} if isinstance(v, dict) else v) for k, v in out.items()}
    print(json.dumps(show, ensure_ascii=False, indent=1))
    print([(t["title"], t["articles"]) for t in out["after"]["top"][:12]])


if __name__ == "__main__":
    main()
