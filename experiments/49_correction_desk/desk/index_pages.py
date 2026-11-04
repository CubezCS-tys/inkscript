"""The index pages (the Web-of-Science face of the Desk, 2026-10-23): the Index overview, journals, institutions, an
author record (times cited, h-index), and the most-cited lists.

Every number is computed here from the state the Desk reads (the newest release copy, else platform_v2.db), opened
read-only, and every number goes out with its definition (`defs`), which the screens show on hover. Per-state
caches are keyed by the state file's path and mtime (`pages._cached`), so a new release is picked up at once.

Definitions used throughout (the same words are in `DEFS`):
- an *article* is a scanned document the pipeline has read (`documents`, one current version each);
- a *reference* is one place an article cites something (full citation, short form, ibid., op. cit.), Quran and
  hadith left out (`v_mention_work`, platform v2's own view);
- a *cited work* is a card that groups the full citations of one work (`cited_works`);
- *times cited* of a cited work = the distinct articles citing it (`v_times_cited.n_citing_pubs`);
- *times cited* of a Mandumah publication = the distinct articles whose references land on it through the linker's
  accepted best link (`citation_links`, the rows `v_pub_times_cited` counts);
- *h-index* = the largest h such that h items each have at least h times cited (Hirsch 2005).
Only the articles read so far can cite: every times cited is "cited by the articles read", not by the archive.
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import pages
from .pages import _cached, open_ro, times_cited
from .reading import Reading

E52 = Path(__file__).resolve().parents[2] / "52_journal_gate1"
GATE1_JOURNAL = "J0130"          # gate 1 (experiment 52): مجلة الطفولة العربية, read whole for 2010-2025
WHOLE_JOURNALS = {"J0130", "J0165"}   # journals read whole (gate 1; gate 2's pilot, experiment 70): never in the random pool

DEFS = dict(
    articles="Articles the pipeline has read: every word from the scan (or, for articles Mandumah holds only as the "
             "publisher's Word file, from that file), structure, metadata and references. 'final' ones went through "
             "the judge and the patches; 'structured' ones are an earlier run.",
    pages="Scanned pages of those articles.",
    words="Words read on those pages (every word keeps its box on the scan).",
    references="Places where an article cites something: full citations, short forms, ibid., op. cit. "
               "Quran and hadith citations are counted apart.",
    authors="Distinct persons who signed at least one of the articles read (byline or catalogue record).",
    institutions="Distinct universities, ministries and centres (organisation level) that an author's printed "
                 "affiliation names as a current post, after the librarian's decisions (experiment 64: one row per "
                 "body, both scripts joined). A degree-granting university (D37) and a former post (D38) are kept "
                 "but not counted.",
    journals="Distinct journals the articles read come from.",
    cited_works="Distinct works cited (books, articles, theses, ...), each the same whichever articles cite it, "
                "most of them not in Mandumah.",
    shared_works="Cited works that two or more of the articles read cite: the bridges between articles.",
    held="References whose cited work is linked to a publication Mandumah holds (its catalogue or its scans), by the "
         "linker or by the librarian's decisions (experiment 67: the work itself, or the same text in another "
         "journal, D44): the share of references a reader can follow into Mandumah.",
    article_links="References from one article read to another article read: the citation network inside the index.",
    times_cited_work="Distinct articles (of those read) citing this work.",
    times_cited_pub="Distinct articles (of those read) whose references land on this publication through an "
                    "accepted link.",
    h_index="The largest h such that h of the items each have at least h times cited (Hirsch). Computed on the "
            "articles read so far only, so small.",
    self_citations="Citing articles signed by the same person (shared person id) are self-citations.",
)


def h_index(counts) -> int:
    """Hirsch's h: the largest h such that h of the counts are each >= h."""
    h = 0
    for i, c in enumerate(sorted((int(x or 0) for x in counts), reverse=True), 1):
        if c >= i:
            h = i
        else:
            break
    return h


def _rows(con, sql, args=()):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def no_twins(con, alias: str) -> str:
    """Experiment 68: ' AND <alias>.twin_of_aff_pk IS NULL' when the reading has the column (experiment 65): an
    affiliation printed again in the other script is the same statement, so counts skip it ('' on older readings)."""
    cols = {r[1] for r in con.execute("PRAGMA table_info(affiliation_mentions)").fetchall()}
    return f" AND {alias}.twin_of_aff_pk IS NULL" if "twin_of_aff_pk" in cols else ""


