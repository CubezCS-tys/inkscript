"""Experiment 47: checks of platform_v2.db against experiment 46's platform.db (read only, attached).

- reconciliation: for every v46 table, its v2 counterpart's count and why the two differ (table reconciliation_v46);
  key columns compared with EXCEPT where a concept maps one to one (blocks, notes, fixes, misprints, works);
- 0 orphans on declared foreign keys (PRAGMA foreign_key_check), and how many keys are declared;
- the ibid. examples (0069-000-026-005 fn-p15-13, fn-p16-1, ...) and that no back reference points at another;
- citation_links holds no same-article row and no back reference;
- the 54 hand checks carried into reviews.

    .venv/bin/python experiments/47_platform_v2/checks47.py [--db DB]     # writes out/checks47.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common47 import DB, V46, connect  # noqa: E402

CUR = "version_id IN (SELECT version_id FROM versions WHERE is_current = 1)"
# v46 table, v2 table, v2 count query, why (when they differ; '' = must be equal)
REC = [
    ("articles", "documents", "SELECT count(*) FROM documents", ""),
    ("articles", "publications (with a file)", "SELECT count(DISTINCT pub_id) FROM documents", ""),
    ("article_runs", "versions", "SELECT count(*) FROM versions",
     "every (document, run) loaded; all versions keep their content now"),
    ("article_runs", "versions (shown)", "SELECT count(*) FROM versions WHERE is_current = 1",
     "v46 'current' = one per article"),
    ("runs", "runs", "SELECT count(*) FROM runs", ""),
    ("blocks", "blocks (shown versions)", f"SELECT count(*) FROM blocks WHERE {CUR}", ""),
    ("blocks", "blocks (all versions)", "SELECT count(*) FROM blocks", "v33_300 and the judged copy kept beside final"),
    ("blocks_fts", "search_units", "SELECT count(*) FROM search_units",
     "blocks plus figure descriptions, picture text, equations, verse lines and printed citations (shown versions)"),
    ("notes", "notes (shown)", f"SELECT count(*) FROM notes WHERE {CUR}", ""),
    ("note_calls", "note_calls (shown)", f"SELECT count(*) FROM note_calls WHERE {CUR}",
     "v46 counted calls from xref elements in shown articles; v2 counts each call with its place in the text"),
    ("note_calls", "note_calls with no target (shown)", f"SELECT count(*) FROM note_calls WHERE status <> 'ok' AND {CUR}",
     "v46 kept them with note_id NULL; v2 marks them no-target"),
    ("figures", "figures (shown)", f"SELECT count(*) FROM figures WHERE {CUR}", ""),
    ("figures (table cells)", "table_cells (shown)", f"SELECT count(*) FROM table_cells WHERE {CUR}",
     "new: every cell with row/col/spans (v46 kept only n_cells)"),
    ("fixes", "text_corrections azure-misread (shown)",
     f"SELECT count(*) FROM text_corrections WHERE layer = 'azure-misread' AND {CUR}", ""),
    ("misprints", "text_corrections misprint (shown)",
     f"SELECT count(*) FROM text_corrections WHERE layer = 'misprint' AND {CUR}", ""),
    ("metadata_changes", "metadata_assertions corrected (shown)",
     f"SELECT count(*) FROM metadata_assertions WHERE form = 'corrected' AND {CUR}", ""),
    ("works", "citation_mentions with a parsed citation (shown)",
     f"SELECT count(*) FROM citation_mentions WHERE parsed IS NOT NULL AND {CUR}", ""),
    ("works", "cited_works (active)", "SELECT count(*) FROM cited_works WHERE status = 'active'",
     "repeats inside an article and across articles become one card (v46: one 'work' per citing place)"),
    ("work_authors", "cited_work_authors", "SELECT count(*) FROM cited_work_authors",
     "authors per card, not per citing place"),
    ("back_references", "citation_mentions ibid/op_cit/loc_cit (shown)",
     f"SELECT count(*) FROM citation_mentions WHERE kind IN ('ibid', 'op_cit', 'loc_cit') AND {CUR}",
     "every marker of a note is its own mention (v46 kept the first per note) and a bare «السابق»/«نفسه» counts"),
    ("back_references", "  of which resolved to a first full citation",
     f"SELECT count(*) FROM citation_mentions WHERE kind IN ('ibid', 'op_cit', 'loc_cit') AND full_mention_pk IS NOT "
     f"NULL AND {CUR}", "v46 resolved 303 of 544"),
    ("back_references", "  of which part of a parsed citation (counted once)",
     f"SELECT count(*) FROM citation_mentions WHERE resolve_method = 'part-of-citation' AND {CUR}",
     "«Pincus: Economic Aid, op. cit.»: the marker belongs to the citation parsed just before it"),
    ("citation_links", "citation_links", "SELECT count(*) FROM citation_links",
     "real links only (accepted + title-only candidates); v46's 306 back-reference rows are resolutions in "
     "citation_mentions, its 301 review/about/part rows are work_relations; linked per card, not per citing place"),
    ("citation_links", "  accepted", "SELECT count(*) FROM citation_links WHERE status = 'accepted'",
     "v46: 109 confident work rows (89 records); v2 counts cards"),
    ("citation_links", "work_relations", "SELECT count(*) FROM work_relations",
     "is_reviewed_in / is_studied_in / is_part_of, by card"),
    ("link_checks", "reviews from link_checks", "SELECT count(*) FROM reviews WHERE source_file = 'link_checks'", ""),
    ("link_runs", "link_runs", "SELECT count(*) FROM link_runs", "one row per linker pass (v46: a timestamp per article)"),
    ("flags", "flags (all versions)", "SELECT count(*) FROM flags",
     "v33_300's flags.json has one flag of an article whose v33_300 master was never written (no version to hang it on)"),
    ("judge_findings", "judge_calls", "SELECT count(*) FROM judge_calls",
     "v46's 'none' rows (a clean page) are clean calls; every look is one call"),
    ("judge_findings", "judge_findings", "SELECT count(*) FROM judge_findings", "problems named only"),
    ("patches", "patches", "SELECT count(*) FROM patches",
     "key run|stem|patch_id: j-1677-p1-1 of two articles no longer collide (+1)"),
    ("keywords", "publication_keywords", "SELECT count(*) FROM publication_keywords",
     "one row per (publication, term, source): repeated terms collapse"),
    ("keywords", "keyword_terms", "SELECT count(*) FROM keyword_terms", "terms counted across the archive"),
    ("subjects", "record_subjects", "SELECT count(*) FROM record_subjects",
     "by 999$c, plus fields of study and databases as subjects; Arabic/English duplicates are one term"),
    ("abstracts", "abstracts", "SELECT count(*) FROM abstracts", "language detected, keyed by publication"),
    ("article_dates", "publication_dates", "SELECT count(*) FROM publication_dates",
     "plus a converted gregorian twin of each hijri date and the catalogue's issue year(s)"),
    ("article_authors", "byline_mentions (shown)", f"SELECT count(*) FROM byline_mentions WHERE {CUR}", ""),
    ("article_authors", "authorships", "SELECT count(*) FROM authorships",
     "a bilingual twin is one authorship with two mentions; catalogue-only contributors added"),
    ("affiliations", "affiliation_mentions (shown)",
     f"SELECT count(*) FROM affiliation_mentions am JOIN byline_mentions b USING (mention_pk) WHERE b.{CUR}", ""),
    ("people", "persons", "SELECT count(*) FROM persons",
     "authority ids + provisional persons per printed mention + cited authors found in the catalogue"),
    ("person_names", "person_names", "SELECT count(*) FROM person_names", "with Arabic name parts"),
    ("institutions", "institutions", "SELECT count(*) FROM institutions",
     "inst46 on the shown versions plus corporate bodies of the catalogue"),
    ("institution_variants", "institution_names", "SELECT count(*) FROM institution_names",
     "plus the catalogue headings of corporate contributors"),
    ("journals", "journals", "SELECT count(*) FROM journals", "plus journals of catalogued-only link targets"),
    ("issues", "issues", "SELECT count(*) FROM issues", "keyed J<code>/<vol>/<issue> from the stem"),
    ("catalogue_records", "catalogue_records", "SELECT count(*) FROM catalogue_records",
     "by 999$c: every record naming a loaded file plus every link / relation target"),
    ("catalogue_authors", "catalogue_contributors", "SELECT count(*) FROM catalogue_contributors",
     "contributors of every record held (link targets too)"),
    ("catalogue_disagreements", "catalogue_reports (print vs catalogue)",
     "SELECT count(*) FROM catalogue_reports WHERE kind NOT IN ('invalid-issn', 'stem-on-several-records')",
     "recomputed by load46.disagreements on the shown versions; v2 also reads the translated titles v46 missed"),
    ("catalogue_disagreements", "catalogue_reports (record-level)",
     "SELECT count(*) FROM catalogue_reports WHERE kind IN ('invalid-issn', 'stem-on-several-records')", "new"),
    ("meta", "load_events", "SELECT count(*) FROM load_events", "one row per load or link pass"),
]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB))
    a = ap.parse_args(argv)
    con = connect(Path(a.db))
    con.execute(f"ATTACH 'file:{V46}?mode=ro' AS o")
    out = {}
    rows = []
    for t46, t2, q, why in REC:
        base = t46.split(" ")[0]
        n46 = con.execute(f"SELECT count(*) FROM o.[{base}]").fetchone()[0] if base != "blocks_fts" else \
            con.execute("SELECT count(*) FROM o.blocks").fetchone()[0]
        n2 = con.execute(q).fetchone()[0]
        rows.append(dict(v46_table=t46, v46_rows=n46, v2_table=t2, v2_rows=n2, v2_query=q, same=int(n46 == n2),
                         why=why or ("equal" if n46 == n2 else "MUST BE EQUAL — not explained")))
    con.execute("DELETE FROM reconciliation_v46")
    for r in rows:
        con.execute("INSERT OR REPLACE INTO reconciliation_v46 VALUES (:v46_table, :v46_rows, :v2_table, :v2_rows, "
                    ":v2_query, :same, :why)", r)
    out["reconciliation"] = rows
    # key columns compared where the concept maps 1:1 (shown versions vs v46)
    sv = "JOIN versions v ON v.version_id = x.version_id AND v.is_current = 1"
    ex = {}
    for name, q2, q46 in (
            ("blocks (stem, block_id, text)", f"SELECT v.stem, x.block_id, x.text FROM blocks x {sv}",
             "SELECT stem, block_id, text FROM o.blocks"),
            ("notes (stem, note_id, text)", f"SELECT v.stem, x.note_id, x.text FROM notes x {sv}",
             "SELECT stem, note_id, text FROM o.notes"),
            ("fixes (stem, id, azure, print)", f"SELECT v.stem, x.xml_id, x.azure_reading, x.printed FROM "
             f"text_corrections x {sv} WHERE x.layer = 'azure-misread'",
             "SELECT stem, fix_id, azure_reading, print FROM o.fixes"),
            ("misprints (stem, id, printed, proposed)", f"SELECT v.stem, x.xml_id, x.printed, x.proposed FROM "
             f"text_corrections x {sv} WHERE x.layer = 'misprint'",
             "SELECT stem, sic_id, printed, proposed FROM o.misprints"),
            ("figures (stem, id, kind)", f"SELECT v.stem, x.figure_id, x.kind FROM figures x {sv} WHERE x.kind NOT LIKE "
             "'inline%'", "SELECT stem, xml_id, kind FROM o.figures WHERE kind NOT LIKE 'inline%'"),
            ("versions (stem, run) shown", "SELECT stem, run FROM versions WHERE is_current = 1",
             "SELECT stem, run FROM o.article_runs WHERE current = 1")):
        a_ = con.execute(f"SELECT count(*) FROM ({q2} EXCEPT {q46})").fetchone()[0]
        b_ = con.execute(f"SELECT count(*) FROM ({q46} EXCEPT {q2})").fetchone()[0]
        ex[name] = dict(only_v2=a_, only_v46=b_)
    out["key_columns_except"] = ex
    # foreign keys
    nfk = sum(len(con.execute(f"PRAGMA foreign_key_list([{t}])").fetchall()) for (t,) in con.execute(
        "SELECT name FROM main.sqlite_master WHERE type = 'table'"))
    orph = con.execute("PRAGMA main.foreign_key_check").fetchall()
    out["foreign_keys"] = dict(declared=nfk, orphans=len(orph),
                               tables=con.execute("SELECT count(*) FROM main.sqlite_master WHERE type = 'table' AND name "
                                                  "NOT LIKE 'search_fts_%' AND name NOT LIKE 'sqlite_%'").fetchone()[0],
                               views=con.execute("SELECT count(*) FROM main.sqlite_master WHERE type = 'view'").fetchone()[0])
    views_ok = {}
    for (v,) in con.execute("SELECT name FROM main.sqlite_master WHERE type = 'view'").fetchall():
        try:
            views_ok[v] = con.execute(f"SELECT count(*) FROM [{v}]").fetchone()[0]
        except Exception as e:
            views_ok[v] = f"ERROR {e}"
    out["views"] = views_ok
    # citations
    out["citation_links_same_article"] = con.execute(
        """SELECT count(*) FROM citation_links l JOIN cited_work_members w ON w.cited_work_pk = l.cited_work_pk
           JOIN citation_mentions c ON c.mention_pk = w.full_mention_pk JOIN versions v ON v.version_id = c.version_id
           JOIN documents d ON d.stem = v.stem WHERE d.pub_id = l.target_pub_id""").fetchone()[0]
    out["citation_links_from_backrefs"] = con.execute(
        "SELECT count(*) FROM citation_links l JOIN citation_mentions m ON m.mention_pk = l.via_mention_pk WHERE "
        "m.kind NOT IN ('full', 'short')").fetchone()[0]
    out["citation_links_non_publication"] = con.execute(
        "SELECT count(*) FROM citation_links WHERE target_kind <> 'publication' OR target_pub_id IS NULL").fetchone()[0]
    out["backref_to_backref"] = con.execute(
        "SELECT count(*) FROM citation_mentions m JOIN citation_mentions t ON t.mention_pk = m.full_mention_pk WHERE "
        "m.kind IN ('ibid', 'op_cit', 'loc_cit') AND t.kind IN ('ibid', 'op_cit', 'loc_cit')").fetchone()[0]
    out["backref_to_later_repeat"] = con.execute(
        """SELECT count(*) FROM citation_mentions m JOIN citation_mentions t ON t.mention_pk = m.full_mention_pk
           JOIN cited_work_members w ON w.full_mention_pk = t.mention_pk
           WHERE m.kind IN ('ibid', 'op_cit', 'loc_cit') AND w.method = 'in-article-repeat'""").fetchone()[0]
    ex_rows = con.execute(
        """SELECT v.stem, m.container_id AS note, m.kind, m.marker, m.printed, m.resolve_method, m.unresolved_why,
                  t.container_kind || ':' || t.container_id AS first_full_in, t.printed AS first_full_printed,
                  t.mention_id AS first_full_mention_id
           FROM citation_mentions m JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
           LEFT JOIN citation_mentions t ON t.mention_pk = m.full_mention_pk
           WHERE v.stem = '0069-000-026-005' AND m.container_id IN ('fn-p15-13', 'fn-p16-1', 'fn-p15-5', 'fn-p15-1',
                 'fn-p14-13', 'fn-p14-5') AND m.kind NOT IN ('full', 'quran') ORDER BY m.reading_ord""").fetchall()
    out["ibid_examples"] = [dict(r) for r in ex_rows]
    old = con.execute("""SELECT from_id, target_id, method FROM o.citation_links WHERE from_id IN
                         ('0069-000-026-005|fn-p15-13', '0069-000-026-005|fn-p16-1', '0069-000-026-005|fn-p15-5',
                          '0069-000-026-005|fn-p15-1', '0069-000-026-005|fn-p14-5')""").fetchall()
    out["ibid_examples_v46"] = [dict(r) for r in old]
    out["hand_checks"] = dict(con.execute("SELECT verdict, count(*) FROM reviews WHERE source_file = 'link_checks' "
                                          "GROUP BY 1").fetchall())
    out["hand_checks_attached"] = dict(con.execute(
        "SELECT substr(note, instr(note, 'attached: ') + 10), count(*) FROM reviews WHERE source_file = 'link_checks' "
        "GROUP BY 1").fetchall())
    out["hand_checks_v2_keys"] = con.execute("SELECT count(*) FROM reviews WHERE source_file = 'link_checks' AND "
                                             "subject_key NOT LIKE 'v46:%'").fetchone()[0]
    con.commit()
    (HERE / "out").mkdir(exist_ok=True)
    (HERE / "out" / "checks47.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        print(f"{r['v46_table']:<26} {r['v46_rows']:>7} -> {r['v2_table']:<52} {r['v2_rows']:>7}  "
              f"{'=' if r['same'] else '≠'} {r['why'][:90]}")
    print(json.dumps({k: v for k, v in out.items() if k not in ("reconciliation", "ibid_examples", "views")},
                     ensure_ascii=False, indent=1))
    bad = {k: v for k, v in views_ok.items() if isinstance(v, str)}
    print("views:", len(views_ok), "errors:", bad)


if __name__ == "__main__":
    main()
