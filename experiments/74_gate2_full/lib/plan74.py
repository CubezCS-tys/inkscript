"""Experiment 74 (from experiment 72's plan72.py): what passes becomes Desk decisions of agent:librarian, for one
journal (read-only: writes OUT/plan74.jsonl, OUT/tasks74.jsonl, OUT/plan74_summary.json; nothing in the Desk is
touched here).

Applied (decide74's tiers, after the verification holds; HOLD_KINDS lists the kinds held as proposals: OUT/
hold_kinds.json when present, else experiment 72's — "rows are one body" and "card ok"):
- institutions: R1 / R6 rules, Flash's strong kinds, Opus high (bodies outside the authority only after the review);
  each body named gets its Desk record (define_institution) and country the first time a decision uses it;
- cited works: K1c links (tightened venue), P6 pairs (and D43's derived-from where the thesis and the article share
  title and author), D44 same-text links (works74.d44), Flash's strong kinds, Opus high;
- persons: only the pairs read by hand into OUT/persons_apply.json.
Every decision carries evidence.provenance: experiment 74, the journal, the question id, the tier (rule / model), the
model and its confidence, the rule, the verification (alarm re-ask, hand check) and the reason; `source_id`
E74:<J>:<id> makes the import idempotent. Held items become Desk tasks (tasks74.jsonl): possible_same_work for pairs,
librarian_question otherwise, with both models' answers. Exp 72's one-offs (exp 68's orphans, its same-person pair,
the lead's twin) are not repeated.

    python plan74.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict

from common74 import DESK, E56, E62, E64, E67, E72, JOURNAL, MARC, OUT, PROMPT, RELEASE, SRC, add_paths, jl, js, ro, reviewed_bodies, wjl, wjs

add_paths(E56, E56.parent / "46_platform_db", DESK, E64, E62, E67)
CONF = dict(high="sure", medium="likely", low="unsure")
TYPE_TO_KIND = {"university": "university", "faculty": "faculty", "institute": "institute", "centre": "centre",
                "ministry": "ministry", "school": "school", "academy": "academy", "other": "organisation",
                "society": "society"}
_HK = OUT / "hold_kinds.json" if (OUT / "hold_kinds.json").exists() else E72 / "out" / "hold_kinds.json"
HOLD_KINDS = set(json.loads(_HK.read_text())) if _HK.exists() else set()
CARD_CAP = 60                     # works74.CARD_CAP: the split questions showed the card's first 60 citations


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
    from inst74 import desk_defined, fold, load_authority
    import judge56  # noqa: F401
    from plan67 import item_title, marc_record
    import tools62
    tools62.OUT = OUT / "works"
    AUTH = load_authority()
    RB = reviewed_bodies()
    mine_rev = {b["id"] for b in (js(OUT / "inst" / "authority74.json")["bodies"]
                                  if (OUT / "inst" / "authority74.json").exists() else [])}
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
    D = {d["id"]: d for d in jl(OUT / "decisions74.jsonl")}
    Q = {}
    for f in (OUT / "questions").glob("*.jsonl"):
        for q in jl(f):
            Q[q["id"]] = q
    alarm = {a["id"]: a for a in jl(OUT / "alarm74.jsonl")}
    hand = {h.get("id") or h.get("question"): h for h in jl(OUT / "handcheck74.jsonl")}
    plan, tasks, held = [], [], Counter()

    def prov(qid, tier, model=None, conf=None, rule=None, reason=None, **extra):
        v = {}
        if qid in alarm:
            v["alarm_reask"] = alarm[qid]
        if qid in hand:
            v["hand_check"] = hand[qid]
        return dict(experiment=74, journal=JOURNAL, question=qid, tier=tier, model=model, model_confidence=conf,
                    rule=rule, reason=reason, verification=v or None, prompt=PROMPT if model else None, **extra)

    def add(src, op, keys, payload, note, conf, rule, pv, supersedes=None):
        plan.append(dict(source_id=f"{SRC}{src}", op=op, subject_keys=keys, payload=payload, note=note,
                         confidence=conf, reason_code=f"librarian:{rule}", supersedes=supersedes,
                         evidence=dict(source_id=f"{SRC}{src}", provenance=pv)))

    # ---------------------------------------------------------------- bodies: their Desk row, record and country
    body_row, body_new = {}, set()
    stmt_rows = defaultdict(set)              # body -> machine org rows of the statements that name it
    for p in jl(OUT / "inst" / f"aff{JOURNAL}.jsonl"):
        o = (p.get("machine") or {}).get("org")
        if o:
            stmt_rows[p["key"]].add(o["inst_id"])

    def rv_rule(L):
        return "review74" if L in mine_rev else "review72" if L in RB else "authority56"

    def body(L):
        if L in RB:
            b = RB[L]
            return dict(type=b["type"], country=b.get("country"), name_ar=b.get("name_ar"), name_en=b.get("name_en"),
                        forms=b.get("forms") or [], rows=b.get("rows") or [], why=b.get("why"))
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
            f"{b['name_en'] or b['name_ar']}: authority entry {L}" + (" (added by an authority review: "
                                                                     f"{b['why']})" if L in RB else ""),
            "sure", rv_rule(L),
            prov(None, "authority", rule=rv_rule(L),
                 authority=dict(id=L, country=b["country"], rows=b["rows"] or [r])))
        if b["country"] and (r not in rows or rows[r]["country_code"] != b["country"]):
            add(f"country|{L}", "set_inst_country", [f"inst:{r}"], dict(country=b["country"], authority=L),
                f"{b['name_en'] or b['name_ar']} is in {b['country']} ({b['why'] or 'the authority'})", "sure",
                rv_rule(L), prov(None, "authority", rule="country of the body"))
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
        if not d["apply"] or d["kind"] in HOLD_KINDS or f"{d['kind']}:{d['label']}" in HOLD_KINDS or \
                f"librarian:{d['tier']}:{d['label']}" in HOLD_KINDS:
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
            link(qid, key, items, tier, model, conf, rule + ("+review74" if a.get("ids_reviewed") else ""), why)
        elif k == "inst:same_institution":
            ra, rb = m["rows"]
            add(f"same|{ra}|{rb}", "same_institution", [f"inst:{ra}", f"inst:{rb}"], {}, why, CONF.get(conf, "likely"),
                rule, pv)
        elif k == "inst:set_parent":
            if lab != "parent" or not (a.get("ids_reviewed") or a.get("ids")):
                continue                      # exp 74: «none» (a top-level body) has nothing to apply
            pid = (a.get("ids_reviewed") or a["ids"])[0]      # exp 74: the reviewed body for a «new:» parent
            add(f"parent|{m['row']}", "set_inst_parent", [f"inst:{m['row']}", f"inst:{row_for(pid)}"],
                dict(authority=pid), why, CONF.get(conf, "likely"), rule, pv)
        elif k == "works:pair":
            x, y = m["cards"]
            op = dict(same_work="same_work", edition_of="edition_of", different_work="not_same_work")[lab]
            add(f"pair|{x}|{y}", op, [f"work:{x}", f"work:{y}"], {}, why, CONF.get(conf, "likely"), rule, pv)
        elif k == "works:split":
            cid = m["card"]
            ms = [mm["mention_id"] for mm in C[cid]["members"][:CARD_CAP]]
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
            if "رسائل" in str(t.get("type") or "") and C[cid].get("pub_type") != "thesis":
                # exp 74 (1001 hand check #308): a thesis record is not the work a conference paper / article card
                # cites (D43: two works; at most derived_from): not linked by the rule
                held["K1c: a thesis record for a card that is not a thesis (D43): not linked"] += 1
                continue
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
        elif r["rule"] == "D44":
            t, cid = r["target"], r["card"]
            pid = t.get("pub_id") or c999_pub.get(str(t.get("c999"))) or f"W{t['c999']}"
            pay = {"as": "same_text", "cited_as": (C[cid]["members"][0]["printed"] or "")[:400]}
            if pid not in pubs:
                rec = marc_record(mcon, pid[1:])
                if not rec:
                    held["D44: record not found"] += 1
                    continue
                pay["record"] = rec
            add(f"link|{cid}", "link_publication", [f"work:{cid}", f"pub:{pid}"], pay, r["reason"], "sure", "D44",
                prov(r["id"], "rule", rule="D44", reason=r["reason"]))
        elif r["rule"] == "P6":
            a, b = r["cards"]
            add(f"pair|{a}|{b}", "not_same_work", [f"work:{a}", f"work:{b}"], {}, r["reason"], "sure", "P6",
                prov(r["id"], "rule", rule="P6", reason=r["reason"]))
            if r.get("derived"):
                art, th = (a, b) if C[a]["pub_type"] == "journal" else (b, a)
                add(f"derived|{art}|{th}", "relate_works", [f"work:{art}", f"work:{th}"],
                    dict(relation="derived_from", why=r["reason"]), "D43: " + r["reason"], "sure", "P6+D43",
                    prov(r["id"], "rule", rule="P6+D43", reason=r["reason"]))
    # ---------------------------------------------------------------- persons read by hand (OUT/persons_apply.json)
    pa = OUT / "persons_apply.json"
    for x in (js(pa) if pa.exists() else []):
        add(f"person|{x['keep']}|{x['other']}", "same_person", [x["keep"], x["other"]], {}, x["why"], "sure",
            "persons74", prov(None, "rule", rule="same name (folded), same body; read by hand", reason=x["why"]))
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
    # exp 74 (1001 hand check #95): a card this plan splits gets no link in the same plan (the link would land on
    # the whole mixed card; a person links the right group after the split)
    split_cards = {p["subject_keys"][0] for p in out if p["op"] == "split_work"}
    linked_split = [p for p in out if p["op"] in ("link_publication", "relate_publication")
                    and p["subject_keys"][0] in split_cards]
    if linked_split:
        held["a link on a card this plan splits: not applied"] += len(linked_split)
        out = [p for p in out if p not in linked_split]
        wjl(OUT / "held_link_on_split.jsonl", linked_split)
    # exp 74: decisions the dry run found in conflict (OUT/exclude74.json: source ids) are not applied; listed
    ex = set(json.loads((OUT / "exclude74.json").read_text())) if (OUT / "exclude74.json").exists() else set()
    if ex:
        wjl(OUT / "held_conflict_in_dryrun.jsonl", [p for p in out if p["source_id"] in ex])
        held["in conflict in the dry run: not applied (held_conflict_in_dryrun.jsonl)"] += sum(p["source_id"] in ex for p in out)
        out = [p for p in out if p["source_id"] not in ex]
    # a rule kind held after the hand check (verify74 score: a reason code under 98%): not applied, listed
    rule_held = [p for p in out if p["reason_code"] in HOLD_KINDS]
    out = [p for p in out if p["reason_code"] not in HOLD_KINDS]
    if rule_held:
        held["rule kind held after the hand check (OUT/held_by_rule.jsonl)"] += len(rule_held)
    wjl(OUT / "held_by_rule.jsonl", rule_held)
    wjl(OUT / "plan74.jsonl", out)
    wjl(OUT / "tasks74.jsonl", tasks)
    S = dict(planned=len(out), by_op=dict(Counter(p["op"] for p in out)),
             by_rule=dict(Counter(p["reason_code"] for p in out)), new_bodies=sorted(body_new),
             held=dict(held), tasks=len(tasks), tasks_by_kind=dict(Counter(t["kind"] for t in tasks)),
             hold_kinds=sorted(HOLD_KINDS))
    wjs(OUT / "plan74_summary.json", S)
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