# ------------------------------------------------------------------ per-state tables (cached)
def _base(path: Path) -> dict:
    """The small tables every page needs, read once per state."""
    def build():
        con = open_ro(path)
        try:
            pubs = {}
            for r in con.execute("""SELECT p.pub_id, p.journal_id, p.issue_id, p.year_shown, p.title_shown, p.status,
                                           p.doc_type, d.stem, d.scan_pages, d.level, v.run
                                    FROM publications p LEFT JOIN documents d ON d.pub_id = p.pub_id
                                    LEFT JOIN versions v ON v.stem = d.stem AND v.is_current = 1"""):
                pubs[r["pub_id"]] = dict(r)
            jname = {}
            for r in con.execute("SELECT journal_id, title, lang, form, is_chosen, n FROM journal_titles "
                                 "ORDER BY is_chosen DESC, (form = 'catalogue') DESC, n DESC"):
                jname.setdefault(r["journal_id"], r["title"])
            for r in con.execute("""SELECT j.journal_id, j.code FROM journals j WHERE NOT EXISTS
                                    (SELECT 1 FROM journal_titles t WHERE t.journal_id = j.journal_id)"""):
                if r[1].startswith("98"):       # Mandumah's thesis databases carry no title of their own
                    jname[r[0]] = f"Theses (Mandumah database {r[1]})"
            jen = {}
            for r in con.execute("SELECT journal_id, title FROM journal_titles WHERE form = 'catalogue-en' "
                                 "ORDER BY n DESC"):
                jen.setdefault(r["journal_id"], r["title"])
            iname = {}
            for r in con.execute("SELECT inst_id, name FROM institution_names "
                                 "ORDER BY (type = 'label') DESC, (script = 'Arab') DESC, n_seen DESC, name"):
                iname.setdefault(r["inst_id"], r["name"])
            inst = {r["inst_id"]: dict(r) for r in con.execute(
                "SELECT inst_id, kind, parent_id, country_code, city, status FROM institutions")}
            pname = {r[0]: r[1] or r[2] for r in con.execute(
                "SELECT person_id, preferred_name_ar, preferred_name_lat FROM persons")}
            # who signed what (read publications; catalogue-only rows included, as the Person page shows them)
            auth = defaultdict(set)          # pub_id -> person ids
            for r in con.execute("SELECT pub_id, person_id FROM authorships WHERE person_id IS NOT NULL"):
                auth[r[0]].add(r[1])
            cat_names = defaultdict(list)    # pub_id -> catalogue contributor names (for publications not read)
            for r in con.execute("""SELECT p.pub_id, cc.name FROM catalogue_contributors cc
                                    JOIN publications p ON p.c999 = cc.c999 WHERE cc.is_org = 0 OR cc.is_org IS NULL
                                    ORDER BY p.pub_id, cc.seq"""):
                if r[1]:
                    cat_names[r[0]].append(r[1])
            # every reference with its citing publication and its cited work
            refs = [tuple(r) for r in con.execute(
                "SELECT mention_pk, citing_pub_id, cited_work_pk, kind FROM v_mention_work")]
            best = {r[0]: r[1] for r in con.execute(
                "SELECT cited_work_pk, target_pub_id FROM citation_links WHERE status = 'accepted' AND best = 1 "
                "AND target_kind = 'publication'")}
            # affiliations of the current bylines, matched to institutions
            affs = _rows(con, """SELECT l.aff_pk, l.inst_id, l.level, d.pub_id, v.stem, am.printed,
                                        (SELECT a.person_id FROM authorship_mentions x JOIN authorships a
                                         ON a.authorship_pk = x.authorship_pk
                                         WHERE x.mention_pk = b.mention_pk LIMIT 1) person_id
                                 FROM affiliation_links l JOIN affiliation_mentions am ON am.aff_pk = l.aff_pk
                                 JOIN byline_mentions b ON b.mention_pk = am.mention_pk
                                 JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1
                                 JOIN documents d ON d.stem = v.stem WHERE 1 = 1""" + no_twins(con, "am"))
            cw = {r[0]: dict(id=r[1], title=r[2], pub_type=r[3], year=r[4]) for r in con.execute(
                "SELECT cited_work_pk, cited_work_id, title, pub_type, year_printed FROM cited_works "
                "WHERE status = 'active'")}
            cwa = defaultdict(list)
            for r in con.execute("SELECT cited_work_pk, printed FROM cited_work_authors ORDER BY cited_work_pk, seq"):
                cwa[r[0]].append(r[1])
        finally:
            con.close()
        cited_by = defaultdict(set)      # cited_work_pk -> citing pubs
        for _, citing, w, _k in refs:
            if w is not None:
                cited_by[w].add(citing)
        pub_cited_by = defaultdict(set)  # target pub -> citing pubs (accepted best links)
        pub_ment = Counter()
        for _, citing, w, _k in refs:
            t = best.get(w)
            if t:
                pub_cited_by[t].add(citing)
                pub_ment[t] += 1
        return dict(pubs=pubs, cat_names=cat_names, jname=jname, jen=jen, iname=iname, inst=inst, pname=pname, auth=auth, refs=refs,
                    best=best, affs=affs, cw=cw, cwa=cwa, cited_by=cited_by, pub_cited_by=pub_cited_by,
                    pub_ment=pub_ment)
    return _cached(path, "index_base", build)


def _pub_brief(B, pid: str) -> dict:
    p = B["pubs"].get(pid) or {}
    return dict(pub_id=pid, title=p.get("title_shown"), year=p.get("year_shown"), stem=p.get("stem"),
                journal_id=p.get("journal_id"), journal=B["jname"].get(p.get("journal_id")),
                read=bool(p.get("stem")), status=p.get("status"), doc_type=p.get("doc_type"),
                times_cited=len(B["pub_cited_by"].get(pid, ())))


def _work_brief(B, pk: int, n_cite: int | None = None) -> dict:
    w = B["cw"].get(pk) or {}
    t = B["best"].get(pk)
    return dict(id=w.get("id"), title=w.get("title"), pub_type=w.get("pub_type"), year=w.get("year"),
                authors=B["cwa"].get(pk, [])[:3], times_cited=n_cite if n_cite is not None else len(B["cited_by"].get(pk, ())),
                held_pub_id=t, held_stem=(B["pubs"].get(t) or {}).get("stem") if t else None)


