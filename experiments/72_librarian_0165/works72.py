"""Experiment 72, cited works, step 1: the machine's cards on the live release, the catalogue drawer for the cards
0165 cites, and the candidate questions (experiment 62's own code, pointed at this experiment's out/; nothing in
experiment 62 is changed).

    python works72.py cards      out/works/cards62.jsonl (every active card), articles62.json, desk_detectors62.json;
                                 out/works0165/ the same for the cards a 0165 article cites
    python works72.py catalogue  experiment 62's catalogue drawer (one pass over marc.db) for the 0165 cards
    python works72.py cands      experiment 62's blocking on every card; packets kept when they touch a 0165 card
                                 that no standing decision has settled -> out/works/packets72.jsonl

Run with the Desk's venv (it has psycopg for the seen list and the detectors).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections import Counter

from common72 import DESK, E62, JOURNAL, MARC, OUT, RELEASE, add_paths, jl, js, wjl, wjs

os.environ["LIBRARIAN62_RELEASE"] = str(RELEASE)      # exp 62's tools read the release through this
add_paths(E62, DESK)
WALL = OUT / "works"
W0165 = OUT / "works0165"


def cards():
    import build62
    build62.OUT = WALL
    WALL.mkdir(parents=True, exist_ok=True)
    build62.main(["--db", str(RELEASE)])
    C = jl(WALL / "cards62.jsonl")
    mine = [c for c in C if any(s.startswith(JOURNAL + "-") for s in c["stems"])]
    W0165.mkdir(parents=True, exist_ok=True)
    wjl(W0165 / "cards62.jsonl", mine)
    shutil.copy(WALL / "articles62.json", W0165 / "articles62.json")
    # the Desk's own detector (possible same work), as exp 62 used it for a recall check
    from desk import db
    from desk.detectors import load_cards, possible_same_work
    from desk.reading import Reading
    R = Reading(db.open_reading(RELEASE))
    found = possible_same_work(R, load_cards(R))
    wjs(WALL / "desk_detectors62.json", dict(possible_same_work=[dict(keys=t["keys"], rule=t["source"]["rule"])
                                                                 for t in found]))
    print(dict(cards=len(C), cards_0165=len(mine), detector_pairs=len(found)))


def catalogue():
    import catindex62
    catindex62.OUT = W0165
    t0 = time.time()
    catindex62.main()
    print("catalogue", round(time.time() - t0), "s")


def seen_list():
    """The subjects earlier passes settled: every key of a standing Desk decision, the cards a standing split made,
    and experiment 62's own standing pair questions (its different_work answers were held, not imported, but they
    are the librarian's answers all the same)."""
    from desk import db
    from desk.ops import pending_cards
    with db.connect("desk") as pg:
        rows = pg.execute("SELECT op, subject_keys FROM decisions WHERE status IN ('proposed', 'accepted') AND op NOT "
                          "IN ('revert', 'retire')").fetchall()
        pend = pending_cards(pg)
    keys = {k for r in rows for k in r["subject_keys"]}
    pairs = {tuple(sorted(r["subject_keys"])) for r in rows if r["op"] in ("same_work", "not_same_work", "edition_of",
                                                                        "relate_works")}
    linked = {r["subject_keys"][0] for r in rows if r["op"] in ("link_publication", "relate_publication")}
    shaped = {r["subject_keys"][0] for r in rows if r["op"] in ("split_work", "not_a_work", "confirm_work")}
    e62 = {}
    for d in jl(E62 / "out" / "decisions62.jsonl"):
        e62[d["qkey"]] = d
    e62pairs = {tuple(sorted(f"work:{x}" for x in d["subject_keys"])): d["kind"] for d in e62.values()
                if d.get("level") == "pair" and d["kind"] != "retired"}
    return dict(keys=keys, pairs=pairs, linked=linked, shaped=shaped, pending=set(pend), e62pairs=e62pairs)


