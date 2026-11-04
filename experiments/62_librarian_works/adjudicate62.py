"""Experiment 62, step 5d: every disagreement between the librarian and the blind second judge, adjudicated against
the printed citations, the body text and the catalogue record, with which side was right; the measured precision
of each decision kind (first pass, Wilson 95% interval); the APPLY rule; the few cases left for the owner.

    python3 adjudicate62.py   -> out/blind62_adjudication.json, out/precision62.json
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))

# bid -> (who was right: librarian | blind | both | neither, verdict, why). "both" = each answer is defensible;
# counted as correct for the librarian. An unsure is never applied, so it is not scored for precision.
VERDICTS = {
    "B009": ("blind", "unsure", "vol. 10 p. 362 fits مجموع الفتاوى; vol. 3 pp. 323-4 on contract conditions fits the "
             "old Cairo «الفتاوى الكبرى», and the citing article predates the Majmu' (1381 h): the two short forms may "
             "be two compilations. Joining them was too bold."),
    "B044": ("blind", "edition_of", "«صحيح مسلم بشرح النووي» is the title al-Nawawi's commentary is printed under; "
             "card B's al-Nawawi citation is «شرح صحيح مسلم»: one work, two printings. (The fix then joined Sahih "
             "Muslim to al-Nawawi through a third decision; the authors check caught it, see escalated case 1.)"),
    "B066": ("blind", "different_work", "as the cards are labelled (B = the article «الاشتقاق ودلالاته»), two works; "
             "B's Ibn Durayd citation is already moved to A by B's split, so the pair needed no unsure."),
    "B067": ("blind", "same_work", "same author, year, journal (مجلة جامعة دمشق) and pages 71-111: one article with "
             "its title worded two ways. The librarian's unsure was over-cautious."),
    "B068": ("both", "unsure", "«op. cit.» points back to the UNESCO 1981 volume; Soundjock may be its editor or a "
             "chapter author: same_work and part_of both fit. Unsure stands."),
    "B069": ("blind", "different_work", "the body text names شوقي ضيف just before «المقامة» p. 8 (his book); «مقدمة "
             "المقامات» p. 7 quotes the preface of an edition of al-Hamadhani: two works."),
    "B070": ("librarian", "split_card", "the bulletin «أصداء نيابوليس» is cited for three named authors' pieces (no. 5 "
             "twice, no. 8, no. 9): the split into those pieces is right; the blind question offered no per-item "
             "option, so the judge answered not_a_work for the bulletin itself."),
    "B093": ("blind", "not_a_work:retitle", "one poem by على الميرملحم in العرفان م47 ج5 ص438: an item whose title "
             "the citation omits, not a bare serial."),
    "B097": ("blind", "not_a_work:drop", "القبس by issue and date, no author, no item title: a serial citation."),
    "B101": ("blind", "not_a_work:drop", "لواء الإسلام by issue only: a serial citation."),
    "B121": ("blind", "relation", "the citation is the 2020 master's thesis; the record is the article drawn from it "
             "with the supervisors: a relation."),
    "B122": ("blind", "unsure", "same title and first author, but different journals (الفيوم 2016 / بحوث ودراسات "
             "الطفولة 2015) and years: perhaps one text printed twice; not safe to link as the cited publication."),
    "B148": ("blind", "relation", "«نظرات في كتاب مناهج البحث في اللغة» is a review of the cited book."),
    "B149": ("blind", "relation", "a 2015 selection of al-Sayyab's poems: drawn from the Diwan (weak relation)."),
    "B152": ("blind", "relation", "a presentation of Wikipedia: about the cited site (weak; the card is not a work)."),
    "B153": ("librarian", "no_link", "the 2012 thesis is on critical thinking, the 2014 article on creative thinking: "
             "same author and programme, but the article is not drawn from that thesis."),
    "B154": ("blind", "links_to_publication", "the citing article is about عمال التراحيل; the record is كمال السيد's "
             "1971 «عمال التراحيل: ثلاثة أسئلة صعبة» in الطليعة, which the citation prints short. A missed link."),
    "B155": ("librarian", "no_link", "the record is about the third report (2005), not the 2002 / 2014 reports cited."),
}

# round 2 (100 links passing K1b, 40 same_work, 20 not-a-work cards, drawn after the round-1 fixes)
VERDICTS2 = {
    "B2005": ("blind", "relation", "the citation gives مجلة المنظومة الرياضية; the record is in مجلة المحترف: the same "
              "title, author and year in another venue (or a mis-cited journal): not the publication cited."),
    "B2033": ("blind", "relation", "a 1995 book of the Moroccan Academy cited; the record is an article of the same "
              "title in فضاءات تربوية."),
    "B2035": ("blind", "relation", "مجلة علامات of Meknes cited; the record is in «علامات في النقد» (Jeddah)."),
    "B2044": ("blind", "relation", "a 2021 book cited (دار النهضة العربية); the record is a 2021 journal article."),
    "B2119": ("both", "same_work", "card A is a chapter (on hisba) of the Ihya', part 2; counting it for the Ihya' "
              "is what a citation index does; part_of is the stricter reading."),
    "B2136": ("both", "same_work", "card A is vol. 1 of Browne's Literary History of Persia under its volume "
              "subtitle; B cites the work at vol. 1 p. 13: one work either way."),
    "B2145": ("librarian", "not_a_work:drop", "unpublished office data is dropped from work counts by the rule; the "
              "round-2 question's wording of 'drop' left unpublished data out, so the judge kept it."),
}

APPLY_THRESHOLD = 0.98


def wilson(k, n, z=1.96):
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((c - r) / d, 3), round((c + r) / d, 3)


def _rows(scored: dict, verdicts: dict, allD: dict, rnd: int) -> list:
    import rules62
    k1b = [r for r in rules62.cat_rules() if r[0].startswith("K1b")][0][2]
    k1c = [r for r in rules62.cat_rules() if r[0].startswith("K1c")][0][2]
    rows = []
    for r in scored["rows"]:
        d = allD[r["decision_id"]]
        v = verdicts.get(r["bid"])
        if r["agree"]:
            right, ok = "both agree", True
        else:
            assert v, r["bid"]
            right, ok = v[0], v[0] in ("librarian", "both")
        row = dict(r, round=rnd, trivial=bool(d.get("trivial")), basis=d["basis"], librarian_correct=ok, right=right)
        if v:
            row.update(verdict=v[1], why=v[2])
        if r["level"] == "catalogue" and r["kind"] == "links_to_publication":
            row["k1b"], row["k1c"] = bool(k1b(d)), bool(k1c(d))
        if r["level"] == "card" and r["kind"] == "not_a_work":
            row["verdict_not_a_work_ok"] = r["blind"].startswith("not_a_work") or right == "librarian"
        rows.append(row)
    return rows


def _adj_file(rows, name):
    adj = [x for x in rows if not x["agree"]]
    (OUT / name).write_text(json.dumps(dict(
        round=rows[0]["round"] if rows else None, n=len(rows), agree=sum(x["agree"] for x in rows),
        disagreements=len(adj),
        by_kind={k: dict(n=sum(1 for x in rows if f"{x['level']}:{x['kind']}" == k),
                         agree=sum(1 for x in rows if f"{x['level']}:{x['kind']}" == k and x["agree"]))
                 for k in sorted({f"{x['level']}:{x['kind']}" for x in rows})},
        right=dict(librarian=sum(x["right"] == "librarian" for x in adj), blind=sum(x["right"] == "blind" for x in adj),
                   both=sum(x["right"] == "both" for x in adj)),
        cases=[{k: x.get(k) for k in ("bid", "decision_id", "level", "kind", "mine", "blind", "my_confidence",
                                      "blind_confidence", "right", "verdict", "why", "blind_reason")} for x in adj]),
        ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    allD = {}
    for l in open(OUT / "decisions62.jsonl", encoding="utf-8"):
        d = json.loads(l)
        allD[d["decision_id"]] = d
    r1 = _rows(json.loads((OUT / "blind62_scored.json").read_text(encoding="utf-8")), VERDICTS, allD, 1)
    _adj_file(r1, "blind62_adjudication.json")
    r2 = []
    if (OUT / "blind62b_scored.json").exists():
        r2 = _rows(json.loads((OUT / "blind62b_scored.json").read_text(encoding="utf-8")), VERDICTS2, allD, 2)
        _adj_file(r2, "blind62b_adjudication.json")
    rows = r1 + r2

    def stat(sel, name, n_pop, note=""):
        n = len(sel)
        k = sum(x["librarian_correct"] for x in sel)
        lo, hi = wilson(k, n)
        return dict(kind=name, n=n, correct=k, precision=round(k / n, 3) if n else None, wilson95=[lo, hi],
                    agreement=round(sum(x["agree"] for x in sel) / n, 3) if n else None, population=n_pop,
                    rounds=sorted({x["round"] for x in sel}), note=note)
    from finalize62 import standing
    import rules62
    D = standing()
    k1c = [r for r in rules62.cat_rules() if r[0].startswith("K1c")][0][2]
    pop = defaultdict(int)
    for d in D:
        pop[(d["level"], d["kind"])] += 1
    out = []
    for lvl, kind in [("pair", "same_work"), ("pair", "edition_of"), ("pair", "different_work"), ("card", "split_card"),
                      ("card", "card_ok"), ("card", "not_a_work"), ("catalogue", "links_to_publication"),
                      ("catalogue", "relation"), ("catalogue", "no_link")]:
        out.append(stat([x for x in rows if x["level"] == lvl and x["kind"] == kind], f"{lvl}:{kind}", pop[(lvl, kind)]))
    out.append(stat([x for x in rows if x["level"] == "pair" and x["kind"] in ("same_work", "edition_of")],
                    "pair:one work (same_work + edition_of)", pop[("pair", "same_work")] + pop[("pair", "edition_of")]))
    nw = [x for x in rows if x["level"] == "card" and x["kind"] == "not_a_work"]
    out.append(stat([dict(x, librarian_correct=x["verdict_not_a_work_ok"]) for x in nw],
                    "card:not_a_work (the verdict only, not the action)", pop[("card", "not_a_work")]))
    out.append(stat([x for x in r2 if x["level"] == "card" and x["kind"] == "not_a_work"],
                    "card:not_a_work after the action fixes (round 2)", pop[("card", "not_a_work")]))
    n_k1c = sum(1 for d in D if d["level"] == "catalogue" and d["kind"] == "links_to_publication" and k1c(d))
    out.append(stat([x for x in rows if x.get("k1c")], "catalogue:links passing K1c (venue fits)", n_k1c))
    out.append(stat([x for x in rows if x.get("k1b") is not None and not x.get("k1c")],
                    "catalogue:links not passing K1c", pop[("catalogue", "links_to_publication")] - n_k1c,
                    "every link of this stratum was re-read after round 2 (the 157 whose venue or form did not "
                    "obviously fit; 11 changed to relation)"))
    nl = [x for x in rows if x["level"] == "catalogue" and x["kind"] == "no_link"]
    out.append(stat([dict(x, librarian_correct=x["right"] != "blind" or x["verdict"] != "links_to_publication")
                     for x in nl], "catalogue:no_link read as 'not the cited work'", pop[("catalogue", "no_link")]))
    unsure = [x for x in rows if x["kind"] == "unsure"]
    get = {o["kind"]: o for o in out}

    def ps(k):
        o = get[k]
        return f"{o['correct']}/{o['n']} ({o['precision']:.1%})"
    R = json.loads((OUT / "rules62.json").read_text(encoding="utf-8"))["rules"]
    rk = {r["rule"][:3]: r for r in R}
    apply_rule = [
        dict(kind="pair:edition_of", apply=True, measured=ps("pair:edition_of"), why="no error found"),
        dict(kind="pair:same_work", apply=True, measured=ps("pair:same_work"), why="above 98% over both rounds; the "
             "one error (two «فتاوى ابن تيمية» short forms on one volume number, B009) is now unsure"),
        dict(kind="pair:different_work", apply=False, measured=ps("pair:different_work"), why="below 98%: not "
             "applied. Nothing is lost: a different_work joins nothing, the two cards stay apart as the platform has "
             "them today. Its one error (B044) was a missed join, fixed"),
        dict(kind="card:split_card", apply=True, measured=ps("card:split_card"), why="no error found"),
        dict(kind="card:card_ok", apply=True, measured=ps("card:card_ok"), why="changes nothing when applied"),
        dict(kind="card:not_a_work", apply=True, measured=ps("card:not_a_work (the verdict only, not the action)") +
             " verdict; " + ps("card:not_a_work after the action fixes (round 2)") + " after the action fixes",
             why="round 1 found the action wrong in 3/15; the 35 actions where the action rule and an author test "
                 "disagree were re-read (23 cards changed, plus the 3 from round 1) and round 2 found none wrong"),
        dict(kind="catalogue:links_to_publication passing K1c", apply=True,
             measured=ps("catalogue:links passing K1c (venue fits)"),
             why=f"K1c reproduces {rk['K1c']['agrees']}/{rk['K1c']['fires']} of the librarian's standing links; the "
                 "blind rounds found one error in it (a journal of a similar name in another country, B2035), fixed"),
        dict(kind="catalogue:links_to_publication, the rest", apply=False,
             measured=ps("catalogue:links not passing K1c"),
             why=f"most of the blind samples' link errors fell here ({get['catalogue:links not passing K1c']['n'] - get['catalogue:links not passing K1c']['correct']} "
                 f"of {get['catalogue:links not passing K1c']['n']}); the links whose venue or form did not fit were "
                 "all re-read after round 2 and 11 changed, but the stratum has no clean measurement after the "
                 "re-read: hold for a third blind round, or apply with the owner's answer to escalated case 5"),
        dict(kind="catalogue:relation", apply=True, measured=ps("catalogue:relation"),
             why="a relation is shown as 'related', never counted as the work"),
        dict(kind="catalogue:no_link", apply=False, measured=ps("catalogue:no_link"),
             why="nothing to apply: no_link leaves the card unlinked (the errors were relations, one missed link)"),
        dict(kind="unsure", apply=False, measured=f"{len(unsure)} sampled", why="never applied"),
    ]
    rep = dict(threshold=APPLY_THRESHOLD, by_kind=out, rounds=dict(
        round1=dict(n=len(r1), agree=sum(x["agree"] for x in r1)),
        round2=dict(n=len(r2), agree=sum(x["agree"] for x in r2))),
        unsure=dict(n=len(unsure), decidable_by_blind=sum(1 for x in unsure if x["blind"] != "unsure"),
                    right_blind=sum(1 for x in unsure if x["right"] == "blind")),
        apply_rule=apply_rule,
        caveat="the blind judge is the same model as the librarian, reading the same evidence without the first "
               "decision: agreement can hide a shared mistake, so the precision is an upper bound. The hard checks "
               "(check62) and the rules audit (rules62) are the independent part; they found 4 errors the sample "
               "did not (2 review records linked as the work, the Sahih Muslim / al-Nawawi chain, an English title "
               "of an Arabic article)")
    (OUT / "precision62.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    for o in out:
        print(f"{o['kind'][:58]:58s} n={o['n']:3d} ok={o['correct']:3d} p={o['precision']} wilson={o['wilson95']} pop={o['population']}")
    print(rep["rounds"], rep["unsure"])


if __name__ == "__main__":
    main()