def _org_affs(B, pub_ids: set | None = None):
    """((aff_pk, inst) -> link) for affiliations matched at organisation level as a current post. Every body a
    statement names counts (experiment 64: «جامعتى القاهرة وصنعاء» is Cairo and Sana'a, each with its own country);
    experiment 52 counted only the first, and gate 1 below still uses its measure unchanged."""
    out = {}
    for a in B["affs"]:
        if a["level"] == "org" and (pub_ids is None or a["pub_id"] in pub_ids):
            out.setdefault((a["aff_pk"], a["inst_id"]), a)
    return out


# ------------------------------------------------------------------ the Index overview
def gate1(path: Path) -> dict:
    """Gate 1 against random articles, measured now on the state the Desk reads, with experiment 52's own code
    (`measure52.measure`, imported read-only): the journal's 126, the random 600, and 20 random sets of 126 drawn
    from the 600 with experiment 52's seed."""
    def build():
        if str(E52) not in sys.path:
            sys.path.insert(0, str(E52))
        import measure52  # noqa: E402  (experiment 52's measure, unchanged)
        B = _base(path)
        jpubs = {p for p, x in B["pubs"].items() if x["stem"] and x["journal_id"] == GATE1_JOURNAL}
        rpubs = {p for p, x in B["pubs"].items() if x["stem"] and x["journal_id"] not in WHOLE_JOURNALS
                 and x["level"] == "final"}
        jruns = sorted({B["pubs"][p]["run"] for p in jpubs if B["pubs"][p]["run"]})
        rruns = sorted({B["pubs"][p]["run"] for p in rpubs if B["pubs"][p]["run"]})
        J = measure52.measure(str(path), jruns, {B["pubs"][p]["stem"] for p in jpubs})
        R = measure52.measure(str(path), rruns, {B["pubs"][p]["stem"] for p in rpubs})
        S = measure52.same_size(str(path), rruns, len(jpubs)) if len(rpubs) > len(jpubs) else None

        def links_inside(pubset, same_journal: bool):
            n, citing, cited = 0, set(), set()
            for _, c, w, _k in B["refs"]:
                if c in pubset and w is not None and w in B["best"]:
                    t = B["best"][w]
                    ok = ((B["pubs"].get(t) or {}).get("journal_id") == GATE1_JOURNAL) if same_journal else t in pubset
                    if ok:
                        n += 1
                        citing.add(c)
                        cited.add(t)
            return dict(links=n, citing=len(citing), cited=len(cited))

        def held(pubset):
            refs = [r for r in B["refs"] if r[1] in pubset]
            h = sum(1 for r in refs if r[2] is not None and r[2] in B["best"])
            return dict(references=len(refs), held=h, share=round(h / max(1, len(refs)), 4))
        rows = []

        def row(key, label, j, r, s=None, fmt="n", define=""):
            rows.append(dict(key=key, label=label, journal=j, random=r, random_same_size=s, fmt=fmt, define=define))
        jp, rp = J["people"], R["people"]
        ji, ri = J["institutions"], R["institutions"]
        jr, rr = J["references"], R["references"]
        m = (S or {}).get("mean", {})
        row("authors2", "Authors with 2+ articles", dict(n=jp["persons_2plus_articles"], of=jp["persons"]),
            dict(n=rp["persons_2plus_articles"], of=rp["persons"]), m.get("people.persons_2plus_articles"),
            define="Byline authors (person ids) who signed two or more articles of the set.")
        row("insts2", "Institutions in 2+ articles", dict(n=ji["institutions_2plus_articles"], of=ji["distinct_institutions"]),
            dict(n=ri["institutions_2plus_articles"], of=ri["distinct_institutions"]),
            m.get("institutions.institutions_2plus_articles"),
            define="Organisation-level institutions matched from printed affiliations, seen in two or more articles.")
        row("affshare", "Affiliations at an institution seen in 2+ articles", ji["share_affiliations_inst_2plus_articles"],
            ri["share_affiliations_inst_2plus_articles"], m.get("institutions.share_affiliations_inst_2plus_articles"),
            fmt="pct", define="Share of matched affiliations whose institution recurs in another article of the set.")
        row("refs", "References (Quran excluded)", jr["mentions_no_quran"], rr["mentions_no_quran"],
            m.get("references.mentions_no_quran"), define=DEFS["references"])
        row("shared", "Cited works shared by 2+ articles", jr["shared_2plus_articles"], rr["shared_2plus_articles"],
            m.get("references.shared_2plus_articles"), define="Cited-work cards that two or more articles of the set cite.")
        row("coupling", "Largest group joined by shared references", dict(n=jr["coupling_largest"], of=jr["of_articles_with_cards"]),
            dict(n=rr["coupling_largest"], of=rr["of_articles_with_cards"]), m.get("references.coupling_largest"),
            define="Articles linked to each other through at least one shared cited work (bibliographic coupling): "
                   "the size of the largest connected group, of the articles with references.")
        hj, hr = held(jpubs), held(rpubs)
        row("held", "References landing on a work Mandumah holds", hj["share"], hr["share"], None, fmt="pct",
            define=DEFS["held"] + " The linker's links and the librarian's applied links (experiment 67: those "
                                  "passing rule K1c, and D44); the librarian's other 217 links are still proposals.")
        ij, ir = links_inside(jpubs, True), links_inside(rpubs, False)
        row("inside", "Citations inside the set", dict(n=ij["links"], citing=ij["citing"], cited=ij["cited"]),
            dict(n=ir["links"], citing=ir["citing"], cited=ir["cited"]), None,
            define="For the journal: references from its articles to any article of the same journal Mandumah holds "
                   "(read or catalogued). For the random set: references from one of its articles to another.")
        return dict(journal_id=GATE1_JOURNAL, journal=B["jname"].get(GATE1_JOURNAL), n_journal=len(jpubs),
                    n_random=len(rpubs), draws=(S or {}).get("draws"), seed=(S or {}).get("seed"),
                    journal_runs=jruns, random_runs=rruns, rows=rows,
                    note="Measured now on the state the Desk reads with experiment 52's measure52.measure (same "
                         "definitions as its README); the random-126 column is the mean of 20 seeded draws from the "
                         "random set.")
    return _cached(path, "index_gate1", build)


