"""Experiment 67, step 1: turn experiment 62's standing cited-work decisions, with the owner's choices of 2026-11-02,
into Desk decisions (read-only: writes out/plan67.jsonl and out/plan67_summary.json, nothing else).

What goes in (the owner, 2026-11-02, under exp 62's APPLY rule):
- applied: edition_of, same_work, split_card, card_ok, not_a_work, relation, part_of, and the 696 links that pass
  rule K1c (title, author, year and venue fit);
- held (stay proposals, not imported): the other 217 links, different_work, no_link, every unsure;
- five rules for the whole index, applied to the decisions they touch:
  D40 «صحيح مسلم بشرح النووي» is Sahih Muslim, al-Nawawi's commentary its edition;
  D41 the DSM's editions are one work, each edition kept;
  D42 a chapter cited under its own author is its own work, part of the collective book;
  D43 a thesis and the article drawn from it are two works, related (derived from);
  D44 one text in two journals: the citation links to the one Mandumah holds, marked "same text".

Each planned decision carries `evidence.provenance` (exp 62 decision id, qkey, kind, basis, confidence, reason, the
blind rounds that sampled it and their verdict, the rule) and a `source_id` that makes the import idempotent. A
subject key 'work:@<source_id>#<g>' names group g of a split planned earlier; import67 resolves it to the card id the
Desk minted for it.

    python3 experiments/67_apply_works/plan67.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
E62 = HERE.parent / "62_librarian_works"
E62O = E62 / "out"
DESK = HERE.parent / "49_correction_desk"
sys.path.insert(0, str(E62))
sys.path.insert(0, str(DESK))
from finalize62 import standing  # noqa: E402  (exp 62's own reading of the standing decisions)
from norm62 import title_sim, tokens  # noqa: E402
from rules62 import _k1b, _venue_fits  # noqa: E402
from desk.keys import defined_work_id  # noqa: E402

STATE = Path("/home/appuser/data/desk/releases/R20261102T155701.db")   # what the Desk reads now (works as exp 62 saw)
MARC = Path.home() / "data" / "marc" / "marc.db"
CONF = dict(high="sure", medium="likely", low="unsure")

# ------------------------------------------------------------------ the owner's rules, case by case
D40_SAHIH, D40_NAWAWI = "C4EZV38PP2", "CMGAH5Y38J"     # D62-42695029d1f3 (different_work) -> edition_of
D40_NOT = "D62-816f18302505"     # «صحيح مسلم بشرح النووي» edition_of al-Nawawi's «شرح صحيح مسلم»: not applied (D40)
D41 = {"D62-483c484d8e47", "D62-2c248bb4f44d", "D62-ac4a11493c79", "D62-fb8f3914df28", "D62-1df76a087cf5"}  # the DSM
D42_PAIR = "D62-b54b601d5028"    # two chapters of «الثقافة العربية: أسئلة التطور والمستقبل» joined as the book
D42_BOOK = dict(title="الثقافة العربية: أسئلة التطور والمستقبل", publisher="مركز دراسات الوحدة العربية",
                place="بيروت", year="2003", pub_type="book", lang="ar",
                series="سلسلة كتب المستقبل العربي (29)",
                natural="الثقافة العربية: أسئلة التطور والمستقبل|مركز دراسات الوحدة العربية|2003")
D42_CHAPTERS = {"C2BE7XGM7E": "عبدالله عبد الدايم", "C7TGVAC7QF": "جيهان سليم"}
D42_PART_OF = {"D62-dc492546748d": ("C8SDEY1PYJ", "C8HQYPRQ6H")}   # exp 62's part_of: (the chapter, the volume)
# D43: different_work pairs that are a thesis and the article drawn from it -> related, derived from
D43_PAIRS = {"D62-a5865f68b55d": ("CQCRSFF7DR", "C5QZVDD45J"),     # (the article, the thesis)
             "D62-bab850153a37": ("CASKNNJDC5", "CHYN8JAW1K")}
# D44: the same text in two journals (the citation names one, Mandumah holds the other): linked, marked same text
D44 = {"C03T2DDVD1", "CABQ4TJABZ", "CCD0SB76WE", "CCRANKFQF8", "CHQ6T3P6JB", "CJEWVA6WMA",   # relation: "another venue"
       "CBMRKZVD45", "CQH4EVBD8J",                                                        # relation: a reprint / copy
       "CK75AY2BG4"}                                                                      # the escalated unsure
# relations whose kind the reason names and the keywords below would miss (card id -> relation)
REL_OVERRIDE = {
    "C4SFV4TEF6": "has_part",       # a serialised instalment of the cited text: part of it
    "CRY7M0YF8Z": "has_part",       # articles publishing lost parts of the cited book
    "C9JPEXWYWC": "has_derived",    # a selection drawn from the cited Diwan
    "CGWJPWHSMH": "derived_from",   # the cited book is the edition of the record's thesis
    "C0YMXW19BN": "derived_from",   # the citation (2001) is a later publication of the 1995 thesis
    "CA72BAH71E": "derived_from",   # the 1986 book of the 1984 thesis
    "CHPDG9RE79": "derived_from",   # her 2012 book of her 2007 thesis
    "C26HHP8KHF": "derived_from",   # the 2006 article he co-wrote from his 2003 thesis
    "CBGW5ZW206": "derived_from",   # the 2009 article with her supervisor from her 2006 thesis
    "CY63YAF1X1": "derived_from",   # his 2009 book of his 2006 conference paper
    "CNT9HESH5S": "related",        # the thesis precedes his book on the same subject
    "CDAF9NA4CA": "related",        # the record (2004) precedes the thesis (2005): related, not drawn from it
    "CZJ2HJT5DR": "reviewed_in",    # «نظرات في كتاب …» is a review
    "C43QRE926B": "reviewed_in", "C46GWBCH4Q": "reviewed_in", "C9XRJQR9E5": "reviewed_in",
    "CBD1ZP7FRA": "related",        # a review of another volume of the same multi-volume history
    "CPXCWHDQ0H": "has_derived",    # the 2021 article re-works the 2012 study cited
    "CE3RK6ZPMY": "related",        # his 1946 article on the text; the citation is his introduction to the edition
}


def rel_kind(d: dict) -> tuple[str, str]:
    """A relation decision's kind, from the cited work's side: (relation, why)."""
    cid = d["subject_keys"][0]
    t = d["decision"].get("target") or {}
    ct, rt, r = d["decision"]["card"]["type"], (t.get("type") or ""), (d["reason"] or "").lower()
    if cid in REL_OVERRIDE:
        return REL_OVERRIDE[cid], "read case by case"
    if rt.startswith("عروض"):
        return "reviewed_in", "the record is a review (عروض)"
    if ct == "thesis" and rt in ("بحوث ومقالات", "بحوث المؤتمرات"):
        return "has_derived", "D43: the record is drawn from the cited thesis"
    if ct != "thesis" and rt == "رسائل جامعية":
        if re.search(r"stud|editing", r):
            return "studied_in", "the thesis studies the cited work"
        return "derived_from", "D43: the cited work comes from the record's thesis"
    if re.search(r"\breview", r):
        return "reviewed_in", "the reason names a review"
    if "a study or a part of it" in r:
        return "related", "a study of the cited book or a part of it: related, no finer name"
    if re.search(r"study of|studies|studying|is a study|about|presenting|digest|on the dictionary|computerisation", r):
        return "studied_in", "the record studies or presents the cited work"
    return "related", "related, not the work cited"


# ------------------------------------------------------------------ helpers
def load_cards() -> dict:
    return {json.loads(l)["cited_work_id"]: json.loads(l) for l in open(E62O / "cards62.jsonl", encoding="utf-8")}


def verification() -> dict:
    """exp 62 decision id -> the blind rounds that sampled it (by qkey: a fixed decision supersedes the sampled one)."""
    rows = [json.loads(l) for l in open(E62O / "decisions62.jsonl", encoding="utf-8")]
    qk = {d["decision_id"]: d["qkey"] for d in rows}
    out = defaultdict(list)
    for rnd, sc, adj in ((1, "blind62_scored.json", "blind62_adjudication.json"),
                         (2, "blind62b_scored.json", "blind62b_adjudication.json")):
        S = json.loads((E62O / sc).read_text(encoding="utf-8"))
        A = {c["bid"]: c for c in json.loads((E62O / adj).read_text(encoding="utf-8"))["cases"]}
        for r in S["rows"]:
            a = A.get(r["bid"])
            out[qk.get(r["decision_id"])].append(dict(
                round=rnd, item=r["bid"], sampled=r["decision_id"], blind=r["blind"], agree=r["agree"],
                verdict=("agree" if r["agree"] else f"adjudicated: {a['right']} right" if a else "disagree"),
                adjudication=(a or {}).get("why")))
    return out


def marc_record(mcon, c999: str) -> dict | None:
    r = mcon.execute("SELECT * FROM records WHERE c999 = ? LIMIT 1", (str(c999),)).fetchone()
    if not r:
        return None
    rec = {k: r[k] for k in ("rec", "c999", "title", "subtitle", "title_en", "type", "year", "year_int", "year_hijri",
                             "language", "journal", "journal_en", "journal_code", "volume", "issue", "pages",
                             "page_first", "page_last", "article_seq", "doi", "databases", "country", "publisher")
           if r[k] not in (None, "")}
    rec["authors"] = [dict(seq=a["seq"], tag=a["tag"], name=a["name"], latin=a["latin"], role=a["role"],
                           authority_id=a["authority_id"] or None, is_org=a["is_org"])
                      for a in mcon.execute("SELECT * FROM authors WHERE rec = ? ORDER BY seq", (r["rec"],))]
    rec["stems"] = [p["stem"] for p in mcon.execute("SELECT stem FROM pdf_ids WHERE rec = ? ORDER BY seq", (r["rec"],))]
    return rec


YEAR_PAREN = re.compile(r"\(\s*(?:1[6-9]\d\d|20\d\d|[١٢][٠-٩]{3})[^()]{0,14}\)\s*[.:،,]?\s*")
YEAR_BARE = re.compile(r"(?<![\d٠-٩])(?:1[6-9]\d\d|20\d\d|[١٢][٠-٩]{3})[a-zأ-ي]?\s*[.:،,]\s+")


def item_title(m: dict) -> str | None:
    """The title of the article a journal-name card's citation prints (exp 62: «the citation is an article whose
    title the reader missed»): the words between the year and the journal's name. None when that is not clean."""
    printed, p = m["printed"] or "", m["parsed"] or {}
    src = (p.get("source_title") or "").strip()
    if len(src) < 3:
        return None
    i = printed.lower().find(src.lower())
    if i <= 0:
        return None
    pre = printed[:i]
    cut = [x.end() for x in YEAR_PAREN.finditer(pre)] or [x.end() for x in YEAR_BARE.finditer(pre)]
    if not cut:
        return None
    t = pre[cut[-1]:].strip(" .,،:;-–—\"'«»“”[]")
    t = re.sub(r"\s+", " ", t)
    words = t.split()
    if not (3 <= len(words) <= 45) or YEAR_PAREN.search(t) or re.search(r"https?:|www\.", t):
        return None
    return t


