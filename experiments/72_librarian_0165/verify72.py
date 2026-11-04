"""Experiment 72: verification without the owner.

    python verify72.py checks     experiment 63's hard checks (institutions) and experiment 62's (cited works) over
                                  every decision this pass plans -> out/checks72.json
    python verify72.py alarm      the cross-family re-ask: Sonnet on 2% of Flash's applied answers; Flash (asked
                                  first, on every question) on all of Opus's -> out/alarm72.jsonl, out/alarm72.json
    python verify72.py sample     40 applied decisions drawn at random (seed 7240) for the hand check
                                  -> out/handcheck72_sample.json, out/handcheck72_sample.txt
    python verify72.py score      the hand check's verdicts (out/handcheck72.jsonl) -> precision by kind
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict

from common72 import DESK, E56, E62, E63, OUT, add_paths, jl, js, wjl, wjs

add_paths(E56, E56.parent / "46_platform_db", E62, E63, DESK)


def plan():
    return jl(OUT / "plan72.jsonl")


def checks():
    from inst72 import desk_defined, load_authority
    AUTH = load_authority()
    import hardchecks63 as H
    P = {p["key"]: p for p in jl(OUT / "inst" / "packets56.jsonl")}
    I = defaultdict(lambda: dict(affiliations=[], names=[], country=None))
    for p in P.values():
        for lvl, m in (p.get("machine") or {}).items():
            I[m["inst_id"]]["affiliations"].append(p["key"])
            I[m["inst_id"]]["names"] = m.get("names") or []
            I[m["inst_id"]]["country"] = m.get("country")
    A = {a["id"]: a for a in js(E56 / "out" / "authority56.json")["institutions"]}
    for b in js(OUT / "inst" / "authority72.json")["bodies"]:
        A[b["id"]] = dict(id=b["id"], name_en=b["name_en"], country=b["country"])
    row_body = {v: k for k, v in desk_defined().items()}
    for p in plan():
        if p["op"] == "define_institution":
            row_body[p["subject_keys"][0][5:]] = p["payload"]["authority"]
    S = []
    for p in plan():
        op, ks, pl = p["op"], p["subject_keys"], p["payload"]
        did = p["source_id"]
        conf = {"sure": "high", "likely": "medium", "unsure": "low"}.get(p["confidence"], "high")
        if op == "link_affiliation" and ks[0][4:].startswith("0165-"):
            S.append(dict(decision_id=did, kind="affiliation_institution", level="affiliation", subject_keys=[ks[0]],
                          confidence=conf, basis=p["reason_code"],
                          decision=dict(status="resolved", institutions=[dict(id=x["authority"]) for x in
                                                                         pl["institutions"]],
                                        country=(pl["institutions"][0] or {}).get("country"))))
        elif op == "not_an_institution":
            S.append(dict(decision_id=did, kind="not_an_institution", level="affiliation", subject_keys=[ks[0]],
                          confidence=conf, basis=p["reason_code"], decision=dict(status="not_institution",
                                                                                 institutions=[], country=None)))
        elif op == "same_institution":
            rows = [k[5:] for k in ks]
            par = None
            from common72 import ro
            con = ro()
            r = con.execute("SELECT parent_id FROM institutions WHERE inst_id = ?", (rows[0],)).fetchone()
            par = row_body.get(r[0]) if r and r[0] else None
            S.append(dict(decision_id=did, kind="same_institution", level="institution", subject_keys=ks,
                          confidence=conf, basis=p["reason_code"],
                          decision=dict(institution=par, machine_rows=rows, bilingual_twin=True)))
        elif op == "set_inst_parent":
            row = ks[0][5:]
            S.append(dict(decision_id=did, kind="set_parent", level="institution", subject_keys=ks, confidence=conf,
                          basis=p["reason_code"], decision=dict(machine_row=row, parent=pl.get("authority"),
                                                                affiliations=I[row]["affiliations"])))
    H.load = lambda: (S, P, I, A)
    H.OUT = OUT / "checks_inst"
    H.main()
    inst = js(OUT / "checks_inst" / "hardchecks63.json")
    # ---------------------------------------------------------------- cited works: experiment 62's checks
    import check62
    import finalize62
    check62.OUT = OUT / "works"
    D = []
    for p in plan():
        op, ks = p["op"], [k.split(":", 1)[1] for k in p["subject_keys"]]
        if op in ("same_work", "edition_of", "not_same_work"):
            D.append(dict(decision_id=p["source_id"], level="pair", subject_keys=ks,
                          kind={"not_same_work": "different_work"}.get(op, op), decision={}))
        elif op == "link_publication":
            rec = p["payload"].get("record") or {}
            D.append(dict(decision_id=p["source_id"], level="catalogue", subject_keys=ks[:1], kind="links_to_publication",
                          decision=dict(target=dict(c999=rec.get("c999") or ks[1][1:], title=rec.get("title") or
                                                    _pub_title(ks[1])))))
    # the earlier answers, for consistency: exp 62's different works (held, not imported) and the Desk's not-same
    e62 = {}
    for d in jl(E62 / "out" / "decisions62.jsonl"):
        e62[d["qkey"]] = d
    C = {json.loads(l)["cited_work_id"] for l in open(OUT / "works" / "cards62.jsonl", encoding="utf-8")}
    for d in e62.values():
        if d.get("level") == "pair" and d["kind"] == "different_work" and set(d["subject_keys"]) <= C:
            D.append(dict(decision_id=d["decision_id"], level="pair", subject_keys=d["subject_keys"],
                          kind="different_work", decision={}))
    finalize62.standing = lambda: D
    check62.main()
    works = js(OUT / "works" / "checks62.json")
    wjs(OUT / "checks72.json", dict(institutions={k: len(v) for k, v in inst.items()},
                                    institutions_findings=inst, works=works["by_check"],
                                    works_findings=works["findings"]))
    print("institutions:", {k: len(v) for k, v in inst.items()})
    print("works:", works["by_check"])


_pt = None


def _pub_title(key):
    global _pt
    if _pt is None:
        from common72 import ro
        _pt = {r[0]: r[1] for r in ro().execute("SELECT pub_id, title_shown FROM publications")}
    return _pt.get(key.split(":", 1)[1] if ":" in key else key)


def alarm():
    from decide72 import answers, label, questions
    Q = questions()
    D = {d["id"]: d for d in jl(OUT / "decisions72.jsonl")}
    S = answers("claude-sonnet-5-5")
    F = answers("gemini-3.8-flash")
    ids = (OUT / "ids_alarm_sonnet.txt").read_text().split()
    rows, ag = [], Counter()
    for i in ids:
        q, d = Q[i], D[i]
        sl = label(q, S.get(i))
        same = sl == d["label"]
        if same and q["kind"] == "works:split" and d["label"] == "split_card":
            g1 = sorted(sorted(g) for g in (d["answer"].get("groups") or []))
            g2 = sorted(sorted(g) for g in ((S[i]["answer"] or {}).get("groups") or []))
            same = g1 == g2
        rows.append(dict(id=i, kind=q["kind"], applied=d["label"], tier="flash", reasker="claude-sonnet-5-5",
                         reask=sl, reask_conf=((S.get(i) or {}).get("answer") or {}).get("confidence"), agree=same))
        ag[(q["kind"], same)] += 1
    # Flash's bodies outside the authority, read through the same review map as Opus's (names, forms, rows)
    import re as _re
    from inst72 import fold
    km = {}
    for b in js(OUT / "inst" / "authority72.json")["bodies"]:
        for x in [b["name_ar"], b["name_en"]] + b["forms"] + b["rows"]:
            if x:
                km[x] = b["id"]
                km[fold(_re.sub(r"\(.*?\)", "", x))] = b["id"]
                km[fold(x)] = b["id"]
    from inst72 import desk_defined
    canon_of = {v: k for k, v in desk_defined().items()}

    def mapped(ids):
        out = []
        for x in ids or []:
            nm = x[4:] if x.startswith("new:") else x
            out.append(km.get(x) or km.get(fold(nm)) or km.get(fold(_re.sub(r"\(.*?\)", "", nm))) or
                       canon_of.get(x) or x)
        return sorted(out)
    orow = []
    for i, d in D.items():
        if d["tier"] == "opus" and d["apply"]:
            fl = label(Q[i], F.get(i))
            same = fl == d["label"]
            if same and d["kind"] == "inst:affiliation" and d["label"] == "resolved":
                same = mapped(d["answer"].get("ids_reviewed") or d["answer"]["ids"]) == mapped(
                    (F[i]["answer"] or {}).get("ids") or [])
            orow.append(dict(id=i, kind=d["kind"], applied=d["label"], tier="opus", reasker="gemini-3.8-flash",
                             reask=fl, agree=same, applied_ids=d["answer"].get("ids_reviewed") or d["answer"].get("ids"),
                             reask_ids=((F.get(i) or {}).get("answer") or {}).get("ids")))
    wjl(OUT / "alarm72.jsonl", rows + orow)
    sonnet_dis = [r for r in rows if not r["agree"]]
    opus = Counter((r["kind"], r["applied"], r["agree"]) for r in orow)
    S_ = dict(sonnet_on_flash=dict(n=len(rows), agree=sum(r["agree"] for r in rows),
                                   disagree_rate=round(len(sonnet_dis) / max(1, len(rows)), 3),
                                   by_kind={f"{k} agree={a}": n for (k, a), n in sorted(ag.items())},
                                   disagreements=sonnet_dis),
              flash_on_opus=dict(n=len(orow), agree=sum(r["agree"] for r in orow),
                                 disagree_rate=round(sum(not r["agree"] for r in orow) / max(1, len(orow)), 3),
                                 by_kind={f"{k} {l} agree={a}": n for (k, l, a), n in sorted(opus.items())}),
              alarm_threshold=0.05)
    wjs(OUT / "alarm72.json", S_)
    print(json.dumps({k: {x: y for x, y in v.items() if x != "disagreements"} if isinstance(v, dict) else v
                      for k, v in S_.items()}, ensure_ascii=False, indent=1))
    for r in sonnet_dis:
        print("  Sonnet disagrees:", r)


def sample(n=40, seed=7240):
    P = [p for p in plan() if p["op"] not in ("define_institution", "set_inst_country")]
    rnd = random.Random(seed)
    pick = rnd.sample(P, n)
    wjs(OUT / "handcheck72_sample.json", pick)
    import tools62
    tools62.OUT = OUT / "works"
    C = tools62.cards()
    aff = {p["key"]: p for p in jl(OUT / "inst" / "aff0165.jsonl")}
    with open(OUT / "handcheck72_sample.txt", "w", encoding="utf-8") as f:
        for i, p in enumerate(pick, 1):
            f.write(f"=== {i:02d} {p['source_id']} {p['op']} {p['reason_code']} ({p['confidence']})\n")
            f.write(f"    keys: {p['subject_keys']}\n    note: {(p['note'] or '')[:300]}\n")
            for k in p["subject_keys"]:
                kind, v = k.split(":", 1)
                if kind == "aff" and k in aff:
                    a = aff[k]
                    f.write(f"    printed: {a['printed']}\n    same author: {[x['printed'] for x in a['same_article']]}\n")
                elif kind == "work" and v in C:
                    c = C[v]
                    f.write(f"    card {v} «{c['title']}» {c['pub_type']}\n")
                    for m in c["members"][:6]:
                        f.write(f"       - [{m['stem']}] {(m['printed'] or '')[:260]}\n")
            if p["op"] in ("link_publication", "relate_publication"):
                rec = p["payload"].get("record") or {}
                f.write(f"    record: {rec.get('c999') or p['subject_keys'][1]} «{rec.get('title') or _pub_title(p['subject_keys'][1])}» "
                        f"{[a.get('name') for a in rec.get('authors', [])][:3]} {rec.get('year')} {rec.get('type')} "
                        f"{rec.get('journal')}  rel={p['payload'].get('relation')} as={p['payload'].get('as')}\n")
            if p["op"] == "link_affiliation":
                f.write(f"    bodies: {[(x['authority'], x['role'], x['country'], x.get('inferred')) for x in p['payload']['institutions']]}\n")
            if p["op"] == "split_work":
                f.write(f"    groups: {[g['members'] for g in p['payload']['groups']]}\n")
            f.write("\n")
    print(open(OUT / "handcheck72_sample.txt", encoding="utf-8").read())


def score():
    H = jl(OUT / "handcheck72.jsonl")
    by = defaultdict(Counter)
    for h in H:
        by[h["op"]][h["verdict"]] += 1
    tot = Counter(h["verdict"] for h in H)
    out = dict(n=len(H), verdicts=dict(tot), precision=round(tot["right"] / max(1, len(H)), 4),
               by_op={k: dict(v) for k, v in by.items()}, wrong=[h for h in H if h["verdict"] != "right"])
    wjs(OUT / "handcheck72_score.json", out)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    dict(checks=checks, alarm=alarm, sample=sample, score=score)[sys.argv[1]]()