def overview(path: Path) -> dict:
    def build():
        B = _base(path)
        con = open_ro(path)
        try:
            levels = dict(con.execute("SELECT level, count(*) FROM documents GROUP BY level").fetchall())
            pages_n, words = con.execute("SELECT count(*), sum(n_words) FROM pages p WHERE EXISTS "
                                         "(SELECT 1 FROM documents d WHERE d.stem = p.stem)").fetchone()
            quran = con.execute("""SELECT count(*) FROM citation_mentions m JOIN versions v ON v.version_id = m.version_id
                                   AND v.is_current = 1 WHERE m.kind IN ('quran', 'hadith')""").fetchone()[0]
        finally:
            con.close()
        read = {p for p, x in B["pubs"].items() if x["stem"]}
        refs = B["refs"]
        authors = set()
        for p in read:
            authors |= B["auth"].get(p, set())
        orgs = {a["inst_id"] for a in _org_affs(B, read).values()}
        tc = times_cited(path)
        held = [r for r in refs if r[2] is not None and r[2] in B["best"]]
        held_pubs = {B["best"][r[2]] for r in held}
        art_links = [r for r in held if B["best"][r[2]] in read]
        n_articles = sum(levels.values())
        nums = [
            dict(key="articles", label="Articles read", value=n_articles,
                 sub=f"{levels.get('final', 0):,} final · {levels.get('structured', 0):,} structured", define=DEFS["articles"]),
            dict(key="pages", label="Pages", value=pages_n, define=DEFS["pages"]),
            dict(key="words", label="Words", value=words, define=DEFS["words"]),
            dict(key="references", label="References", value=len(refs),
                 sub=f"{sum(1 for r in refs if r[3] == 'full'):,} full citations · {len({r[1] for r in refs}):,} articles carry them",
                 define=DEFS["references"] + f" Quran and hadith: {quran:,} more."),
            dict(key="authors", label="Authors", value=len(authors), define=DEFS["authors"]),
            dict(key="institutions", label="Institutions", value=len(orgs), define=DEFS["institutions"],
                 href="/institutions"),
            dict(key="journals", label="Journals", value=len({B["pubs"][p]["journal_id"] for p in read
                                                               if B["pubs"][p]["journal_id"]}),
                 sub=f"{len(WHOLE_JOURNALS)} read whole (gate 1 and gate 2's pilot) · the rest a random sample", define=DEFS["journals"], href="/journals"),
            dict(key="cited_works", label="Cited works", value=len({r[2] for r in refs if r[2] is not None}),
                 sub=f"{sum(1 for v in tc.values() if v[0] >= 2):,} cited by 2+ articles", define=DEFS["cited_works"],
                 href="/most-cited"),
            dict(key="held", label="References landing in Mandumah", value=round(100 * len(held) / max(1, len(refs)), 1),
                 unit="%", sub=f"{len(held):,} references → {len(held_pubs):,} Mandumah publications",
                 define=DEFS["held"]),
            dict(key="article_links", label="Links between articles read", value=len(art_links),
                 sub=f"{len({r[1] for r in art_links})} citing → {len({B['best'][r[2]] for r in art_links})} cited",
                 define=DEFS["article_links"] + " Mostly inside and between the two journals read whole; the 600 "
                                                "random articles were drawn from the whole archive and rarely cite "
                                                "each other."),
        ]
        top = sorted(((pk, v) for pk, v in tc.items() if pk in B["cw"]), key=lambda x: (-x[1][0], -x[1][1]))[:8]
        inst_arts = defaultdict(set)
        for a in _org_affs(B, read).values():
            inst_arts[a["inst_id"]].add(a["pub_id"])
        top_inst = sorted(inst_arts.items(), key=lambda kv: (-len(kv[1]), B["iname"].get(kv[0]) or ""))[:8]
        jcount = Counter(B["pubs"][p]["journal_id"] for p in read if B["pubs"][p]["journal_id"])
        return dict(numbers=nums, n_articles=n_articles, n_final=levels.get("final", 0),
                    top_works=[_work_brief(B, pk, v[0]) for pk, v in top],
                    top_institutions=[dict(inst_id=i, name=B["iname"].get(i), country=B["inst"].get(i, {}).get("country_code"),
                                           articles=len(s)) for i, s in top_inst],
                    top_journals=[dict(journal_id=j, title=B["jname"].get(j), articles=n) for j, n in jcount.most_common(5)],
                    defs=DEFS)
    return _cached(path, "index_overview", build)