def cands():
    import cands62
    cands62.OUT = WALL

    def edge_strength(f):           # exp 62's, with "weak" (only given names shared) that its data never met
        t = f["title"]
        s = t["dice"] + 0.3 * t["cover"] + {"agree": 0.4, "translit": 0.2, "unknown": 0.0, "weak": 0.0,
                                            "contradict": -0.5}[f["author"]]
        s += {"same": 0.1, "differ": -0.05, "unknown": 0}[f["year"]]
        return round(s, 3)
    cands62.edge_strength = edge_strength
    t0 = time.time()
    cands62.main()
    P = jl(WALL / "packets62.jsonl")
    C = {c["cited_work_id"]: c for c in jl(WALL / "cards62.jsonl")}
    mine = {c["cited_work_id"] for c in jl(W0165 / "cards62.jsonl")}
    S = seen_list()
    kept, why = [], Counter()
    for p in P:
        if p["kind"] == "merge":
            es = []
            for e in p["edges"]:
                k = tuple(sorted((f"work:{e['a']}", f"work:{e['b']}")))
                if not ({e["a"], e["b"]} & mine):
                    why["pair: no 0165 card"] += 1
                elif k in S["pairs"]:
                    why["pair: a standing Desk decision"] += 1
                elif k in S["e62pairs"]:
                    why[f"pair: exp 62 answered ({S['e62pairs'][k]})"] += 1
                else:
                    es.append(e)
            if es:
                cs = sorted({x for e in es for x in (e["a"], e["b"])})
                kept.append(dict(p, cards=cs, edges=es))
        elif p["kind"] in ("split", "notwork"):
            cid = p["cards"][0]
            if cid not in mine:
                why[f"{p['kind']}: not a 0165 card"] += 1
            elif f"work:{cid}" in S["shaped"]:
                why[f"{p['kind']}: a standing Desk decision"] += 1
            else:
                kept.append(p)
        elif p["kind"] == "catalogue" and p.get("proposal") == "read-article":
            cid = p["cards"][0]
            if cid in mine and f"work:{cid}" not in S["linked"]:
                kept.append(p)
            else:
                why["read-article: not 0165 or already linked by a decision"] += 1
    # the catalogue drawer's proposals for the 0165 cards
    for x in jl(W0165 / "catalogue" / "cat62.jsonl"):
        if x["decision"] not in ("accept", "candidate", "relation"):
            continue
        if f"work:{x['cited_work_id']}" in S["linked"]:
            why["catalogue: a standing Desk link"] += 1
            continue
        kept.append(dict(key=f"catalogue:{x['cited_work_id']}", kind="catalogue", cards=[x["cited_work_id"]],
                         proposal=x["decision"], why=x["why"], best=x["best"], top=x["top"]))
    # link47's own accepted links on 0165 cards that the drawer did not propose (the librarian confirms or rejects
    # what the machine linked, as exp 62 did through its catalogue packets)
    have = {p["cards"][0] for p in kept if p["kind"] == "catalogue" and p.get("proposal") != "read-article"}
    for cid in sorted(mine):
        c = C[cid]
        if cid in have or f"work:{cid}" in S["linked"]:
            continue
        best = [l for l in c["links"] if l.get("best") and l["status"] == "accepted"]
        if best:
            l = best[0]
            kept.append(dict(key=f"catalogue:{cid}", kind="catalogue", cards=[cid], proposal="link47",
                             why=f"link47 {l['method']} {l['score']}", best=dict(pub_id=l["pub_id"], c999=l["c999"],
                                                                                 title=l["title"]), top=[]))
    wjl(WALL / "packets72.jsonl", kept)
    B = js(WALL / "blocking62.json")
    wjs(WALL / "packets72_summary.json", dict(kept=dict(Counter(p["kind"] + (":" + p.get("proposal", "") if
                                                                            p["kind"] == "catalogue" else "")
                                                                 for p in kept)),
                                             pair_edges=sum(len(p["edges"]) for p in kept if p["kind"] == "merge"),
                                             left_out=dict(why), blocking=B, seconds=round(time.time() - t0)))
    print(json.dumps(dict(kept=len(kept), edges=sum(len(p["edges"]) for p in kept if p["kind"] == "merge"),
                          left_out=dict(why)), ensure_ascii=False, indent=1))




