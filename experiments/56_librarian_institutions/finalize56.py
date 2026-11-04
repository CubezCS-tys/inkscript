"""Experiment 56, step 3-4: institution-level decisions, the clean authority, and the numbers before and after.

Reads the newest per-affiliation verdicts (judge56 over the packets, the same ones committed to decisions56.jsonl),
then:
- writes the institution-level decisions (`same_institution`, `not_same_institution`, `set_country`, `set_parent`,
  `set_type`, `not_an_institution` on machine rows) to out/decisions56.jsonl (append-only, superseding);
- writes the authority: out/authority56.json (every institution with its names, country and basis, type, parent,
  units seen under it, every printed form mapped to it, the machine rows it replaces);
- measures before (the machine's affiliation_links, as experiment 52's measure52 counts them) and after (the
  authority), on the 780 articles and on gate 1's journal against 20 random sets of 126 (measure52's seed 5250):
  out/numbers56.json.

    python3 finalize56.py [--db RELEASE]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
import judge56 as J  # noqa: E402
from decisions56 import ACTOR, append, did  # noqa: E402
from build56 import newest_release  # noqa: E402

GATE1 = "J0130"
TYPE_TO_MACHINE = {"university": "university", "faculty": "faculty", "institute": "centre", "centre": "centre",
                   "ministry": "ministry", "school": "organisation", "academy": "society", "other": "organisation"}


def fold_fac(s: str | None) -> str:
    return J.fk(re.sub(r"^\s*(ب|و|في)\s*", "", s or "")) if s else ""


def inst_decision(kind, qkey, subjects, decision, reason, evidence, confidence, basis, trivial, extra=None):
    sig = json.dumps([kind, decision, confidence, basis], ensure_ascii=False, sort_keys=True)
    d = dict(decision_id=did("inst", qkey, sig), qkey=qkey, made_at=time.strftime("%Y-%m-%dT%H:%M:%S"), actor=ACTOR,
             level="institution", kind=kind, question=extra.pop("question") if extra and "question" in extra else None,
             subject_keys=subjects, decision=decision, reason=reason, evidence_ids=evidence, confidence=confidence,
             basis=basis, trivial=trivial)
    if extra:
        d.update(extra)
    d["size"] = dict(decision_chars=len(json.dumps({k: d[k] for k in ("kind", "decision", "reason", "evidence_ids",
                                                                      "confidence")}, ensure_ascii=False)))
    return d


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else newest_release()
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    P = J.load_packets()
    ov = J.load_overrides()
    V = {p["key"]: J.judge(p, ov) for p in P}
    PK = {p["key"]: p for p in P}
    AUTH = J.AUTH

    inst = {r["inst_id"]: dict(r) for r in con.execute("SELECT * FROM institutions")}
    natkey = {r[0]: r[1] for r in con.execute("SELECT public_id, natural_key FROM id_registry WHERE kind = 'institution'")}
    iname = defaultdict(list)
    for r in con.execute("SELECT inst_id, name, script, n_seen FROM institution_names ORDER BY n_seen DESC"):
        iname[r[0]].append(r[1])
    links = defaultdict(dict)
    for r in con.execute("SELECT aff_pk, inst_id, level FROM affiliation_links"):
        links[r[0]].setdefault(r[2], r[1])

    # ------------------------------------------------------------------ the authority
    used = defaultdict(list)                 # authority org -> affiliation keys
    units = defaultdict(Counter)             # org -> faculty/unit printed forms
    forms = defaultdict(Counter)             # org -> printed org strings
    machine_rows = defaultdict(Counter)      # org -> machine org rows of its affiliations
    unparented = []
    for k, v in V.items():
        p = PK[k]
        if v["status"] == "resolved":
            m = p["machine"].get("org")
            for o in v["orgs"]:
                used[o].append(k)
                forms[o][(p["parts"].get("org") or p["printed"]).split(" | ")[0][:120]] += 1
            if m:
                # the machine row stands for the one printed body its own name matches, else the first printed
                own = [o for o in v["orgs"] if any(J.top_of(x) == o for x, _ in J.matches(" ".join((m.get("names") or [])[:3])))]
                machine_rows[own[0] if own else v["orgs"][0]][m["inst_id"]] += 1
            if v.get("faculty") and v["orgs"]:
                units[v["orgs"][0]][v["faculty"].strip(" .،,")] += 1
            for u in v.get("units") or []:
                units[J.top_of(u)][AUTH[u]["name_ar"]] += 1
        elif v["status"] == "unit_only":
            unparented.append(dict(key=k, faculty=v.get("faculty"), city=p["parts"].get("city"), stem=p["stem"],
                                   country=v.get("country"), reason=v.get("reason")))

    def arts(o):
        return sorted({PK[k]["stem"] for k in used[o]})

    authority = []
    for o in sorted(used, key=lambda x: (-len(arts(x)), x)):
        e = AUTH[o]
        authority.append(dict(
            id=o, type=e["type"], name_ar=e["name_ar"], name_en=e["name_en"], country=e.get("country"),
            country_basis=(e.get("country_basis") or ("world" if e.get("country") else None)),
            catalogue=e.get("catalogue"), parent=e.get("parent"), note=e.get("note"),
            n_affiliations=len(used[o]), n_articles=len(arts(o)), articles=arts(o),
            printed_forms=[dict(form=f, n=n) for f, n in forms[o].most_common()],
            units=[dict(name=f, n=n) for f, n in units[o].most_common()],
            machine_rows=[dict(inst_id=i, names=iname.get(i, [])[:3], n=n, country=inst.get(i, {}).get("country_code"),
                               kind=inst.get(i, {}).get("kind")) for i, n in machine_rows[o].most_common()]))
    (OUT / "authority56.json").write_text(json.dumps(dict(
        made=time.strftime("%Y-%m-%d %H:%M"), release=db.name, institutions=authority, units_kept_apart=unparented),
        ensure_ascii=False, indent=1), encoding="utf-8")

    # ------------------------------------------------------------------ institution-level decisions
    decs = []
    by_row = defaultdict(lambda: defaultdict(list))   # machine row -> verdict target -> affiliation keys
    for k, v in V.items():
        p = PK[k]
        for lvl in ("org", "faculty"):
            m = p["machine"].get(lvl)
            if not m or (lvl == "faculty" and "org:?" not in (m.get("key") or "")):
                continue                 # faculty rows are judged here only when the machine lumped them («org:?»)
            tgt = f"<{v['status']}>"
            if v["status"] == "unit_only":
                tgt = f"<unit kept apart: {p['stem']}>"     # each faculty printed alone is its own unit
            if v["status"] == "resolved" and v["orgs"]:
                own = [o for o in v["orgs"] if any(J.top_of(x) == o for x, _ in
                                                   J.matches(" ".join((m.get("names") or [])[:3])))]
                tgt = own[0] if own else v["orgs"][0]
            by_row[m["inst_id"]][tgt].append(k)
    split_rows = {r for r, tg in by_row.items() if len(tg) >= 2}
    conf_of = lambda ks: "high" if all(V[k]["confidence"] == "high" for k in ks) else (  # noqa: E731
        "low" if any(V[k]["confidence"] == "low" for k in ks) else "medium")
    def row_class(o, i):
        """How a machine org row relates to authority entry o: 'name' (its names are o's forms), 'unit' (a unit of o),
        'other' (another body: the affiliation printed several), 'variant' (no authority form: a damaged, truncated
        or unnamed form the librarian resolved to o)."""
        ms = J.matches(" ".join(iname.get(i, [])[:3]))
        if any(J.canon(x) == o for x, _ in ms):
            return "name"
        if any(J.top_of(x) == o for x, _ in ms):
            return "unit"
        if ms:
            return "other"
        nm = " ".join(iname.get(i, [])[:2])

        def words(x):
            return {re.sub(r"^(ال|بال|وال|لل)", "", w) for w in J.fk(x).split()}
        names_o = [AUTH[o]["name_ar"], AUTH[o]["name_en"]] + AUTH[o]["forms"]
        if any(words(n_) and words(n_) <= words(f_) for n_ in iname.get(i, [])[:1] for f_ in names_o):
            return "variant"            # a shorter form of the body's own name (no city, no country word)
        if re.fullmatch(r"\s*(ال)?(جامعة|جامعه|معهد|المعهد|كلية|الكلية)\s*(\|.*)?", nm) or not nm.strip():
            return "variant"            # an unnamed «الجامعة» / «المعهد»: the affiliation decisions name it
        if re.search(r"(معهد|مركز|كلي|قسم|مختبر|مخبر|وحد|institut|cent|college|faculty|facult|school|department|"
                     r"laborator|fsjes|msik|m sik|unit|grad)", J.fk(nm), re.I):
            return "unit"
        return "variant"
    rclass = {(o, i): row_class(o, i) for o, rows in machine_rows.items() for i in rows}
    for o, rows in machine_rows.items():
        e = AUTH[o]
        ids = sorted(i for i in rows if rclass[(o, i)] in ("name", "variant") and i not in split_rows)
        if len(ids) >= 2:
            names = {i: iname.get(i, [])[:2] for i in ids}
            scripts = {("Arab" if re.search("[؀-ۿ]", " ".join(n)) else "Latn") for n in names.values()}
            twin = len(scripts) > 1
            variants = [i for i in ids if rclass[(o, i)] == "variant"]
            ks = [k for k in used[o] if PK[k]["machine"].get("org", {}).get("inst_id") in ids]
            via_same_as = any(J.canon(x) == o and x != o for i in ids for x, _ in J.matches(" ".join(names[i])))
            kb = Counter(V[k].get("basis") for k in ks if PK[k]["machine"].get("org", {}).get("inst_id") in variants)
            basis = "world" if (twin or via_same_as) else (kb.most_common(1)[0][0] if variants and kb else "rule")
            why = ("one body printed in two scripts" if twin else "spelling variants of one name")
            if variants:
                why += "; " + ", ".join(f"«{(iname.get(i) or ['?'])[0]}»" for i in variants) + \
                       " is a damaged, cut or unnamed form the affiliation decisions resolve to it"
            if e.get("note") and (twin or via_same_as):
                why += f"; {e['note']}"
            decs.append(inst_decision(
                "same_institution", f"same|{o}", [f"inst:{i}" for i in ids],
                dict(institution=o, name_ar=e["name_ar"], name_en=e["name_en"], machine_rows=names, bilingual_twin=twin,
                     variant_rows=variants),
                why, ids + ks[:12], "medium" if via_same_as else conf_of(ks) if variants else "high", basis,
                trivial=not (twin or via_same_as or variants), extra=dict(question="Are these machine institution rows one body?")))
    for row, tg in by_row.items():
        if len(tg) >= 2:
            groups = {t: ks for t, ks in tg.items()}
            nm = iname.get(row, [])[:2]
            lumped = "org:?" in (natkey.get(row) or "")
            if lumped:
                arts_ = {PK[k]["stem"] for ks in groups.values() for k in ks}
            decs.append(inst_decision(
                "not_same_institution", f"split|{row}", [f"inst:{row}"],
                dict(machine_row=row, names=nm, groups={t: ks for t, ks in groups.items()}, lumped_faculty=lumped,
                     group_names={t: (AUTH[t]["name_ar"] if t in AUTH else t) for t in groups}),
                ("a faculty printed without its university, lumped by the machine under «org:?» across "
                 f"{len({PK[k]['stem'] for ks in groups.values() for k in ks})} articles; they are different units: "
                 if lumped else "one machine row holds affiliations of different bodies: ") +
                "; ".join(f"{AUTH[t]['name_en'] if t in AUTH else t} ×{len(ks)}" for t, ks in groups.items()),
                [row] + [k for ks in groups.values() for k in ks][:15],
                "high" if all(conf_of(ks) != "low" for ks in groups.values()) else "medium", "judgement", False,
                extra=dict(question="Is this machine row one body?")))
        elif "<not_institution>" in tg and len(tg) == 1:
            ks = tg["<not_institution>"]
            decs.append(inst_decision(
                "not_an_institution", f"notinst|{row}", [f"inst:{row}"],
                dict(machine_row=row, names=iname.get(row, [])[:2]),
                "every affiliation linked to this row names no body («" + (iname.get(row, ["?"])[0]) + "»): "
                + (V[ks[0]].get("reason") or ""), [row] + ks, conf_of(ks), V[ks[0]].get("basis") or "judgement",
                False, extra=dict(question="Is this machine row an institution?")))
    # countries, parents and types where the authority differs from the machine row it replaces
    for o, rows in machine_rows.items():
        e = AUTH[o]
        for i in rows:
            if rclass[(o, i)] == "other" or i in split_rows:
                continue                # a row being split gets its country per part, through the split
            mi = inst.get(i, {})
            if e.get("country") and mi.get("country_code") != e["country"]:
                cb = e.get("country_basis") or "world"
                decs.append(inst_decision(
                    "set_country", f"country|{i}", [f"inst:{i}"],
                    dict(machine_row=i, names=iname.get(i, [])[:2], was=mi.get("country_code"), country=e["country"],
                         institution=o),
                    (f"the catalogue (MARC 502) puts {e['name_ar']} in {e['country']} ({e['catalogue']['n']} theses)"
                     if cb == "catalogue" else f"{e['name_en']} is in {e['country']} (world knowledge)")
                    + ("" if not mi.get("country_code") else f"; the machine had {mi['country_code']}"),
                    [i] + used[o][:5], conf_of([k for k in used[o] if PK[k]["machine"].get("org", {}).get("inst_id") == i]
                                               or used[o]), cb, cb == "catalogue",
                    extra=dict(question="In which country is this institution?")))
            mk = mi.get("kind")
            if mk and rclass[(o, i)] != "unit" and TYPE_TO_MACHINE.get(e["type"]) != mk and mk not in ("faculty", "department"):
                decs.append(inst_decision(
                    "set_type", f"type|{i}", [f"inst:{i}"],
                    dict(machine_row=i, names=iname.get(i, [])[:2], was=mk, type=e["type"], institution=o),
                    f"{e['name_en']} is a {e['type']}", [i], "high", "judgement", False,
                    extra=dict(question="What kind of body is this?")))
    # parents: a machine org row that is really a unit inside the body (institute, centre, laboratory), and a lumped
    # «org:?» faculty row whose affiliations the librarian placed under a university; one decision per machine row
    par = defaultdict(lambda: defaultdict(list))      # row -> parent -> affiliation keys
    lvl_of = {}
    for o, rows in machine_rows.items():
        for i in rows:
            if rclass[(o, i)] == "unit" and i not in split_rows:
                for k in used[o]:
                    if PK[k]["machine"].get("org", {}).get("inst_id") == i:
                        par[i][o].append(k)
                lvl_of[i] = "org"
    for row, tg in by_row.items():
        if "org:?" in (natkey.get(row) or ""):
            for t, ks in tg.items():
                if t in AUTH and not (iname.get(row) and set(J.fk(iname[row][0]).split()) <= set(J.fk(AUTH[t]["name_ar"]).split())):
                    par[row][t] += ks
                    lvl_of[row] = "faculty"
    for row, ps in par.items():
        nm = iname.get(row, [])[:2]
        for o, ks in ps.items():
            lump = lvl_of[row] == "faculty"
            bs = Counter(V[k].get("basis") or "rule" for k in ks)
            decs.append(inst_decision(
                "set_parent", f"parent|{row}|{o}", [f"inst:{row}"] + ks[:10],
                dict(machine_row=row, names=nm, parent=o, parent_name=AUTH[o]["name_ar"], level=lvl_of[row],
                     affiliations=ks),
                (f"«{nm[0] if nm else '?'}» is a unit of {AUTH[o]['name_en']}" +
                 (" (printed without its university; the machine's «org:?» row): " + "; ".join(
                     sorted({V[k].get('reason') or 'the university is printed' for k in ks}))[:300] if lump else
                  ": the machine took the unit for the institution")),
                [row] + ks[:10], conf_of(ks), bs.most_common(1)[0][0], all(b_ == "rule" for b_ in bs),
                extra=dict(question="Which body is this unit part of?")))
    # a question asked by an earlier run and not asked now is retired (append-only: a record that supersedes it)
    from decisions56 import latest
    asked = {d["qkey"] for d in decs}
    for q, old in latest().items():
        if old["level"] == "institution" and q not in asked and old["kind"] != "retired":
            decs.append(dict(decision_id=did("retire", q, old["decision_id"]), qkey=q,
                             made_at=time.strftime("%Y-%m-%dT%H:%M:%S"), actor=ACTOR, level="institution",
                             kind="retired", question=old.get("question"), subject_keys=old["subject_keys"],
                             decision=dict(retired=old["decision_id"]), reason="no longer asked: the librarian's "
                             "authority changed and this question does not arise", evidence_ids=[],
                             confidence=None, basis="judgement", trivial=True))
    n = append(decs)

    # ------------------------------------------------------------------ numbers
    stems = {r["stem"]: dict(r) for r in con.execute(
        """SELECT v.stem, v.run, d.level, p.journal_id FROM versions v JOIN documents d ON d.stem = v.stem
           LEFT JOIN publications p ON p.pub_id = d.pub_id WHERE v.is_current = 1""")}
    aff_rows = [dict(r) for r in con.execute(
        """SELECT am.aff_pk, v.stem, b.byline_pos, b.script, am.seq FROM affiliation_mentions am
           JOIN byline_mentions b USING (mention_pk) JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1""")]
    for r in aff_rows:
        r["key"] = f"aff:{r['stem']}|b{r['byline_pos']}|{r['script']}|a{r['seq']}"

    def machine_orgs(r):
        o = links.get(r["aff_pk"], {}).get("org")
        return [o] if o else []

    def librarian_orgs(r):
        v = V.get(r["key"])
        return list(v["orgs"]) if v and v["status"] == "resolved" else []

    def measure(org_fn, keep):
        arts_of = defaultdict(set)
        linked = 0
        for r in aff_rows:
            if r["stem"] not in keep:
                continue
            os_ = org_fn(r)
            if os_:
                linked += 1
            for o in os_:
                arts_of[o].add(r["stem"])
        return dict(distinct=len(arts_of), two_plus=sum(1 for s in arts_of.values() if len(s) >= 2), linked=linked,
                    arts_of=arts_of)

    def country_share(arts_of, country_fn):
        ids = list(arts_of)
        return round(sum(1 for i in ids if country_fn(i)) / max(1, len(ids)), 3), sum(1 for i in ids if country_fn(i))

    all_stems = set(stems)
    B = measure(machine_orgs, all_stems)
    A_ = measure(librarian_orgs, all_stems)
    jst = {s for s, x in stems.items() if x["journal_id"] == GATE1}
    rst_runs = sorted({x["run"] for s, x in stems.items() if x["journal_id"] != GATE1 and x["level"] == "final"})
    pool = sorted(s for s, x in stems.items() if x["run"] in rst_runs)
    rnd = random.Random(5250)
    draws = [set(rnd.sample(pool, len(jst))) for _ in range(20)]

    def gate(fn):
        j = measure(fn, jst)["two_plus"]
        rs = [measure(fn, d)["two_plus"] for d in draws]
        r600 = measure(fn, set(pool))
        return dict(journal=j, random_same_size=round(sum(rs) / len(rs), 2), random_range=[min(rs), max(rs)],
                    random_600=r600["two_plus"], journal_distinct=measure(fn, jst)["distinct"])
    unit_rows = {i for i, x in inst.items() if x["kind"] in ("faculty", "department")}
    lumped_rows = [i for i in inst if "org:?" in (natkey.get(i) or "")]
    lumped_fac = [i for i in lumped_rows if inst[i]["kind"] == "faculty"]
    lump_affs = [r for r in aff_rows if any(links.get(r["aff_pk"], {}).get(l) in lumped_rows for l in ("faculty", "dept"))]
    lump_res = Counter(V[r["key"]]["status"] for r in lump_affs if r["key"] in V)
    lump_orgs = Counter(V[r["key"]]["orgs"][0] for r in lump_affs if r["key"] in V and V[r["key"]]["orgs"])
    twins = [d for d in decs if d["kind"] == "same_institution" and d["decision"]["bilingual_twin"]]
    org_rows = {i for i, x in inst.items() if x["kind"] not in ("faculty", "department")}
    mc_share, mc_n = country_share(B["arts_of"], lambda i: inst.get(i, {}).get("country_code"))
    ac_share, ac_n = country_share(A_["arts_of"], lambda i: AUTH[i].get("country"))
    aff_country_before = sum(1 for r in aff_rows if any(inst.get(o, {}).get("country_code") for o in machine_orgs(r)))
    aff_country_after = sum(1 for r in aff_rows if V.get(r["key"]) and V[r["key"]].get("country"))
    nums = dict(
        release=db.name, articles=len(stems), affiliations=len(aff_rows),
        before=dict(institution_rows=len(inst), org_level_rows=len(org_rows), faculty_department_rows=len(unit_rows),
                    rows_without_country=sum(1 for x in inst.values() if not x["country_code"]),
                    institutions_linked=B["distinct"], institutions_2plus_articles=B["two_plus"],
                    affiliations_with_institution=B["linked"], share_institutions_with_country=mc_share,
                    institutions_with_country=mc_n, affiliations_with_country=aff_country_before,
                    gate1=gate(machine_orgs)),
        after=dict(institutions=A_["distinct"], institutions_2plus_articles=A_["two_plus"],
                   affiliations_with_institution=A_["linked"], share_institutions_with_country=ac_share,
                   institutions_with_country=ac_n, affiliations_with_country=aff_country_after,
                   units_kept_apart=len(unparented), gate1=gate(librarian_orgs)),
        lumped=dict(machine_rows=len(lumped_rows), faculty_rows=len(lumped_fac), affiliations=len(lump_affs),
                    resolved_to_university=lump_res.get("resolved", 0), kept_apart=lump_res.get("unit_only", 0),
                    other=dict(lump_res), universities=dict(lump_orgs.most_common())),
        bilingual_twins_joined=len(twins), twins=[d["decision"]["name_en"] for d in twins],
        verdicts=dict(Counter(v["status"] for v in V.values())),
        decisions_appended=n)
    (OUT / "numbers56.json").write_text(json.dumps(nums, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in nums.items() if k != "twins"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