# ------------------------------------------------------------------ journals
def journals(path: Path) -> list[dict]:
    B = _base(path)
    by = defaultdict(list)
    for p, x in B["pubs"].items():
        if x["stem"] and x["journal_id"]:
            by[x["journal_id"]].append(p)
    nref = Counter(B["pubs"][r[1]]["journal_id"] for r in B["refs"] if B["pubs"].get(r[1]))
    rec = Counter()
    for t, s in B["pub_cited_by"].items():
        j = (B["pubs"].get(t) or {}).get("journal_id")
        if j:
            rec[j] += len(s)
    out = []
    for j, ps in by.items():
        years = [B["pubs"][p]["year_shown"] for p in ps if B["pubs"][p]["year_shown"]]
        out.append(dict(journal_id=j, title=B["jname"].get(j), title_en=B["jen"].get(j), articles=len(ps),
                        first=min(years) if years else None, last=max(years) if years else None,
                        references=nref.get(j, 0), times_cited=rec.get(j, 0)))
    out.sort(key=lambda x: (-x["articles"], -x["times_cited"], x["title"] or ""))
    return out


def journal(path: Path, jid: str) -> dict | None:
    B = _base(path)
    con = open_ro(path)
    try:
        J = con.execute("SELECT * FROM journals WHERE journal_id = ?", (jid,)).fetchone()
        if not J:
            return None
        J = dict(J)
        titles = _rows(con, "SELECT title, lang, form, is_chosen FROM journal_titles WHERE journal_id = ? "
                            "ORDER BY is_chosen DESC, form", (jid,))
        issns = _rows(con, "SELECT issn, kind, valid_check FROM journal_issns WHERE journal_id = ?", (jid,))
        publishers = _rows(con, """SELECT pb.name, pb.name_en FROM journal_publishers jp
                                   JOIN publishers pb USING (publisher_id) WHERE jp.journal_id = ?""", (jid,))
        issues = _rows(con, """SELECT i.issue_id, i.volume_raw, i.issue_raw, i.issue_printed, i.year_greg, i.is_special
                               FROM issues i WHERE i.journal_id = ? ORDER BY i.year_greg, i.volume_num, i.issue_raw""",
                       (jid,))
        authors_of = defaultdict(list)
        for r in con.execute("""SELECT a.pub_id, a.person_id, a.position FROM authorships a
                                JOIN publications p ON p.pub_id = a.pub_id WHERE p.journal_id = ?
                                ORDER BY a.pub_id, a.position""", (jid,)):
            if r[1] and r[1] not in authors_of[r[0]]:
                authors_of[r[0]].append(r[1])
    finally:
        con.close()
    jpubs = [p for p, x in B["pubs"].items() if x["journal_id"] == jid]
    read = {p for p in jpubs if B["pubs"][p]["stem"]}
    # issues by year: what Mandumah holds in the platform for each issue, and how many of those are read
    held_in = Counter(B["pubs"][p]["issue_id"] for p in jpubs)
    read_in = Counter(B["pubs"][p]["issue_id"] for p in read)
    years = defaultdict(list)
    for i in issues:
        years[i["year_greg"]].append(dict(issue_id=i["issue_id"], label=i["issue_printed"] or f"{i['volume_raw']}/{i['issue_raw']}",
                                          special=bool(i["is_special"]), in_platform=held_in.get(i["issue_id"], 0),
                                          read=read_in.get(i["issue_id"], 0)))
    # references made by the journal's articles
    jrefs = [r for r in B["refs"] if r[1] in read]
    held = [r for r in jrefs if r[2] is not None and r[2] in B["best"]]
    cites_w = defaultdict(set)
    for r in jrefs:
        if r[2] is not None:
            cites_w[r[2]].add(r[1])
    most_cited_by_journal = sorted(((w, s) for w, s in cites_w.items() if w in B["cw"]),
                                   key=lambda x: (-len(x[1]), B["cw"][x[0]]["id"]))[:20]
    # citations received by the journal's publications (read or only catalogued), inside and outside the journal
    received = []
    inside_refs = outside_refs = 0
    inside_citing, outside_citing = set(), set()
    for p in jpubs:
        s = B["pub_cited_by"].get(p, set())
        if not s:
            continue
        ins = {c for c in s if (B["pubs"].get(c) or {}).get("journal_id") == jid}
        received.append(dict(_pub_brief(B, p), inside=len(ins), outside=len(s) - len(ins)))
        inside_citing |= ins
        outside_citing |= s - ins
    for _, c, w, _k in B["refs"]:
        t = B["best"].get(w) if w is not None else None
        if t and (B["pubs"].get(t) or {}).get("journal_id") == jid:
            if (B["pubs"].get(c) or {}).get("journal_id") == jid:
                inside_refs += 1
            else:
                outside_refs += 1
    received.sort(key=lambda x: (-x["times_cited"], -(x["year"] or 0)))
    # journals this journal cites, and journals citing it (through accepted links)
    cites_j, cited_by_j = Counter(), Counter()
    for _, c, w, _k in B["refs"]:
        t = B["best"].get(w) if w is not None else None
        if not t:
            continue
        cj, tj = (B["pubs"].get(c) or {}).get("journal_id"), (B["pubs"].get(t) or {}).get("journal_id")
        if cj == jid and tj:
            cites_j[tj] += 1
        if tj == jid and cj:
            cited_by_j[cj] += 1
    # authors and institutions of the read articles
    per_person = defaultdict(set)
    for p in read:
        for a in authors_of.get(p, []):
            per_person[a].add(p)
    authors2 = sorted(((a, s) for a, s in per_person.items() if len(s) >= 2), key=lambda x: (-len(x[1]), B["pname"].get(x[0]) or ""))
    inst_arts = defaultdict(set)
    for a in _org_affs(B, read).values():
        inst_arts[a["inst_id"]].add(a["pub_id"])
    countries = Counter(B["inst"].get(i, {}).get("country_code") or "not recorded" for i in inst_arts)
    # articles read, with their times cited
    arts = []
    nref = Counter(r[1] for r in jrefs)
    for p in read:
        x = B["pubs"][p]
        arts.append(dict(_pub_brief(B, p), issue_id=x["issue_id"], references=nref.get(p, 0),
                         authors=[dict(person_id=a, name=B["pname"].get(a)) for a in authors_of.get(p, [])]))
    arts.sort(key=lambda a: (-(a["year"] or 0), a["stem"] or ""))
    # the year chart
    chart = defaultdict(lambda: dict(read=0, references=0, cited=0))
    for a in arts:
        chart[a["year"]]["read"] += 1
        chart[a["year"]]["references"] += a["references"]
    for r in received:
        chart[r["year"]]["cited"] += r["times_cited"]
    tcs = [len(B["pub_cited_by"].get(p, ())) for p in jpubs]
    return dict(
        journal_id=jid, code=J["code"], country=J["country_code"], databases=J["databases"], first_year=J["first_year"],
        last_year=J["last_year"], title=B["jname"].get(jid), title_en=B["jen"].get(jid), titles=titles, issns=issns,
        publishers=publishers, is_gate1=jid == GATE1_JOURNAL, is_whole=jid in WHOLE_JOURNALS,
        whole_gate=("gate 1" if jid == GATE1_JOURNAL else "gate 2 pilot") if jid in WHOLE_JOURNALS else None,
        counts=dict(read=len(read), in_platform=len(jpubs),
                    word=sum(1 for p in read if (B["pubs"][p]["run"] or "").startswith("w")), platform_read=sum(1 for x in B["pubs"].values() if x["stem"]), issues=len(issues),
                    issues_read=sum(1 for i in issues if read_in.get(i["issue_id"])),
                    pages=sum(B["pubs"][p]["scan_pages"] or 0 for p in read),
                    authors=len(per_person), authors_2plus=len(authors2), institutions=len(inst_arts),
                    institutions_2plus=sum(1 for s in inst_arts.values() if len(s) >= 2),
                    references=len(jrefs), held=len(held), held_share=round(len(held) / max(1, len(jrefs)), 4),
                    cited_works=len(cites_w), shared_works=sum(1 for s in cites_w.values() if len(s) >= 2),
                    times_cited=sum(tcs), cited_pubs=sum(1 for t in tcs if t),
                    inside_refs=inside_refs, outside_refs=outside_refs,
                    inside_citing=len(inside_citing), outside_citing=len(outside_citing),
                    h_index=h_index(tcs)),
        years=[dict(year=y, issues=v) for y, v in sorted(years.items(), key=lambda kv: kv[0] or 0)],
        chart=[dict(year=y, **v) for y, v in sorted(chart.items(), key=lambda kv: kv[0] or 0) if y],
        articles=arts,
        authors_2plus=[dict(person_id=a, name=B["pname"].get(a), articles=len(s)) for a, s in authors2],
        institutions=[dict(inst_id=i, name=B["iname"].get(i), country=B["inst"].get(i, {}).get("country_code"),
                           articles=len(s)) for i, s in sorted(inst_arts.items(), key=lambda kv: (-len(kv[1]), B["iname"].get(kv[0]) or ""))[:25]],
        countries=countries.most_common(12),
        most_cited_works=[_work_brief(B, w, len(s)) for w, s in most_cited_by_journal],
        received=received[:60],
        cites_journals=[dict(journal_id=j, title=B["jname"].get(j), references=n, self=j == jid) for j, n in cites_j.most_common(10)],
        cited_by_journals=[dict(journal_id=j, title=B["jname"].get(j), references=n, self=j == jid) for j, n in cited_by_j.most_common(10)],
        defs=dict(DEFS, inside="References from this journal's own articles that land on one of its publications "
                               "(journal self-citation), through accepted links.",
                  outside="References from articles of other journals that land on one of this journal's publications.",
                  journal_h="h-index over all of this journal's publications Mandumah holds in the platform (read or "
                            "catalogued), by times cited from the articles read."))


