"""Experiment 61: the corpus view of the per-article audits (out/articles/*.json) -> out/audit.json.

    leak table        by field and kind (mapping / not_asked / gemini_missed): lines, words, articles, by prompt
                      version, examples
    funnel            the main fields: printed / asked / returned / in JATS / in the platform, by prompt version
    answer drops      every answer key that does not reach its field, by status and reason
    bilingual         pairs printed in both scripts, stored both, linked
    platform          JATS elements against platform rows; platform columns never filled
    fix list          the mapping fixes (free, from saved answers) and the prompt additions, ranked by impact
    index             one row per article (for the Desk's article picker)
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from collections import Counter, defaultdict

from audit61 import ART, OUT, RELEASE, release

VERSIONS = ("v2", "v3.3", "v3.5b", "v3.6")   # v3.6: gate 2 pilot (experiment 70)
FIELD_LABEL = {
    "position": "author's post / rank", "affiliation": "affiliation", "author_name": "author name",
    "email": "e-mail", "honorific": "honorific / title before a name", "history_date": "history dates (received, accepted)",
    "abstract": "abstract", "keywords": "keywords", "article_doi": "the article's own DOI", "license": "licence / copyright",
    "journal_info": "journal / volume / issue line", "journal_section": "journal section (rubric)",
    "other": "unclassified «other» text", "unclassified": "unclassified text", "signature": "closing signature",
    "phone_address": "phone / postal address", "doi_url": "web address", "funding_ack": "funding / thanks",
    "author_id": "ORCID / researcher id", "corresp": "corresponding-author mark", "date": "a date",
    "title": "title", "trans_title": "translated title", "subtitle": "subtitle", "conference": "conference",
    "author_note": "author note", "not_placed_by_gemini": "line Gemini left out", "figure_text": "text in a figure",
}


STORED_FIELDS = {"position", "affiliation", "author_name", "email", "history_date", "abstract", "keywords", "title",
                 "trans_title", "subtitle", "journal_info", "author_id", "author_note", "conference", "role",
                 "table_note", "pub_date", "reviewed_work", "thesis", "original"}


def norm_key(k: str) -> str:
    k = re.sub(r"\[\d+\]", "[]", k)
    return re.sub(r"\[a=\d+\]", "[]", k)


def main():
    t0 = time.time()
    arts = []
    for f in sorted(ART.glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        arts.append(r)
    errors = [dict(stem=r["stem"], error=r["error"]) for r in arts if "error" in r]
    arts = [r for r in arts if "error" not in r]
    vers = lambda r: r["prompt"] if r["prompt"] in VERSIONS else "other"  # noqa: E731

    # ---------------------------------------------------------------- totals
    tot = {v: Counter() for v in VERSIONS + ("all",)}
    by_journal = defaultdict(Counter)
    for r in arts:
        for b, n in r["totals"]["lines"].items():
            tot[vers(r)][f"lines_{b}"] += n
            tot["all"][f"lines_{b}"] += n
            by_journal[r["journal"]][f"lines_{b}"] += n
        for b, n in r["totals"]["words"].items():
            tot[vers(r)][f"words_{b}"] += n
            tot["all"][f"words_{b}"] += n
            by_journal[r["journal"]][f"words_{b}"] += n
        tot[vers(r)]["articles"] += 1
        tot["all"]["articles"] += 1
        by_journal[r["journal"]]["articles"] += 1

    def shares(c):
        L = sum(c.get(f"lines_{b}", 0) for b in "abcd")
        W = sum(c.get(f"words_{b}", 0) for b in "abcd")
        return dict(articles=c.get("articles", 0), lines=L, words=W,
                    lines_by_bucket={b: c.get(f"lines_{b}", 0) for b in "abcd"},
                    words_by_bucket={b: c.get(f"words_{b}", 0) for b in "abcd"},
                    accounted_lines=round(100 * (c.get("lines_a", 0) + c.get("lines_c", 0)) / L, 3) if L else None,
                    accounted_words=round(100 * (c.get("words_a", 0) + c.get("words_c", 0)) / W, 3) if W else None)
    totals = {k: shares(v) for k, v in tot.items()}
    journals = {j: shares(c) for j, c in sorted(by_journal.items())}

    # ---------------------------------------------------------------- leak table
    rows = defaultdict(lambda: dict(lines=0, words=0, articles=set(), by_version=defaultdict(lambda: dict(
        lines=0, articles=set())), examples=[], by_bucket=Counter(), scripts=Counter(), platform_has=0))
    for r in arts:
        for lk in r["leaks"]:
            k = (lk["field"], lk["kind"])
            R = rows[k]
            R["lines"] += 1
            R["words"] += lk["words"]
            R["articles"].add(r["stem"])
            R["by_version"][vers(r)]["lines"] += 1
            R["by_version"][vers(r)]["articles"].add(r["stem"])
            R["by_bucket"][lk["bucket"]] += 1
            R["scripts"][lk["script"]] += 1
            R["platform_has"] += bool(lk.get("platform_field"))
            if len(R["examples"]) < 40:
                R["examples"].append(dict(stem=r["stem"], page=lk["page"], line=lk["id"], text=lk["text"],
                                          leak=lk["leak_text"], why=lk["why"], where=lk["where"], box=lk["box"],
                                          alto=lk["alto"], prompt=r["prompt"]))
    leak_table = []
    for (field, kind), R in rows.items():
        leak_table.append(dict(field=field, label=FIELD_LABEL.get(field, field), kind=kind, lines=R["lines"],
                               words=R["words"], articles=len(R["articles"]),
                               by_version={v: dict(lines=x["lines"], articles=len(x["articles"]))
                                           for v, x in R["by_version"].items()},
                               by_bucket=dict(R["by_bucket"]), scripts=dict(R["scripts"]),
                               platform_has=R["platform_has"], examples=R["examples"]))
    leak_table.sort(key=lambda x: (-x["articles"], -x["lines"]))

    # ---------------------------------------------------------------- answer accounting
    ans = defaultdict(lambda: defaultdict(lambda: dict(n=0, articles=set(), by_version=Counter(), examples=[],
                                                      reasons=Counter())))
    counts = defaultdict(lambda: [0, 0])
    works_r, works_d = Counter(), Counter()
    works_ex = defaultdict(list)
    for r in arts:
        A = r["answer"]
        for d in A["values"]:
            k = norm_key(d["key"])
            X = ans[k][d["status"]]
            X["n"] += 1
            X["articles"].add(r["stem"])
            X["by_version"][vers(r)] += 1
            if d.get("reason"):
                X["reasons"][d["reason"][:160]] += 1
            if len(X["examples"]) < 8 and d["status"] != "stored":
                X["examples"].append(dict(stem=r["stem"], value=d["value"][:160], where=d.get("where")))
        for k, (a, b) in A["counts"].items():
            counts[k][0] += a or 0
            counts[k][1] += b or 0
        works_r.update(A["works"]["returned"])
        works_d.update(A["works"]["dropped"])
        for k, v in A["works"]["examples"].items():
            if len(works_ex[k]) < 4:
                works_ex[k] += [dict(stem=r["stem"], value=x) for x in v[:2]]
    answer_rows = []
    for k, sts in ans.items():
        row = dict(key=k, total=sum(x["n"] for x in sts.values()))
        for st, X in sts.items():
            row[st] = dict(n=X["n"], articles=len(X["articles"]), by_version=dict(X["by_version"]),
                           reasons=dict(X["reasons"].most_common(3)), examples=X["examples"])
        row["lost"] = sum(sts[s]["n"] for s in ("dropped", "flattened") if s in sts)
        answer_rows.append(row)
    answer_rows.sort(key=lambda x: -x["lost"])
    works = sorted([dict(key=k, returned=n, dropped=works_d.get(k, 0), examples=works_ex.get(k, []))
                    for k, n in works_r.items()], key=lambda x: -x["dropped"])

    # ---------------------------------------------------------------- bilingual
    bil = defaultdict(lambda: defaultdict(Counter))
    for r in arts:
        for k, d in r["bilingual"].items():
            both = {"ar", "lat"} <= set(d["printed"])
            if not both:
                continue
            c = bil[k][vers(r)]
            c["printed_both"] += 1
            c["jats_both"] += {"ar", "lat"} <= set(d["jats"])
            c["linked"] += bool(d["linked"]) and {"ar", "lat"} <= set(d["jats"])
            c["platform_both"] += {"ar", "lat"} <= set(d["platform"])
            if k == "names":
                c["platform_linked"] += bool(d.get("platform_linked"))
    bilingual = {k: {v: dict(c) for v, c in vv.items()} for k, vv in bil.items()}
    for k, vv in bilingual.items():
        allc = Counter()
        for c in vv.values():
            allc.update(c)
        vv["all"] = dict(allc)

    # ---------------------------------------------------------------- platform
    plat = defaultdict(lambda: dict(jats=0, platform=0, articles_short=0, examples=[]))
    for r in arts:
        for k, (j, p) in r["platform"].items():
            P = plat[k]
            P["jats"] += j or 0
            P["platform"] += p or 0
            if (j or 0) > (p or 0):
                P["articles_short"] += 1
                if len(P["examples"]) < 5:
                    P["examples"].append(dict(stem=r["stem"], jats=j, platform=p))
    platform_rows = [dict(element=k, **v) for k, v in plat.items()]
    pl_container = Counter()
    for r in arts:
        pl_container.update(r.get("platform_leaks") or {})
    columns = never_filled()

    # ---------------------------------------------------------------- index
    index = []
    for r in arts:
        kinds = Counter(lk["kind"] for lk in r["leaks"])
        fields = Counter(lk["field"] for lk in r["leaks"])
        stored = Counter(L["field"] for L in r["lines"] if L["bucket"] == "a" and L["field"] in STORED_FIELDS)
        index.append(dict(stem=r["stem"], journal=r["journal"], prompt=vers(r), run=r["run"],
                          lines=r["totals"]["lines_all"], buckets=r["totals"]["lines"], leak_lines=len(r["leaks"]),
                          kinds=dict(kinds), top=fields.most_common(3),
                          leaks=dict(Counter(f"{lk['field']}|{lk['kind']}" for lk in r["leaks"])),
                          stored=dict(stored)))
    wrong_page = dict(words=sum(r.get("alto_wrong_page", 0) for r in arts),
                      articles=sorted(r["stem"] for r in arts if r.get("alto_wrong_page")))
    out = dict(made=time.strftime("%Y-%m-%d %H:%M"), release=str(RELEASE.name), n_articles=len(arts),
               alto_wrong_page=wrong_page,
               errors=errors, totals=totals, journals=journals, leak_table=leak_table, answers=answer_rows,
               answer_counts={k: v for k, v in counts.items()}, works=works, bilingual=bilingual,
               platform=platform_rows, platform_containers=dict(pl_container), columns=columns,
               fixes=fix_list(leak_table, answer_rows, bilingual, platform_rows), index=index)
    bt = [(r["stem"], lk) for r in arts for lk in r["leaks"] if lk["where"] == "byline_in_text"]
    for f in out["fixes"]:
        if f["id"] == "M4":
            f["evidence"] = dict(lines=len(bt), articles=len({s_ for s_, _ in bt}),
                                 kinds=dict(Counter(lk["kind"] for _, lk in bt)))
    (OUT / "audit.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"{len(arts)} articles ({len(errors)} errors) -> {OUT / 'audit.json'} in {time.time() - t0:.0f}s")


def never_filled() -> list[dict]:
    """Columns of the content tables that no current version fills (or fills rarely)."""
    con = release()
    cur = "(SELECT version_id FROM versions WHERE is_current = 1)"
    pubs = "(SELECT pub_id FROM documents)"
    tables = {"blocks": f"version_id IN {cur}", "notes": f"version_id IN {cur}", "figures": f"version_id IN {cur}",
              "byline_mentions": f"version_id IN {cur}", "page_marks": f"version_id IN {cur}",
              "figure_notes": f"version_id IN {cur}", "verse_lines": f"version_id IN {cur}",
              "citation_mentions": f"version_id IN {cur}", "text_corrections": f"version_id IN {cur}",
              "sections": f"version_id IN {cur}", "page_regions": f"version_id IN {cur}",
              "table_cells": f"version_id IN {cur}", "note_calls": f"version_id IN {cur}",
              "abstracts": f"version_id IN {cur}", "publication_keywords": f"version_id IN {cur}",
              "affiliation_mentions": f"mention_pk IN (SELECT mention_pk FROM byline_mentions WHERE version_id IN {cur})",
              "metadata_assertions": f"version_id IN {cur}", "publication_dates": f"pub_id IN {pubs}",
              "publications": f"pub_id IN {pubs}", "authorships": f"pub_id IN {pubs}"}
    out = []
    for t, where in tables.items():
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        n = con.execute(f"SELECT COUNT(*) FROM {t} WHERE {where}").fetchone()[0]
        if not n:
            continue
        sel = ", ".join(f"SUM({c} IS NOT NULL AND {c} != '')" for c in cols)
        got = con.execute(f"SELECT {sel} FROM {t} WHERE {where}").fetchone()
        for c, g in zip(cols, got):
            g = g or 0
            if g / n < 0.01:
                out.append(dict(table=t, column=c, rows=n, filled=g, share=round(100 * g / n, 2)))
    return out


def fix_list(leak_table, answer_rows, bilingual, platform_rows) -> list[dict]:
    """The fixes, ranked by the articles they touch. Files and functions were found by reading the code."""
    lt = defaultdict(lambda: dict(lines=0, articles=0, by_version={}))
    for r in leak_table:
        X = lt[(r["field"], r["kind"])]
        X["lines"] += r["lines"]
        X["articles"] += r["articles"]
        X["by_version"] = r["by_version"]
    ak = {r["key"]: r for r in answer_rows}

    def lost(k):
        r = ak.get(k) or {}
        return dict(values=r.get("lost", 0), articles=max(r.get(s, {}).get("articles", 0)
                                                           for s in ("dropped", "flattened")) if r else 0)
    F = [
        dict(id="M1", kind="mapping", title="Keep every author's post / rank as a field",
             what="Gemini returns the post («طالبة باحثة في علم الاجتماع», «PhD Student in Sociology», «أستاذ مساعد») "
                  "in authors[].role; the masters write <role> only for translators, reviewers, editors, supervisors "
                  "and rapporteurs, so an author's post survives only inside the generic front-matter block.",
             where="experiments/43_rehearsal/meta43.py names_pre (the `if kind:` branch: also write <role> "
                   "content-type=\"position\" when kind is None and the phrase is not an honorific); "
                   "experiments/47_platform_v2/parse47.py contrib_extras -> byline_mentions.role_phrase, and "
                   "affiliation_mentions.position_title from it",
             evidence=dict(answer=lost("metadata.authors[].role"),
                           lines=lt[("position", "mapping")])),
        dict(id="M2", kind="mapping", title="Keep the English (Latin) affiliation, e-mail and post of an author "
                                           "printed in two scripts",
             what="When the same person is printed in Arabic and in English, the code folds the English byline into "
                  "the Arabic person and copies its affiliation / e-mail only if the Arabic one has none. The "
                  "English affiliation (0130-018-072-003: «University of Mohamed V - Faculty of Education Sciences - "
                  "Morocco») is then only generic text.",
             where="experiments/43_rehearsal/meta43.py names_pre (Latin fold: `for e in la: if e.tag in (\"email\", "
                   "\"aff\") and ar.find(e.tag) is None`) and meta43.enrich (same_as: the same line) -> append the "
                   "twin's aff as a second <aff xml:lang=\"en\"> (and its role); parse47.affiliations_v35 then loads "
                   "it as a second affiliation_mentions row",
             evidence=dict(answer=lost("metadata.authors[].affiliation"),
                           lines=lt[("affiliation", "mapping")])),
        dict(id="M3", kind="mapping", title="Rebuild the 54 v2 articles with today's code",
             what="The current v2_55 masters were built before the abstract / keywords / history moves; their "
                  "abstracts, keywords lines and dates blocks sit in the body as generic paragraphs.",
             where="run masters43.build43 on out/v2_55/raw with today's rules (as lettersfix43.py plain does for the "
                   "v3.3 runs), then load47",
             evidence=dict(abstract=lt[("abstract", "mapping")], keywords=lt[("keywords", "mapping")])),
        dict(id="M4", kind="mapping", title="Bylines printed in the text (a closing signature, a second author block "
                                           "on page 2, a supervisor block)",
             what="A byline block outside the first page's front is kept as <p content-type=\"byline\">: its names, "
                  "posts and affiliations are not fields even when Gemini returned them in metadata.authors.",
             where="experiments/41_azure_structure/masters.py (body byline -> p content-type byline); "
                   "jats43.fill_slots could tag it as <sig-block> / <contrib> when its text matches an author",
             evidence=dict(lines=sum(r["lines"] for r in leak_table if r["kind"] == "mapping" and any(
                 e["where"] == "byline_in_text" for e in r["examples"][:40])))),
        dict(id="M5", kind="mapping", title="The subtitle as its own field",
             what="metadata.subtitle is returned but written only when it is not inside the printed title lines, so "
                  "it stays inside article-title.",
             where="experiments/41_azure_structure/masters.py Masters.front (`if sub_t and nows(sub_t) not in "
                   "printed`) -> keep the title lines, add <subtitle> as the value (or split article-title)",
             evidence=dict(answer=lost("metadata.subtitle"))),
        dict(id="M6", kind="mapping", title="Keep the honorific / title printed before a name",
             what="When Gemini returns «أ.د.», «الدكتور», «الأستاذ» in role instead of the name, the honorific is "
                  "neither in the name nor in its printed form (name-alternatives printed-on-the-page).",
             where="meta43.names_pre: when the role phrase is only an honorific (HONORIFIC), add it back to the "
                   "printed string-name; parse47 then fills byline_mentions.titles",
             evidence=dict(lines=lt[("honorific", "mapping")])),
        dict(id="M7", kind="mapping", title="Parsed reference parts dropped where the print breaks a word",
             what="refs43 keeps a part only if it is an exact substring of the entry, but the masters join a word "
                  "hyphenated over a line break («Psychol- ogy» -> «Psychology»), so Gemini's exact copy no longer "
                  "matches and the part is dropped.",
             where="experiments/43_rehearsal/refs43.py citation() ok(): compare with the de-hyphenated text too",
             evidence=dict(note="see works[] in audit.json: parts returned vs not in any element-citation")),
        dict(id="P1", kind="prompt", title="Ask for each author's post / rank as its own value",
             what="No prompt version names the post (أستاذ مساعد، طالب دكتوراه، Professor). Gemini puts it in "
                  "role (dropped, M1) or inside the affiliation string. Ask authors[].position (exact substring); "
                  "M1 alone saves what is already returned, P1 makes it reliable.",
             where="prompt43.py META_FULL (authors[].position) -> meta43 <role content-type=position>",
             evidence=dict(lines=lt[("position", "not_asked")], also_mapping=lt[("position", "mapping")])),
        dict(id="P2", kind="prompt", title="Ask for the article's own DOI, the licence / copyright line and the "
                                           "journal's section (rubric)",
             what="Printed «Doi: 10.29343/1-79-4» (0130 prints one on every article since 2018), «CC BY 4.0 ... "
                  "licence» and the rubric over the title («البحوث والدراسات»، «المقالات»، «تقارير») are typed "
                  "«other» and kept only as generic paragraphs.",
             where="prompt43.py META_FULL: \"doi\", \"license\" (line ids), \"section\" -> jats43 "
                   "article-id[@pub-id-type=doi], permissions/license, article-categories subj-group "
                   "[@subj-group-type=heading]",
             evidence=dict(doi=lt[("article_doi", "not_asked")], license=lt[("license", "not_asked")],
                           section=lt[("journal_section", "not_asked")])),
        dict(id="P3", kind="prompt", title="Bylines printed away from the title: ask for every author block "
                                           "and closing signature as authors",
             what="Second-language bylines at the end (English summary page), signatures with place and date, "
                  "author notes «أستاذ بالمعهد...». v3.5b asks for them only as byline blocks.",
             where="prompt43.py META_FULL authors: \"every printing of an author anywhere in the article\"; "
                   "M4 for the code side",
             evidence=dict(signature=lt[("signature", "mapping")], names=lt[("author_name", "mapping")])),
        dict(id="P4", kind="prompt", title="v3.3 -> v3.5b already covers: table notes and sources, corresponding "
                                           "author, ORCID, conference / book-review details",
             what="These leak only in v3.3 articles (not asked there). Gate 2 runs v3.5b, which asks for them; one "
                  "v3.5b article (0130-027-105-003) still lost three ORCIDs and a corresponding-author mark printed "
                  "on its English summary page (P3).",
             where="nothing to add; keep v3.5b",
             evidence=dict(table_note=lt[("table_note", "not_asked")], orcid=lt[("author_id", "gemini_missed")])),
    ]
    return F


if __name__ == "__main__":
    main()
