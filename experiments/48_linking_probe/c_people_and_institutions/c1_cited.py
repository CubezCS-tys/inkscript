"""C1e. Cited authors (authors inside the citations of the 600): what share platform v2 links to a person, how many
could be linked by name at all (who in the whole catalogue carries the printed name), and two seeded samples to judge
(seed 4823): 40 of the links made, and 20 unlinked cited authors whose name has exactly one holder in the catalogue
("what if we linked by a unique name?"). Read-only."""
from __future__ import annotations

import json
import random
import re
from collections import Counter

from common48c import (OUT, RUNS600, exact_holders, given_surname, hcon, is_arab, loose_holders, mcon, name_key,
                       pcon, progress, save, split_titles)


def kind_of(printed: str) -> str:
    s = split_titles(printed or "")[1]
    if not s:
        return "empty"
    if re.fullmatch(r"(?:[A-Za-z]\.?\s*){1,3}", s) or re.fullmatch(r"(?:[؀-ۿ]\s*\.\s*){1,3}", s):
        return "initials"
    if re.match(r"^(ابن|إبن|أبو|ابو|أبي|ابي)\s", s) or re.search(r"\(ت\s*\.?|ت\.\s*\d|هـ\)", printed or ""):
        return "classical/kunya/shuhra"
    if not is_arab(s):
        return "latin"
    n = len(s.replace("،", " ").split())
    return "arabic-1-word" if n == 1 else "arabic-2-words" if n == 2 else "arabic-3+-words"


def main():
    p, m, h = pcon(), mcon(), hcon()
    rows = [dict(r) for r in p.execute(f"""
        SELECT ca.cited_work_pk, ca.seq, ca.printed, ca.person_id, ca.authority_id, ca.match_method, ca.match_score,
               w.title, w.pub_type, w.year_printed,
               (SELECT c.mention_pk FROM cited_work_members mm JOIN citation_mentions c ON c.mention_pk = mm.full_mention_pk
                JOIN versions v ON v.version_id = c.version_id AND v.is_current = 1 AND v.run IN {RUNS600}
                WHERE mm.cited_work_pk = ca.cited_work_pk ORDER BY c.mention_pk LIMIT 1) first_mention
        FROM cited_work_authors ca JOIN cited_works w USING (cited_work_pk)""")]
    rows = [r for r in rows if r["first_mention"]]
    EH = exact_holders(h, {name_key(r["printed"]) for r in rows})
    for r in rows:
        r["kind"] = kind_of(r["printed"])
        r["exact_holders"] = len(EH.get(name_key(r["printed"]), ()))
    S = dict(cited_author_rows_600=len(rows), cited_works_600=len({r["cited_work_pk"] for r in rows}),
             linked=sum(1 for r in rows if r["person_id"]), by_method=Counter(r["match_method"] for r in rows),
             kinds=Counter(r["kind"] for r in rows),
             exact_holders=Counter("0" if r["exact_holders"] == 0 else "1" if r["exact_holders"] == 1 else "2-5"
                                   if r["exact_holders"] <= 5 else "6+" for r in rows),
             exact_holders_by_kind={k: dict(Counter("0" if r["exact_holders"] == 0 else "1" if r["exact_holders"] == 1
                                                    else "2+" for r in rows if r["kind"] == k))
                                    for k in sorted({r["kind"] for r in rows})})
    # evidence for judging
    def ev(r):
        c = p.execute("""SELECT c.mention_id, c.printed, c.page, c.container_id, v.stem FROM citation_mentions c
                         JOIN versions v USING (version_id) WHERE c.mention_pk = ?""", (r["first_mention"],)).fetchone()
        e = dict(r, citation=dict(c) if c else None)
        aid = r["authority_id"]
        if not aid and r["person_id"]:
            a = p.execute("SELECT authority_id FROM person_authorities WHERE person_id = ?", (r["person_id"],)).fetchone()
            aid = a[0] if a else None
            if not aid:
                e["person_names"] = [x[0] for x in p.execute("SELECT full_form FROM person_names WHERE person_id = ?",
                                                             (r["person_id"],))][:6]
        e["authority_used"] = aid
        if aid:
            hs = m.execute("SELECT name, latin, count(*) n FROM authors WHERE authority_id = ? GROUP BY name ORDER BY n DESC "
                           "LIMIT 1", (aid,)).fetchone()
            e["authority_heading"] = dict(hs) if hs else None
            e["authority_titles"] = [f"{x[0]} {x[1][:70]}" for x in m.execute(
                "SELECT r.year_int, coalesce(r.title,'') FROM authors a JOIN records r ON r.rec = a.rec WHERE "
                "a.authority_id = ? ORDER BY r.year_int LIMIT 12", (aid,))]
        return e
    rnd = random.Random(4823)
    linked = [r for r in rows if r["person_id"]]
    s1 = [ev(r) for r in rnd.sample(linked, min(40, len(linked)))]
    uniq = [r for r in rows if not r["person_id"] and r["exact_holders"] == 1]
    s2 = []
    for r in rnd.sample(uniq, min(20, len(uniq))):
        r = dict(r, authority_id=next(iter(EH[name_key(r["printed"])])))
        s2.append(ev(r))
    S["unlinked_with_one_holder"] = len(uniq)
    save("c1_cited_summary.json", S)
    save("c1_cited_rows.json", rows)
    save("c1_cited_sample_linked.json", s1)
    save("c1_cited_sample_unique_unlinked.json", s2)
    progress(f"- c1_cited.py: {len(rows)} cited-author rows in the 600, linked {S['linked']}")
    print(json.dumps(S, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
