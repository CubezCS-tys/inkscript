"""Experiment 52: how dense the bridges are inside one set of articles, measured from a platform v2 database
(read-only). The same code measures the journal (run j0130_final in gate1.db) and the random 600 (runs v33_300_final +
v33_300b_fix3 in platform_v2.db), so the two sets of numbers are comparable. Definitions follow experiment 48's
probes C and D (byline person authorships, authority ids, co-authorship, bibliographic coupling, raw cards).

    .venv/bin/python experiments/52_journal_gate1/measure52.py --db DB --runs RUN [RUN ...] --label NAME
        -> out/bridges_<label>.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
NONE = {"provisional", "weak-name-rejected"}


def components(nodes, edges):
    par = {n: n for n in nodes}

    def f(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for a, b in edges:
        ra, rb = f(a), f(b)
        if ra != rb:
            par[ra] = rb
    comp = defaultdict(list)
    for n in nodes:
        comp[f(n)].append(n)
    return sorted(comp.values(), key=len, reverse=True)


def measure(db: str, runs: list[str], stems: set | None = None) -> dict:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    q = ",".join("?" * len(runs))
    V = {r["version_id"]: dict(r) for r in c.execute(
        f"""SELECT v.version_id, v.stem, v.run, d.pub_id, p.c999, p.journal_id, p.year_shown
            FROM versions v JOIN documents d ON d.stem = v.stem LEFT JOIN publications p ON p.pub_id = d.pub_id
            WHERE v.is_current = 1 AND v.run IN ({q})""", runs)}
    if stems is not None:                      # a subset (the same-size draws from the 600)
        V = {k: v for k, v in V.items() if v["stem"] in stems}
    pubs = {v["pub_id"]: v for v in V.values()}
    R = dict(db=db, runs=runs, articles=len(V))

    # ---------------------------------------------------------------- people (probe C's definitions)
    rows = [dict(r) for r in c.execute(
        f"""SELECT a.authorship_pk, a.pub_id, a.position, a.role_code, a.method, a.person_id, a.inst_id, a.c999,
                   a.catalogue_seq, cc.authority_id, cc.is_org,
                   (SELECT count(*) FROM authorship_mentions am WHERE am.authorship_pk = a.authorship_pk) n_ment
            FROM authorships a JOIN versions v ON v.version_id = a.from_version AND v.is_current = 1
            LEFT JOIN catalogue_contributors cc ON cc.c999 = a.c999 AND cc.seq = a.catalogue_seq
            WHERE v.run IN ({q})""", runs)]
    rows = [r for r in rows if r["pub_id"] in pubs]
    byl = [r for r in rows if r["n_ment"] and not (r["inst_id"] or r["method"] in ("editorial-role", "corporate-byline"))]
    with_auth = [r for r in byl if r["authority_id"] and r["method"] != "weak-name-rejected"]
    per_person = defaultdict(set)
    for r in byl:
        if r["person_id"]:
            per_person[r["person_id"]].add(r["pub_id"])
    names = {r[0]: r[1] or r[2] for r in c.execute("SELECT person_id, preferred_name_ar, preferred_name_lat FROM persons")}
    multi = {p: s for p, s in per_person.items() if len(s) >= 2}
    by_pub = defaultdict(set)
    for r in byl:
        if r["person_id"] and r["role_code"] in ("author", "coauthor", None):
            by_pub[r["pub_id"]].add(r["person_id"])
    pair = Counter()
    for pub, ps in by_pub.items():
        for a, b in combinations(sorted(ps), 2):
            pair[(a, b)] += 1
    nodes = set(per_person)
    comps = components(nodes, list(pair))
    R["people"] = dict(
        byline_person_authorships=len(byl), with_authority_id=len(with_auth),
        share_with_authority=round(len(with_auth) / max(1, len(byl)), 3),
        persons=len(per_person), persons_2plus_articles=len(multi),
        share_persons_2plus=round(len(multi) / max(1, len(per_person)), 3),
        authorships_by_persons_2plus=sum(len(s) for s in multi.values()),
        max_articles_one_person=max((len(s) for s in per_person.values()), default=0),
        coauthor_pairs=len(pair), repeated_pairs=sum(1 for v in pair.values() if v >= 2),
        articles_2plus_persons=sum(1 for ps in by_pub.values() if len(ps) >= 2),
        coauthor_largest_component=len(comps[0]) if comps else 0,
        top_persons=[dict(person_id=p, name=names.get(p), articles=len(s), stems=sorted(pubs[x]["stem"] for x in s))
                     for p, s in sorted(multi.items(), key=lambda kv: -len(kv[1]))[:15]],
        top_pairs=[dict(a=names.get(a), b=names.get(b), articles=n) for (a, b), n in pair.most_common(10) if n >= 2])

    # ---------------------------------------------------------------- institutions (probe C2)
    # experiment 68: an affiliation printed again in the other script (twin_of_aff_pk) is not counted twice
    tw = (" AND am.twin_of_aff_pk IS NULL" if "twin_of_aff_pk" in
          {r[1] for r in c.execute("PRAGMA table_info(affiliation_mentions)")} else "")
    affs = [dict(r) for r in c.execute(
        f"""SELECT am.aff_pk, v.version_id, d.pub_id, am.printed, am.org_text, am.kind
            FROM affiliation_mentions am JOIN byline_mentions b USING (mention_pk)
            JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1 JOIN documents d ON d.stem = v.stem
            WHERE v.run IN ({q}){tw}""", runs)]
    affs = [a for a in affs if a["version_id"] in V]
    links = defaultdict(list)
    for r in c.execute("SELECT aff_pk, inst_id, level FROM affiliation_links"):
        links[r["aff_pk"]].append(dict(r))
    iname = {}
    for r in c.execute("SELECT inst_id, name, script, n_seen FROM institution_names ORDER BY n_seen"):
        if r["inst_id"] not in iname or r["script"] == "Arab":
            iname[r["inst_id"]] = r["name"]
    inst_country = {r[0]: r[1] for r in c.execute("SELECT inst_id, country_code FROM institutions")}
    org_of = {}
    for a in affs:
        org = [l["inst_id"] for l in links.get(a["aff_pk"], []) if l["level"] == "org"]
        org_of[a["aff_pk"]] = org[0] if org else None
    arts_of = defaultdict(set)
    for a in affs:
        if org_of[a["aff_pk"]]:
            arts_of[org_of[a["aff_pk"]]].add(a["pub_id"])
    linked = [a for a in affs if org_of[a["aff_pk"]]]
    rep = [a for a in linked if len(arts_of[org_of[a["aff_pk"]]]) >= 2]
    R["institutions"] = dict(
        affiliation_mentions=len(affs), with_org_institution=len(linked),
        articles_with_affiliation=len({a["pub_id"] for a in affs}),
        distinct_institutions=len(arts_of), institutions_2plus_articles=sum(1 for s in arts_of.values() if len(s) >= 2),
        share_affiliations_inst_2plus_articles=round(len(rep) / max(1, len(linked)), 3),
        countries=Counter(inst_country.get(i) for i in arts_of).most_common(12),
        top=[dict(inst_id=i, name=iname.get(i), articles=len(s)) for i, s in
             sorted(arts_of.items(), key=lambda kv: -len(kv[1]))[:15]])

    # ---------------------------------------------------------------- references (probe D's raw cards)
    ms = [dict(r) for r in c.execute(
        f"""SELECT m.mention_pk, m.version_id, m.kind, coalesce(m.full_mention_pk, m.mention_pk) full_pk, w.cited_work_pk
            FROM citation_mentions m JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
            LEFT JOIN cited_work_members w ON w.full_mention_pk = coalesce(m.full_mention_pk, m.mention_pk)
            WHERE v.run IN ({q}) AND m.kind NOT IN ('quran', 'hadith')""", runs)]
    ms = [m for m in ms if m["version_id"] in V]
    work_pubs = defaultdict(set)
    work_ment = Counter()
    for m in ms:
        if m["cited_work_pk"]:
            work_pubs[m["cited_work_pk"]].add(V[m["version_id"]]["pub_id"])
            work_ment[m["cited_work_pk"]] += 1
    W = {r["cited_work_pk"]: dict(r) for r in c.execute(
        "SELECT cited_work_pk, cited_work_id, pub_type, title, year_printed, lang FROM cited_works WHERE status = 'active'")}
    au = defaultdict(list)
    for r in c.execute("SELECT cited_work_pk, printed FROM cited_work_authors ORDER BY cited_work_pk, seq"):
        au[r[0]].append(r[1])
    shared = {w: s for w, s in work_pubs.items() if len(s) >= 2 and w in W}
    edges = set()
    for w, s in shared.items():
        for a, b in combinations(sorted(s), 2):
            edges.add((a, b))
    e_count = Counter()
    for w, s in shared.items():
        for a, b in combinations(sorted(s), 2):
            e_count[(a, b)] += 1
    cnodes = {p for e in edges for p in e}
    cc = components(cnodes, edges)
    arts_with_cards = {p for s in work_pubs.values() for p in s}
    R["references"] = dict(
        mentions_no_quran=len(ms), full=sum(1 for m in ms if m["kind"] == "full"),
        on_cards=sum(1 for m in ms if m["cited_work_pk"]), per_article=round(len(ms) / max(1, len(V)), 1),
        cited_works=len(work_pubs), shared_2plus_articles=len(shared),
        shared_per_100_articles=round(100 * len(shared) / max(1, len(V)), 1),
        articles_in_coupling=len(cnodes), of_articles_with_cards=len(arts_with_cards),
        coupling_edges=len(edges), coupling_edges_2plus_shared=sum(1 for v in e_count.values() if v >= 2),
        coupling_components=len(cc), coupling_largest=len(cc[0]) if cc else 0,
        coupling_second=len(cc[1]) if len(cc) > 1 else 0,
        times_cited_hist=dict(Counter(min(len(s), 6) for s in work_pubs.values())),
        top_cited=[dict(cited_work_pk=w, id=W[w]["cited_work_id"], title=W[w]["title"], authors=au.get(w, [])[:3],
                        year=W[w]["year_printed"], type=W[w]["pub_type"], lang=W[w]["lang"], articles=len(s),
                        mentions=work_ment[w], stems=sorted(pubs[x]["stem"] for x in s))
                   for w, s in sorted(shared.items(), key=lambda kv: (-len(kv[1]), -work_ment[kv[0]]))[:25]])
    R["_coupling_graph"] = dict(nodes=sorted(pubs[p]["stem"] for p in cnodes),
                                edges=[[pubs[a]["stem"], pubs[b]["stem"], n] for (a, b), n in e_count.items()])
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--label", required=True)
    a = ap.parse_args()
    R = measure(a.db, a.runs)
    out = HERE / "out" / f"bridges_{a.label}.json"
    out.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    show = {k: ({kk: vv for kk, vv in v.items() if not kk.startswith("top")} if isinstance(v, dict) else v)
            for k, v in R.items() if not k.startswith("_")}
    print(json.dumps(show, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())


def same_size(db: str, runs: list[str], n: int, draws: int = 20, seed: int = 5250) -> dict:
    """The 600 cut to n articles, `draws` seeded random subsets: the bridges a random set of the journal's size has."""
    import random
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = ",".join("?" * len(runs))
    stems = sorted(r[0] for r in c.execute(f"SELECT stem FROM versions WHERE is_current = 1 AND run IN ({q})", runs))
    rnd = random.Random(seed)
    keys = [("people", "persons_2plus_articles"), ("people", "share_with_authority"), ("people", "repeated_pairs"),
            ("institutions", "distinct_institutions"), ("institutions", "institutions_2plus_articles"),
            ("institutions", "share_affiliations_inst_2plus_articles"), ("references", "mentions_no_quran"),
            ("references", "shared_2plus_articles"), ("references", "articles_in_coupling"),
            ("references", "coupling_largest"), ("references", "of_articles_with_cards")]
    vals = defaultdict(list)
    for _ in range(draws):
        R = measure(db, runs, set(rnd.sample(stems, n)))
        for a, b in keys:
            vals[f"{a}.{b}"].append(R[a][b])
    return dict(n=n, draws=draws, seed=seed,
                mean={k: round(sum(v) / len(v), 3) for k, v in vals.items()},
                range={k: [min(v), max(v)] for k, v in vals.items()})