# ------------------------------------------------------------------ institutions
def institutions(path: Path, limit: int = 200) -> list[dict]:
    B = _base(path)
    arts, people = defaultdict(set), defaultdict(set)
    for a in _org_affs(B).values():
        arts[a["inst_id"]].add(a["pub_id"])
        if a["person_id"]:
            people[a["inst_id"]].add(a["person_id"])
    out = []
    for i, s in arts.items():
        js = Counter(B["pubs"][p]["journal_id"] for p in s if B["pubs"].get(p))
        out.append(dict(inst_id=i, name=B["iname"].get(i), kind=B["inst"].get(i, {}).get("kind"),
                        country=B["inst"].get(i, {}).get("country_code"), articles=len(s), authors=len(people[i]),
                        journals=len(js), times_cited=sum(len(B["pub_cited_by"].get(p, ())) for p in s)))
    out.sort(key=lambda x: (-x["articles"], -x["authors"], x["name"] or ""))
    return out[:limit]


def institution(path: Path, iid: str) -> dict | None:
    B = _base(path)
    I = B["inst"].get(iid)
    if not I:
        return None
    con = open_ro(path)
    try:
        names = _rows(con, "SELECT name, lang, script, type, n_seen FROM institution_names WHERE inst_id = ? "
                           "ORDER BY n_seen DESC, name", (iid,))
        rel = _rows(con, "SELECT from_id, to_id, relation FROM institution_relations WHERE from_id = ? OR to_id = ?",
                    (iid, iid))
    finally:
        con.close()
    # D37 / D38: an "educated at" or a former post stays linked but is not this institution's output
    mine = [a for a in B["affs"] if a["inst_id"] == iid and a["level"] not in ("former", "educated_at")]
    aff_pks = {a["aff_pk"] for a in mine}
    pubs = {a["pub_id"] for a in mine}
    people = defaultdict(set)
    for a in mine:
        if a["person_id"]:
            people[a["person_id"]].add(a["pub_id"])
    sub = defaultdict(set)              # faculties / departments printed on the same affiliations
    for a in B["affs"]:
        if a["aff_pk"] in aff_pks and a["inst_id"] != iid:
            sub[a["inst_id"]].add(a["pub_id"])
    children = [i for i, x in B["inst"].items() if x["parent_id"] == iid]
    printed = Counter(a["printed"] for a in mine if a["printed"])
    tcs = {p: len(B["pub_cited_by"].get(p, ())) for p in pubs}
    years = Counter(B["pubs"][p]["year_shown"] for p in pubs if B["pubs"].get(p))
    js = Counter(B["pubs"][p]["journal_id"] for p in pubs if B["pubs"].get(p) and B["pubs"][p]["journal_id"])
    nref = Counter(r[1] for r in B["refs"] if r[1] in pubs)
    arts = []
    for p in pubs:
        b = _pub_brief(B, p)
        b["references"] = nref.get(p, 0)
        b["authors"] = [dict(person_id=x, name=B["pname"].get(x)) for x in sorted(B["auth"].get(p, ()))]
        arts.append(b)
    arts.sort(key=lambda a: (-(a["times_cited"] or 0), -(a["year"] or 0), a["stem"] or ""))
    parent = I["parent_id"]
    return dict(inst_id=iid, name=B["iname"].get(iid), kind=I["kind"], country=I["country_code"], city=I["city"],
                status=I["status"], names=names,
                parent=dict(inst_id=parent, name=B["iname"].get(parent)) if parent else None,
                children=[dict(inst_id=c, name=B["iname"].get(c), kind=B["inst"][c]["kind"]) for c in children],
                relations=rel,
                counts=dict(articles=len(pubs), authors=len(people), journals=len(js), references=sum(nref.values()),
                            times_cited=sum(tcs.values()), cited_articles=sum(1 for v in tcs.values() if v),
                            h_index=h_index(tcs.values())),
                articles=arts,
                authors=[dict(person_id=x, name=B["pname"].get(x), articles=len(s)) for x, s in
                         sorted(people.items(), key=lambda kv: (-len(kv[1]), B["pname"].get(kv[0]) or ""))],
                units=[dict(inst_id=i, name=B["iname"].get(i), kind=B["inst"].get(i, {}).get("kind"), articles=len(s))
                       for i, s in sorted(sub.items(), key=lambda kv: -len(kv[1]))],
                journals=[dict(journal_id=j, title=B["jname"].get(j), articles=n) for j, n in js.most_common()],
                years=sorted([dict(year=y, articles=n) for y, n in years.items() if y], key=lambda r: r["year"]),
                printed=[dict(text=t, n=n) for t, n in printed.most_common(8)],
                defs=dict(DEFS, inst_articles="Articles read with at least one author whose printed affiliation was "
                                              "matched to this institution."))


