"""Experiment 74 (from persons72.py), persons: obvious same-person cases among the people who sign the journal's
(LIB74_J) articles (read-only; nothing is asked of a model). Nothing is applied from here: a pair read by hand as one
person goes into OUT/persons_apply.json ([{"keep": "person:..", "other": "person:..", "why": ".."}]), which plan74 reads. The Desk's existing operation is `same_person` (two person ids are one person).

A pair is proposed when two active person ids, at least one signing an article of the journal, carry the same full name once
folded (hamza / alef / ya / taa marbuta, «ال», «عبد ال…» spacing, punctuation, honorifics), the name has 3+ words,
and nothing contradicts: they never sign the same article, and a body their statements name is shared (or one of
them has no statement). "Obvious" is read by hand (`out/persons/pairs.txt`); only pairs read as one person are applied.

    python persons74.py     -> OUT/persons/pairs.json, OUT/persons/pairs.txt
"""
from __future__ import annotations

import re
from collections import defaultdict

from common74 import E56, JOURNAL, OUT, add_paths, ro, wjs

add_paths(E56.parent / "46_platform_db")
from common46 import key  # noqa: E402

HON = {"د", "دكتور", "الدكتور", "أ", "ا", "اد", "أد", "الاستاذ", "الأستاذ", "استاذ", "م", "dr", "prof", "pr", "mr", "mrs",
       "ms", "الشيخ", "السيد", "السيده", "السيدة"}


def nkey(s: str) -> str:
    k = key(s or "")
    k = re.sub(r"\bعبد\s+ال", "عبدال", k)
    k = re.sub(r"\bابو\s+", "ابو", k)
    ws = [re.sub(r"^ال(?=\S{3})", "", w) for w in k.split() if w not in HON and len(w) > 1]
    return " ".join(ws)


def main():
    con = ro()
    names = defaultdict(set)
    for r in con.execute("SELECT person_id, full_form FROM person_names"):
        names[r[0]].add(r[1])
    for r in con.execute("SELECT person_id, preferred_name_ar, preferred_name_lat FROM persons WHERE status != 'merged'"):
        for n in (r[1], r[2]):
            if n:
                names[r[0]].add(n)
    status = {r[0]: r[1] for r in con.execute("SELECT person_id, status FROM persons")}
    arts = defaultdict(set)
    for r in con.execute("""SELECT a.person_id, v.stem FROM authorships a JOIN authorship_mentions am USING (authorship_pk)
                            JOIN byline_mentions b ON b.mention_pk = am.mention_pk
                            JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1
                            WHERE a.person_id IS NOT NULL"""):
        arts[r[0]].add(r[1])
    bodies = defaultdict(set)
    for r in con.execute("""SELECT a.person_id, al.inst_id FROM authorships a JOIN authorship_mentions am USING (authorship_pk)
                            JOIN affiliation_mentions af ON af.mention_pk = am.mention_pk
                            JOIN affiliation_links al ON al.aff_pk = af.aff_pk AND al.level = 'org'
                            WHERE a.person_id IS NOT NULL"""):
        bodies[r[0]].add(r[1])
    mine = {p for p, s in arts.items() if any(x.startswith(JOURNAL + "-") for x in s)}
    by = defaultdict(set)
    for p, ns in names.items():
        if status.get(p) == "merged":
            continue
        for n in ns:
            k = nkey(n)
            if len(k.split()) >= 3:
                by[k].add(p)
    pairs = []
    for k, ps in sorted(by.items()):
        ps = sorted(ps)
        if len(ps) < 2 or not (set(ps) & mine):
            continue
        for i, a in enumerate(ps):
            for b in ps[i + 1:]:
                if not ({a, b} & mine):
                    continue
                if arts[a] & arts[b]:
                    why = "contradicted: both sign one article"
                elif bodies[a] and bodies[b] and not (bodies[a] & bodies[b]):
                    why = "different bodies"
                else:
                    why = "candidate"
                pairs.append(dict(key=k, a=a, b=b, names_a=sorted(names[a])[:3], names_b=sorted(names[b])[:3],
                                  arts_a=sorted(arts[a])[:6], arts_b=sorted(arts[b])[:6], bodies_a=sorted(bodies[a]),
                                  bodies_b=sorted(bodies[b]), status=[status.get(a), status.get(b)], why=why))
    wjs(OUT / "persons" / "pairs.json", pairs)
    with open(OUT / "persons" / "pairs.txt", "w", encoding="utf-8") as f:
        for x in pairs:
            f.write(f"{x['why']}: {x['a']} {x['names_a']} {x['arts_a']} {x['bodies_a']}\n"
                    f"      {x['b']} {x['names_b']} {x['arts_b']} {x['bodies_b']}\n")
    from collections import Counter
    print(len(pairs), Counter(x["why"] for x in pairs))


if __name__ == "__main__":
    main()
