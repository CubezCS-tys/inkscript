"""Experiment 70: gate 2's question on its pilot - do education journals cite each other? Read-only on a release DB
(the state the Desk serves: machine reading + every Desk decision).

Sets (current versions):
  J  = journal 0130 (gate 1, J0130)       K = journal 0165 (this pilot, J0165; scan route + Word route)
  R  = the random 600 (runs v33_300_final_lettersfix_fix61_d30 + v33_300b_fix3_lettersfix_fix61_d30)
Inside a set: experiment 52's measure52.measure, unchanged (K whole, K scan only, K Word only), and its same_size
draws from R (20 seeded sets of K's size, seed 5250).
Between J and K (both directions), each against a baseline of J with 20 random sets of K's size from R (seed 7070):
  - citations: references whose card has an accepted best link (link47 + Desk) to a publication of the other journal
    (read here or not), and to an article read here; plus references whose printed text NAMES the other journal
  - shared authors (byline person ids), shared institutions (org level), shared cited works (cards cited from both),
    coupling edges between a J article and a K article (they cite a common card)
  - held: references whose card has an accepted best link to a publication Mandumah holds (index_pages' rule)

    measure70.py --db RELEASE.db [--out out/measure70.json]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "52_journal_gate1"))
import measure52  # noqa: E402

R_RUNS = ["v33_300_final_lettersfix_fix61_d30", "v33_300b_fix3_lettersfix_fix61_d30"]
NAME_K = re.compile(r"الطفولة\s+والتنمية|Childhood\s+(and|&)\s+Development", re.I)
NAME_J = re.compile(r"الطفولة\s+العربية|Arab(ic)?\s+Childhood", re.I)


def base(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    cur = {r["stem"]: dict(r) for r in c.execute(
        """SELECT v.version_id, v.stem, v.run, d.pub_id, p.journal_id, p.year_shown, d.has_azure_json
           FROM versions v JOIN documents d ON d.stem = v.stem LEFT JOIN publications p ON p.pub_id = d.pub_id
           WHERE v.is_current = 1""")}
    pubj = {r[0]: (r[1], r[2]) for r in c.execute("SELECT pub_id, journal_id, year_shown FROM publications")}
    best = {r[0]: r[1] for r in c.execute(
        "SELECT cited_work_pk, target_pub_id FROM citation_links WHERE status = 'accepted' AND best = 1 "
        "AND target_kind = 'publication'")}
    refs = [dict(r) for r in c.execute(
        """SELECT m.mention_pk, m.version_id, m.kind, m.printed, w.cited_work_pk
           FROM citation_mentions m JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
           LEFT JOIN cited_work_members w ON w.full_mention_pk = coalesce(m.full_mention_pk, m.mention_pk)
           WHERE m.kind NOT IN ('quran', 'hadith')""")]
    vpub = {v["version_id"]: v["pub_id"] for v in cur.values()}
    auth = defaultdict(set)
    for r in c.execute("""SELECT a.pub_id, a.person_id FROM authorships a JOIN versions v ON v.version_id = a.from_version
                          AND v.is_current = 1 WHERE a.person_id IS NOT NULL AND (a.method IS NULL OR a.method NOT IN
                          ('editorial-role', 'corporate-byline', 'weak-name-rejected')) AND a.inst_id IS NULL
                          AND EXISTS (SELECT 1 FROM authorship_mentions x WHERE x.authorship_pk = a.authorship_pk)"""):
        auth[r[0]].add(r[1])
    tw = (" AND am.twin_of_aff_pk IS NULL" if "twin_of_aff_pk" in
          {r[1] for r in c.execute("PRAGMA table_info(affiliation_mentions)")} else "")
    inst = defaultdict(set)
    for r in c.execute(f"""SELECT d.pub_id, l.inst_id FROM affiliation_links l JOIN affiliation_mentions am
                           ON am.aff_pk = l.aff_pk JOIN byline_mentions b ON b.mention_pk = am.mention_pk
                           JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1
                           JOIN documents d ON d.stem = v.stem WHERE l.level = 'org'{tw}"""):
        inst[r[0]].add(r[1])
    pname = {r[0]: r[1] or r[2] for r in c.execute("SELECT person_id, preferred_name_ar, preferred_name_lat FROM persons")}
    iname = {}
    for r in c.execute("SELECT inst_id, name, script FROM institution_names ORDER BY n_seen"):
        if r[0] not in iname or r[2] == "Arab":
            iname[r[0]] = r[1]
    cwt = {r[0]: (r[1], r[2]) for r in c.execute("SELECT cited_work_pk, cited_work_id, title FROM cited_works")}
    return dict(cur=cur, pubj=pubj, best=best, refs=refs, vpub=vpub, auth=auth, inst=inst, pname=pname, iname=iname,
                cwt=cwt, title={r[0]: r[1] for r in c.execute("SELECT pub_id, title_shown FROM publications")})


def cross(B, A: set, Bs: set, jid_b: str, name_b, detail=False) -> dict:
    """From set A (pub ids) to set Bs / journal jid_b."""
    out = Counter()
    ex = []
    for m in B["refs"]:
        p = B["vpub"].get(m["version_id"])
        if p not in A:
            continue
        out["references"] += 1
        w = m["cited_work_pk"]
        t = B["best"].get(w) if w is not None else None
        if t is not None:
            out["held"] += 1
            if (B["pubj"].get(t) or (None,))[0] == jid_b:
                out["to_journal"] += 1
                out["to_read_article"] += t in Bs
                if detail:
                    ex.append(dict(citing=p, target=t, target_year=B["pubj"][t][1], read=t in Bs,
                                   target_title=B["title"].get(t), printed=(m["printed"] or "")[:240]))
        if name_b is not None and name_b.search(m["printed"] or ""):
            out["names_journal"] += 1
            out["names_journal_linked"] += bool(t is not None and (B["pubj"].get(t) or (None,))[0] == jid_b)
    res = dict(out)
    if detail:
        res["links"] = ex
        res["citing_articles"] = len({e["citing"] for e in ex})
        res["cited_publications"] = len({e["target"] for e in ex})
    return res


def shared(B, A: set, Bs: set, detail=False) -> dict:
    pa = set().union(*[B["auth"][p] for p in A]) if A else set()
    pb = set().union(*[B["auth"][p] for p in Bs]) if Bs else set()
    ia = set().union(*[B["inst"][p] for p in A]) if A else set()
    ib = set().union(*[B["inst"][p] for p in Bs]) if Bs else set()
    wa, wb = defaultdict(set), defaultdict(set)
    for m in B["refs"]:
        p = B["vpub"].get(m["version_id"])
        w = m["cited_work_pk"]
        if w is None:
            continue
        if p in A:
            wa[w].add(p)
        elif p in Bs:
            wb[w].add(p)
    sw = set(wa) & set(wb)
    edges = {(a, b) for w in sw for a in wa[w] for b in wb[w]}
    r = dict(authors=len(pa & pb), institutions=len(ia & ib), cited_works=len(sw), coupling_edges=len(edges),
             coupled_articles_a=len({e[0] for e in edges}), coupled_articles_b=len({e[1] for e in edges}))
    if detail:
        r["top_authors"] = [dict(person_id=x, name=B["pname"].get(x),
                                 a=sum(x in B["auth"][p] for p in A), b=sum(x in B["auth"][p] for p in Bs))
                            for x in sorted(pa & pb)][:60]
        r["top_institutions"] = sorted(([B["iname"].get(x), sum(x in B["inst"][p] for p in A),
                                         sum(x in B["inst"][p] for p in Bs)] for x in ia & ib), key=lambda v: -v[1] - v[2])[:30]
        r["top_works"] = sorted(([B["cwt"].get(w, (None, None))[0], B["cwt"].get(w, (None, None))[1], len(wa[w]), len(wb[w])]
                                 for w in sw), key=lambda v: -v[2] - v[3])[:30]
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", default=str(HERE / "out" / "measure70.json"))
    a = ap.parse_args()
    B = base(a.db)
    cur = B["cur"]
    J = {v["pub_id"] for v in cur.values() if v["journal_id"] == "J0130"}
    K = {v["pub_id"] for v in cur.values() if v["journal_id"] == "J0165"}
    Ks = {v["pub_id"] for v in cur.values() if v["journal_id"] == "J0165" and v["has_azure_json"]}
    Kw = K - Ks
    Rr = {v["pub_id"] for v in cur.values() if v["run"] in R_RUNS and v["journal_id"] not in ("J0130", "J0165")}
    stem = {v["pub_id"]: s for s, v in cur.items()}
    runs = lambda ps: sorted({cur[stem[p]]["run"] for p in ps})  # noqa: E731
    out = dict(db=a.db, sets=dict(J=len(J), K=len(K), K_scan=len(Ks), K_word=len(Kw), R=len(Rr)))
    # inside
    ins = {}
    for lab, S in (("K", K), ("K_scan", Ks), ("K_word", Kw), ("J", J), ("R", Rr)):
        m = measure52.measure(a.db, runs(S), {stem[p] for p in S})
        m.pop("_coupling_graph", None)
        ins[lab] = m
    ins["R_same_size_K"] = measure52.same_size(a.db, runs(Rr), len(K))
    ins["R_same_size_J"] = measure52.same_size(a.db, runs(Rr), len(J))
    out["inside"] = ins
    # inside citations of K (links to its own journal) and held
    out["K_to_K"] = cross(B, K, K, "J0165", None, detail=True)
    out["J_to_J"] = cross(B, J, J, "J0130", None)
    out["R_held"] = cross(B, Rr, set(), "none", None)
    # between
    out["J_to_K"] = cross(B, J, K, "J0165", NAME_K, detail=True)
    out["K_to_J"] = cross(B, K, J, "J0130", NAME_J, detail=True)
    out["shared_J_K"] = shared(B, J, K, detail=True)
    # baseline: J against random sets of K's size from R; K against random sets of J's size from R
    rnd = random.Random(7070)
    rl = sorted(Rr)
    base_rows = defaultdict(list)
    for _ in range(20):
        S = set(rnd.sample(rl, min(len(K), len(rl))))
        s1 = shared(B, J, S)
        for k, v in s1.items():
            base_rows[f"J_vs_randomK.{k}"].append(v)
        T = set(rnd.sample(rl, min(len(J), len(rl))))
        s2 = shared(B, K, T)
        for k, v in s2.items():
            base_rows[f"K_vs_randomJ.{k}"].append(v)
    out["baseline"] = {k: dict(mean=round(sum(v) / len(v), 2), range=[min(v), max(v)]) for k, v in base_rows.items()}
    # citations from J / K into the 600's journals at all (how often does any article cite one of the other set's journals?)
    jr = Counter()
    for m in B["refs"]:
        p = B["vpub"].get(m["version_id"])
        t = B["best"].get(m["cited_work_pk"]) if m["cited_work_pk"] is not None else None
        if t is None or p is None:
            continue
        tj = (B["pubj"].get(t) or (None,))[0]
        sj = "J" if p in J else "K" if p in K else None
        if sj:
            jr[f"{sj}->{tj}"] += 1
    out["targets_by_journal"] = dict(jr.most_common(40))
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    show = {k: v for k, v in out.items() if k not in ("inside",)}
    print(json.dumps(show, ensure_ascii=False, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