# ------------------------------------------------------------------ step 2: rules first, then the model questions
Q_PAIR = ("Are card A and card B the same work? same_work = one work (same or unknown edition); edition_of = one work, "
          "another printing / translation / tahqiq; part_of = one is a volume, chapter or part of the other; "
          "different_work; unsure.")
Q_SPLIT = ("Are all citations on this card one work? card_ok = yes; split_card = no: give the groups of citation "
           "numbers that are one work each (e.g. [[1,3],[2]]); not_a_work = the card is not a work at all; unsure.")
Q_NOTWORK = ("Is this card a work? card_ok = a real work (its title is right); not_a_work_drop = a journal / newspaper "
             "named only by issue or date, unpublished data, a bare web site (not a work: drop from work counts); "
             "not_a_work_retitle = one real item whose own title the card lost (the card shows a journal's name); "
             "not_a_work_one_per_citation = several different items on one card titled with a journal's name; unsure.")
Q_CAT = ("Is the cited work (the card) this Mandumah record? links_to_publication = the record IS the cited work; "
         "same_text = the same text (same title and author) published in another journal or reprinted, and Mandumah "
         "holds this one; relation = the record is about it or related (a review, a thesis summary, an article drawn "
         "from the cited thesis, a later article on the same theme) but not the cited work; no_link = unrelated; unsure.")
O_PAIR = ["same_work", "edition_of", "part_of", "different_work", "unsure"]
O_SPLIT = ["card_ok", "split_card", "not_a_work", "unsure"]
O_NOTWORK = ["card_ok", "not_a_work_drop", "not_a_work_retitle", "not_a_work_one_per_citation", "unsure"]
O_CAT = ["links_to_publication", "same_text", "relation", "no_link", "unsure"]


def marc_rec(mcon, c999):
    if not c999:
        return None
    r = mcon.execute("SELECT rec, c999, title, subtitle, year_int, type, journal FROM records WHERE c999 = ? LIMIT 1",
                     (str(c999),)).fetchone()
    if not r:
        return None
    au = [x[0] for x in mcon.execute("SELECT name FROM authors WHERE rec = ? ORDER BY seq", (r[0],))][:4]
    return dict(rec=r[0], c999=r[1], title=r[2], subtitle=r[3], year=r[4], type=r[5], journal=r[6], authors=au)