def pick_group(cards, split, cid, other) -> int:
    """finalize62.pick_group: which group of a split card is the one the other card is one work with."""
    if cid not in split:
        return 0
    ot = tokens(cards[other]["title"])
    ostems = set(cards[other]["stems"])
    oau = {w for a in cards[other]["authors"] for w in tokens(a["printed"])}
    best, bi = -1, 0
    for gi, g in enumerate(split[cid]):
        for m in [m for m in cards[cid]["members"] if any(pc in m["mention_id"] for pc in g)]:
            pp = m["parsed"] or {}
            t = pp.get("article_title") or pp.get("chapter_title") or pp.get("source_title") or ""
            s = 2.0 * (m["stem"] in ostems) + 0.5 * bool(oau & set(tokens(m["printed"] or ""))) + \
                title_sim(tokens(t), ot)["dice"]
            if s > best:
                best, bi = s, gi
    return bi


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cards = load_cards()
    D = standing()
    V = verification()
    con = sqlite3.connect(f"file:{STATE}?mode=ro", uri=True)
    pubs = {r[0] for r in con.execute("SELECT pub_id FROM publications")}
    active = {r[0] for r in con.execute("SELECT cited_work_id FROM cited_works WHERE status = 'active'")}
    mcon = sqlite3.connect(f"file:{MARC}?mode=ro", uri=True)
    mcon.row_factory = sqlite3.Row
    plan, held, notes = [], Counter(), []

    def mids(cid, pieces):
        return [m["mention_id"] for m in cards[cid]["members"] if any(pc in m["mention_id"] for pc in pieces)]

    def prov(d, rule, **extra):
        return dict(experiment=62, decision_id=d["decision_id"], qkey=d["qkey"], kind=d["kind"], level=d["level"],
                    basis=d["basis"], confidence=d["confidence"], reason=d["reason"], made_at=d["made_at"],
                    proposing_rule_stood=d["trivial"], verification=V.get(d["qkey"], []), rule=rule,
                    evidence_ids=d["evidence_ids"][:12], **extra)

    def add(src, op, keys, payload, d, rule, note=None, conf=None, **extra):
        plan.append(dict(source_id=src, op=op, subject_keys=keys, payload=payload,
                         reason_code=f"librarian:{rule}", note=note or d["reason"],
                         confidence=conf or CONF.get(d["confidence"], "likely"),
                         evidence=dict(source_id=src, provenance=prov(d, rule, **extra))))

    def record_of(pid):
        if pid in pubs:
            return None
        return marc_record(mcon, pid[1:])

    # ---------------------------------------------------------------- 1. the cards: splits, not a work
    split = {}           # card -> groups (pieces), from the standing split decisions
    split_src = {}
    dropped, per_cit, see_split = set(), set(), set()
    for d in D:
        if d["level"] != "card":
            continue
        cid = d["subject_keys"][0]
        if d["kind"] == "split_card":
            split[cid] = d["decision"]["groups"]
            split_src[cid] = f"E62:{d['decision_id']}"
        elif d["kind"] == "not_a_work":
            a = d["decision"].get("action")
            (dropped if a == "drop" else per_cit if a == "one_per_citation" else see_split if a == "see_split"
             else set()).add(cid)
    for d in D:
        if d["kind"] != "split_card":
            continue
        cid = d["subject_keys"][0]
        groups = [dict(members=mids(cid, g)) for g in d["decision"]["groups"]]
        add(split_src[cid], "split_work", [f"work:{cid}"], dict(groups=groups), d, "exp62-apply")
    # joins: a split-off citation that is another card's work
    for d in D:
        if d["kind"] != "split_card":
            continue
        cid = d["subject_keys"][0]
        for j in d["decision"].get("joins") or []:
            m = mids(cid, [j["member"]])
            tc, _, tg = j["card"].partition("#")
            tkey = f"work:@{split_src[tc]}#{int(tg) - 1}" if tg and int(tg) > 1 else f"work:{tc}"
            add(f"E62:{d['decision_id']}:join:{m[0]}", "move_member", [f"mention:{m[0]}", tkey], {}, d,
                "exp62-apply", note=f"split-off citation joins {j['card']}: {d['reason']}")
    # a card can carry two not-a-work answers (its split packet and its not-a-work packet): one Desk decision per
    # card, with finalize62's precedence (drop, then one per citation, then retitle); the other is recorded beside it
    PREC = dict(drop=0, one_per_citation=1, retitle=2)
    nw = defaultdict(list)
    for d in D:
        if d["kind"] == "not_a_work":
            nw[d["subject_keys"][0]].append(d)
    for cid, ds in sorted(nw.items()):
        ds = sorted(ds, key=lambda x: PREC.get(x["decision"].get("action"), 9))
        d, also = ds[0], ds[1:]
        a = d["decision"].get("action")
        for x in also:
            held[f"not_a_work: a second answer on the card ({x['decision'].get('action')}; "
                 f"{a} applied, finalize62's precedence)"] += 1
        if a == "see_split":
            held["not_a_work: see_split (its split decision carries it)"] += 1
            continue
        if cid in split:
            held["not_a_work on a card also split (the split carries it)"] += 1
            continue
        payload = dict(action=a)
        if a in ("retitle", "one_per_citation"):
            titles = {m["mention_id"]: t for m in cards[cid]["members"] if (t := item_title(m))}
            if titles:
                payload["titles"] = titles
        add(f"E62:{d['decision_id']}", "not_a_work", [f"work:{cid}"], payload, d, "exp62-apply",
            note=f"{d['reason']} ({d['decision'].get('why')})",
            also=[dict(decision_id=x["decision_id"], qkey=x["qkey"], action=x["decision"].get("action"))
                  for x in also])
    for d in D:
        if d["kind"] == "card_ok":
            add(f"E62:{d['decision_id']}", "confirm_work", [f"work:{d['subject_keys'][0]}"], {}, d, "exp62-apply")

    # ---------------------------------------------------------------- 2. pairs: same work, editions (D40, D41)
    def wkey(cid, other):
        gi = pick_group(cards, split, cid, other)
        return f"work:{cid}" if gi == 0 else f"work:@{split_src[cid]}#{gi}"

    gone = dropped | per_cit
    for d in D:
        if d["level"] != "pair":
            continue
        a, b = d["subject_keys"]
        k = d["kind"]
        if d["decision_id"] == D40_NOT:
            held["edition_of not applied: D40 (al-Nawawi's «شرح صحيح مسلم» stays his commentary)"] += 1
            notes.append(dict(decision=d["decision_id"], why="D40"))
            continue
        if d["decision_id"] == "D62-42695029d1f3":       # D40: different_work -> edition_of Sahih Muslim
            add(f"E62:{d['decision_id']}:D40", "edition_of", [f"work:{D40_SAHIH}", f"work:{D40_NAWAWI}"],
                dict(edition_b="بشرح النووي (شرح النووي على صحيح مسلم)"), d, "D40", conf="sure",
                note="D40 (owner, 2026-11-02): «صحيح مسلم بشرح النووي» is a citation of Sahih Muslim; al-Nawawi's "
                     "commentary is recorded as its edition")
            continue
        if d["decision_id"] == D42_PAIR:
            continue                                      # below, as two chapters of one book
        if d["decision_id"] in D43_PAIRS:
            art, th = D43_PAIRS[d["decision_id"]]
            add(f"E62:{d['decision_id']}:D43", "relate_works", [f"work:{art}", f"work:{th}"],
                dict(relation="derived_from", why=d["reason"]), d, "D43", conf="sure",
                note="D43 (owner, 2026-11-02): a thesis and the article drawn from it are two works, related "
                     f"(derived from). {d['reason']}")
            continue
        if d["decision_id"] in D42_PART_OF:
            ch, vol = D42_PART_OF[d["decision_id"]]
            add(f"E62:{d['decision_id']}:type", "set_work_type", [f"work:{ch}"], dict(type="chapter"), d, "D42",
                note=f"D42: a chapter cited under its own author is its own work. {d['reason']}")
            add(f"E62:{d['decision_id']}", "relate_works", [f"work:{ch}", f"work:{vol}"],
                dict(relation="part_of", why=d["reason"]), d, "D42")
            continue
        if k not in ("same_work", "edition_of"):
            held[f"pair: {k}"] += 1
            continue
        if a in gone or b in gone:
            held[f"pair {k} on a card that is not a work (dropped / one per citation)"] += 1
            notes.append(dict(decision=d["decision_id"], why="card not a work", cards=[a, b]))
            continue
        rule = "D41" if d["decision_id"] in D41 else "exp62-apply"
        add(f"E62:{d['decision_id']}", k, [wkey(a, b), wkey(b, a)], {}, d, rule)

    # D42: the collective book, its two chapters
    d = next(x for x in D if x["decision_id"] == D42_PAIR)
    book = defined_work_id(D42_BOOK["natural"])
    add(f"E62:{D42_PAIR}:book", "define_work", [f"work:{book}"],
        dict(natural=D42_BOOK["natural"], title=D42_BOOK["title"], pub_type="book", year=D42_BOOK["year"],
             publisher=D42_BOOK["publisher"], place=D42_BOOK["place"], lang="ar", series=D42_BOOK["series"]),
        d, "D42", conf="sure",
        note="D42 (owner, 2026-11-02): the collective book whose chapters are cited under their authors' names")
    for ch, au in D42_CHAPTERS.items():
        add(f"E62:{D42_PAIR}:type:{ch}", "set_work_type", [f"work:{ch}"], dict(type="chapter"), d, "D42",
            conf="sure", note=f"D42: {au}'s chapter in «{D42_BOOK['title']}», a work of its own credited to {au}")
        add(f"E62:{D42_PAIR}:part:{ch}", "relate_works", [f"work:{ch}", f"work:{book}"],
            dict(relation="part_of", why=f"{au}'s chapter of the collective book (D42)"), d, "D42", conf="sure",
            note=f"D42: {au}'s chapter is part of «{D42_BOOK['title']}» (the book shows it holds the chapter)")

    # ---------------------------------------------------------------- 3. links and relations
    # the works the applied pairs make (to see a relation made moot: the same work linked to that record as itself)
    par = {}

    def find(x):
        while par.get(x, x) != x:
            x = par[x]
        return x
    for p in plan:
        if p["op"] in ("same_work", "edition_of"):
            a, b = (k.split(":", 1)[1] for k in p["subject_keys"])
            par[find(b)] = find(a)
    linked = defaultdict(set)
    for d in D:
        if d["kind"] == "links_to_publication" and _k1b(d) and _venue_fits(d):
            t = d["decision"]["target"]
            linked[find(d["subject_keys"][0])].add(t.get("pub_id") or f"W{t['c999']}")
    rel_table = []
    for d in D:
        if d["level"] != "catalogue":
            continue
        cid = d["subject_keys"][0]
        t = d["decision"].get("target") or {}
        pid = t.get("pub_id") or (f"W{t['c999']}" if t.get("c999") else None)
        if cid in dropped:
            held[f"catalogue {d['kind']} on a dropped card"] += 1
            continue
        if cid in D44 and d["kind"] in ("relation", "unsure"):
            rec = record_of(pid)
            pay = dict(**{"as": "same_text"}, cited_as=(cards[cid]["members"][0]["printed"] or "")[:400])
            if rec:
                pay["record"] = rec
            add(f"E62:{d['decision_id']}:D44", "link_publication", [f"work:{cid}", f"pub:{pid}"], pay, d, "D44",
                conf="sure" if d["kind"] == "relation" else "likely",
                note="D44 (owner, 2026-11-02): the same text published in two journals; the citation is linked to "
                     f"the one Mandumah holds, marked same text. {d['reason']}")
            continue
        if d["kind"] == "links_to_publication":
            if not (_k1b(d) and _venue_fits(d)):
                held["link not passing K1c"] += 1
                continue
            rec = record_of(pid)
            pay = {"as": "work"}
            if rec:
                pay["record"] = rec
            add(f"E62:{d['decision_id']}", "link_publication", [f"work:{cid}", f"pub:{pid}"], pay, d, "K1c")
        elif d["kind"] == "relation":
            if pid in linked[find(cid)]:
                held["relation made moot: the work it joins is linked to that record as itself"] += 1
                notes.append(dict(decision=d["decision_id"], why="relation moot: same work linked to the record",
                                  card=cid, pub=pid))
                continue
            rel, why = rel_kind(d)
            rec = record_of(pid)
            pay = dict(relation=rel, why=why, unlink=True)
            if rec:
                pay["record"] = rec
            rule = "D43" if why.startswith("D43") else "exp62-apply"
            add(f"E62:{d['decision_id']}", "relate_publication", [f"work:{cid}", f"pub:{pid}"], pay, d, rule)
            rel_table.append(dict(card=cid, pub=pid, relation=rel, why=why, record_type=t.get("type"),
                                  card_type=d["decision"]["card"]["type"], reason=d["reason"]))
        else:
            held[f"catalogue: {d['kind']}"] += 1

    # every key must exist (or be planned)
    missing = sorted({k for p in plan for k in p["subject_keys"] if k.startswith("work:C") and k[5:] not in active
                      and k[5:] != book})
    (OUT / "plan67.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in plan), encoding="utf-8")
    (OUT / "relations67.json").write_text(json.dumps(rel_table, ensure_ascii=False, indent=1), encoding="utf-8")
    S = dict(planned=len(plan), by_op=dict(Counter(p["op"] for p in plan)),
             by_rule=dict(Counter(p["reason_code"] for p in plan)),
             by_op_rule={f"{p['op']} {p['reason_code']}": n for p, n in []},
             relations=dict(Counter(r["relation"] for r in rel_table)),
             new_publications=sum(1 for p in plan if "record" in p["payload"]),
             titles_found=sum(len(p["payload"].get("titles") or {}) for p in plan if p["op"] == "not_a_work"),
             retitle_without_title=sum(1 for p in plan if p["op"] == "not_a_work" and p["payload"]["action"] ==
                                       "retitle" and not p["payload"].get("titles")),
             held=dict(held), notes=notes, missing_cards=missing)
    S["by_op_rule"] = dict(Counter(f"{p['op']} {p['reason_code']}" for p in plan))
    (OUT / "plan67_summary.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
