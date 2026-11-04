"""Experiment 72: what passes becomes Desk decisions of agent:librarian (read-only: writes out/plan72.jsonl,
out/tasks72.jsonl, out/plan72_summary.json; nothing in the Desk is touched here).

Applied (decide72's tiers, after the verification holds; `HOLD_KINDS` below lists any kind held as proposals):
- institutions: R1 / R6 rules, Flash's strong kinds, Opus high (bodies outside the authority only after the review);
  each body named gets its Desk record (define_institution) and country the first time a decision uses it;
- cited works: K1c links, P6 pairs (and D43's derived-from where the thesis and the article share title and author),
  Flash's strong kinds, Opus high;
- persons: the one obvious same-person pair (persons72);
- experiment 68's three orphans, re-anchored by their owner (agent:librarian): the two English lines are now the
  twins of their Arabic lines, so each is superseded by a link on the twin line naming the bodies the Arabic line
  names; the English faculty row the parent named is gone, so it is superseded on the row that now holds that line.
Every decision carries evidence.provenance: experiment 72, the question id, the tier (rule / model), the model and
its confidence, the rule, the verification (alarm re-ask, hand check) and the reason; `source_id` E72:<id> makes the
import idempotent. Held items become Desk tasks (tasks72.jsonl): possible_same_work for pairs (the queue's own kind),
librarian_question otherwise, with both models' answers.

    python plan72.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict

from common72 import DESK, E56, E62, E64, E67, MARC, OUT, RELEASE, add_paths, jl, js, ro, wjl, wjs

add_paths(E56, E56.parent / "46_platform_db", DESK, E64, E62, E67)
CONF = dict(high="sure", medium="likely", low="unsure")
TYPE_TO_KIND = {"university": "university", "faculty": "faculty", "institute": "institute", "centre": "centre",
                "ministry": "ministry", "school": "school", "academy": "academy", "other": "organisation",
                "society": "society"}
HOLD_KINDS = set(json.loads((OUT / "hold_kinds.json").read_text())) if (OUT / "hold_kinds.json").exists() else set()
ORPHANS = {
    "e6c12524-3040-4958-a7b8-112456822ff7": ("aff:0130-019-074-002|b0|Latn|a1", "b5ac3103-3a11-4fe5-99be-894cc7778a20"),
    "087c4c39-2b9a-45af-86bc-37a1d7c547ed": ("aff:0130-027-105-001|b0|Latn|a1", "c9985c65-8315-41cf-bb66-ceb64f79b4f3"),
}
ORPHAN_PARENT = ("1ceb5a59-28ac-418d-9b83-9d4667db8d03", "inst:IZB3FM7D22", "inst:I1DMCZRCFE")
SAME_PERSON = [("person:AR846KS7BM", "person:A2AN262X2S",
                "«منى حسين الدهان» and «منى حسين محمد الدهان»: two catalogue authority records of one person; both sign "
                "0165 articles (0165-000-048-004, 0165-009-031-001; 0165-000-049-001) as a professor at Ain Shams' "
                "Faculty of Specific Education («كلية التربية النوعية - جامعة عين شمس»), same field (mental health)")]


def whole_word_source(m) -> bool:
    """plan67.item_title cuts the title at the journal's name found in the print; a name found inside a word («Emot» in
    «emotions») cuts it wrong, so no title is taken then (the card keeps its own)."""
    printed, src = (m["printed"] or ""), ((m["parsed"] or {}).get("source_title") or "").strip()
    i = printed.lower().find(src.lower())
    if i < 0:
        return False
    before = printed[i - 1] if i > 0 else " "
    after = printed[i + len(src)] if i + len(src) < len(printed) else " "
    broken = printed[:i].rstrip().endswith("-")          # «Psycho- logical Science …»: a word broken at the name
    return not before.isalpha() and not after.isalpha() and not broken


def main():
    from desk.keys import authority_inst_id
    from inst72 import desk_defined, fold, load_authority
    import judge56  # noqa: F401
    from plan67 import item_title, marc_record
    import tools62
    tools62.OUT = OUT / "works"
    AUTH = load_authority()
    rev = js(OUT / "inst" / "authority72.json")
    RB = {b["id"]: b for b in rev["bodies"]}
    defined = desk_defined()
    claimed = {v: k for k, v in defined.items()}
    con = ro()
    rows = {r["inst_id"]: dict(r) for r in con.execute("SELECT * FROM institutions")}
    names = defaultdict(set)
    for r in con.execute("SELECT inst_id, name FROM institution_names"):
        names[r[0]].add(fold(r[1]))
    c999_pub = {r[0]: r[1] for r in con.execute("SELECT c999, pub_id FROM publications WHERE c999 IS NOT NULL")}
    pubs = {r[0] for r in con.execute("SELECT pub_id FROM publications")}
    mcon = sqlite3.connect(f"file:{MARC}?mode=ro", uri=True)
    mcon.row_factory = sqlite3.Row
    C = tools62.cards()
    D = {d["id"]: d for d in jl(OUT / "decisions72.jsonl")}
    Q = {}
    for f in (OUT / "questions").glob("*.jsonl"):
        for q in jl(f):
            Q[q["id"]] = q
    alarm = {a["id"]: a for a in jl(OUT / "alarm72.jsonl")}
    hand = {h["id"]: h for h in jl(OUT / "handcheck72.jsonl")}
    plan, tasks, held = [], [], Counter()

    def prov(qid, tier, model=None, conf=None, rule=None, reason=None, **extra):
        v = {}
        if qid in alarm:
            v["alarm_reask"] = alarm[qid]
        if qid in hand:
            v["hand_check"] = hand[qid]
        return dict(experiment=72, question=qid, tier=tier, model=model, model_confidence=conf, rule=rule,
                    reason=reason, verification=v or None, prompt="72.1" if model else None, **extra)

    def add(src, op, keys, payload, note, conf, rule, pv, supersedes=None):
        plan.append(dict(source_id=f"E72:{src}", op=op, subject_keys=keys, payload=payload, note=note,
                         confidence=conf, reason_code=f"librarian:{rule}", supersedes=supersedes,
                         evidence=dict(source_id=f"E72:{src}", provenance=pv)))

    # ---------------------------------------------------------------- bodies: their Desk row, record and country
    body_row, body_new = {}, set()
    stmt_rows = defaultdict(set)              # body -> machine org rows of the statements that name it
    for p in jl(OUT / "inst" / "aff0165.jsonl"):
        o = (p.get("machine") or {}).get("org")
        if o:
            stmt_rows[p["key"]].add(o["inst_id"])

    def body(L):
        if L in RB:
            b = RB[L]
            return dict(type=b["type"], country=b["country"], name_ar=b["name_ar"], name_en=b["name_en"],
                        forms=b["forms"], rows=b["rows"], why=b["why"])
        if L not in AUTH:                       # a generic body made on demand (exp 56's «وزارة التربية» per country)
            mm = re.fullmatch(r"L-([a-z]{2})-([a-z]+)", L)
            judge56.generic_entry(mm.group(2), mm.group(1).upper())
        a = AUTH[L]
        return dict(type=a["type"], country=a.get("country"), name_ar=a.get("name_ar"), name_en=a.get("name_en"),
                    forms=a.get("forms") or [], rows=[], why=a.get("note"))

    def row_for(L, keys=()):
        if L in defined:
            return defined[L]
        if L in body_row:
            return body_row[L]
        b = body(L)
        want = {fold(x) for x in [b["name_ar"], b["name_en"]] + list(b["forms"]) if x}
        cand = [r for r in b["rows"] if r in rows and r not in claimed]
        if not cand:
            pool = set().union(*[stmt_rows.get(k, set()) for k in keys]) if keys else set()
            cand = sorted([r for r in pool if r in rows and r not in claimed and names[r] & want])
        if not cand:
            cand = sorted(r for r, ns in names.items() if ns & want and r not in claimed and r in rows
                          and rows[r]["kind"] not in ("faculty", "department"))[:1]
        r = cand[0] if cand else authority_inst_id(L)
        body_row[L] = r
        claimed[r] = L
        body_new.add(L)
        nm = [dict(name=b["name_ar"], lang="ar", script="Arab", type="label")] if b["name_ar"] else []
        if b["name_en"]:
            nm.append(dict(name=b["name_en"], lang="en", script="Latn", type="label"))
        kind = rows[r]["kind"] if r in rows else TYPE_TO_KIND.get(b["type"], "organisation")
        add(f"define|{L}", "define_institution", [f"inst:{r}"],
            dict(authority=L, kind=kind, authority_type=b["type"], names=nm),
            f"{b['name_en'] or b['name_ar']}: authority entry {L}" + (" (added by experiment 72's authority review: "
                                                                     f"{b['why']})" if L in RB else ""),
            "sure", "review72" if L in RB else "authority56",
            prov(None, "authority", rule="review72" if L in RB else "authority56",
                 authority=dict(id=L, country=b["country"], rows=b["rows"] or [r])))
        if b["country"] and (r not in rows or rows[r]["country_code"] != b["country"]):
            add(f"country|{L}", "set_inst_country", [f"inst:{r}"], dict(country=b["country"], authority=L),
                f"{b['name_en'] or b['name_ar']} is in {b['country']} ({b['why'] or 'the authority'})", "sure",
                "review72" if L in RB else "authority56", prov(None, "authority", rule="country of the body"))
        return r

    def link(qid, key, items, tier, model, conf, rule, reason):
        """items: [(L, role, inferred)]"""
        seen, insts = set(), []
        for L, role, inf in items:
            r = row_for(L, [key])
            if r in seen:
                continue
            seen.add(r)
            insts.append(dict(inst=f"inst:{r}", authority=L, role=role or "current", country=body(L)["country"],
                              inferred={"from": inf, "rule": "D39"} if inf else None))
        add(f"aff|{key}", "link_affiliation", [key] + [x["inst"] for x in insts], dict(institutions=insts), reason,
            CONF.get(conf, "sure"), rule, prov(qid, tier, model, conf, rule, reason))

    # ---------------------------------------------------------------- institutions: rules
    for r in jl(OUT / "inst" / "rule_decisions.jsonl"):
        if r["rule"] == "R1":
            link(r["id"], r["key"], [(o, "current", None) for o in r["orgs"]], "rule", None, "high", "R1", r["reason"])
        else:
            add(f"aff|{r['key']}", "not_an_institution", [r["key"]], {}, r["reason"], "sure", "R6",
                prov(r["id"], "rule", rule="R6", reason=r["reason"]))
    # ---------------------------------------------------------------- the models' decisions
    for qid, d in sorted(D.items()):
        if not d["apply"] or d["kind"] in HOLD_KINDS or f"{d['kind']}:{d['label']}" in HOLD_KINDS:
            if d.get("nochange"):
                continue
            q = Q[qid]
            held[f"{d['kind']}: {d['held'] or 'held kind'}"] += 1
            tasks.append(dict(qid=qid, kind=d["kind"], q=q, flash=d["flash"], opus=d["opus"], why=d["held"] or
                              "kind held as proposals (precision below 98%)"))
            continue
        a, lab, k, m = d["answer"], d["label"], d["kind"], d["meta"] or {}
        tier, model, conf = d["tier"], d["model"], a.get("confidence")
        rule = f"{tier}:{lab}"
        why = a.get("reason")
        pv = prov(qid, tier, model, conf, rule, why, flash=d["flash"] if tier == "opus" else None)
        if k == "inst:affiliation":
            key = m["key"]
            if lab == "not_institution":
                add(f"aff|{key}", "not_an_institution", [key], {}, why, CONF.get(conf, "likely"), rule, pv)
                continue
            ids = a.get("ids_reviewed") or a["ids"]
            roles = a.get("roles") or []
            items = [(L, roles[i] if i < len(roles) else "current", a.get("inferred")) for i, L in enumerate(ids)]
            link(qid, key, items, tier, model, conf, rule + ("+review72" if a.get("ids_reviewed") else ""), why)
        elif k == "inst:same_institution":
            ra, rb = m["rows"]
            add(f"same|{ra}|{rb}", "same_institution", [f"inst:{ra}", f"inst:{rb}"], {}, why, CONF.get(conf, "likely"),
                rule, pv)
        elif k == "inst:set_parent":
            pid = a["ids"][0]
            add(f"parent|{m['row']}", "set_inst_parent", [f"inst:{m['row']}", f"inst:{row_for(pid)}"],
                dict(authority=pid), why, CONF.get(conf, "likely"), rule, pv)
        elif k == "works:pair":
            x, y = m["cards"]
            op = dict(same_work="same_work", edition_of="edition_of", different_work="not_same_work")[lab]
            add(f"pair|{x}|{y}", op, [f"work:{x}", f"work:{y}"], {}, why, CONF.get(conf, "likely"), rule, pv)
        elif k == "works:split":
            cid = m["card"]
            ms = [mm["mention_id"] for mm in C[cid]["members"][:12]]
            if lab == "card_ok":
                add(f"card|{cid}", "confirm_work", [f"work:{cid}"], {}, why, CONF.get(conf, "likely"), rule, pv)
            elif lab == "split_card":
                groups = [dict(members=[ms[i - 1] for i in g]) for g in a["groups"]]
                add(f"card|{cid}", "split_work", [f"work:{cid}"], dict(groups=groups), why, CONF.get(conf, "likely"),
                    rule, pv)
            else:
                held[f"{k}: {lab} on a split question (no action)"] += 1
                tasks.append(dict(qid=qid, kind=k, q=Q[qid], flash=d["flash"], opus=d["opus"], why="not_a_work "
                                  "answered on a split question: the action is not known"))
        elif k == "works:notwork":
            cid = m["card"]
            if lab == "card_ok":
                add(f"card|{cid}", "confirm_work", [f"work:{cid}"], {}, why, CONF.get(conf, "likely"), rule, pv)
            else:
                act = lab.replace("not_a_work_", "")
                pay = dict(action=act)
                if act in ("retitle", "one_per_citation"):
                    titles = {mm["mention_id"]: t for mm in C[cid]["members"] if (t := item_title(mm))
                              and whole_word_source(mm)}
                    if titles:
                        pay["titles"] = titles
                add(f"card|{cid}", "not_a_work", [f"work:{cid}"], pay, why, CONF.get(conf, "likely"),
                    rule + ("+C1" if m.get("c1") else ""), pv)
        elif k == "works:catalogue":
            cid, t = m["card"], m["target"] or {}
            pid = t.get("pub_id") or c999_pub.get(str(t.get("c999"))) or (f"W{t['c999']}" if t.get("c999") else None)
            if not pid:
                held[f"{k}: no publication id"] += 1
                continue
            pay = {}
            if pid not in pubs:
                rec = marc_record(mcon, pid[1:])
                if not rec:
                    held[f"{k}: record not found"] += 1
                    continue
                pay["record"] = rec
            if lab in ("links_to_publication", "same_text"):
                pay["as"] = "work" if lab == "links_to_publication" else "same_text"
                if lab == "same_text":
                    pay["cited_as"] = (C[cid]["members"][0]["printed"] or "")[:400]
                add(f"link|{cid}", "link_publication", [f"work:{cid}", f"pub:{pid}"], pay, why,
                    CONF.get(conf, "likely"), rule + ("+D44" if lab == "same_text" else ""), pv)
            elif lab == "relation":
                ct, rt = C[cid]["pub_type"], (t.get("type") or "")
                rel = ("reviewed_in" if rt.startswith("عروض") else "has_derived" if ct == "thesis" and rt in
                       ("بحوث ومقالات", "بحوث المؤتمرات") else "derived_from" if ct != "thesis" and rt == "رسائل جامعية"
                       else "related")
                pay.update(relation=rel, why=why, unlink=True)
                add(f"rel|{cid}|{pid}", "relate_publication", [f"work:{cid}", f"pub:{pid}"], pay, why,
                    CONF.get(conf, "likely"), rule + ("+D43" if rel in ("has_derived", "derived_from") else ""), pv)
            else:                                   # no_link: nothing to apply; a person looks only at a machine link
                if m.get("proposal") == "link47":
                    tasks.append(dict(qid=qid, kind=k, q=Q[qid], flash=d["flash"], opus=d["opus"],
                                      why="the librarian finds no link where link47 linked: a person decides"))
                    held[f"{k}: no_link against a link47 link -> a person"] += 1
                else:
                    held[f"{k}: no_link (nothing to apply)"] += 1
    # ---------------------------------------------------------------- cited works: rules
    for r in jl(OUT / "works" / "rule_decisions.jsonl"):
        if r["rule"] == "K1c":
            t, cid = r["target"], r["card"]
            pid = t.get("pub_id") or c999_pub.get(str(t.get("c999"))) or f"W{t['c999']}"
            pay = {"as": "work"}
            if pid not in pubs:
                rec = marc_record(mcon, pid[1:])
                if not rec:
                    held["K1c: record not found"] += 1
                    continue
                pay["record"] = rec
            add(f"link|{cid}", "link_publication", [f"work:{cid}", f"pub:{pid}"], pay, r["reason"], "sure", "K1c",
                prov(r["id"], "rule", rule="K1c", reason=r["reason"]))
        elif r["rule"] == "P6":
            a, b = r["cards"]
            add(f"pair|{a}|{b}", "not_same_work", [f"work:{a}", f"work:{b}"], {}, r["reason"], "sure", "P6",
                prov(r["id"], "rule", rule="P6", reason=r["reason"]))
            if r.get("derived"):
                art, th = (a, b) if C[a]["pub_type"] == "journal" else (b, a)
                add(f"derived|{art}|{th}", "relate_works", [f"work:{art}", f"work:{th}"],
                    dict(relation="derived_from", why=r["reason"]), "D43: " + r["reason"], "sure", "P6+D43",
                    prov(r["id"], "rule", rule="P6+D43", reason=r["reason"]))
    # ---------------------------------------------------------------- the twin the lead named (exp 68 / exp 70)
    # «كلية علوم التربية» (I1NW24RKQM, the Arabic row) and «Faculty of Education Sciences» (IP0XR2KXSC, its English
    # twin since exp 68) are one faculty of Mohammed V University. Flash's "rows are one body" kind is held (the hand
    # check found 16 of 17 right, under 98%); this one is applied on its own evidence: the two rows carry the two
    # scripts of one printed line (0130-018-072-003: «كلية علوم التربية - جامعة محمد الخامس» / «University of Mohamed V
    # - Faculty of Education Sciences»), under one parent
    add("same|I1NW24RKQM|IP0XR2KXSC", "same_institution", ["inst:I1NW24RKQM", "inst:IP0XR2KXSC"], {},
        "one faculty printed in two scripts: «كلية علوم التربية - جامعة محمد الخامس - المملكة المغربية» and its twin "
        "«University of Mohamed V - Faculty of Education Sciences - Morocco» (0130-018-072-003); both rows are units of "
        "Mohammed V University (exp 68 split them into an Arabic and an English row; exp 70 asked for one)", "sure",
        "twin68", prov("I72-T012", "rule", rule="twin of one printed line (exp 68 / exp 70)",
                       flash=D.get("I72-T012", {}).get("flash")))
    # ---------------------------------------------------------------- persons; experiment 68's orphans
    for keep, other, why in SAME_PERSON:
        add(f"person|{keep}|{other}", "same_person", [keep, other], {}, why, "sure", "persons72",
            prov(None, "rule", rule="same name (folded), same body, both sign 0165; read by hand", reason=why))
    from desk import db
    with db.connect("desk") as pg:
        for orphan, (newkey, arabic) in ORPHANS.items():
            d = pg.execute("SELECT payload, subject_keys FROM decisions WHERE decision_id = %s", (arabic,)).fetchone()
            add(f"reanchor|{orphan}", "link_affiliation", [newkey] + d["subject_keys"][1:], d["payload"],
                f"exp 68 orphan re-anchored: the English line is now the twin of its Arabic line ({newkey}); it names "
                f"the bodies the Arabic line's decision {arabic} names", "sure", "reanchor68",
                prov(None, "rule", rule="re-anchor (exp 68 orphan)", orphan=orphan, arabic_decision=arabic),
                supersedes=orphan)
    oid, row, parent = ORPHAN_PARENT
    add(f"reanchor|{oid}", "set_inst_parent", [row, parent], dict(authority="L-x-aiu"),
        "exp 68 orphan re-anchored: the English «Faculty of Educational Sciences» row (IRV1KRDSVW) is gone; the line "
        "«… Faculty of Educational Sciences- (AIU)» and its Arabic twin «كلية العلوم التربوية - جامعة أكاديميون العالمية» "
        "now sit on IZB3FM7D22 (which the machine put under Alexandria); that row is AIU's faculty", "sure",
        "reanchor68", prov(None, "rule", rule="re-anchor (exp 68 orphan)", orphan=oid), supersedes=oid)
    # one Desk answer per question: a later plan entry with the same source wins only if it is the same op
    # a not_same_work on a card that holds no citation (exp 67's defined book) or that a drop takes off every work
    # count holds nothing apart: it would only be orphaned by the release (dry run 2 found 8)
    from desk import db as _db
    with _db.connect("desk") as pg:
        dropped = {r["k"] for r in pg.execute("SELECT subject_keys[1] k FROM decisions WHERE op = 'not_a_work' AND "
                                              "status = 'accepted' AND payload->>'action' = 'drop'")}
    dropped |= {p["subject_keys"][0] for p in plan if p["op"] == "not_a_work" and p["payload"]["action"] == "drop"}
    empty = {f"work:{cid}" for cid, c in C.items() if not c["members"]}
    keep = []
    for p in plan:
        if p["op"] == "not_same_work" and set(p["subject_keys"]) & (dropped | empty):
            held["not_same_work with a card that is not a work (dropped) or has no citation: nothing to hold apart"] += 1
            continue
        keep.append(p)
    plan = keep
    # one Desk answer per question. Two answers to one question (a card asked twice: a read-article hit and the
    # drawer's proposal, or a model answer and K1c) are one decision when they agree; when they disagree (another
    # record, another op) neither is applied and a person decides
    by, order = defaultdict(list), []
    for p in plan:
        if p["source_id"] not in by:
            order.append(p["source_id"])
        by[p["source_id"]].append(p)
    out = []
    for sid in order:
        ps = by[sid]
        same = all(x["op"] == ps[0]["op"] and x["subject_keys"] == ps[0]["subject_keys"] for x in ps)
        if same:
            if len(ps) > 1:
                ps[0]["evidence"]["provenance"]["also"] = [x["evidence"]["provenance"] for x in ps[1:]]
                held["two answers that agree, recorded as one decision"] += 1
            out.append(ps[0])
        else:
            held[f"two answers that disagree on one question ({ps[0]['op']}): to a person"] += 1
            tasks.append(dict(qid=sid, kind="conflicting_answers", q=dict(question="Two librarian answers disagree",
                                                                           options=[], evidence=dict(answers=ps),
                                                                           meta=dict(keys=ps[0]["subject_keys"])),
                              flash=None, opus=None, why="two answers disagree: " + "; ".join(
                                  f"{x['op']} {x['subject_keys']} ({x['reason_code']})" for x in ps)))
    wjl(OUT / "plan72.jsonl", out)
    wjl(OUT / "tasks72.jsonl", tasks)
    S = dict(planned=len(out), by_op=dict(Counter(p["op"] for p in out)),
             by_rule=dict(Counter(p["reason_code"] for p in out)), new_bodies=sorted(body_new),
             held=dict(held), tasks=len(tasks), tasks_by_kind=dict(Counter(t["kind"] for t in tasks)),
             hold_kinds=sorted(HOLD_KINDS))
    wjs(OUT / "plan72_summary.json", S)
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
