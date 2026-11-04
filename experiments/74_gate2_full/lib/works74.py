"""Experiment 74 (from experiment 72's works72.py), cited works of one journal (LIB74_J): the machine's cards on the
release, the catalogue drawer for the cards the journal cites, the candidate questions, and the rules (experiment
62's code, pointed at OUT; nothing in experiment 62 is changed).

    python works74.py cards      OUT/works/cards62.jsonl (every active card), articles62.json, desk_detectors62.json;
                                 OUT/works<J>/ the same for the cards an article of the journal cites
    python works74.py catalogue  experiment 62's catalogue drawer (one pass over marc.db) for the journal's cards
    python works74.py cands      experiment 62's blocking on every card; packets kept when they touch a card of the
                                 journal that no standing decision has settled -> OUT/works/packets74.jsonl
    python works74.py questions  rules first (K1c, P6, D44, C1), then the questions -> OUT/questions/works.jsonl

Changed against exp 72 (its lessons):
- 4: split and not-a-work questions show the WHOLE card (every citation, up to CARD_CAP = 60 with a note when the
  card holds more); exp 72's packets showed 12 (CBDD9P2BCR: 12 of 18, a wrong confirm). plan74 maps the split
  groups to the same members.
- 6: rule D44 (same text in another journal): a catalogue proposal whose title (s_title >= 0.9) and author
  (s_author >= 0.8) fit, the card a journal article, the record a Mandumah journal article (journal_code), and the
  citation printing ANOTHER journal (its source title shares the script but not the distinctive words, either way)
  -> link_publication as "same_text" (desk.ops LINK_AS; release.py writes it as the D44 link).
- 7: K1c's venue test is tightened: every DISTINCTIVE word of the record's journal (generic words such as مجلة،
  العربية، العلوم، التربوية، النفسية، دراسات، بحوث, journal, of, studies dropped) must be printed in the citation's
  source title (or, when no source title is parsed, anywhere in the citation). «مجلة الطفولة والتربية» no longer passes
  for «مجلة الطفولة والتنمية» (test_k1c74.py).

Run with the Desk's venv (it has psycopg for the seen list and the detectors).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections import Counter

from common74 import DESK, E62, JOURNAL, MARC, OUT, RELEASE, TAG, add_paths, jl, js, wjl, wjs

os.environ["LIBRARIAN62_RELEASE"] = str(RELEASE)      # exp 62's tools read the release through this
add_paths(E62, DESK)
WALL = OUT / "works"
WJ = OUT / f"works{JOURNAL}"
CARD_CAP = 60


def cards():
    import build62
    build62.OUT = WALL
    WALL.mkdir(parents=True, exist_ok=True)
    build62.main(["--db", str(RELEASE)])
    C = jl(WALL / "cards62.jsonl")
    mine = [c for c in C if any(s.startswith(JOURNAL + "-") for s in c["stems"])]
    WJ.mkdir(parents=True, exist_ok=True)
    wjl(WJ / "cards62.jsonl", mine)
    shutil.copy(WALL / "articles62.json", WJ / "articles62.json")
    # the Desk's own detector (possible same work), as exp 62 used it for a recall check
    from desk import db
    from desk.detectors import load_cards, possible_same_work
    from desk.reading import Reading
    R = Reading(db.open_reading(RELEASE))
    found = possible_same_work(R, load_cards(R))
    wjs(WALL / "desk_detectors62.json", dict(possible_same_work=[dict(keys=t["keys"], rule=t["source"]["rule"])
                                                                 for t in found]))
    print(dict(cards=len(C), journal=JOURNAL, cards_journal=len(mine), detector_pairs=len(found)))


def catalogue():
    import catindex62
    catindex62.OUT = WJ
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
        held = pg.execute("SELECT kind, subject_keys FROM tasks WHERE state IN ('open', 'claimed') AND kind IN "
                          "('librarian_question', 'possible_same_work') AND source->>'detector' LIKE 'librarian%%'"
                          ).fetchall()
    keys = {k for r in rows for k in r["subject_keys"]}
    pairs = {tuple(sorted(r["subject_keys"])) for r in rows if r["op"] in ("same_work", "not_same_work", "edition_of",
                                                                        "relate_works")}
    linked = {r["subject_keys"][0] for r in rows if r["op"] in ("link_publication", "relate_publication")}
    shaped = {r["subject_keys"][0] for r in rows if r["op"] in ("split_work", "not_a_work", "confirm_work")}
    # exp 74: questions an earlier librarian pass held for a person (open tasks) are not asked again
    for t in held:
        ks = t["subject_keys"] or []
        if t["kind"] == "possible_same_work" and len(ks) == 2:
            pairs.add(tuple(sorted(ks)))
        elif ks and ks[0].startswith("work:"):
            linked.add(ks[0])          # a held catalogue question
            shaped.add(ks[0])          # or a held split / not-a-work question
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
    mine = {c["cited_work_id"] for c in jl(WJ / "cards62.jsonl")}
    S = seen_list()
    kept, why = [], Counter()
    for p in P:
        if p["kind"] == "merge":
            es = []
            for e in p["edges"]:
                k = tuple(sorted((f"work:{e['a']}", f"work:{e['b']}")))
                if not ({e["a"], e["b"]} & mine):
                    why["pair: no card of the journal"] += 1
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
                why[f"{p['kind']}: not a card of the journal"] += 1
            elif f"work:{cid}" in S["shaped"]:
                why[f"{p['kind']}: a standing Desk decision"] += 1
            else:
                kept.append(p)
        elif p["kind"] == "catalogue" and p.get("proposal") == "read-article":
            cid = p["cards"][0]
            if cid in mine and f"work:{cid}" not in S["linked"]:
                kept.append(p)
            else:
                why["read-article: not the journal's or already linked by a decision"] += 1
    # the catalogue drawer's proposals for the 0165 cards
    for x in jl(WJ / "catalogue" / "cat62.jsonl"):
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
    wjl(WALL / "packets74.jsonl", kept)
    B = js(WALL / "blocking62.json")
    wjs(WALL / "packets74_summary.json", dict(kept=dict(Counter(p["kind"] + (":" + p.get("proposal", "") if
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


GENERIC = ("مجلة المجلة مجلات journal journals of the and for in review revue studies study research العربية العربي عربية "
           "للعلوم العلوم علوم التربوية التربوي النفسية النفسي دراسات الدراسات بحوث البحوث الدولية الدولي international "
           "و في science sciences educational psychological arab arabic bulletin annals")


def _toks(s: str) -> set:
    from norm62 import tokens
    return set(tokens(s or ""))


_GEN = None


def distinctive(name: str) -> set:
    global _GEN
    if _GEN is None:
        _GEN = set()
        for w in GENERIC.split():
            _GEN |= _toks(w) | {w}
    return {w for w in _toks(name) if w not in _GEN and len(w) > 1}


def venue_fits74(d: dict, sources: list[str]) -> bool:
    """K1c's venue test, tightened (exp 72's lesson 7): for a journal card, every distinctive word of the record's
    journal (when its name has none, every word but «مجلة») is printed in the citation's source title (else anywhere
    in the citation); books as exp 62."""
    t = d["decision"].get("target") or {}
    ct = d["decision"]["card"]["type"]
    if ct == "journal" and t.get("journal"):
        want = distinctive(t["journal"]) or (_toks(t["journal"]) - {"مجله", "journal"})
        if not want:                        # a name of generic words only: all of them must be printed
            return False
        src = [s for s in sources if s]
        have = set().union(*[_toks(s) for s in src]) if src else _toks(" ".join(d.get("printed") or []))
        return want <= have
    if ct in ("book", "chapter"):
        return t.get("type") != "بحوث ومقالات"
    return True


def _script(s: str) -> str:
    import re
    return "ar" if re.search("[\u0600-\u06ff]", s or "") else "lat"


def d44(d: dict, best: dict, sources: list[str], top: list = ()) -> bool:
    """Rule D44 (exp 72's lesson 6): the same text published in another journal. Title and author fit, the card is a
    journal article, the record is a Mandumah journal article, and the citation prints another journal: a source
    title in the record journal's script that shares no distinctive word set with it (neither holds the other's).
    Never when another record the drawer found has the title and the printed journal (that one is the cited work:
    exp 72's C70RAZGS25, the 2014 copy in «مجلة الطفولة والتربية» beside the cited 2015 one in «مجلة الطفولة والتنمية»)."""
    if d["decision"]["card"]["type"] != "journal":
        return False
    if (best.get("s_title") or 0) < 0.9 or (best.get("s_author") or 0) < 0.8:
        return False
    if best.get("type") != "بحوث ومقالات" or not best.get("journal") or not best.get("journal_code"):
        return False
    src = [s for s in sources if s]
    if not src:
        return False
    rj = distinctive(best["journal"])
    if not rj:
        return False
    for s in src:
        if _script(s) != _script(best["journal"]):
            return False
        pj = distinctive(s)
        if not pj or pj <= rj or rj <= pj:
            return False
    for t in top or []:
        if t.get("c999") != best.get("c999") and (t.get("s_title") or 0) >= 0.9 and t.get("journal") and \
                distinctive(t["journal"]) and distinctive(t["journal"]) <= set().union(*[_toks(x) for x in src]):
            return False
    return True


def whole_view(c: dict, ctx) -> dict:
    """blind62.card_view with every citation (up to CARD_CAP), for split / not-a-work questions."""
    import blind62
    v = blind62.card_view(dict(c, members=c["members"][:CARD_CAP]), ctx) if len(c["members"]) <= 12 else None
    if v is None:
        ms = []
        for i, m in enumerate(c["members"][:CARD_CAP]):
            x = dict(n=i + 1, article=m["stem"], kind=m["kind"], printed=(m["printed"] or "")[:500])
            if m.get("note") and m["note"] != m["printed"]:
                x["note"] = m["note"][:400]
            if m["kind"] != "full" or len(m["printed"] or "") < 40:
                t = ctx(m["mention_id"])
                if t:
                    x["text_before_the_note_call"] = t[-260:]
            ms.append(x)
        v = dict(card=c["cited_work_id"], title=c["title"], type=c["pub_type"],
                 authors=[a["printed"] for a in c["authors"]][:5], cited_by_articles=c["n_articles"], citations=ms)
    if len(c["members"]) > CARD_CAP:
        v["note"] = (f"the card holds {len(c['members'])} citations; the first {CARD_CAP} are shown (answer split groups "
                     f"with these numbers only)")
    return v


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
    P = jl(WALL / "packets74.jsonl")
    mcon = sqlite3.connect(f"file:{MARC}?mode=ro&immutable=1", uri=True)
    ctx = tools62.context
    k1b = [r for r in rules62.cat_rules() if r[0].startswith("K1b")][0][2]
    cv = {}

    def view(cid):
        if cid not in cv:
            cv[cid] = blind62.card_view(C[cid], ctx)
        return cv[cid]

    def whole(cid):
        return whole_view(C[cid], ctx)
    rules, qs, stat = [], [], Counter()
    for p in P:
        if p["kind"] == "merge":
            for e in p["edges"]:
                a, b = e["a"], e["b"]
                qid = f"W{TAG}-P{a}{b}"
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
            qs.append(dict(id=f"W{TAG}-S{cid}", domain="works", kind="works:split", question=Q_SPLIT, options=O_SPLIT,
                           evidence=dict(card=whole(cid)), meta=dict(card=cid, why=p["why"])))
            stat["model split"] += 1
        elif p["kind"] == "notwork":
            cid = p["cards"][0]
            c1 = bool(rules62.JOURNAL_RE.match((C[cid]["title"] or "").strip()))
            qs.append(dict(id=f"W{TAG}-N{cid}", domain="works", kind="works:notwork", question=Q_NOTWORK,
                           options=O_NOTWORK, evidence=dict(card=whole(cid)),
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
            srcs = [((m.get("parsed") or {}).get("source_title") or "") for m in C[cid]["members"]]
            if p.get("proposal") == "accept" and k1b(d) and venue_fits74(d, srcs):      # K1c (tightened venue)
                rules.append(dict(id=f"W{TAG}-K{cid}", level="catalogue", rule="K1c", kind="links_to_publication",
                                  card=cid, target=best, confidence="high",
                                  reason=f"K1c: title, author, year and venue fit ({p['why']})"))
                stat["rule K1c"] += 1
                continue
            if p.get("proposal") in ("accept", "candidate") and d44(d, best, srcs, p.get("top") or []):   # D44
                rules.append(dict(id=f"W{TAG}-K{cid}", level="catalogue", rule="D44", kind="same_text",
                                  card=cid, target=best, confidence="high",
                                  reason=f"D44: the same title and author printed in another journal "
                                         f"(«{next(x for x in srcs if x)}» / Mandumah: «{best.get('journal')}»; "
                                         f"{p.get('why')})"))
                stat["rule D44"] += 1
                continue
            rec = {k: best.get(k) for k in ("c999", "title", "subtitle", "authors", "year", "type", "journal", "stem")
                   if best.get(k)}
            qs.append(dict(id=f"W{TAG}-K{cid}", domain="works", kind="works:catalogue", question=Q_CAT, options=O_CAT,
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
