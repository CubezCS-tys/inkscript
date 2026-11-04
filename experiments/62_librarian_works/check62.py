"""Experiment 62, step 5a: hard consistency checks over the librarian's standing decisions (no judgement: rules a
reviewer would apply blindly). Each finding is a case to look at; the README says which were real errors.

1. transitivity: two cards that end in one work although a standing decision says they are different works;
2. authors: one work whose cards print authors with nothing in common (surnames, either script);
3. death dates: one work whose cards give their authors death years more than 5 years apart;
4. years: one work whose citations' years span more than 150 years (works other than classical books) or more
   than 8 years for journal articles and theses;
5. type: one work holding both a thesis and a journal article (an article drawn from a thesis is a relation);
6. catalogue: one work linked to two Mandumah records with unlike titles; one record linked from two works.

    python3 check62.py   -> out/checks62.json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from norm62 import author_relation, name_words, title_sim, tokens  # noqa: E402


def main():
    import finalize62 as F
    cards = {json.loads(l)["cited_work_id"]: json.loads(l) for l in open(OUT / "cards62.jsonl", encoding="utf-8")}
    D = F.standing()
    # rebuild the union exactly as finalize62 does (pairs only; splits by group)
    split = {d["subject_keys"][0]: d["decision"]["groups"] for d in D
             if d["level"] == "card" and d["kind"] == "split_card" and d["decision"].get("groups")}
    uf = F.UF()
    pairs = [d for d in D if d["level"] == "pair"]
    for d in pairs:
        if d["kind"] in ("same_work", "edition_of"):
            uf.union(d["subject_keys"][0], d["subject_keys"][1])
    groups = defaultdict(set)
    for d in pairs:
        for c in d["subject_keys"]:
            groups[uf.find(c)].add(c)
    find = []
    diff = {tuple(sorted(d["subject_keys"])): d for d in pairs if d["kind"] == "different_work"}

    def authors(cid):
        c = cards[cid]
        au, sur = set(), set()
        for m in c["members"]:
            for x in ((m["parsed"] or {}).get("authors") or []):
                if isinstance(x, list) and x:
                    au |= name_words(" ".join(y for y in x if y))
                    sur |= name_words(x[0])
        for a in c["authors"]:
            au |= name_words(a["printed"])
        return au, sur or au

    def years(cid):
        ys = []
        for m in cards[cid]["members"]:
            for y in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", str((m["parsed"] or {}).get("year") or "")):
                ys.append(int(y))
        return ys
    cat = {}
    for d in D:
        if d["level"] == "catalogue" and d["kind"] == "links_to_publication":
            t = d["decision"].get("target") or {}
            if t.get("c999"):
                cat[d["subject_keys"][0]] = t
    for root, cs in groups.items():
        if len(cs) < 2:
            continue
        cs = sorted(cs)
        for a, b in combinations(cs, 2):
            if (a, b) in diff:
                find.append(dict(check="transitivity", work=root, cards=[a, b], why="joined through other cards, "
                                 "though a decision says they are different works", decision=diff[(a, b)]["decision_id"]))
            (A, SA), (B, SB) = authors(a), authors(b)
            if A and B and author_relation(A, B, SA, SB) == "contradict":
                find.append(dict(check="authors", work=root, cards=[a, b], why=f"authors with nothing in common: "
                                 f"{sorted(SA)[:3]} / {sorted(SB)[:3]}"))
        dh = {c: [a["died_hijri"] for a in cards[c]["authors"] if a.get("died_hijri")] for c in cs}
        flat = [(c, y) for c, ys in dh.items() for y in ys]
        if flat and max(y for _, y in flat) - min(y for _, y in flat) > 5:
            find.append(dict(check="death dates", work=root, cards=cs, why=f"death years {sorted({y for _, y in flat})}"))
        ys = [y for c in cs for y in years(c)]
        types = {cards[c]["pub_type"] for c in cs}
        if ys:
            span = max(ys) - min(ys)
            if (span > 150 and not types <= {"book", "chapter", "other"}) or (span > 8 and types <= {"journal", "thesis"}):
                find.append(dict(check="years", work=root, cards=cs, why=f"years {min(ys)}–{max(ys)}, types {sorted(types)}"))
        if "thesis" in types and "journal" in types:
            find.append(dict(check="type", work=root, cards=cs, why="a thesis and a journal article in one work"))
        links = {c: cat[c] for c in cs if c in cat}
        tl = list(links.values())
        for x, y in combinations(tl, 2):
            if x["c999"] != y["c999"] and title_sim(tokens(x.get("title")), tokens(y.get("title")))["dice"] < 0.6:
                find.append(dict(check="catalogue", work=root, cards=sorted(links), why=f"two unlike records: "
                                 f"{x['c999']} «{x.get('title')}» / {y['c999']} «{y.get('title')}»"))
    by_rec = defaultdict(set)
    for cid, t in cat.items():
        by_rec[t["c999"]].add(uf.find(cid) if cid in uf.p else cid)
    for rec, roots in by_rec.items():
        if len(roots) >= 2:
            find.append(dict(check="catalogue", work=None, cards=sorted(c for c, t in cat.items() if t["c999"] == rec),
                             why=f"record {rec} linked from {len(roots)} works"))
    out = dict(findings=find, by_check={k: sum(1 for f in find if f["check"] == k) for k in
                                         ("transitivity", "authors", "death dates", "years", "type", "catalogue")})
    (OUT / "checks62.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out["by_check"])
    for f in find:
        print(f["check"], f["cards"][:4], f["why"][:150])


if __name__ == "__main__":
    main()
