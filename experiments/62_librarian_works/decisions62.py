"""Experiment 62, step 3b: the librarian's verdicts written as decisions (append-only JSONL, one per question).

Levels and kinds
- pair (two cards that might be one work): same_work | edition_of | part_of | different_work | unsure
- card (a card that might hold two works, or might not be a work): split_card | card_ok | not_a_work | unsure
- catalogue (a card and a Mandumah record): links_to_publication | relation | no_link | unsure

Every decision carries the decision, a short reason, the evidence ids (card ids, mention ids, catalogue c999),
confidence (high / medium / low), basis (rule | catalogue | world | context | judgement) and `trivial` (the rule's
own proposal stood). The newest decision per question (`qkey`) stands; a changed answer is a new decision that
supersedes the old one (both stay in the file). Decisions are proposals: nothing is applied to the platform.

    python3 decisions62.py            # judge every packet (rule + overrides62.json) and append what changed
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DEC = OUT / "decisions62.jsonl"
ACTOR = "agent:librarian-62"
sys.path.insert(0, str(HERE))

LEVEL = dict(merge="pair", split="card", notwork="card", catalogue="catalogue")
QUESTION = dict(
    pair="Are these two cards one work (or an edition / part of one)?",
    split="Is this card one work, or does it hold several?",
    notwork="Is this card a work at all?",
    catalogue="Is this cited work a Mandumah publication?")


def did(*parts) -> str:
    return "D62-" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


def latest() -> dict:
    out = {}
    if DEC.exists():
        for l in open(DEC, encoding="utf-8"):
            d = json.loads(l)
            out[d["qkey"]] = d
    return out


def append(decs: list) -> int:
    have = latest()
    n = 0
    with open(DEC, "a", encoding="utf-8") as f:
        for d in decs:
            old = have.get(d["qkey"])
            d["content_id"] = d["decision_id"]
            if old and old.get("content_id", old["decision_id"]) == d["content_id"]:
                continue
            if old:
                d["supersedes"] = old["decision_id"]
                d["decision_id"] = did(d["content_id"], old["decision_id"])
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            have[d["qkey"]] = d
            n += 1
    return n


def _card_brief(cid: str) -> dict:
    from tools62 import authors_of, cards, years_printed
    c = cards()[cid]
    return dict(id=cid, title=c["title"], type=c["pub_type"], authors=authors_of(c)[:3], years=years_printed(c)[:3],
                n_articles=c["n_articles"], n_mentions=c["n_mentions"])


def evidence_text(p: dict) -> str:
    """The evidence a model would read for this packet (its size is what the scale report counts)."""
    from tools62 import cards
    C = cards()
    keep = []
    for cid in p["cards"]:
        c = C[cid]
        keep.append(dict(id=cid, title=c["title"], type=c["pub_type"], authors=[a["printed"] for a in c["authors"]][:4],
                         members=[dict(stem=m["stem"], kind=m["kind"], printed=(m["printed"] or "")[:400])
                                  for m in c["members"][:4]]))
    extra = {k: p.get(k) for k in ("why", "proposal", "best", "edges") if p.get(k)}
    if "edges" in extra:
        extra["edges"] = [dict(a=e["a"], b=e["b"], title=e.get("title"), author=e.get("author"), year=e.get("year"))
                          for e in extra["edges"]]
    if "best" in extra and extra["best"]:
        b = extra["best"]
        extra["best"] = {k: b.get(k) for k in ("c999", "title", "subtitle", "authors", "year", "type", "journal")}
    return json.dumps(dict(cards=keep, **extra), ensure_ascii=False)


def to_decision(p: dict, v: dict) -> dict:
    lvl = LEVEL[p["kind"]]
    kind = v["kind"]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    if p["kind"] == "merge":
        e = v["edge"]
        a, b = e["a"], e["b"]
        dec = dict(cards=[_card_brief(a), _card_brief(b)], rule=e.get("rule"),
                   features={k: e.get(k) for k in ("title", "author", "year", "container") if e.get(k) is not None})
        subj, ev = [a, b], [a, b]
        printed = []
        from tools62 import cards
        for cid in (a, b):
            ms = cards()[cid]["members"]
            printed.append((ms[0]["printed"] or "")[:300] if ms else "")
        q = QUESTION["pair"]
    else:
        cid = p["cards"][0]
        from tools62 import cards
        c = cards()[cid]
        dec = dict(card=_card_brief(cid))
        for k in ("groups", "joins", "action", "no_author"):
            if v.get(k):
                dec[k] = v[k]
        if p["kind"] == "split":
            dec["why"] = p.get("why")
        if p["kind"] == "notwork":
            dec["why"] = p.get("why")
        if p["kind"] == "catalogue":
            t = v.get("target") or p.get("best") or {}
            if p.get("proposal") == "read-article":
                t = dict(c999=p.get("target_c999"), pub_id=p.get("target_pub_id"), stem=p.get("target_stem"),
                         title=p.get("target_title"))
            dec["proposal"] = p.get("proposal")
            dec["target"] = {k: t.get(k) for k in ("c999", "pub_id", "stem", "title", "subtitle", "authors", "year",
                                                    "type", "journal", "s_title", "s_author", "s_year") if t.get(k)}
        subj = [cid]
        ev = [cid] + [m["mention_id"] for m in c["members"][:6]]
        if dec.get("target", {}).get("c999"):
            ev.append(f"c999:{dec['target']['c999']}")
        printed = [(m["printed"] or "")[:300] for m in c["members"][:4]]
        q = QUESTION[p["kind"]]
    sig = json.dumps([kind, dec.get("groups"), dec.get("action"), dec.get("joins"), (dec.get("target") or {}).get("c999"),
                      v.get("confidence"), v.get("basis"), v.get("reason")], ensure_ascii=False, sort_keys=True)
    out = dict(decision_id=did(v["qkey"], sig), qkey=v["qkey"], made_at=now, actor=ACTOR, level=lvl, kind=kind,
               question=q, packet=p["key"], subject_keys=subj, decision=dec, reason=v.get("reason"), evidence_ids=ev,
               confidence=v.get("confidence"), basis=v.get("basis"), trivial=bool(v.get("trivial")), printed=printed,
               found_while_judging=bool(v.get("extra")))
    out["size"] = dict(evidence_chars=len(evidence_text(p)),
                       decision_chars=len(json.dumps({k: out[k] for k in ("kind", "decision", "reason", "evidence_ids",
                                                                           "confidence")}, ensure_ascii=False)))
    return out


def orphan_overrides(ovr: dict, packets: list) -> list:
    """Overrides for questions no packet asked (a pair the blocking missed whose cards share no packet; a card split
    found while judging): judged as packets of their own."""
    keys = {p["key"] for p in packets}
    in_packets = set()
    for p in packets:
        if p["kind"] == "merge":
            cs = set(p["cards"])
            for k in ovr:
                a, _, b = k.partition("|")
                if b and a in cs and b in cs:
                    in_packets.add(k)
    extra = []
    for k, o in sorted(ovr.items()):
        if "|" in k and not k.startswith(("split:", "notwork:", "catalogue:")):
            a, _, b = k.partition("|")
            if k not in in_packets and a < b:
                extra.append(dict(key=f"merge:{a}|{b}", kind="merge", cards=[a, b], orphan=True,
                                  edges=[dict(a=a, b=b, rule="found while judging")]))
        elif k.startswith("split:") and k not in keys:
            extra.append(dict(key=k, kind="split", cards=[k.split(":", 1)[1]], why=["found while judging"],
                              author_groups=[], no_author=[], orphan=True))
    return extra


def main():
    from judge62 import judge, overrides, packets as all_packets
    ovr = overrides()
    P = all_packets()
    P += orphan_overrides(ovr, P)
    decs = []
    for p in P:
        if p.get("orphan") and p["kind"] == "merge":
            e = p["edges"][0]
            k = f"{e['a']}|{e['b']}"
            v = dict(ovr[k], trivial=False, qkey=f"pair|{k}", edge=e, extra=True)
            vs = [v]
        elif p.get("orphan") and p["kind"] == "split":
            vs = [dict(ovr[p["key"]], trivial=False, qkey=p["key"], extra=True)]
        else:
            vs = judge(p, ovr)
        for v in vs:
            if "edge" in v and "title" not in v["edge"]:
                v["edge"].setdefault("title", None)
            decs.append(to_decision(p, v))
    n = 0
    for i in range(0, len(decs), 60):          # written batch by batch: nothing lost if stopped
        n += append(decs[i:i + 60])
    L = [d for d in latest().values()]
    print(dict(decisions=len(decs), appended=n, standing=len(L), kinds=dict(Counter((d["level"], d["kind"]) for d in L)),
               confidence=dict(Counter(d["confidence"] for d in L)), trivial=sum(d["trivial"] for d in L)))


if __name__ == "__main__":
    main()
