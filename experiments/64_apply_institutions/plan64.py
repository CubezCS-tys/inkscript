"""Experiment 64, step 1: turn experiment 56's standing institution decisions, as verified by experiment 63 and with
the owner's choices of 2026-11-02, into Desk decisions (read-only: writes out/plan64.jsonl, nothing else).

What goes in (the owner, 2026-11-02):
- every standing exp 56 decision except the 10 `unsure` and the 22 `set_type` (types stay proposals);
- exp 63's 4 errors fixed: O351 (a reprint source -> not an institution, its set_country O610 dropped), O495 (the
  Integrative Psychology Society is a body -> linked), S107 / S182 (Cairo + Sana'a: both universities with both
  countries; the row «جامعتى القاهرة وصنعاء» is not merged into Sana'a);
- a country per linked institution (from the authority), never one per affiliation;
- D37 (a degree-granting university is "educated at", not an affiliation), D38 (a former post is linked as `former`),
  D39 (an unnamed body filled from the journal's publisher only when the wording points to it, marked `inferred`).

Each planned decision carries its provenance in `evidence.provenance` (exp 56 decision, exp 63 item and verdict,
basis, confidence, the rule) and a `source_id` that makes the import idempotent.

    python3 experiments/64_apply_institutions/plan64.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
E56 = HERE.parent / "56_librarian_institutions" / "out"
E63 = HERE.parent / "63_verify_institutions" / "out"
DESK = HERE.parent / "49_correction_desk"
sys.path.insert(0, str(DESK))
from desk.keys import authority_inst_id  # noqa: E402

RELEASE = Path("/home/appuser/data/desk/releases/R20261023T005909.db")     # the release exp 56 and 63 judged
CONF = dict(high="sure", medium="likely", low="unsure")
# the librarian's types -> the machine's kinds, for rows the Desk mints (finalize56.TYPE_TO_MACHINE); existing rows
# keep the machine's kind (set_type stays a proposal)
TYPE_TO_KIND = {"university": "university", "faculty": "faculty", "institute": "centre", "centre": "centre",
                "ministry": "ministry", "school": "organisation", "academy": "society", "other": "organisation",
                "society": "society"}

# ------------------------------------------------------------------ the owner's corrections and the three rules
# bodies the authority lacks: added by the fixes (O495) and by D37 / D39
NEW_BODIES = {
    "L-eg-ipsych": dict(type="society", name_ar="جماعة علم النفس التكاملي", name_en="Integrative Psychology Society",
                        country="EG", why="exp 63 O495: printed «جماعة علم النفس التكاملى»; it publishes J0513 (EG)"),
    "L-eg-capmas": dict(type="other", name_ar="الجهاز المركزي للتعبئة العامة والإحصاء",
                        name_en="Central Agency for Public Mobilization and Statistics (CAPMAS)", country="EG",
                        why="D39: the publisher of J0700 (catalogue), EG"),
    "L-eg-ansar-sunna": dict(type="society", name_ar="جماعة أنصار السنة المحمدية",
                             name_en="Jamaat Ansar al-Sunna al-Muhammadiyya", country="EG",
                             why="D39: the publisher of J0596 al-Tawhid (catalogue), EG"),
    "L-x-palm-centre": dict(type="centre", name_ar=None, name_en="Palm Strategic Initiative Centre", country=None,
                            why="D37: the author's post printed beside his degree (O014); country not printed, "
                                "not guessed"),
}
ARABNEWS_ROW_COUNTRY = "D56-"   # placeholder, resolved below (O610)
CAIRO_SANAA_ROW = "ISXAR3JR19"  # «جامعتى القاهرة وصنعاء» (S182): not merged into Sana'a

# per exp 63 item: how the affiliation decision changes. role per authority id; extra links; a replacement op
AFF_FIX = {
    # the four errors
    "O351": dict(op="not_an_institution", rule="exp63-error",
                 why="a reprint source («عن صحيفة عرب نيوز»: by J. Schulz, translated by …, from the Arab News "
                     "newspaper), not an affiliation (exp 63 O351)"),
    "O495": dict(op="link", links=[("L-eg-ipsych", "current", None)], rule="exp63-error",
                 why="the statement prints a body: «جماعة علم النفس التكاملى», the Integrative Psychology Society, "
                     "which publishes this journal J0513 (exp 63 O495)"),
    "S107": dict(rule="exp63-error", note_only=True,
                 why="Cairo University (EG) and Sana'a University (YE): each linked body keeps its own country "
                     "(exp 63 S107; one country per affiliation was the fault)"),
    # D37: a degree-granting university is "educated at"
    "O014": dict(op="link", roles={"L-my-um": "educated_at"}, extra=[("L-x-palm-centre", "current", None)],
                 rule="D37", why="«A Ph.D. … from the University of Malaya» is a degree, not a post (D37); the post "
                                 "printed beside it is the Palm Strategic Initiative Centre"),
    "O402": dict(op="link", roles={"L-sa-uqu": "educated_at"}, rule="D37",
                 why="«ماجستير … بجامعة أم القرى»: a master's degree from Umm Al-Qura, not a post (D37)"),
    "S214": dict(op="link", roles={"L-ma-uca": "educated_at"}, rule="D37",
                 why="«دكتوراه في النقد الأدبي كلية الآداب، جامعة القاضي عياض»: a doctorate from Cadi Ayyad (D37)"),
    "O007": dict(op="link", extra=[("L-ma-um5", "educated_at", None)], rule="D37",
                 why="«دكتوراه دولة … كلية الآداب - الرباط»: a doctorate from Mohammed V University (the Faculty of "
                     "Arts in Rabat, R4), kept as educated at (D37); the post is CRMEF Settat"),
    # D38: a former post is linked as former
    "S160": dict(op="link", roles={"L-eg-zagazig": "former"}, rule="D38",
                 why="«نائب رئيس جامعة الزقازيق سابقا»: a former post (D38)"),
    "O448": dict(op="link", roles={"L-eg-cairo": "former"}, rule="D38",
                 why="«… جامعة القاهرة سابقا»: Cairo is a former post; KISR is the current one (D38)"),
    "O459": dict(op="link", roles={"L-om-squ": "former"}, rule="D38",
                 why="«مُحاضرة سابقة … جامعة السلطان قابوس»: a former post (D38)"),
    "O337": dict(op="link", roles={"L-lb-cabinet": "former"}, rule="D38",
                 why="«رئيس مجلس الوزراء اللبناني السابق»: a former post (D38)"),
    # D39: an unnamed body filled from the journal's publisher where the wording points to it
    "S069": dict(op="link", links=[("L-sa-kau", "current", "journal")], rule="D39",
                 why="«قسم التاريخ» in J0389, published by King Abdulaziz University's Faculty of Arts and "
                     "Humanities: the department is the publisher's (D39)"),
    "S165": dict(op="link", links=[("L-iq-baghdad", "current", "journal")], rule="D39",
                 why="«قسم اللغة العربية» in J0739, published by the University of Baghdad's College of Arts (D39)"),
    "S212": dict(op="link", links=[("L-eg-helwan", "current", "journal")], rule="D39",
                 why="«قسم التصميم الصناعي» in J0241, published by Helwan University (D39)"),
    "S199": dict(op="link", links=[("L-sa-imamu", "current", "journal")], rule="D39",
                 why="«بالكلية» ('at the college') in J0290, published by Imam University's Faculty of Usul "
                     "al-Din (D39)"),
    "S137": dict(op="link", links=[("L-eg-capmas", "current", "journal")], rule="D39",
                 why="«رئيسة شعبة بحوث» (head of a research division) in J0700, CAPMAS's own population journal "
                     "(D39)"),
    "S088": dict(op="link", links=[("L-eg-ansar-sunna", "current", "journal")], rule="D39",
                 why="«فرع الإسكندرية» ('the Alexandria branch') in J0596 al-Tawhid, Ansar al-Sunna's journal: "
                     "the society's branch (D39)"),
    "O479": dict(op="link", links=[("L-eg-ansar-sunna", "current", "journal")], rule="D39",
                 why="«الرئيس العام للجماعة» ('the general president of the society') in J0596, Ansar al-Sunna's "
                     "journal (D39)"),
    "O499": dict(op="link", links=[("L-eg-academy", "current", "journal")], rule="D39",
                 why="«العضو المراسل من تونس» (a corresponding member) in J0692, the Cairo Arabic Language "
                     "Academy's journal, as «عضو المجمع» is linked (D39)"),
}
# exp 56 links already filled from the journal or the article (R5 / context, body not printed by name): D39 marks them
INFERRED_56 = {
    "D56-2c3de57e7286": "journal", "D56-3b4d82923b8c": "journal", "D56-b7e6f1debc90": "journal",
    "D56-48d9658e57ca": "journal", "D56-3f72693b0773": "journal", "D56-b19bb08caa6e": "journal",
    "D56-aca2df2a47d2": "journal",
    "D56-5fcf10114625": "article", "D56-5d29b52c9292": "article", "D56-e63ad9abae9e": "article",
    "D56-a4c2dc563726": "article", "D56-23f0ef92ba9a": "article", "D56-69ba45362f84": "article",
}
# set on an institution row (D39: the body is the journal's publisher)
COUNTRY_FIX = {"S201": ("L-x-bibcentre", "EG", "D39: J1510's publisher is this very centre at Egypt's National Library "
                                               "(Dar al-Kutub), EG (exp 63 S201)")}
# reviewed and left as exp 56 has them (reported, not applied)
NOT_APPLIED = {
    "O170": "«كلية الدراسات العليا (سابقا) جامعة الخليج العربي»: «(سابقا)» qualifies the college's old name, not the "
            "post (the author is an associate professor of gifted education at AGU now): kept current, not former",
    "S116": "Al-Zahraa University Hospital: the article's abstract places it in Cairo (Al-Azhar's), but nothing "
            "points to the journal's publisher, so D39 does not apply; left as exp 56 has it (country open)",
}


def load_56():
    latest = {}
    for line in open(E56 / "decisions56.jsonl", encoding="utf-8"):
        d = json.loads(line)
        latest[d["qkey"]] = d
    return [d for d in latest.values() if d["kind"] != "retired"]


def exp63_items(standing):
    """decision id -> (exp 63 item id, its adjudication if blind)."""
    key = json.loads((E63 / "sample63_key.json").read_text(encoding="utf-8"))
    adj = json.loads((E63 / "adjudication63.json").read_text(encoding="utf-8"))
    out = {v["decision_id"]: (s, adj.get(s)) for s, v in key.items()}
    sampled = set(out)
    # openreview63.py's order, reproduced (read-only) to name the O### lines
    P = {json.loads(l)["key"]: json.loads(l) for l in open(E56 / "packets56.jsonl", encoding="utf-8")}
    order = ["affiliation_institution", "not_an_institution", "unit_kept_apart", "unsure", "set_country",
             "set_parent", "same_institution", "not_same_institution", "set_type"]
    S = [d for d in standing if d["decision_id"] not in sampled]
    S.sort(key=lambda d: (order.index(d["kind"]), d["confidence"], d["basis"], d.get("printed", "")))
    for n, d in enumerate(S, 1):
        out[d["decision_id"]] = (f"O{n:03d}", None)
    assert len(out) == len(standing) == 908, (len(out), len(standing))
    _ = P
    return out


def main():
    OUT.mkdir(exist_ok=True)
    standing = load_56()
    items = exp63_items(standing)
    by_item = {v[0]: k for k, v in items.items()}
    auth = {e["id"]: e for e in json.loads((E56 / "authority56.json").read_text(encoding="utf-8"))["institutions"]}
    con = sqlite3.connect(f"file:{RELEASE}?mode=ro", uri=True)
    rows = {r[0]: dict(kind=r[1], country=r[2], status=r[3]) for r in con.execute(
        "SELECT inst_id, kind, country_code, status FROM institutions")}
    names = defaultdict(set)
    for i, n in con.execute("SELECT inst_id, name FROM institution_names"):
        names[i].add(n.strip())

    # the fixes must name decisions of the kind they expect
    o610 = by_item["O610"]
    fix_ids = {by_item[k]: k for k in list(AFF_FIX) + list(COUNTRY_FIX) + list(NOT_APPLIED)}
    S = {d["decision_id"]: d for d in standing}
    assert S[o610]["kind"] == "set_country" and "عرب نيوز" in json.dumps(S[o610]["decision"], ensure_ascii=False)

    # ------------------------------------------------------------------ which row stands for each body
    split_rows = {d["subject_keys"][0][5:] for d in standing if d["kind"] == "not_same_institution"}
    norow_rows = {d["subject_keys"][0][5:] for d in standing if d["kind"] == "not_an_institution"
                  and d["level"] == "institution"}
    unit_rows = {d["decision"]["machine_row"] for d in standing if d["kind"] == "set_parent"}
    excluded = split_rows | norow_rows | unit_rows | {CAIRO_SANAA_ROW}
    claims = defaultdict(list)
    for e in auth.values():
        for m in e["machine_rows"]:
            claims[m["inst_id"]].append(e["id"])
    canon, how = {}, Counter()
    for L, e in auth.items():
        cands = [m for m in e["machine_rows"] if len(claims[m["inst_id"]]) == 1 and m["inst_id"] not in excluded]
        named = {x for x in (e["name_ar"], e["name_en"]) if x}
        cands.sort(key=lambda m: (-bool(named & names[m["inst_id"]]), -m["n"], m["inst_id"]))
        if cands:
            canon[L] = cands[0]["inst_id"]
            how["machine row"] += 1
        else:
            canon[L] = authority_inst_id(L)
            how["minted"] += 1
    for L in NEW_BODIES:
        canon[L] = authority_inst_id(L)
        how["minted (new body)"] += 1

    def ik(L):
        return f"inst:{canon[L]}"

    def body(L):
        return auth.get(L) or NEW_BODIES[L]

    plan = []

    def add(source_id, op, keys, payload, d56=None, item=None, rule=None, confidence=None, note=None, extra=None):
        prov = dict(applied_by="experiment 64 (2026-11-02)", rule=rule)
        if d56:
            prov["exp56"] = dict(decision_id=d56["decision_id"], qkey=d56["qkey"], kind=d56["kind"],
                                 basis=d56["basis"], confidence=d56["confidence"], reason=d56["reason"],
                                 made_at=d56["made_at"])
            it = items.get(d56["decision_id"])
            if it:
                prov["exp63"] = dict(item=it[0], verdict=(it[1] or {}).get("verdict") or "open read-through: no error",
                                     blind=it[1] is not None)
        if item and (not d56 or items.get(d56["decision_id"], (None,))[0] != item):
            prov["exp63_fix"] = item
        if extra:
            prov.update(extra)
        conf = confidence or (CONF[d56["confidence"]] if d56 and d56.get("confidence") else "sure")
        plan.append(dict(source_id=source_id, op=op, subject_keys=keys, payload=payload, confidence=conf,
                         reason_code=f"librarian:{rule or 'exp56'}", note=note or (d56 or {}).get("reason"),
                         evidence=dict(source_id=source_id, provenance=prov)))

    # ------------------------------------------------------------------ phase 5: the bodies' records
    used = set()
    for d in standing:
        if d["kind"] == "affiliation_institution" and fix_ids.get(d["decision_id"]) != "O351":
            used |= {i["id"] for i in d["decision"]["institutions"]}
        if d["kind"] == "set_parent":
            used.add(d["decision"]["parent"])
        if d["kind"] == "not_same_institution":
            used |= {g for g in d["decision"]["groups"] if g.startswith("L-")}
    for f in AFF_FIX.values():
        used |= {x[0] for x in f.get("links", []) + f.get("extra", [])}
    used |= {v[0] for v in COUNTRY_FIX.values()}
    for L in sorted(used):
        e = body(L)
        nm = [dict(name=e["name_ar"], lang="ar", script="Arab", type="label")] if e.get("name_ar") else []
        if e.get("name_en"):
            nm.append(dict(name=e["name_en"], lang="en", script="Latn", type="label"))
        kind = rows[canon[L]]["kind"] if canon[L] in rows else TYPE_TO_KIND[e["type"]]
        add(f"E64|define|{L}", "define_institution", [ik(L)],
            dict(authority=L, kind=kind, authority_type=e["type"], names=nm),
            rule="authority56" if L in auth else "exp64-new-body", confidence="sure",
            note=(f"{e.get('name_en') or e.get('name_ar')}: the librarian's authority entry {L}"
                  + ("" if L in auth else f" (new: {NEW_BODIES[L]['why']})")),
            extra=dict(authority=dict(id=L, country=e.get("country"), country_basis=e.get("country_basis"),
                                      machine_rows=[m["inst_id"] for m in e.get("machine_rows", [])])))

    # ------------------------------------------------------------------ phase 6: one body, several rows; rows that name none
    for d in standing:
        if d["kind"] == "same_institution":
            L = d["decision"]["institution"]
            rws = [k[5:] for k in d["subject_keys"]]
            drop = [r for r in rws if r == CAIRO_SANAA_ROW]
            others = [r for r in rws if r != canon[L] and r not in drop]
            if not others:
                continue
            add(f"E64|same|{d['decision_id']}", "same_institution", [ik(L)] + [f"inst:{r}" for r in others],
                dict(authority=L), d56=d, rule="exp63-error" if drop else None,
                note=d["reason"] + (f" — without «جامعتى القاهرة وصنعاء» ({CAIRO_SANAA_ROW}): it names two "
                                    "universities, so it is not merged into Sana'a (exp 63 S182)" if drop else ""),
                item="S182" if drop else None)
        elif d["kind"] == "not_an_institution" and d["level"] == "institution":
            add(f"E64|norow|{d['decision_id']}", "not_an_institution_row", d["subject_keys"][:1], {}, d56=d)

    # ------------------------------------------------------------------ phase 7: countries and parents
    country_done = defaultdict(set)
    for d in standing:
        if d["kind"] == "set_country" and d["decision_id"] != o610:
            r = d["decision"]["machine_row"]
            if r == CAIRO_SANAA_ROW:
                continue
            L = d["decision"]["institution"]
            c = d["decision"]["country"]
            if L in auth and auth[L]["country"] and auth[L]["country"] != c:
                raise SystemExit(f"{d['decision_id']}: country {c} differs from the authority's {auth[L]['country']}")
            add(f"E64|country|{d['decision_id']}", "set_inst_country", [f"inst:{r}"], dict(country=c, authority=L),
                d56=d)
            country_done[r].add(c)
    for L in sorted(used):
        e = body(L)
        c = e.get("country")
        r = canon[L]
        if not c or c in country_done[r] or (r in rows and rows[r]["country"] == c):
            continue
        add(f"E64|country|{L}", "set_inst_country", [ik(L)], dict(country=c, authority=L),
            rule="authority56" if L in auth else "exp64-new-body", confidence="sure",
            note=f"{e.get('name_en') or e.get('name_ar')} is in {c} ({e.get('country_basis') or NEW_BODIES[L]['why']})")
    for item, (L, c, why) in COUNTRY_FIX.items():
        d = S[by_item[item]]
        add(f"E64|country|{item}", "set_inst_country", [ik(L)], dict(country=c, authority=L, inferred="journal"),
            d56=d, item=item, rule="D39", confidence="likely", note=why)
    # a lumped «org:?» faculty row the librarian split gets one parent per group: those set_parent decisions are
    # carried by the split (phase 9), which gives each group's row its university
    lumped = {d["subject_keys"][0][5:]: d for d in standing if d["kind"] == "not_same_institution"
              and d["decision"].get("lumped_faculty")}
    folded = defaultdict(list)
    for d in standing:
        if d["kind"] == "set_parent" and d["decision"]["machine_row"] in lumped:
            sp = lumped[d["decision"]["machine_row"]]["decision"]["groups"]
            assert sorted(sp.get(d["decision"]["parent"], [])) == sorted(d["decision"]["affiliations"]), d["decision_id"]
            folded[d["decision"]["machine_row"]].append(d["decision_id"])
            continue
        if d["kind"] == "set_parent":
            add(f"E64|parent|{d['decision_id']}", "set_inst_parent",
                [f"inst:{d['decision']['machine_row']}", ik(d["decision"]["parent"])],
                dict(authority=d["decision"]["parent"]), d56=d)

    # ------------------------------------------------------------------ phase 8: which bodies each affiliation names
    def link_payload(lst):
        return dict(institutions=[dict(inst=ik(L), authority=L, role=role, country=body(L).get("country"),
                                       inferred={"from": inf, "rule": "D39"} if inf else None)
                                  for L, role, inf in lst])
    for d in standing:
        k = d["kind"]
        did = d["decision_id"]
        item = fix_ids.get(did)
        fx = AFF_FIX.get(item) if item else None
        if k in ("unsure", "set_type") or d["level"] != "affiliation":
            continue
        aff = d["subject_keys"][0]
        if fx and fx.get("op") == "not_an_institution":
            add(f"E64|aff|{did}", "not_an_institution", [aff], dict(why="reprint source"), d56=d, item=item,
                rule=fx["rule"], confidence="sure", note=fx["why"])
            continue
        if k == "affiliation_institution" or (fx and fx.get("op") == "link"):
            if fx and fx.get("links"):
                lst = list(fx["links"])
            else:
                inf = INFERRED_56.get(did)
                roles = (fx or {}).get("roles", {})
                lst = [(i["id"], roles.get(i["id"], "current"), inf) for i in d["decision"]["institutions"]]
                lst += list((fx or {}).get("extra", []))
            pl = link_payload(lst)
            keys = [aff] + [x["inst"] for x in pl["institutions"]]
            rule = (fx or {}).get("rule") or ("D39" if did in INFERRED_56 else None)
            note = d["reason"] + (f" — {fx['why']}" if fx else "") + (
                f" — marked inferred (from the {INFERRED_56[did]}, D39)" if did in INFERRED_56 and not fx else "")
            conf = "likely" if rule == "D39" and fx else None
            add(f"E64|aff|{did}", "link_affiliation", keys, pl, d56=d, item=item if fx else None, rule=rule,
                confidence=conf, note=note)
        elif k == "not_an_institution":
            add(f"E64|aff|{did}", "not_an_institution", [aff], {}, d56=d)
        elif k == "unit_kept_apart":
            add(f"E64|aff|{did}", "unit_kept_apart", [aff], dict(faculty=d["decision"].get("faculty")), d56=d)
        else:
            raise SystemExit(f"unhandled {k} {did}")

    # ------------------------------------------------------------------ phase 9: rows that held several bodies
    for d in standing:
        if d["kind"] == "not_same_institution":
            groups = [dict(label=g if not g.startswith("L-") else body(g).get("name_en"),
                           body=ik(g) if g.startswith("L-") else None, affiliations=affs)
                      for g, affs in d["decision"]["groups"].items()]
            row = d["subject_keys"][0][5:]
            add(f"E64|split|{d['decision_id']}", "not_same_institution", d["subject_keys"][:1],
                dict(groups=groups, lumped_faculty=d["decision"].get("lumped_faculty", False)), d56=d,
                extra=dict(set_parent_carried=folded.get(row, [])) if folded.get(row) else None)

    with open(OUT / "plan64.jsonl", "w", encoding="utf-8") as f:
        for p in plan:
            f.write(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n")
    skipped = Counter(d["kind"] for d in standing if d["kind"] in ("unsure", "set_type"))
    summary = dict(planned=len(plan), by_op=dict(Counter(p["op"] for p in plan)),
                   set_parent_carried_by_splits=sum(len(v) for v in folded.values()),
                   by_rule=dict(Counter(p["reason_code"] for p in plan)), not_imported=dict(skipped, set_country_O610=1),
                   canonical_rows=dict(how), bodies_defined=len(used),
                   reviewed_not_applied=NOT_APPLIED,
                   roles=dict(Counter(i["role"] for p in plan if p["op"] == "link_affiliation"
                                      for i in p["payload"]["institutions"])),
                   inferred=sum(1 for p in plan if p["op"] == "link_affiliation"
                                for i in p["payload"]["institutions"] if i["inferred"]))
    (OUT / "plan64_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
