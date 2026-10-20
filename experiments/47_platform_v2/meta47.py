"""Experiment 47: write metadata47.json for Datasette — the database's title and description, one plain description
per table (the @role line of schema47.sql) and per view, label columns, and canned queries for what only this
database can answer (the ink behind a value, «المرجع السابق» resolved, the corrections ledger, metadata as printed
vs corrected, trust, the cited-reference index with books, the Quran index, catalogue reports, Arabic search).

    python3 experiments/47_platform_v2/meta47.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE))
from schema_doc47 import parse_sql  # noqa: E402

INK = "'http://127.0.0.1:8003/diagram/ink.html?a=' || {a}"


def ink(a):
    return INK.format(a=a)


QUERIES = {
    "show_me_the_ink": dict(
        title="Show me the ink: any citation of an article, with its crop of the scan",
        description="Every citation mention of the shown version of one document, in reading order, with a link that "
                    "draws the page and the box of Azure's words it was read from.",
        sql=f"""SELECT m.reading_ord, m.container_id AS note, m.kind, m.marker, m.printed, m.cited_volume, m.cited_pages,
       t.printed AS counts_for_first_full_citation, m.resolve_method, m.unresolved_why, m.trust,
       a.anchor_key, {ink('m.anchor_pk')} AS ink
FROM citation_mentions m JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
LEFT JOIN citation_mentions t ON t.mention_pk = m.full_mention_pk
LEFT JOIN ink_anchors a ON a.anchor_pk = m.anchor_pk
WHERE v.stem = :stem ORDER BY m.reading_ord"""),
    "back_references_resolved": dict(
        title="«المرجع السابق» / «نفسه» / ibid. / op. cit. → the first full citation",
        description="Each back reference of an article and the first full citation of the work it counts for (chains "
                    "collapsed); unresolved ones say why.",
        sql=f"""SELECT m.container_id AS note, m.kind, m.marker, m.printed AS back_reference, m.resolve_method,
       m.resolve_score, m.unresolved_why, t.container_kind || ':' || t.container_id AS first_full_in,
       t.printed AS first_full_citation, w.cited_work_id, {ink('m.anchor_pk')} AS ink
FROM citation_mentions m JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1
LEFT JOIN citation_mentions t ON t.mention_pk = m.full_mention_pk
LEFT JOIN cited_work_members cm ON cm.full_mention_pk = m.full_mention_pk
LEFT JOIN cited_works w ON w.cited_work_pk = cm.cited_work_pk
WHERE v.stem = :stem AND m.kind IN ('ibid', 'op_cit', 'loc_cit', 'short') ORDER BY m.reading_ord"""),
    "most_cited_works": dict(
        title="Cited-reference index: most cited works, books included",
        description="Times cited per cited work: citing articles (the Web-of-Science headline) and every mention, "
                    "back references included; with the archive/catalogue record when one is linked.",
        sql="""SELECT w.cited_work_id, w.pub_type, w.title, w.first_author_key, w.year_printed, w.year_calendar,
       t.n_citing_pubs, t.n_mentions, t.n_full, t.n_backrefs, l.target_pub_id AS in_mandumah,
       (SELECT group_concat(relation || ' ' || object_pub_id, '; ') FROM work_relations r
        WHERE r.subject_cited_work_pk = w.cited_work_pk) AS relations
FROM v_times_cited t JOIN cited_works w USING (cited_work_pk)
LEFT JOIN citation_links l ON l.cited_work_pk = w.cited_work_pk AND l.status = 'accepted' AND l.best = 1
ORDER BY t.n_citing_pubs DESC, t.n_mentions DESC LIMIT 200"""),
    "corrections_ledger": dict(
        title="The corrections ledger: what Azure read, what the page says, what is proposed",
        description="Azure misreadings fixed in the text (Azure's reading and confidence kept) and suspected misprints "
                    "kept as printed with a proposed correction (D30), each on its ink.",
        sql=f"""SELECT v.stem, c.layer, c.xml_id, c.azure_reading, c.azure_wc, c.printed, c.proposed, c.why, c.block_id,
       c.anchor_method, {ink('c.anchor_pk')} AS ink
FROM text_corrections c JOIN versions v ON v.version_id = c.version_id AND v.is_current = 1
WHERE (:stem = '' OR v.stem = :stem) AND (:layer = '' OR c.layer = :layer)
ORDER BY v.stem, c.corr_pk LIMIT 1000"""),
    "metadata_as_printed_and_corrected": dict(
        title="Metadata as printed, as corrected (D33) and as catalogued",
        description="Every reading of every field of one publication; the chosen one is marked with the rule that "
                    "chose it.",
        sql=f"""SELECT a.field, a.form, a.value, a.is_chosen, a.chosen_rule, a.reason, a.rule, v.run,
       {ink('a.anchor_pk')} AS ink
