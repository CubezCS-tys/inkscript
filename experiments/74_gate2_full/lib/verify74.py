"""Experiment 74 (from verify72.py): verification of one journal's pass without the owner.

    python verify74.py checks     experiment 63's hard checks (institutions) and experiment 62's (cited works) over
                                  every decision this pass plans -> OUT/checks74.json
    python verify74.py alarm      the cross-family re-ask: Sonnet on 2% of Flash's applied answers (min 40); Flash
                                  (asked first, on every question) on all of Opus's -> OUT/alarm74.jsonl, alarm74.json
    python verify74.py sample     the hand-check sheet (exp 72's lesson 4: read the small kinds whole): EVERY planned
                                  decision of each kind (reason code) with fewer than 50, 10 random of each larger kind,
                                  and 30 more at random over everything (seed 7400 + the journal code)
                                  -> OUT/handcheck_sheet.txt (printed text / record beside each), OUT/handcheck74_
                                  sample.json, OUT/handcheck74_template.jsonl (one line per item: fill "verdict" =
                                  right | minor | wrong and "note"; save as OUT/handcheck74.jsonl)
    python verify74.py score      the verdicts (OUT/handcheck74.jsonl) -> precision by kind; kinds under 98% (minor
                                  counted right) -> OUT/hold_kinds_suggested.json
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict

from common74 import DESK, E56, E62, E63, JOURNAL, OUT, add_paths, jl, js, reviewed_bodies, wjl, wjs

add_paths(E56, E56.parent / "46_platform_db", E62, E63, DESK)


def plan():
    return jl(OUT / "plan74.jsonl")


def checks():
    from inst74 import desk_defined, load_authority
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
    for b in reviewed_bodies().values():
        A[b["id"]] = dict(id=b["id"], name_en=b.get("name_en"), country=b.get("country"))
    row_body = {v: k for k, v in desk_defined().items()}
    for p in plan():
        if p["op"] == "define_institution":
            row_body[p["subject_keys"][0][5:]] = p["payload"]["authority"]
    S = []
    for p in plan():
        op, ks, pl = p["op"], p["subject_keys"], p["payload"]
        did = p["source_id"]
        conf = {"sure": "high", "likely": "medium", "unsure": "low"}.get(p["confidence"], "high")
        if op == "link_affiliation" and ks[0][4:].startswith(JOURNAL + "-"):
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
            from common74 import ro
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
    wjs(OUT / "checks74.json", dict(institutions={k: len(v) for k, v in inst.items()},
                                    institutions_findings=inst, works=works["by_check"],
                                    works_findings=works["findings"]))
    print("institutions:", {k: len(v) for k, v in inst.items()})
    print("works:", works["by_check"])


_pt = None


def _pub_title(key):
    global _pt
    if _pt is None:
        from common74 import ro
        _pt = {r[0]: r[1] for r in ro().execute("SELECT pub_id, title_shown FROM publications")}
    return _pt.get(key.split(":", 1)[1] if ":" in key else key)


def alarm():
    from decide74 import answers, label, questions
    Q = questions()
    D = {d["id"]: d for d in jl(OUT / "decisions74.jsonl")}
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
    from inst74 import fold
    km = {}
    for b in reviewed_bodies().values():
        for x in [b.get("name_ar"), b.get("name_en")] + list(b.get("forms") or []) + list(b.get("rows") or []):
            if x:
                km[x] = b["id"]
                km[fold(_re.sub(r"\(.*?\)", "", x))] = b["id"]
                km[fold(x)] = b["id"]
    from inst74 import desk_defined
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
    wjl(OUT / "alarm74.jsonl", rows + orow)
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
    wjs(OUT / "alarm74.json", S_)
    print(json.dumps({k: {x: y for x, y in v.items() if x != "disagreements"} if isinstance(v, dict) else v
                      for k, v in S_.items()}, ensure_ascii=False, indent=1))
    for r in sonnet_dis:
        print("  Sonnet disagrees:", r)


_MC = None


def _marc(pid):
    """The catalogue record behind a publication id W<c999> (title, authors, year, type, journal), for the sheet."""
    global _MC
    import sqlite3
    from common74 import MARC
    if not pid or not pid.startswith("W"):
        return {}
    if _MC is None:
        _MC = sqlite3.connect(f"file:{MARC}?mode=ro&immutable=1", uri=True)
    r = _MC.execute("SELECT rec, c999, title, year_int, type, journal FROM records WHERE c999 = ? LIMIT 1",
                    (pid[1:],)).fetchone()
    if not r:
        return {}
    au = [x[0] for x in _MC.execute("SELECT name FROM authors WHERE rec = ? ORDER BY seq", (r[0],))][:3]
    return dict(c999=r[1], title=r[2], year=r[3], type=r[4], journal=r[5], authors=au)


def _record_line(p):
    rec = p["payload"].get("record") or _marc(p["subject_keys"][1].split(":", 1)[1])
    au = [a.get("name") if isinstance(a, dict) else a for a in rec.get("authors", [])][:3]
    return (f"    record: {rec.get('c999') or p['subject_keys'][1]} «{rec.get('title') or _pub_title(p['subject_keys'][1])}» "
            f"{au} {rec.get('year')} {rec.get('type')} {rec.get('journal')}  rel={p['payload'].get('relation')} "
            f"as={p['payload'].get('as')}\n")


def sample(seed=None, small=50, per_large=10, extra=30):
    seed = 7400 + int(JOURNAL) if seed is None else seed
    P = [p for p in plan() if p["op"] not in ("define_institution", "set_inst_country")]
    rnd = random.Random(seed)
    by = defaultdict(list)
    for p in P:
        by[p["reason_code"]].append(p)
    pick, why = [], {}
    for rc, ps in sorted(by.items()):
        take = ps if len(ps) < small else rnd.sample(ps, per_large)
        for p in take:
            pick.append(p)
            why[p["source_id"]] = f"whole kind ({len(ps)})" if len(ps) < small else f"10 of {len(ps)}"
    taken = {p["source_id"] for p in pick}
    rest = [p for p in P if p["source_id"] not in taken]
    for p in rnd.sample(rest, min(extra, len(rest))):
        pick.append(p)
        why[p["source_id"]] = "random over everything"
    wjs(OUT / "handcheck74_sample.json", pick)
    wjl(OUT / "handcheck74_template.jsonl", [dict(source_id=p["source_id"], question=(p["evidence"].get("provenance")
                                                                                     or {}).get("question"),
                                                 op=p["op"], reason_code=p["reason_code"], drawn=why[p["source_id"]],
                                                 verdict="", note="") for p in pick])
    import tools62
    tools62.OUT = OUT / "works"
    C = tools62.cards()
    aff = {p["key"]: p for p in jl(OUT / "inst" / "packets56.jsonl")}
    con = None
    with open(OUT / "handcheck_sheet.txt", "w", encoding="utf-8") as f:
        f.write(f"journal {JOURNAL}: {len(pick)} planned decisions to read ({dict(sorted((rc, len(v)) for rc, v in by.items()))})\n\n")
        for i, p in enumerate(pick, 1):
            f.write(f"=== {i:03d} {p['source_id']} {p['op']} {p['reason_code']} ({p['confidence']}) [{why[p['source_id']]}]\n")
            f.write(f"    keys: {p['subject_keys']}\n    note: {(p['note'] or '')[:400]}\n")
            for k in p["subject_keys"]:
                kind, v = k.split(":", 1)
                if kind == "aff" and k in aff:
                    a = aff[k]
                    f.write(f"    printed: {a['printed']}\n    same author: {[x['printed'] for x in a['same_article']][:3]}\n")
                elif kind == "work" and v in C:
                    c = C[v]
                    f.write(f"    card {v} «{c['title']}» {c['pub_type']} ({len(c['members'])} citations)\n")
                    lim = 60 if p["op"] in ("split_work", "confirm_work", "not_a_work") else 6
                    for j, m in enumerate(c["members"][:lim], 1):
                        f.write(f"       {j}. [{m['stem']}] {(m['printed'] or '')[:260]}\n")
                elif kind == "inst":
                    if con is None:
                        from common74 import ro
                        con = ro()
                    rr = con.execute("SELECT i.inst_id, i.kind, i.parent_id, (SELECT group_concat(name, ' | ') FROM "
                                     "institution_names n WHERE n.inst_id = i.inst_id) FROM institutions i WHERE "
                                     "inst_id = ?", (v,)).fetchone()
                    f.write(f"    row: {tuple(rr) if rr else v}\n")
            if p["op"] in ("link_publication", "relate_publication"):
                f.write(_record_line(p))
            if p["op"] == "link_affiliation":
                f.write(f"    bodies: {[(x['authority'], x['role'], x['country'], x.get('inferred')) for x in p['payload']['institutions']]}\n")
            if p["op"] == "split_work":
                cid = p["subject_keys"][0][5:]
                idx = {m["mention_id"]: j for j, m in enumerate(C[cid]["members"], 1)} if cid in C else {}
                f.write(f"    groups: {[[idx.get(x, x) for x in g['members']] for g in p['payload']['groups']]}\n")
            if p["op"] == "not_a_work":
                f.write(f"    action: {p['payload']['action']} titles: {list((p['payload'].get('titles') or {}).values())[:3]}\n")
            f.write("\n")
    print(f"{len(pick)} items -> {OUT / 'handcheck_sheet.txt'}; by kind:",
          dict(sorted((rc, len(v)) for rc, v in by.items())))


def score():
    H = [h for h in jl(OUT / "handcheck74.jsonl") if h.get("verdict")]
    by = defaultdict(Counter)
    for h in H:
        by[h["reason_code"]][h["verdict"]] += 1
    tot = Counter(h["verdict"] for h in H)
    low = {k: round((v["right"] + v["minor"]) / max(1, sum(v.values())), 4) for k, v in by.items()
           if (v["right"] + v["minor"]) / max(1, sum(v.values())) < 0.98}
    out = dict(n=len(H), verdicts=dict(tot), precision=round(tot["right"] / max(1, len(H)), 4),
               precision_minor_right=round((tot["right"] + tot["minor"]) / max(1, len(H)), 4),
               by_kind={k: dict(v) for k, v in sorted(by.items())}, kinds_under_98=low,
               wrong=[h for h in H if h["verdict"] != "right"])
    wjs(OUT / "handcheck74_score.json", out)
    wjs(OUT / "hold_kinds_suggested.json", sorted(low))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    dict(checks=checks, alarm=alarm, sample=sample, score=score)[sys.argv[1]]()
