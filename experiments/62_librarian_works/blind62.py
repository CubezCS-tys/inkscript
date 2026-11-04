"""Experiment 62, step 5b: the blind second judgement — a random stratified sample of standing decisions, written as
evidence only (no decision, no reason, no rule proposal, no confidence) for an independent judge, and the scoring of
its answers against the librarian's.

    python3 blind62.py make            -> out/blind62_packets.jsonl (+ out/blind62_key.json: which decision each is)
    python3 blind62.py score ANSWERS   -> out/blind62_scored.json (agreement per kind; the disagreements to adjudicate)
    python3 blind62.py make2 / score2 ANSWERS  -> round 2 (out/blind62b_*): 100 links passing K1b, 40 same_work,
                                                  20 not-a-work cards, drawn after the round-1 fixes
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))

SEED = 6262
STRATA = [  # (level, kind, n)
    ("pair", "same_work", 25), ("pair", "edition_of", 15), ("pair", "different_work", 25), ("pair", "unsure", 4),
    ("card", "split_card", 10), ("card", "card_ok", 10), ("card", "not_a_work", 15),
    ("catalogue", "links_to_publication", 30), ("catalogue", "relation", 12), ("catalogue", "no_link", 10),
]
OPTIONS = dict(
    pair=["same_work", "edition_of", "part_of", "different_work", "unsure"],
    card_split=["card_ok", "split_card", "not_a_work", "unsure"],
    card_notwork=["card_ok", "not_a_work_drop", "not_a_work_retitle", "not_a_work_one_per_citation", "unsure"],
    catalogue=["links_to_publication", "relation", "no_link", "unsure"])


def card_view(c: dict, ctx) -> dict:
    ms = []
    for i, m in enumerate(c["members"][:12]):
        x = dict(n=i + 1, article=m["stem"], kind=m["kind"], printed=(m["printed"] or "")[:500])
        if m.get("note") and m["note"] != m["printed"]:
            x["note"] = m["note"][:400]
        if m["kind"] != "full" or len(m["printed"] or "") < 40:
            t = ctx(m["mention_id"])
            if t:
                x["text_before_the_note_call"] = t[-260:]
        ms.append(x)
    return dict(card=c["cited_work_id"], title=c["title"], type=c["pub_type"],
                authors=[a["printed"] for a in c["authors"]][:5], cited_by_articles=c["n_articles"], citations=ms)


# round 2 (after the fixes of round 1): the kinds that decide the APPLY rule, larger samples, none drawn in round 1
SEED2 = 6264
STRATA2 = [("catalogue", "links_to_publication", 100), ("pair", "same_work", 40), ("card", "not_a_work", 20)]


def make(round2: bool = False):
    from finalize62 import standing
    from tools62 import cards, context
    C = cards()
    D = sorted(standing(), key=lambda d: d["decision_id"])
    rnd = random.Random(SEED2 if round2 else SEED)
    items, key = [], {}
    taken = set()
    if round2:
        k1 = json.loads((OUT / "blind62_key.json").read_text(encoding="utf-8"))["key"]
        taken = {k["packet"] for k in k1.values()} | {k["decision_id"] for k in k1.values()}
        import rules62
        k1b = [r for r in rules62.cat_rules() if r[0].startswith("K1b")][0][2]
    for lvl, kind, n in (STRATA2 if round2 else STRATA):
        pool = [d for d in D if d["level"] == lvl and d["kind"] == kind]
        if round2:
            pool = [d for d in pool if d["decision_id"] not in taken and d["packet"] not in taken
                    and (kind != "links_to_publication" or k1b(d))
                    and (kind != "not_a_work" or d["packet"].startswith("notwork:"))]
        for d in rnd.sample(pool, min(n, len(pool))):
            bid = f"{'B2' if round2 else 'B'}{len(items) + 1:03d}"
            if lvl == "pair":
                a, b = d["subject_keys"]
                pk = dict(bid=bid, question="Are card A and card B the same work? same_work = one work (same or "
                          "unknown edition); edition_of = one work, another printing / translation / tahqiq; part_of "
                          "= one is a volume, chapter or part of the other; different_work; unsure.",
                          options=OPTIONS["pair"], A=card_view(C[a], context), B=card_view(C[b], context))
            elif lvl == "card":
                cid = d["subject_keys"][0]
                if d["packet"].startswith("notwork:"):
                    pk = dict(bid=bid, question="Is this card a work? card_ok = a real work (its title is right); "
                              "not_a_work_drop = a journal / newspaper named only by issue or date, unpublished data, a "
                              "bare web site (not a work: drop from work counts); not_a_work_retitle = one real item "
                              "whose own title the card lost (the card shows a journal's name); "
                              "not_a_work_one_per_citation = several different items on one card titled with a journal's "
                              "name; unsure.", options=OPTIONS["card_notwork"], card=card_view(C[cid], context))
                else:
                    pk = dict(bid=bid, question="Are all citations on this card one work? card_ok = yes; split_card = "
                              "no: give the groups of citation numbers that are one work each (e.g. [[1,3],[2]]); "
                              "not_a_work = the card is not a work at all; unsure.", options=OPTIONS["card_split"],
                              card=card_view(C[cid], context))
            else:
                cid = d["subject_keys"][0]
                t = d["decision"].get("target") or {}
                pk = dict(bid=bid, question="Is the cited work (the card) this Mandumah record? links_to_publication = "
                          "the record IS the cited work; relation = the record is about it or related (a review, a thesis "
                          "summary, an article drawn from the cited thesis, a later article on the same theme) but not "
                          "the cited work; no_link = unrelated; unsure.", options=OPTIONS["catalogue"],
                          card=card_view(C[cid], context),
                          record={k: t.get(k) for k in ("c999", "title", "subtitle", "authors", "year", "type", "journal",
                                                        "stem") if t.get(k)})
            items.append(pk)
            key[bid] = dict(decision_id=d["decision_id"], level=lvl, kind=kind, confidence=d["confidence"],
                            action=d["decision"].get("action"), groups=d["decision"].get("groups"),
                            packet=d["packet"])
    tag = "blind62b" if round2 else "blind62"
    with open(OUT / f"{tag}_packets.jsonl", "w", encoding="utf-8") as f:
        for x in items:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    (OUT / f"{tag}_key.json").write_text(json.dumps(dict(seed=SEED2 if round2 else SEED, strata=STRATA2 if round2
                                                         else STRATA, key=key), ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print(len(items), Counter((k["level"], k["kind"]) for k in key.values()))


def norm_answer(a: dict, k: dict) -> str:
    ans = a.get("answer")
    if k["level"] == "card" and k["packet"].startswith("notwork:"):
        if ans == "not_a_work_drop":
            return "not_a_work:drop"
        if ans == "not_a_work_retitle":
            return "not_a_work:retitle"
        if ans == "not_a_work_one_per_citation":
            return "not_a_work:one_per_citation"
        return ans
    return ans


def mine(k: dict) -> str:
    if k["kind"] == "not_a_work":
        return f"not_a_work:{k.get('action')}"
    return k["kind"]


def score(path: str, tag: str = "blind62"):
    key = json.loads((OUT / f"{tag}_key.json").read_text(encoding="utf-8"))["key"]
    ans = {}
    for l in open(path, encoding="utf-8"):
        if l.strip():
            a = json.loads(l)
            ans[a["bid"]] = a
    rows = []
    for bid, k in key.items():
        a = ans.get(bid)
        if not a:
            continue
        m, b = mine(k), norm_answer(a, k)
        # a same-work vs edition-of disagreement joins the same two cards either way: counted as agreement on
        # "one work", and listed separately
        one = {"same_work", "edition_of"}
        agree = m == b or (m in one and b in one)
        rows.append(dict(bid=bid, decision_id=k["decision_id"], level=k["level"], kind=k["kind"], mine=m, blind=b,
                         agree=agree, exact=m == b, blind_reason=a.get("reason"), blind_confidence=a.get("confidence"),
                         blind_groups=a.get("groups"), my_groups=k.get("groups"), my_confidence=k["confidence"]))
    by = defaultdict(lambda: Counter())
    for r in rows:
        by[f"{r['level']}:{r['mine'].split(':')[0]}"]["n"] += 1
        by[f"{r['level']}:{r['mine'].split(':')[0]}"]["agree"] += r["agree"]
    out = dict(n=len(rows), agree=sum(r["agree"] for r in rows), exact=sum(r["exact"] for r in rows),
               by_kind={k: dict(v) for k, v in sorted(by.items())},
               disagreements=[r for r in rows if not r["agree"]], rows=rows)
    (OUT / f"{tag}_scored.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n", "agree", "exact", "by_kind")}, ensure_ascii=False, indent=1))
    print(len(out["disagreements"]), "disagreements")


if __name__ == "__main__":
    {"make": lambda: make(), "make2": lambda: make(True), "score": lambda: score(sys.argv[2]),
     "score2": lambda: score(sys.argv[2], "blind62b")}[sys.argv[1]]()