FROM metadata_assertions a LEFT JOIN versions v ON v.version_id = a.version_id
WHERE a.pub_id = (SELECT pub_id FROM documents WHERE stem = :stem)
ORDER BY a.field, a.is_chosen DESC, a.form"""),
    "catalogue_reports_for_mandumah": dict(
        title="Catalogue reports for Mandumah (print vs catalogue, record problems)",
        description="Who is right, the evidence on the page, and the status of each report.",
        sql=f"""SELECT kind, field, stem, c999, catalogue_value, our_value, who_is_right, severity, evidence, note,
       status, {ink('anchor_pk')} AS ink
FROM catalogue_reports WHERE (:kind = '' OR kind = :kind) ORDER BY kind, stem LIMIT 1000"""),
    "catalogue_reports_summary": dict(
        title="Catalogue reports by kind and who is right",
        sql="SELECT kind, who_is_right, count(*) AS n FROM catalogue_reports GROUP BY 1, 2 ORDER BY 3 DESC"),
    "quran_index": dict(
        title="Quran citation index: each aya, how often and by how many documents",
        sql="""SELECT q.sura, a.sura_name_ar, q.aya_from, q.aya_to, q.n_places, q.n_documents
FROM v_quran_index q JOIN quran_ayat a ON a.sura = q.sura AND a.aya = q.aya_from
ORDER BY q.n_places DESC, q.sura, q.aya_from"""),
    "quran_places": dict(
        title="Every place the Quran is quoted or cited (with the ink)",
        sql=f"""SELECT v.stem, q.source_kind, q.method, q.sura, a.sura_name_ar, q.aya_from, q.aya_to, q.printed_ref,
       q.quoted_text, {ink('q.anchor_pk')} AS ink
FROM quran_citations q JOIN versions v ON v.version_id = q.version_id AND v.is_current = 1
LEFT JOIN quran_ayat a ON a.sura = q.sura AND a.aya = q.aya_from
WHERE (:sura = '' OR q.sura = cast(:sura AS INTEGER)) ORDER BY q.sura, q.aya_from LIMIT 1000"""),
    "search_arabic": dict(
        title="Search (folded, clitics stripped): blocks, figure texts, equations, verses, citations",
        description="Type the words as printed (hamza, ta marbuta, vowels and و/ب/ال are handled); each hit opens "
                    "its ink.",
        sql=f"""SELECT v.stem, u.unit_kind, u.unit_id, u.text, {ink('u.anchor_pk')} AS ink
FROM search_fts f JOIN search_units u ON u.uid = f.rowid JOIN versions v ON v.version_id = u.version_id
WHERE search_fts MATCH 'stemmed : ' || stem47(:q) ORDER BY rank LIMIT 200"""),
    "verse_search": dict(
        title="Verse index: vowelled verse lines, searched without vowels",
        sql=f"""SELECT v.stem, l.verse_id, l.text, l.poet_hint, {ink('l.anchor_pk')} AS ink
FROM verse_lines l JOIN versions v ON v.version_id = l.version_id AND v.is_current = 1
WHERE l.text_bare LIKE '%' || fold(:q) || '%' LIMIT 300"""),
    "least_trusted_blocks": dict(
        title="Least trusted text (trust from Azure confidence, fixes, flags, retries)",
        sql=f"""SELECT v.stem, b.block_id, b.role, b.trust, b.wc_min, b.n_fixes, b.n_flags, b.text_source,
       substr(b.text, 1, 160) AS text, {ink('b.anchor_pk')} AS ink
FROM blocks b JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1
WHERE b.trust IS NOT NULL ORDER BY b.trust, b.wc_min LIMIT 300"""),
    "author_self_citations": dict(
        title="True self-citation (the same person id cites their own work)",
        sql="""SELECT s.citing_pub_id, p.title_shown, s.person_id, pe.preferred_name_ar, w.title AS cited_work
FROM v_author_self_citations s JOIN publications p ON p.pub_id = s.citing_pub_id
JOIN persons pe ON pe.person_id = s.person_id JOIN cited_works w USING (cited_work_pk)"""),
    "person_by_name": dict(
        title="A person by any form of the name (Arabic or Latin), with authorships",
        sql="""SELECT pe.person_id, pe.status, pe.preferred_name_ar, pe.preferred_name_lat,
       (SELECT group_concat(authority_id) FROM person_authorities pa WHERE pa.person_id = pe.person_id) AS authority,
       a.pub_id, p.title_shown, a.role_code, a.method, a.score
