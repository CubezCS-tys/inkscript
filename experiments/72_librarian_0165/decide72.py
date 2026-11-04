"""Experiment 72: experiment 71's production rule, applied to the answers.

    python decide72.py tier1      Flash's answers: which apply (its eight strong kinds), which go to Opus
                                  -> out/ids_opus.txt, out/tier1.json
    python decide72.py final      rules + Flash + Opus (+ the authority review) -> out/decisions72.jsonl (one per
                                  question: the answer, its tier, applied or held and why), out/decisions72_summary.json
    python decide72.py alarm      the 2% cross-family re-ask list: Flash's applied answers to Sonnet
                                  -> out/ids_alarm_sonnet.txt (seed 7272)

The rule (experiment 71's README, "Recommendation"):
1. rules first (R1, R6 for institutions; K1c, P6 for cited works; C1 marks a card as not a work, its action asked);
2. Flash 3.8 (thinking low) on every question the rules leave; applied only for its strong kinds: links to a
   Mandumah record, different works, card ok / card split, set country, rows are one body, set parent, affiliation
   names no body;
3. Opus 5.5 (effort medium) on everything else; applied when it says high, never for unsure, part_of, unit_only or
   a body that is not in the authority (new: or a machine row) before an authority review;
4. the rest -> Desk tasks, with both answers.
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter, defaultdict

from common72 import OUT, jl, js, wjl, wjs

FLASH, OPUS, SONNET = "gemini-3.8-flash", "claude-opus-5-5", "claude-sonnet-5-5"
STRONG = {("works:catalogue", "links_to_publication"), ("works:pair", "different_work"), ("works:split", "card_ok"),
          ("works:split", "split_card"), ("inst:country", "<ISO>"), ("inst:same_institution", "same"),
          ("inst:set_parent", "parent"), ("inst:affiliation", "not_institution")}
NEVER = {"unsure", "part_of", "unit_only"}
# answers that only keep things apart as they are: nothing to apply, nothing for a person (experiment 62's rule for
# different works, which experiment 71 lets Flash apply as a recorded decision; rows of institutions have no such op)
NOCHANGE = {("inst:same_institution", "different")}
ISO = re.compile(r"^[A-Z]{2}$")


def questions() -> dict:
    Q = {}
    for f in sorted((OUT / "questions").glob("*.jsonl")):
        for q in jl(f):
            Q[q["id"]] = q
    return Q


def answers(model) -> dict:
    out = {}
    for a in jl(OUT / "answers" / f"{model}.jsonl"):
        if a.get("answer") is not None or a["id"] not in out:
            out[a["id"]] = a
    return out


def label(q, a) -> str | None:
    if not a or not a.get("answer"):
        return None
    x = (a["answer"].get("answer") or "").strip()
    if q["kind"] == "inst:country":
        return "<ISO>" if ISO.match(x) else ("unsure" if x == "unsure" else None)
    return x if x in q["options"] else None


def cand_ids(q) -> set:
    ev = q["evidence"]
    ids = {c["id"] for c in ev.get("authority_candidates") or []}
    for r in ev.get("rows") or []:
        ids.add(r["id"])
    for m in ev.get("machine") or []:
        mm = re.search(r"id=(I[0-9A-Z]{9})", m)
        if mm:
            ids.add(mm.group(1))
    return ids


def valid(q, a, lab) -> str | None:
    """None when the answer can be applied as it stands; else why not."""
    ans = a["answer"]
    k = q["kind"]
    ids = ans.get("ids") or []
    if k == "works:split" and lab == "split_card":
        n = len(q["evidence"]["card"]["citations"])
        gs = ans.get("groups") or []
        flat = [x for g in gs for x in g]
        if len(gs) < 2 or len(flat) != len(set(flat)) or not set(flat) <= set(range(1, n + 1)):
            return "split groups are not a partition of the citations"
    if k in ("inst:set_parent",) and lab == "parent":
        if len(ids) != 1 or ids[0].startswith("new:") or ids[0] not in cand_ids(q):
            return "the parent is not a candidate (new body: authority review)"
    if k == "inst:affiliation" and lab == "resolved":
        if not ids:
            return "resolved without ids"
        auth = {c["id"] for c in q["evidence"].get("authority_candidates") or []}
        if any(i.startswith("new:") or i not in auth for i in ids):
            return "a body not in the authority (new: or a machine row): authority review"
    if k == "inst:country" and not ISO.match((ans.get("answer") or "")):
        return "not a country code"
    return None


def tier1():
    Q = questions()
    F = answers(FLASH)
    out, to_opus, stat = {}, [], Counter()
    for qid, q in sorted(Q.items()):
        a = F.get(qid)
        lab = label(q, a)
        if lab is None:
            to_opus.append(qid)
            stat[f"{q['kind']}: no usable Flash answer"] += 1
            continue
        why = valid(q, a, lab)
        strong = (q["kind"], lab) in STRONG and not why and not (q["kind"] == "works:notwork" and q["meta"].get("c1"))
        if strong:
            out[qid] = dict(kind=q["kind"], label=lab, tier="flash")
            stat[f"{q['kind']}: Flash applies ({lab})"] += 1
        elif (q["kind"], lab) in NOCHANGE:
            stat[f"{q['kind']}: no change ({lab}: the two stay apart, nothing to apply or ask)"] += 1
        else:
            to_opus.append(qid)
            stat[f"{q['kind']}: to Opus (Flash {lab}{'; ' + why if why else ''})"] += 1
    (OUT / "ids_opus.txt").write_text("\n".join(to_opus))
    wjs(OUT / "tier1.json", dict(flash_applies=len(out), to_opus=len(to_opus), stat=dict(sorted(stat.items()))))
    print(json.dumps(dict(flash_applies=len(out), to_opus=len(to_opus)), indent=1))
    for k, v in sorted(stat.items()):
        print(f"  {v:5d}  {k}")


def alarm(share=0.02, minimum=40, seed=7272):
    D = [d for d in jl(OUT / "decisions72.jsonl") if d["tier"] == "flash" and d["apply"]] if \
        (OUT / "decisions72.jsonl").exists() else []
    if not D:
        t = js(OUT / "tier1.json")
        raise SystemExit(f"run final first ({t['flash_applies']} Flash applies)")
    rnd = random.Random(seed)
    n = max(minimum, round(share * len(D)))
    pick = sorted(rnd.sample([d["id"] for d in D], min(n, len(D))))
    (OUT / "ids_alarm_sonnet.txt").write_text("\n".join(pick))
    print(len(pick), "of", len(D), "Flash-applied decisions to Sonnet")


def final():
    Q = questions()
    F, O = answers(FLASH), answers(OPUS)
    review = {}
    rp = OUT / "inst" / "authority72.json"
    if rp.exists():
        R = js(rp)
        review = R.get("answer_map") or {}           # question id -> {"ids": [...], "ok": bool, "why": ...}
    rows, stat = [], Counter()
    for qid, q in sorted(Q.items()):
        a = F.get(qid)
        lab = label(q, a)
        why = valid(q, a, lab) if lab else "no usable answer"
        base = dict(id=qid, domain=q["domain"], kind=q["kind"], meta=q.get("meta"),
                    flash=(a or {}).get("answer"), opus=(O.get(qid) or {}).get("answer"))
        c1_conflict = q["kind"] == "works:notwork" and q["meta"].get("c1")
        if lab and (q["kind"], lab) in STRONG and not why and not c1_conflict:
            rows.append(dict(base, tier="flash", model=FLASH, label=lab, answer=a["answer"], apply=True, held=None))
            stat[(q["kind"], lab, "flash", "applied")] += 1
            continue
        if lab and (q["kind"], lab) in NOCHANGE and not why:
            rows.append(dict(base, tier="flash", model=FLASH, label=lab, answer=a["answer"], apply=False,
                             held=None, nochange=True))
            stat[(q["kind"], lab, "flash", "no change")] += 1
            continue
        o = O.get(qid)
        olab = label(q, o)
        if not olab:
            rows.append(dict(base, tier="desk", model=None, label=lab, answer=(a or {}).get("answer"), apply=False,
                             held="no usable Opus answer"))
            stat[(q["kind"], str(lab), "desk", "no Opus answer")] += 1
            continue
        ans = dict(o["answer"])
        held = None
        if olab in NEVER:
            held = f"Opus: {olab} (never applied)"
        elif ans.get("confidence") != "high":
            held = f"Opus: {olab}, confidence {ans.get('confidence')}"
        else:
            w = valid(q, o, olab)
            if w and "authority review" in w:
                rv = review.get(qid)
                if rv and rv.get("ok"):
                    ans["ids_reviewed"] = rv["ids"]
                    ans["review"] = rv.get("why")
                else:
                    held = "Opus high, but a body outside the authority that the review did not accept" if rv else \
                        "Opus high, a body outside the authority: authority review pending"
            elif w:
                held = f"Opus: {w}"
            if c1_conflict and olab == "card_ok":
                held = "Opus says card_ok on a card C1 calls not a work (journal's name): to a person"
        rows.append(dict(base, tier="opus" if not held else "desk", model=OPUS, label=olab, answer=ans,
                         apply=held is None, held=held))
        stat[(q["kind"], olab, "opus" if not held else "desk", "applied" if not held else held.split(",")[0])] += 1
    wjl(OUT / "decisions72.jsonl", rows)
    S = defaultdict(dict)
    for (k, lab, tier, what), n in sorted(stat.items()):
        S[k][f"{tier}: {lab} ({what})"] = n
    tot = Counter((r["tier"], r["apply"]) for r in rows)
    summ = dict(questions=len(rows), applied_flash=tot[("flash", True)], applied_opus=tot[("opus", True)],
                no_change=sum(1 for r in rows if r.get("nochange")),
                to_desk=sum(1 for r in rows if not r["apply"] and not r.get("nochange")), by_kind=S)
    wjs(OUT / "decisions72_summary.json", summ)
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    dict(tier1=tier1, final=final, alarm=alarm)[sys.argv[1]]()