# ------------------------------------------------------------------ an author record
def person_record(path: Path, pid: str) -> dict | None:
    """Web of Science's author record: publications, times cited (with and without self-citations), h-index,
    citing articles, journals, years. The items are (a) the works cited under this person's name (cited-work
    authors matched to the person) and (b) publications they signed that the references reach through a link; a
    cited work that links to one of their publications counts once, as that publication."""
    B = _base(path)
    con = open_ro(path)
    try:
        R = Reading(con)
        rid, how = R.resolve_person(pid)
        if not rid:
            return None
        signed = {r[0] for r in con.execute("SELECT pub_id FROM authorships WHERE person_id = ?", (rid,))}
        auths = [r[0] for r in con.execute("SELECT authority_id FROM person_authorities WHERE person_id = ?", (rid,))]
        if auths:
            q = ",".join("?" * len(auths))
            signed |= {r[0] for r in con.execute(
                f"""SELECT p.pub_id FROM catalogue_contributors cc JOIN publications p ON p.c999 = cc.c999
                    WHERE cc.authority_id IN ({q})""", auths)}
        named = {r[0] for r in con.execute(
            """SELECT DISTINCT ca.cited_work_pk FROM cited_work_authors ca JOIN cited_works w
               ON w.cited_work_pk = ca.cited_work_pk WHERE ca.person_id = ? AND w.status = 'active'""", (rid,))}
    finally:
        con.close()
    items = {}                      # key -> dict(citing set, ...)
    for p in signed:
        s = B["pub_cited_by"].get(p, set())
        items[("pub", p)] = dict(kind="publication", **_pub_brief(B, p), citing=set(s))
    for w in named:
        t = B["best"].get(w)
        if t and ("pub", t) in items:
            continue                # counted as that publication (its citing set already includes this card's)
        if t:
            items[("pub", t)] = dict(kind="publication", **_pub_brief(B, t), citing=set(B["pub_cited_by"].get(t, ())))
            continue
        items[("work", w)] = dict(kind="cited work", **_work_brief(B, w), citing=set(B["cited_by"].get(w, ())))
    rows = []
    all_citing, self_citing = set(), set()
    for k, it in items.items():
        s = it.pop("citing")
        own = {c for c in s if rid in B["auth"].get(c, set())}
        it["times_cited"] = len(s)
        it["self_citations"] = len(own)
        it["signed"] = k[0] == "pub" and k[1] in signed
        all_citing |= s
        self_citing |= own
        rows.append(it)
    rows.sort(key=lambda x: (-x["times_cited"], -(x.get("year") or 0) if isinstance(x.get("year"), int) else 0,
                             x.get("title") or ""))
    read_signed = [p for p in signed if (B["pubs"].get(p) or {}).get("stem")]
    years = sorted(B["pubs"][p]["year_shown"] for p in signed if B["pubs"].get(p) and B["pubs"][p]["year_shown"])
    js = Counter(B["pubs"][p]["journal_id"] for p in signed if B["pubs"].get(p) and B["pubs"][p]["journal_id"])
    tcs = [r["times_cited"] for r in rows]
    return dict(person_id=rid, resolved_from=None if how == "live" else pid, name=B["pname"].get(rid),
                counts=dict(publications_signed=len(signed), articles_read=len(read_signed),
                            catalogued_only=len(signed) - len(read_signed), works_cited=sum(1 for t in tcs if t),
                            times_cited=sum(tcs), times_cited_no_self=sum(tcs) - sum(r["self_citations"] for r in rows),
                            citing_articles=len(all_citing), citing_articles_no_self=len(all_citing - self_citing),
                            h_index=h_index(tcs),
                            h_index_no_self=h_index(r["times_cited"] - r["self_citations"] for r in rows),
                            first_year=years[0] if years else None, last_year=years[-1] if years else None),
                journals=[dict(journal_id=j, title=B["jname"].get(j), n=n) for j, n in js.most_common(10)],
                items=[r for r in rows if r["times_cited"] or r.get("signed")][:100],
                defs=dict(DEFS, person_items="Works by this person: the works cited under their name (the cited "
                                             "work's author matched to this person) and the publications they signed; "
                                             "a cited work that links to one of their publications counts once.",
                          person_tc="Sum of times cited (as in Web of Science): for each of their works, the distinct articles read that cite it, added up. An article citing three of their works counts three times; Citing articles counts it once.",
                          citing_articles="Distinct articles read that cite at least one of the works."))