FROM persons pe JOIN authorships a USING (person_id) JOIN publications p ON p.pub_id = a.pub_id
WHERE pe.person_id IN (SELECT person_id FROM person_names WHERE name_key LIKE '%' || replace(fold(:name), ' ', '') || '%')
ORDER BY pe.person_id"""),
    "versions_side_by_side": dict(
        title="One document read by every run: versions, why one is shown, cost, flags",
        sql="""SELECT v.version_id, v.run, r.kind, v.is_current, v.current_reason, v.complete, v.pages_covered, v.usd,
       (SELECT count(*) FROM blocks b WHERE b.version_id = v.version_id) AS blocks,
       (SELECT count(*) FROM text_corrections c WHERE c.version_id = v.version_id) AS corrections,
       (SELECT count(*) FROM flags f WHERE f.version_id = v.version_id) AS flags,
       (SELECT count(*) FROM citation_mentions m WHERE m.version_id = v.version_id) AS citation_mentions
FROM versions v JOIN runs r USING (run) WHERE v.stem = :stem ORDER BY v.version_id"""),
    "flags_on_the_ink": dict(
        title="Flags and judge findings of a document, each on its ink",
        sql=f"""SELECT 'flag' AS what, v.run, f.page, f.kind AS type, f.severity AS level, f.reason AS text, f.block_id,
       {ink('f.anchor_pk')} AS ink
FROM flags f JOIN versions v USING (version_id) WHERE v.stem = :stem
UNION ALL
SELECT 'judge', c.run, c.page, j.type, j.route, j.evidence, NULL, {ink('j.anchor_pk')}
FROM judge_findings j JOIN judge_calls c USING (call_id) WHERE c.stem = :stem ORDER BY 3"""),
    "reconciliation_with_v46": dict(
        title="Reconciliation with platform.db (experiment 46)",
        sql="SELECT * FROM reconciliation_v46"),
}

LABELS = {"publications": "title_shown", "persons": "preferred_name_ar", "cited_works": "title",
          "institutions": "inst_id", "journals": "code", "catalogue_records": "title", "versions": "version_key",
          "documents": "stem", "ink_anchors": "anchor_key", "citation_mentions": "printed", "byline_mentions": "printed",
          "runs": "run", "patches": "patch_id", "quran_ayat": "sura_name_ar", "actors": "name",
          "role_codes": "name_en", "languages": "name_en", "keyword_terms": "display", "subject_terms": "term_key",
          "issues": "issue_id", "publishers": "name", "judge_calls": "call_id", "affiliation_mentions": "printed",
          "authorships": "pub_id", "flag_detectors": "kind", "storage_roots": "root_id",
          "catalogue_exports": "export_id", "link_runs": "linker", "load_events": "tool",
          "metadata_assertions": "value", "judge_findings": "type", "notes": "label", "note_calls": "call_text"}


def main():
    text = (HERE / "schema47.sql").read_text(encoding="utf-8")
    tables = {}
    for group, ts in parse_sql(text):
        for name, role, notes in ts:
            d = dict(description=f"{role or ''} [{group.split(' — ')[0]}]")
            if name in LABELS:
                d["label_column"] = LABELS[name]
            if notes:
                d["columns"] = {k: v for k, v in notes.items()}
            tables[name] = d
    for m in re.finditer(r"((?:--[^\n]*\n)+)CREATE VIEW (\w+)", text):
        why = " ".join(l.lstrip("- ").strip() for l in m.group(1).splitlines())
        tables[m.group(2)] = dict(description=why)
    tables["search_fts"] = dict(description="FTS5 index over search_units (columns folded, stemmed); query it with "
                                            "MATCH 'stemmed : ' || stem47(:q) (plugin fold47)", hidden=False)
    tables["reconciliation_v46"] = dict(description="Builder report: each table of platform.db (experiment 46), its "
                                                    "v2 counterpart's count, and why they differ.")
    meta = dict(
        title="Mandumah platform v2 (experiment 47)",
        description_html=(
            "The scan is the bottom layer: every value points at Azure's words on the page (<code>ink_anchors</code>; "
            "open <code>ink</code> links to see the crop). Each run's reading of a document is its own "
            "<code>version</code>, side by side; one is shown. Printed values are never overwritten: corrections, "
            "misprints and D33 changes are readings beside the print. «المرجع السابق» resolves to the first full "
            "citation; <code>citation_links</code> holds real links only. "
            "Schema diagram: <a href='/diagram/schema47.html'>/diagram/schema47.html</a>. "
            "Built by experiments/47_platform_v2 (load47.py, link47.py) from the same sources as platform.db; "
            "read only."),
        databases={"platform_v2": dict(tables=tables, queries=QUERIES)})
    (HERE / "metadata47.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(tables), "tables/views described,", len(QUERIES), "canned queries")


if __name__ == "__main__":
    main()
