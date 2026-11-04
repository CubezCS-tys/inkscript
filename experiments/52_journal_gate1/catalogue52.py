"""Experiment 52: the journal's cited works against Mandumah's catalogue, by experiment 48 probe A's own code
(classify.py, match.py, decide.py, imported unchanged) pointed at gate1.db (read-only) and marc.db (read-only).
Also the citations inside the journal: references whose accepted target (probe A's accept, or link47's accepted
link) is a record of the same journal (journal_code 0130), and those whose printed source names the journal.

    .venv/bin/python experiments/52_journal_gate1/catalogue52.py extract|match|decide|results [--db gate1.db] [--run j0130_final]
        -> out/catalogue/{works,classified,matches,decisions}.jsonl, out/catalogue/results.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PA = HERE.parent / "48_linking_probe" / "a_cited_to_catalogue"
OUT = HERE / "out" / "catalogue"
DB = "/home/appuser/data/platform_v2/gate1.db"
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
sys.path.insert(0, str(PA))
sys.path.insert(0, str(HERE.parent / "45_marc_db"))
import q as Q  # noqa: E402

JOURNAL = "0130"


def setup(db):
    Q.P = db                                   # q.pv() opens P read-only: every probe module reads gate1.db


def versions(con, run):
    return {r[0]: r[1] for r in con.execute("SELECT version_id, stem FROM versions WHERE is_current = 1 AND run = ?", (run,))}


def cmd_extract(a):
    """extract.py's dump, for the cards that hold a mention of the journal's articles; members and mention counts
    of the journal only."""
    con = Q.pv()
    con.row_factory = sqlite3.Row
    V = versions(con, a.run)
    nm = collections.defaultdict(lambda: [0, set(), 0])
    for r in con.execute("SELECT version_id, citing_pub_id, kind, cited_work_pk FROM v_mention_work WHERE cited_work_pk IS NOT NULL"):
        if r[0] in V:
            x = nm[r[3]]
            x[0] += 1
            x[1].add(r[1])
            x[2] += r[2] == "full"
    authors = collections.defaultdict(list)
    for r in con.execute("select cited_work_pk, seq, printed, latin, authority_id from cited_work_authors order by 1,2"):
        authors[r[0]].append(dict(printed=r[2], latin=r[3], authority_id=r[4]))
    members = collections.defaultdict(list)
    for r in con.execute("""select m.cited_work_pk, c.mention_pk, c.mention_id, v.stem, c.page, c.container_kind, c.container_id,
            c.printed, c.parsed, v.version_id from cited_work_members m join citation_mentions c on c.mention_pk=m.full_mention_pk
            join versions v using(version_id) where v.is_current=1 order by c.mention_id"""):
        if r[9] in V:
            members[r[0]].append(dict(mention_pk=r[1], mention_id=r[2], stem=r[3], page=r[4], container_kind=r[5],
                                      container_id=r[6], printed=r[7], parsed=json.loads(r[8]) if r[8] else None))
    links = collections.defaultdict(list)
    for r in con.execute("""select l.cited_work_pk, l.status, l.best, l.score, l.method, l.target_pub_id, p.c999
            from citation_links l left join publications p on p.pub_id=l.target_pub_id"""):
        links[r[0]].append(dict(status=r[1], best=r[2], score=r[3], method=r[4], target_pub_id=r[5], c999=r[6]))
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(OUT / "works.jsonl", "w", encoding="utf-8") as f:
        for r in con.execute("select * from cited_works where status='active'"):
            d = dict(r)
            pk = d["cited_work_pk"]
            if pk not in nm:
                continue
            d["n_mentions"], d["n_citing"], d["n_full"] = nm[pk][0], len(nm[pk][1]), nm[pk][2]
            d["authors"], d["members"], d["links47"] = authors[pk], members[pk], links[pk]
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            n += 1
    print(n, "works;", sum(x[0] for x in nm.values()), "mentions on cards")


def cmd_classify(a):
    import classify as CL
    with open(OUT / "classified.jsonl", "w", encoding="utf-8") as f:
        for line in open(OUT / "works.jsonl", encoding="utf-8"):
            w = json.loads(line)
            k, why = CL.classify(w)
            f.write(json.dumps(dict(cited_work_pk=w["cited_work_pk"], cls=k, why=why, lang=w["lang"], pub_type=w["pub_type"],
                                    n_mentions=w["n_mentions"]), ensure_ascii=False) + "\n")


def cmd_match(a):
    import match as MA                         # name_token_freq.json is read from probe A's folder, as it was built
    MA.OUT = str(OUT) + "/"
    MA.main()


def cmd_decide(a):
    import decide as DE
    DE.OUT = str(OUT) + "/"
    DE.main()


def cmd_results(a):
    con = Q.pv()
    V = versions(con, a.run)
    W = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT / "works.jsonl", encoding="utf-8")}
    CLS = {r["cited_work_pk"]: r for r in map(json.loads, open(OUT / "classified.jsonl", encoding="utf-8"))}
    DEC = {r["cited_work_pk"]: r for r in map(json.loads, open(OUT / "decisions.jsonl", encoding="utf-8"))}
    total = sum(1 for (vid, kind) in con.execute("SELECT version_id, kind FROM citation_mentions WHERE kind NOT IN ('quran','hadith')")
                if vid in V)
    m = sqlite3.connect(MARC, uri=True)
    rec_j = {}

    def rec_of(c999):
        if c999 not in rec_j:
            r = m.execute("SELECT journal_code, year_int, title, type FROM records WHERE c999 = ?", (c999,)).fetchone()
            rec_j[c999] = r
        return rec_j[c999]
    stem_c999 = {r[0]: r[1] for r in con.execute("SELECT d.stem, p.c999 FROM documents d JOIN publications p USING (pub_id)")}
    ours = {stem_c999.get(s) for s in V.values()}
    all195 = json.loads((HERE / "out" / "sample52_all.json").read_text())["articles"]
    c195 = {}
    for x in all195:
        r = m.execute("SELECT c999 FROM records WHERE rec = ?", (x["rec"],)).fetchone()
        if r:
            c195[r[0]] = x["stem"]
    # accepted links: probe A (this run of it) and link47's own accepted best link
    acc = {pk: d["c999"] for pk, d in DEC.items() if d["decision"] == "accept" and d["c999"]}
    l47 = {}
    for pk, w in W.items():
        for L in w["links47"]:
            if L["status"] == "accepted" and L["best"] and L["c999"]:
                l47[pk] = L["c999"]
    union = dict(l47)
    union.update(acc)
    ment = {pk: w["n_mentions"] for pk, w in W.items()}
    R = dict(db=a.db, run=a.run, articles=len(V), mentions_no_quran=total, works=len(W),
             mentions_on_cards=sum(ment.values()))
    R["type_works"] = dict(collections.Counter(CLS[pk]["cls"] for pk in W).most_common())
    tm = collections.Counter()
    for pk in W:
        tm[CLS[pk]["cls"]] += ment[pk]
    R["type_mentions"] = dict(tm.most_common())
    R["decisions"] = dict(collections.Counter(d["decision"] for d in DEC.values()))
    R["accept_by_type"] = dict(collections.Counter(DEC[pk]["cls"] for pk in acc))
    R["held"] = dict(
        works_accept=len(acc), mentions_accept=sum(ment[pk] for pk in acc),
        share_mentions_accept=round(sum(ment[pk] for pk in acc) / max(1, total), 4),
        works_union_link47=len(union), mentions_union=sum(ment[pk] for pk in union),
        share_mentions_union=round(sum(ment[pk] for pk in union) / max(1, total), 4))
    from classify import CATALOGUE_TYPES
    ar = [pk for pk in W if CLS[pk]["cls"] in CATALOGUE_TYPES and W[pk]["lang"] == "ara"]
    la = [pk for pk in W if CLS[pk]["cls"] in CATALOGUE_TYPES and W[pk]["lang"] != "ara"]
    R["arabic_script_catalogue_types"] = dict(works=len(ar), accepted=sum(pk in acc for pk in ar),
                                              share=round(sum(pk in acc for pk in ar) / max(1, len(ar)), 3))
    R["latin_script_catalogue_types"] = dict(works=len(la), accepted=sum(pk in acc for pk in la))
    # inside the journal
    inside = []
    for pk, c999 in union.items():
        r = rec_of(c999)
        if r and r[0] == JOURNAL:
            for mem in W[pk]["members"]:
                inside.append(dict(cited_work_pk=pk, citing_stem=mem["stem"], target_c999=c999, target_year=r[1],
                                   target_title=r[2], target_type=r[3], target_stem=c195.get(c999),
                                   target_in_run=c999 in ours, via="probe A" if pk in acc else "link47",
                                   printed=(mem["printed"] or "")[:300]))
    pairs = {(x["citing_stem"], x["target_c999"]) for x in inside}
    R["inside_journal"] = dict(
        mentions=len(inside), links=len(pairs), citing_articles=len({p[0] for p in pairs}),
        cited_records=len({p[1] for p in pairs}),
        cited_records_in_run=len({p[1] for p in pairs if p[1] in ours}),
        cited_records_in_bucket195=len({p[1] for p in pairs if p[1] in c195}),
        links_to_run=len({p for p in pairs if p[1] in ours}))
    # the printed source names the journal (whether or not the article is linked)
    pat = re.compile(r"الطفولة العربية|Arab Childhood|Arabic Childhood", re.I)
    named = []
    for pk, w in W.items():
        for mem in w["members"]:
            p = mem["parsed"] or {}
            if pat.search(p.get("source_title") or "") or pat.search(mem["printed"] or ""):
                named.append(dict(cited_work_pk=pk, citing_stem=mem["stem"], linked=union.get(pk),
                                  linked_inside=bool(union.get(pk) and (rec_of(union[pk]) or [None])[0] == JOURNAL),
                                  printed=(mem["printed"] or "")[:300]))
    R["names_the_journal"] = dict(mentions=len(named), citing_articles=len({x["citing_stem"] for x in named}),
                                  linked_inside=sum(x["linked_inside"] for x in named))
    (OUT / "inside.json").write_text(json.dumps(dict(linked=inside, named=named), ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(R, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["extract", "classify", "match", "decide", "results"])
    ap.add_argument("--db", default=DB)
    ap.add_argument("--run", default="j0130_final")
    a = ap.parse_args()
    setup(a.db)
    {"extract": cmd_extract, "classify": cmd_classify, "match": cmd_match, "decide": cmd_decide,
     "results": cmd_results}[a.cmd](a)


if __name__ == "__main__":
    main()