def questions():
    import sqlite3
    import blind62
    import rules62
    import tools62
    tools62.OUT = WALL
    blind62.OUT = WALL
    C = tools62.cards()
    P = jl(WALL / "packets72.jsonl")
    mcon = sqlite3.connect(f"file:{MARC}?mode=ro&immutable=1", uri=True)
    ctx = tools62.context
    k1b = [r for r in rules62.cat_rules() if r[0].startswith("K1b")][0][2]
    cv = {}

    def view(cid):
        if cid not in cv:
            cv[cid] = blind62.card_view(C[cid], ctx)
        return cv[cid]
    rules, qs, stat = [], [], Counter()
    for p in P:
        if p["kind"] == "merge":
            for e in p["edges"]:
                a, b = e["a"], e["b"]
                qid = f"W72-P{a}{b}"
                types = {C[a]["pub_type"], C[b]["pub_type"]}
                if types == {"thesis", "journal"}:               # P6: a thesis and a journal article: two works
                    t, au = e["title"], e["author"]
                    derived = t["dice"] >= 0.85 and au in ("agree", "translit")
                    rules.append(dict(id=qid, level="pair", rule="P6", kind="different_work", cards=[a, b],
                                      derived=derived, confidence="high",
                                      reason="P6: a thesis and a journal article are two works"
                                             + ("; same title and author: the article is drawn from the thesis (D43)"
                                                if derived else "")))
                    stat["rule P6"] += 1
                    continue
                qs.append(dict(id=qid, domain="works", kind="works:pair", question=Q_PAIR, options=O_PAIR,
                               evidence=dict(A=view(a), B=view(b)),
                               meta=dict(cards=[a, b], blocking=e["rule"], dice=e["title"]["dice"], author=e["author"])))
                stat["model pair"] += 1
        elif p["kind"] == "split":
            cid = p["cards"][0]
            qs.append(dict(id=f"W72-S{cid}", domain="works", kind="works:split", question=Q_SPLIT, options=O_SPLIT,
                           evidence=dict(card=view(cid)), meta=dict(card=cid, why=p["why"])))
            stat["model split"] += 1
        elif p["kind"] == "notwork":
            cid = p["cards"][0]
            c1 = bool(rules62.JOURNAL_RE.match((C[cid]["title"] or "").strip()))
            qs.append(dict(id=f"W72-N{cid}", domain="works", kind="works:notwork", question=Q_NOTWORK,
                           options=O_NOTWORK, evidence=dict(card=view(cid)),
                           meta=dict(card=cid, why=p["why"], c1=c1)))
            stat["model notwork" + (" (C1: not a work by rule, the action asked)" if c1 else "")] += 1
        elif p["kind"] == "catalogue":
            cid = p["cards"][0]
            if p.get("proposal") == "read-article":
                rec = marc_rec(mcon, p.get("target_c999"))
                best = dict(rec or {}, pub_id=p.get("target_pub_id"), stem=p.get("target_stem"))
            elif p.get("proposal") == "link47":
                rec = marc_rec(mcon, (p.get("best") or {}).get("c999"))
                best = dict(rec or {}, pub_id=p["best"].get("pub_id"), title=(rec or {}).get("title") or p["best"]["title"])
            else:
                best = p["best"]
            d = dict(decision=dict(target=best, card=dict(type=C[cid]["pub_type"])),
                     printed=[m["printed"] for m in C[cid]["members"]])
            if p.get("proposal") == "accept" and k1b(d) and rules62._venue_fits(d):      # K1c
                rules.append(dict(id=f"W72-K{cid}", level="catalogue", rule="K1c", kind="links_to_publication",
                                  card=cid, target=best, confidence="high",
                                  reason=f"K1c: title, author, year and venue fit ({p['why']})"))
                stat["rule K1c"] += 1
                continue
            rec = {k: best.get(k) for k in ("c999", "title", "subtitle", "authors", "year", "type", "journal", "stem")
                   if best.get(k)}
            qs.append(dict(id=f"W72-K{cid}", domain="works", kind="works:catalogue", question=Q_CAT, options=O_CAT,
                           evidence=dict(card=view(cid), record=rec),
                           meta=dict(card=cid, proposal=p.get("proposal"), why=p.get("why"), target=best)))
            stat[f"model catalogue ({p.get('proposal')})"] += 1
    seen, uq = set(), []
    for q in qs:                       # one question per id (a read-article and a drawer proposal on one card)
        if q["id"] in seen:
            q["id"] += "-2"
        seen.add(q["id"])
        uq.append(q)
    wjl(WALL / "rule_decisions.jsonl", rules)
    wjl(OUT / "questions" / "works.jsonl", uq)
    S = dict(stat=dict(stat), rules=len(rules), questions=len(uq),
             chars=sum(len(json.dumps(q["evidence"], ensure_ascii=False)) for q in uq) // max(1, len(uq)))
    wjs(WALL / "questions_summary.json", S)
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    dict(cards=cards, catalogue=catalogue, cands=cands, questions=questions)[sys.argv[1]]()