# ------------------------------------------------------------------ most cited
def most_cited(path: Path, kind: str = "works", limit: int = 100, journal_id: str | None = None) -> dict:
    B = _base(path)
    if kind == "pubs":
        ranked = sorted(B["pub_cited_by"].items(), key=lambda kv: (-len(kv[1]), -B["pub_ment"][kv[0]], kv[0]))
        out = []
        for p, s in ranked:
            if journal_id and (B["pubs"].get(p) or {}).get("journal_id") != journal_id:
                continue
            b = _pub_brief(B, p)
            b["mentions"] = B["pub_ment"][p]
            b["authors"] = ([B["pname"].get(x) for x in sorted(B["auth"].get(p, ()))] or B["cat_names"].get(p, []))[:3]
            out.append(b)
            if len(out) >= limit:
                break
        for i, b in enumerate(out, 1):
            b["rank"] = i
        return dict(kind="pubs", items=out, total=len(B["pub_cited_by"]),
                    total_read=sum(1 for p in B["pub_cited_by"] if (B["pubs"].get(p) or {}).get("stem")),
                    define=DEFS["times_cited_pub"])
    tc = times_cited(path)
    ranked = sorted(((pk, v) for pk, v in tc.items() if pk in B["cw"]),
                    key=lambda x: (-x[1][0], -x[1][1], B["cw"][x[0]]["id"]))[:limit]
    items = []
    for i, (pk, (npub, nm)) in enumerate(ranked, 1):
        b = _work_brief(B, pk, npub)
        b.update(rank=i, mentions=nm)
        items.append(b)
    return dict(kind="works", items=items, total=len(tc), cited_2plus=sum(1 for v in tc.values() if v[0] >= 2),
                define=DEFS["times_cited_work"] + " Ties are broken by mentions, «المرجع السابق» included.")
