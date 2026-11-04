"""The Explorer (owner, 2026-10-23: "centralise everything ... being able to see and order all fields").

One flat table per thing we hold (articles, the references each article makes, authors, institutions, journals,
cited works), with every field we keep for it as a column. The tables are built once per state (the newest release
copy on disk, else platform_v2.db, always opened read-only) into an in-memory SQLite database, so sorting, filtering,
grouping and paging 14k references take milliseconds. A new release is picked up at once (the cache is keyed by the
state's path and mtime).

Safety: a request names columns, operators and an entity; each is looked up in the lists below and refused (422) if
unknown. Only names from these lists are ever written into SQL; every value travels as a bound parameter.

Where each field lives (experiment 51's inventory, `out/homes.json` -> platform_where, and schema47.sql) is carried
on every column as `src`, so the column chooser can say it."""
from __future__ import annotations

import csv
import functools
import io
import json
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

from .pages import fold

# ------------------------------------------------------------------ the columns
# (name, sql expression over the entity's FROM, type, group, label, where it lives, ref)
# type: text | id | int | real | year | date ; ref: what an id points to (article, work, person, journal,
# institution, mention), for the screens' links.


def _c(name, expr, typ="text", group="", label="", src="", ref=None):
    return dict(name=name, expr=expr, type=typ, group=group, label=label or name.replace("_", " "), src=src, ref=ref)


def _meta(field, form, name, label, group, typ="text"):
    """A metadata_assertions value, pivoted: form 'chosen' = the shown value, 'printed' = this version's reading,
    'corrected' = a correction (D33 or a person's), otherwise that form."""
    cond = {"chosen": "m.is_chosen = 1",
            "printed": "m.form = 'printed' AND m.version_id = c.version_id",
            "corrected": "m.form IN ('corrected', 'person')"}.get(form, f"m.form = '{form}'")
    return (name, f"max(CASE WHEN m.field = '{field}' AND {cond} THEN m.value END)", typ, group, label,
            f"metadata_assertions field {field}, form {form}")


META = [
    _meta("title", "printed", "title_printed", "Title as printed", "Title"),
    _meta("title", "corrected", "title_corrected", "Title corrected", "Title"),
    _meta("title", "catalogue", "title_catalogue", "Title in the catalogue", "Title"),
    _meta("title", "gemini-title", "title_gemini", "Title read by Gemini (old)", "Title"),
    _meta("subtitle", "chosen", "subtitle", "Subtitle", "Title"),
    _meta("subtitle", "catalogue", "subtitle_catalogue", "Subtitle in the catalogue", "Title"),
    _meta("title_translated", "chosen", "title_translated", "Translated title", "Title"),
    _meta("title_translated", "printed", "title_translated_printed", "Translated title as printed", "Title"),
    _meta("title_translated", "catalogue", "title_translated_catalogue", "Translated title in the catalogue", "Title"),
    _meta("year", "printed", "year_printed", "Year as printed", "Publication"),
    _meta("year", "corrected", "year_corrected", "Year corrected", "Publication"),
    _meta("year", "catalogue", "year_catalogue", "Year in the catalogue", "Publication"),
    _meta("year_hijri", "chosen", "year_hijri_meta", "Hijri year", "Publication"),
    _meta("volume", "chosen", "volume", "Volume", "Publication"),
    _meta("volume", "printed", "volume_printed", "Volume as printed", "Publication"),
    _meta("issue", "chosen", "issue", "Issue", "Publication"),
    _meta("issue", "printed", "issue_printed", "Issue as printed", "Publication"),
    _meta("fpage", "chosen", "fpage", "First page", "Publication"),
    _meta("lpage", "chosen", "lpage", "Last page", "Publication"),
    _meta("fpage", "printed", "fpage_printed", "First page as printed", "Publication"),
    _meta("lpage", "printed", "lpage_printed", "Last page as printed", "Publication"),
    _meta("fpage", "catalogue", "fpage_catalogue", "First page in the catalogue", "Publication"),
    _meta("lpage", "catalogue", "lpage_catalogue", "Last page in the catalogue", "Publication"),
    _meta("journal_title", "printed", "journal_title_printed", "Journal title as printed", "Journal"),
    _meta("journal_title", "catalogue", "journal_title_catalogue", "Journal title in the catalogue", "Journal"),
    _meta("language", "chosen", "language", "Language", "Publication"),
    _meta("language", "catalogue", "language_catalogue", "Language in the catalogue", "Publication"),
    _meta("doi", "chosen", "doi", "DOI", "Identifiers"),
    _meta("doc_type", "reader", "doc_type_page", "Document type on the page", "Type"),
    _meta("doc_type", "catalogue", "doc_type_catalogue", "Document type in the catalogue", "Type"),
    _meta("conference.name", "chosen", "conference_name", "Conference", "About"),
    _meta("conference.place", "chosen", "conference_place", "Conference place", "About"),
    _meta("conference.date", "chosen", "conference_date", "Conference date", "About"),
    _meta("thesis.degree", "chosen", "thesis_degree", "Thesis degree", "About"),
    _meta("thesis.university", "chosen", "thesis_university", "Thesis university", "About"),
    _meta("thesis.year", "chosen", "thesis_year", "Thesis year", "About"),
    _meta("thesis.supervisor", "chosen", "thesis_supervisor", "Thesis supervisor", "About"),
    _meta("reviewed_book.title", "chosen", "reviewed_book_title", "Reviewed book", "About"),
    _meta("reviewed_book.authors", "chosen", "reviewed_book_authors", "Reviewed book's authors", "About"),
    _meta("reviewed_book.publisher", "chosen", "reviewed_book_publisher", "Reviewed book's publisher", "About"),
    _meta("reviewed_book.year", "chosen", "reviewed_book_year", "Reviewed book's year", "About"),
    _meta("original.title", "chosen", "original_title", "Original title (translation)", "About"),
    _meta("original.author", "chosen", "original_author", "Original author (translation)", "About"),
    _meta("original.lang", "chosen", "original_lang", "Original language", "About"),
]

JT = """jt AS (SELECT journal_id, title FROM (SELECT journal_id, title, row_number() OVER (PARTITION BY journal_id
        ORDER BY is_chosen DESC, n DESC) r FROM journal_titles WHERE form = 'catalogue' OR form IS NULL
        OR is_chosen = 1) WHERE r = 1)"""
INAME = """iname AS (SELECT inst_id, name FROM (SELECT inst_id, nullif(trim(name), '') name, row_number() OVER (
           PARTITION BY inst_id ORDER BY nullif(trim(name), '') IS NULL, (type = 'label') DESC, (script = 'Arab') DESC,
           n_seen DESC) r
           FROM institution_names) WHERE r = 1)"""
TC = "tc AS MATERIALIZED (SELECT * FROM v_times_cited)"
CUR = """cur AS MATERIALIZED (SELECT d.*, v.version_id, v.run, v.complete, v.usd, v.pages_covered, v.pages_expected,
         v.n_chunks, v.n_retries, v.tokens_in, v.tokens_out, v.made, v.chosen_by, v.current_reason
         FROM documents d JOIN versions v ON v.stem = d.stem AND v.is_current = 1)"""

ART_WITH = [CUR, JT, INAME, TC,
            "meta AS (SELECT m.pub_id" + "".join(f", {e} AS {n}" for n, e, *_ in META) +
            " FROM metadata_assertions m JOIN cur c ON c.pub_id = m.pub_id GROUP BY m.pub_id)",
            """au AS (SELECT a.pub_id, count(*) n_authors, sum(a.is_corresponding) n_corresponding,
                  group_concat(coalesce(p.preferred_name_ar, p.preferred_name_lat, cc.name), ' · ' ORDER BY a.position) authors,
                  group_concat(a.person_id, ' ' ORDER BY a.position) person_ids,
                  group_concat(DISTINCT a.role_code) roles
                FROM authorships a LEFT JOIN persons p ON p.person_id = a.person_id
                LEFT JOIN catalogue_contributors cc ON cc.c999 = a.c999 AND cc.seq = a.catalogue_seq
                WHERE a.pub_id IN (SELECT pub_id FROM cur) GROUP BY a.pub_id)""",
            """ai AS (SELECT pub_id, count(*) n_institutions, group_concat(name, ' · ') institutions,
                  group_concat(inst_id, ' ') inst_ids FROM (SELECT DISTINCT a.pub_id, l.inst_id, n.name
                  FROM authorships a JOIN authorship_mentions am ON am.authorship_pk = a.authorship_pk
                  JOIN affiliation_mentions f ON f.mention_pk = am.mention_pk /*TW*/
                  JOIN affiliation_links l ON l.aff_pk = f.aff_pk AND l.level = 'org'
                  LEFT JOIN iname n ON n.inst_id = l.inst_id WHERE a.pub_id IN (SELECT pub_id FROM cur))
                GROUP BY pub_id)""",
            """af AS (SELECT a.pub_id, count(DISTINCT f.aff_pk) n_affiliations,
                  group_concat(DISTINCT f.country_code) aff_countries, count(DISTINCT CASE WHEN b.email IS NOT NULL
                  THEN b.mention_pk END) n_emails, count(DISTINCT CASE WHEN b.is_corresponding = 1 THEN b.mention_pk END)
                  n_corresponding
                FROM authorships a JOIN authorship_mentions am ON am.authorship_pk = a.authorship_pk
                JOIN byline_mentions b ON b.mention_pk = am.mention_pk
                JOIN cur c ON c.version_id = b.version_id
                LEFT JOIN affiliation_mentions f ON f.mention_pk = b.mention_pk /*TW*/ GROUP BY a.pub_id)""",
            """rf AS (SELECT m.version_id, count(*) n_mentions, sum(m.kind = 'full') n_full,
                  sum(m.kind = 'short') n_short, sum(m.kind IN ('ibid', 'op_cit', 'loc_cit')) n_backrefs,
                  sum(m.kind = 'quran') n_quran_refs, sum(m.container_kind = 'ref-list') n_in_reflist,
                  sum(m.container_kind = 'note') n_in_notes, sum(m.kind = 'full' AND cm.cited_work_pk IS NOT NULL) n_linked,
                  count(DISTINCT cm.cited_work_pk) n_works_cited, sum(m.max_flag IS NOT NULL) n_refs_flagged
                FROM citation_mentions m JOIN cur c ON c.version_id = m.version_id
                LEFT JOIN cited_work_members cm ON cm.full_mention_pk = coalesce(m.full_mention_pk, m.mention_pk)
                GROUP BY m.version_id)""",
            """bk AS (SELECT b.version_id, count(*) n_blocks, sum(b.n_words) n_words, round(avg(b.wc_mean), 3) wc_mean,
                  min(b.wc_min) wc_min, sum(b.n_low_wc) n_low_wc, sum(b.role = 'paragraph') n_paragraphs,
                  sum(b.role = 'heading') n_headings, sum(b.role = 'list-item') n_list_items,
                  sum(b.role = 'quote') n_quotes, sum(b.lang NOT LIKE 'ar%') n_blocks_not_arabic
                FROM blocks b JOIN cur c ON c.version_id = b.version_id GROUP BY b.version_id)""",
            """sc AS (SELECT s.version_id, count(*) n_sections, max(s.level) max_level FROM sections s
                JOIN cur c ON c.version_id = s.version_id GROUP BY s.version_id)""",
            """nt AS (SELECT n.version_id, count(*) n_notes, sum(n.kind = 'footnote') n_footnotes,
                  sum(n.kind = 'endnote') n_endnotes, sum(n.written_by IS NOT NULL) n_notes_not_author
                FROM notes n JOIN cur c ON c.version_id = n.version_id GROUP BY n.version_id)""",
            """fg AS (SELECT f.version_id, sum(f.kind = 'table') n_tables, sum(f.kind = 'figure') n_figures,
                  sum(f.kind IN ('equation', 'inline-equation')) n_equations, sum(f.kind = 'inline-picture') n_pictures
                FROM figures f JOIN cur c ON c.version_id = f.version_id GROUP BY f.version_id)""",
            """vl AS (SELECT x.version_id, count(*) n_verse_lines FROM verse_lines x JOIN cur c ON c.version_id = x.version_id
                GROUP BY x.version_id)""",
            """qc AS (SELECT x.version_id, count(*) n_quran FROM quran_citations x JOIN cur c ON c.version_id = x.version_id
                GROUP BY x.version_id)""",
            """fl AS (SELECT x.version_id, count(*) n_flags, sum(x.severity = 'high') n_flags_high,
                  sum(x.severity = 'medium') n_flags_medium FROM flags x JOIN cur c ON c.version_id = x.version_id
                GROUP BY x.version_id)""",
            """tx AS (SELECT x.version_id, sum(x.layer = 'azure-misread') n_reader_fixes, sum(x.layer = 'misprint') n_misprints
                FROM text_corrections x JOIN cur c ON c.version_id = x.version_id GROUP BY x.version_id)""",
            """pm AS (SELECT x.version_id, count(*) n_page_problems FROM page_marks x JOIN cur c ON c.version_id = x.version_id
                GROUP BY x.version_id)""",
            """pg AS (SELECT stem, count(*) n_pages_read, round(avg(wc_mean), 3) page_wc_mean, sum(n_low_wc) page_low_wc
                FROM pages GROUP BY stem)""",
            """ab AS (SELECT pub_id, count(*) n_abstracts, group_concat(DISTINCT lang) abstract_langs FROM abstracts
                WHERE pub_id IN (SELECT pub_id FROM cur) GROUP BY pub_id)""",
            """kw AS (SELECT pub_id, count(*) n_keywords, group_concat(printed, ' · ' ORDER BY seq) keywords
                FROM publication_keywords WHERE pub_id IN (SELECT pub_id FROM cur) GROUP BY pub_id)""",
            """dt AS (SELECT pub_id,
                  max(CASE WHEN date_type = 'received' THEN iso END) date_received,
                  max(CASE WHEN date_type = 'accepted' THEN iso END) date_accepted,
                  max(CASE WHEN date_type = 'published' AND calendar = 'gregorian' THEN iso END) date_published,
                  max(CASE WHEN date_type = 'issue' AND calendar = 'gregorian' THEN iso END) date_issue,
                  max(CASE WHEN date_type = 'issue' THEN month_name_printed END) issue_month_printed
                FROM (SELECT *, printf('%04d', year) || CASE WHEN month IS NOT NULL THEN printf('-%02d', month) ELSE '' END
                        || CASE WHEN day IS NOT NULL THEN printf('-%02d', day) ELSE '' END iso FROM publication_dates
                      WHERE pub_id IN (SELECT pub_id FROM cur)) GROUP BY pub_id)""",
            """sx AS (SELECT citing_pub_id pub_id, count(*) n_self_citations FROM v_author_self_citations GROUP BY 1)""",
            ]
ART_FROM = """cur c LEFT JOIN publications p ON p.pub_id = c.pub_id LEFT JOIN meta mt ON mt.pub_id = c.pub_id
  LEFT JOIN journals j ON j.journal_id = p.journal_id LEFT JOIN jt ON jt.journal_id = p.journal_id
  LEFT JOIN issues i ON i.issue_id = p.issue_id LEFT JOIN catalogue_records cr ON cr.c999 = p.c999
  LEFT JOIN v_doc_types vd ON vd.pub_id = c.pub_id LEFT JOIN v_pub_times_cited pt ON pt.pub_id = c.pub_id
  LEFT JOIN au ON au.pub_id = c.pub_id LEFT JOIN ai ON ai.pub_id = c.pub_id LEFT JOIN af ON af.pub_id = c.pub_id
  LEFT JOIN rf ON rf.version_id = c.version_id LEFT JOIN bk ON bk.version_id = c.version_id
  LEFT JOIN sc ON sc.version_id = c.version_id LEFT JOIN nt ON nt.version_id = c.version_id
  LEFT JOIN fg ON fg.version_id = c.version_id LEFT JOIN vl ON vl.version_id = c.version_id
  LEFT JOIN qc ON qc.version_id = c.version_id LEFT JOIN fl ON fl.version_id = c.version_id
  LEFT JOIN tx ON tx.version_id = c.version_id LEFT JOIN pm ON pm.version_id = c.version_id
  LEFT JOIN pg ON pg.stem = c.stem LEFT JOIN ab ON ab.pub_id = c.pub_id LEFT JOIN kw ON kw.pub_id = c.pub_id
  LEFT JOIN dt ON dt.pub_id = c.pub_id LEFT JOIN sx ON sx.pub_id = c.pub_id"""


def _n(name, expr, group, label, src):
    return _c(name, f"coalesce({expr}, 0)", "int", group, label, src)


ARTICLES = [
    _c("stem", "c.stem", "id", "Identity", "Article", "documents.stem", "article"),
    _c("pub_id", "c.pub_id", "id", "Identity", "Publication id (W)", "documents.pub_id"),
    _c("c999", "p.c999", "id", "Identity", "Catalogue 999$c", "publications.c999"),
    _c("title", "p.title_shown", "text", "Title", "Title (shown)", "publications.title_shown"),
    *[_c(n, f"mt.{n}", t, g, lab, s) for n, e, t, g, lab, s in META[:9]],
    _c("year", "p.year_shown", "year", "Publication", "Year", "publications.year_shown"),
    *[_c(n, f"mt.{n}", t, g, lab, s) for n, e, t, g, lab, s in META[9:13]],
    _c("year_greg_issue", "i.year_greg", "year", "Publication", "Issue year (Gregorian)", "issues.year_greg"),
    _c("year_hijri_issue", "i.year_hijri", "year", "Publication", "Issue year (Hijri)", "issues.year_hijri"),
    *[_c(n, f"mt.{n}", t, g, lab, s) for n, e, t, g, lab, s in META[13:23]],
    _c("issue_label", "i.issue_printed", "text", "Publication", "Issue as catalogued", "issues.issue_printed"),
    _c("issue_special", "i.is_special", "int", "Publication", "Special issue", "issues.is_special"),
    _c("issue_joint", "i.is_joint", "int", "Publication", "Joint issue", "issues.is_joint"),
    _c("issue_id", "p.issue_id", "id", "Publication", "Issue id", "publications.issue_id"),
    _c("seq_in_issue", "p.seq_in_issue", "int", "Publication", "Order in the issue", "publications.seq_in_issue"),
    _c("journal_id", "p.journal_id", "id", "Journal", "Journal id", "publications.journal_id", "journal"),
    _c("journal_code", "j.code", "id", "Journal", "Journal code", "journals.code"),
    _c("journal", "jt.title", "text", "Journal", "Journal", "journal_titles (chosen)"),
    _c("journal_country", "j.country_code", "text", "Journal", "Journal country", "journals.country_code"),
    _c("databases", "cr.databases", "text", "Journal", "Mandumah databases", "catalogue_records.databases"),
    *[_c(n, f"mt.{n}", t, g, lab, s) for n, e, t, g, lab, s in META[23:28]],
    _c("doc_type", "p.doc_type", "text", "Type", "Document type (shown)", "publications.doc_type"),
    _c("doc_type_source", "p.doc_type_source", "text", "Type", "Document type from", "publications.doc_type_source"),
    *[_c(n, f"mt.{n}", t, g, lab, s) for n, e, t, g, lab, s in META[28:30]],
    _c("doc_type_disagrees", "vd.disagreement", "int", "Type", "Page and catalogue disagree", "v_doc_types.disagreement"),
    _c("type_catalogue", "p.type_catalogue", "text", "Type", "Catalogue category", "publications.type_catalogue"),
    _c("status", "p.status", "text", "Type", "Status", "publications.status"),
    *[_c(n, f"mt.{n}", t, g, lab, s) for n, e, t, g, lab, s in META[30:]],
    _n("n_authors", "au.n_authors", "Authors", "Authors (n)", "authorships"),
    _c("authors", "au.authors", "text", "Authors", "Authors", "authorships -> persons"),
    _c("person_ids", "au.person_ids", "id", "Authors", "Author ids", "authorships.person_id", "person"),
    _c("author_roles", "au.roles", "text", "Authors", "Roles", "authorships.role_code"),
    _n("n_corresponding", "af.n_corresponding", "Authors", "Corresponding authors", "byline_mentions.is_corresponding"),
    _n("n_emails", "af.n_emails", "Authors", "E-mails printed", "byline_mentions.email"),
    _n("n_affiliations", "af.n_affiliations", "Institutions", "Affiliations printed", "affiliation_mentions"),
    _c("aff_countries", "af.aff_countries", "text", "Institutions", "Affiliation countries", "affiliation_mentions.country_code"),
    _n("n_institutions", "ai.n_institutions", "Institutions", "Institutions (n)", "affiliation_links (org) -> institutions"),
    _c("institutions", "ai.institutions", "text", "Institutions", "Institutions", "affiliation_links -> institution_names"),
    _c("inst_ids", "ai.inst_ids", "id", "Institutions", "Institution ids", "affiliation_links.inst_id", "institution"),
    _n("n_mentions", "rf.n_mentions", "References", "Reference mentions", "citation_mentions (current version)"),
    _n("n_full", "rf.n_full", "References", "Full references", "citation_mentions kind full"),
    _n("n_short", "rf.n_short", "References", "Short references", "citation_mentions kind short"),
    _n("n_backrefs", "rf.n_backrefs", "References", "Ibid / op. cit.", "citation_mentions kind ibid, op_cit, loc_cit"),
    _n("n_quran_refs", "rf.n_quran_refs", "References", "Quran references", "citation_mentions kind quran"),
    _n("n_in_reflist", "rf.n_in_reflist", "References", "In the reference list", "citation_mentions container ref-list"),
    _n("n_in_notes", "rf.n_in_notes", "References", "In notes", "citation_mentions container note"),
    _n("n_linked", "rf.n_linked", "References", "Full references linked to a cited work", "cited_work_members (full references only)"),
    _n("n_works_cited", "rf.n_works_cited", "References", "Distinct works cited", "cited_work_members -> cited_works"),
    _n("n_refs_flagged", "rf.n_refs_flagged", "References", "References flagged", "citation_mentions.max_flag"),
    _n("n_self_citations", "sx.n_self_citations", "References", "Author self-citations", "v_author_self_citations"),
    _n("times_cited", "pt.n_citing_pubs", "Impact", "Times cited (articles)", "v_pub_times_cited.n_citing_pubs"),
    _n("times_cited_mentions", "pt.n_mentions", "Impact", "Times cited (mentions)", "v_pub_times_cited.n_mentions"),
    _n("n_abstracts", "ab.n_abstracts", "Content", "Abstracts", "abstracts"),
    _c("abstract_langs", "ab.abstract_langs", "text", "Content", "Abstract languages", "abstracts.lang"),
    _n("n_keywords", "kw.n_keywords", "Content", "Keywords (n)", "publication_keywords"),
    _c("keywords", "kw.keywords", "text", "Content", "Keywords", "publication_keywords.printed"),
    _n("n_sections", "sc.n_sections", "Content", "Sections", "sections"),
    _n("max_heading_level", "sc.max_level", "Content", "Deepest heading level", "sections.level"),
    _n("n_blocks", "bk.n_blocks", "Content", "Blocks", "blocks"),
    _n("n_paragraphs", "bk.n_paragraphs", "Content", "Paragraphs", "blocks role paragraph"),
    _n("n_headings", "bk.n_headings", "Content", "Headings", "blocks role heading"),
    _n("n_list_items", "bk.n_list_items", "Content", "List items", "blocks role list-item"),
    _n("n_quotes", "bk.n_quotes", "Content", "Block quotes", "blocks role quote"),
    _n("n_words", "bk.n_words", "Content", "Words", "blocks.n_words"),
    _n("n_blocks_not_arabic", "bk.n_blocks_not_arabic", "Content", "Blocks not in Arabic", "blocks.lang"),
    _n("n_notes", "nt.n_notes", "Content", "Notes", "notes"),
    _n("n_footnotes", "nt.n_footnotes", "Content", "Footnotes", "notes kind footnote"),
    _n("n_endnotes", "nt.n_endnotes", "Content", "Endnotes", "notes kind endnote"),
    _n("n_notes_not_author", "nt.n_notes_not_author", "Content", "Translator's / editor's notes", "notes.written_by"),
    _n("n_tables", "fg.n_tables", "Content", "Tables", "figures kind table"),
    _n("n_figures", "fg.n_figures", "Content", "Figures", "figures kind figure"),
    _n("n_equations", "fg.n_equations", "Content", "Equations", "figures kind equation, inline-equation"),
    _n("n_pictures", "fg.n_pictures", "Content", "Inline pictures", "figures kind inline-picture"),
    _n("n_verse_lines", "vl.n_verse_lines", "Content", "Verse lines", "verse_lines"),
    _n("n_quran", "qc.n_quran", "Content", "Quran quotations", "quran_citations"),
    _c("date_received", "dt.date_received", "date", "Dates", "Received", "publication_dates received"),
    _c("date_accepted", "dt.date_accepted", "date", "Dates", "Accepted", "publication_dates accepted"),
    _c("date_published", "dt.date_published", "date", "Dates", "Published", "publication_dates published"),
    _c("date_issue", "dt.date_issue", "date", "Dates", "Issue date", "publication_dates issue"),
    _c("issue_month_printed", "dt.issue_month_printed", "text", "Dates", "Issue month as printed", "publication_dates.month_name_printed"),
    _n("n_flags", "fl.n_flags", "Quality", "Flags", "flags"),
    _n("n_flags_high", "fl.n_flags_high", "Quality", "Flags (high)", "flags severity high"),
    _n("n_flags_medium", "fl.n_flags_medium", "Quality", "Flags (medium)", "flags severity medium"),
    _n("n_reader_fixes", "tx.n_reader_fixes", "Quality", "Reader fixes", "text_corrections layer azure-misread"),
    _n("n_misprints", "tx.n_misprints", "Quality", "Misprints", "text_corrections layer misprint"),
    _n("n_page_problems", "pm.n_page_problems", "Quality", "Scan problems", "page_marks"),
    _c("wc_mean", "bk.wc_mean", "real", "Quality", "Mean word confidence", "blocks.wc_mean"),
    _c("wc_min", "bk.wc_min", "real", "Quality", "Lowest word confidence", "blocks.wc_min"),
    _n("n_low_wc", "bk.n_low_wc", "Quality", "Low-confidence words", "blocks.n_low_wc"),
    _n("scan_pages", "c.scan_pages", "Pipeline", "Scan pages", "documents.scan_pages"),
    _n("pages_covered", "c.pages_covered", "Pipeline", "Pages covered", "versions.pages_covered"),
    _n("pages_expected", "c.pages_expected", "Pipeline", "Pages expected", "versions.pages_expected"),
    _c("complete", "c.complete", "int", "Pipeline", "Complete", "versions.complete"),
    _c("run", "c.run", "text", "Pipeline", "Run", "versions.run"),
    _c("version_id", "c.version_id", "id", "Pipeline", "Version id", "versions.version_id"),
    _c("version_made", "c.made", "date", "Pipeline", "Version made", "versions.made"),
    _c("current_reason", "c.current_reason", "text", "Pipeline", "Why this version", "versions.current_reason"),
    _c("usd", "round(c.usd, 4)", "real", "Pipeline", "Model cost (USD)", "versions.usd"),
    _n("tokens_in", "c.tokens_in", "Pipeline", "Tokens in", "versions.tokens_in"),
    _n("tokens_out", "c.tokens_out", "Pipeline", "Tokens out", "versions.tokens_out"),
    _n("n_chunks", "c.n_chunks", "Pipeline", "Chunks", "versions.n_chunks"),
    _n("n_retries", "c.n_retries", "Pipeline", "Retries", "versions.n_retries"),
    _c("part_label", "c.part_label", "text", "Pipeline", "Part", "documents.part_label"),
    _c("level", "c.level", "text", "Pipeline", "Level", "documents.level"),
    _c("catalogue_pages", "cr.pages_raw", "text", "Catalogue", "Pages in the catalogue", "catalogue_records.pages_raw"),
    _c("catalogue_language", "cr.language_raw", "text", "Catalogue", "Language in the catalogue (raw)", "catalogue_records.language_raw"),
    _c("catalogue_doi", "cr.doi", "text", "Catalogue", "DOI in the catalogue", "catalogue_records.doi"),
    _c("catalogue_added", "cr.added", "text", "Catalogue", "Added to the catalogue", "catalogue_records.added"),
]
ARTICLES_DEFAULT = ["stem", "title", "authors", "journal", "year", "doc_type", "n_full", "n_linked", "times_cited",
                    "n_flags"]

# ------------------------------------------------------------------ references (each reference an article makes)
REF_WITH = [CUR, JT, TC,
            """m AS MATERIALIZED (SELECT x.*, CASE WHEN json_valid(x.parsed) THEN x.parsed END pj
                FROM citation_mentions x JOIN cur c ON c.version_id = x.version_id)""",
            """ppl AS (SELECT q.mention_pk,
                  group_concat(CASE WHEN q.role = 'author' THEN q.printed END, ' · ' ORDER BY q.seq) authors,
                  sum(q.role = 'author') n_authors,
                  group_concat(CASE WHEN q.role = 'editor' THEN q.printed END, ' · ' ORDER BY q.seq) editors,
                  group_concat(CASE WHEN q.role = 'translator' THEN q.printed END, ' · ' ORDER BY q.seq) translators,
                  group_concat(q.died, ' · ') died
                FROM citation_mention_people q JOIN m ON m.mention_pk = q.mention_pk GROUP BY q.mention_pk)""",
            """lk AS (SELECT cited_work_pk, target_pub_id, status FROM (SELECT l.*, row_number() OVER (PARTITION BY
                  cited_work_pk ORDER BY best DESC, status = 'accepted' DESC, score DESC) r FROM citation_links l)
                WHERE r = 1)""",
            ]
REF_FROM = """m JOIN cur c ON c.version_id = m.version_id LEFT JOIN publications p ON p.pub_id = c.pub_id
  LEFT JOIN jt ON jt.journal_id = p.journal_id
  LEFT JOIN cited_work_members cm ON cm.full_mention_pk = coalesce(m.full_mention_pk, m.mention_pk)
  LEFT JOIN cited_works w ON w.cited_work_pk = cm.cited_work_pk LEFT JOIN tc ON tc.cited_work_pk = w.cited_work_pk
  LEFT JOIN cited_work_editions e ON e.edition_pk = cm.edition_pk
  LEFT JOIN citation_mentions fm ON fm.mention_pk = m.full_mention_pk LEFT JOIN ppl ON ppl.mention_pk = m.mention_pk
  LEFT JOIN lk ON lk.cited_work_pk = w.cited_work_pk LEFT JOIN publications lp ON lp.pub_id = lk.target_pub_id
  LEFT JOIN documents ld ON ld.pub_id = lk.target_pub_id"""


def _pj(name, key, label, group="Parsed", typ="text"):
    return _c(name, f"json_extract(m.pj, '$.{key}')", typ, group, label, f"citation_mentions.parsed {key}")


REFERENCES = [
    _c("mention_id", "m.mention_id", "id", "Identity", "Reference", "citation_mentions.mention_id", "mention"),
    _c("stem", "c.stem", "id", "Citing article", "Citing article", "versions.stem", "article"),
    _c("citing_title", "p.title_shown", "text", "Citing article", "Citing article's title", "publications.title_shown"),
    _c("citing_year", "p.year_shown", "year", "Citing article", "Citing year", "publications.year_shown"),
    _c("citing_journal", "jt.title", "text", "Citing article", "Citing journal", "journal_titles"),
    _c("citing_journal_id", "p.journal_id", "id", "Citing article", "Citing journal id", "publications.journal_id", "journal"),
    _c("kind", "m.kind", "text", "Reference", "Kind", "citation_mentions.kind (full, short, ibid, op_cit, quran)"),
    _c("container", "m.container_kind", "text", "Reference", "Where (note / ref list)", "citation_mentions.container_kind"),
    _c("marker", "m.marker", "text", "Reference", "Marker", "citation_mentions.marker"),
    _c("reading_ord", "m.reading_ord", "int", "Reference", "Order in the article", "citation_mentions.reading_ord"),
    _c("page", "m.page", "int", "Reference", "Page", "citation_mentions.page"),
    _c("printed", "m.printed", "text", "Reference", "As printed", "citation_mentions.printed"),
    _c("printed_fixed", "m.printed_fixed", "text", "Reference", "As printed, reader fixes applied", "citation_mentions.printed_fixed"),
    _pj("pub_type", "pub_type", "Reference type"),
    _c("authors", "ppl.authors", "text", "Parsed", "Authors", "citation_mention_people role author"),
    _c("n_authors", "coalesce(ppl.n_authors, 0)", "int", "Parsed", "Authors (n)", "citation_mention_people"),
    _pj("first_author", "first_author", "First author"),
    _pj("article_title", "article_title", "Article title"),
    _pj("chapter_title", "chapter_title", "Chapter title"),
    _pj("source_title", "source_title", "Book / journal title"),
    _pj("year_parsed", "year", "Year as printed"),
    _c("year_calendar", "m.year_calendar", "text", "Parsed", "Year calendar", "citation_mentions.year_calendar"),
    _c("year2", "m.year2", "text", "Parsed", "Other calendar's year", "citation_mentions.year2"),
    _pj("publisher", "publisher", "Publisher"),
    _pj("place", "place", "Place"),
    _c("edition", "m.edition", "text", "Parsed", "Edition", "citation_mentions.edition"),
    _pj("series", "series", "Series"),
    _pj("volume", "volume", "Volume"),
    _pj("issue", "issue", "Issue"),
    _pj("fpage", "fpage", "First page"),
    _pj("lpage", "lpage", "Last page"),
    _pj("page_range", "page_range", "Page range"),
    _c("cited_pages", "m.cited_pages", "text", "Parsed", "Page referred to", "citation_mentions.cited_pages"),
    _c("cited_volume", "m.cited_volume", "text", "Parsed", "Volume referred to", "citation_mentions.cited_volume"),
    _c("work_pages", "m.work_pages", "text", "Parsed", "The work's own pages", "citation_mentions.work_pages"),
    _c("editors", "ppl.editors", "text", "Parsed", "Editors (tahqiq)", "citation_mention_people role editor"),
    _c("translators", "ppl.translators", "text", "Parsed", "Translators", "citation_mention_people role translator"),
    _c("died", "coalesce(m.died, ppl.died)", "text", "Parsed", "Author's death date", "citation_mentions.died"),
    _pj("doi", "doi", "DOI"),
    _pj("url", "url", "URL"),
    _c("access_date", "m.access_date", "text", "Parsed", "Access date", "citation_mentions.access_date"),
    _c("thesis_degree", "coalesce(m.thesis_degree, json_extract(m.pj, '$.degree'))", "text", "Parsed", "Thesis degree", "citation_mentions.thesis_degree"),
    _c("conf_name", "m.conf_name", "text", "Parsed", "Conference", "citation_mentions.conf_name"),
    _c("conf_loc", "m.conf_loc", "text", "Parsed", "Conference place", "citation_mentions.conf_loc"),
    _c("ms_library", "m.ms_library", "text", "Parsed", "Manuscript library", "citation_mentions.ms_library"),
    _c("ms_shelfmark", "m.ms_shelfmark", "text", "Parsed", "Manuscript shelfmark", "citation_mentions.ms_shelfmark"),
    _c("ms_folio", "m.ms_folio", "text", "Parsed", "Manuscript folio", "citation_mentions.ms_folio"),
    _c("cited_work_id", "w.cited_work_id", "id", "Cited work", "Cited work", "cited_work_members -> cited_works", "work"),
    _c("work_title", "w.title", "text", "Cited work", "Cited work's title", "cited_works.title"),
    _c("work_type", "w.pub_type", "text", "Cited work", "Cited work's type", "cited_works.pub_type"),
    _c("work_year", "w.year_greg", "year", "Cited work", "Cited work's year (Gregorian)", "cited_works.year_greg"),
    _c("work_times_cited", "tc.n_citing_pubs", "int", "Cited work", "Cited work: times cited", "v_times_cited.n_citing_pubs"),
    _c("edition_printed", "e.edition_printed", "text", "Cited work", "Edition (the work's)", "cited_work_editions.edition_printed"),
    _c("member_method", "cm.method", "text", "Cited work", "Grouped by", "cited_work_members.method"),
    _c("member_score", "cm.score", "real", "Cited work", "Grouping score", "cited_work_members.score"),
    _c("catalogue_link", "lp.pub_id", "id", "Catalogue link", "Linked catalogue record", "citation_links.target_pub_id"),
    _c("catalogue_link_title", "lp.title_shown", "text", "Catalogue link", "Linked record's title", "publications.title_shown"),
    _c("catalogue_link_stem", "ld.stem", "id", "Catalogue link", "Linked article (read)", "documents.stem", "article"),
    _c("catalogue_link_status", "lk.status", "text", "Catalogue link", "Link status", "citation_links.status"),
    _c("points_to", "fm.mention_id", "id", "Back reference", "Points to (ibid target)", "citation_mentions.full_mention_pk", "mention"),
    _c("resolve_method", "m.resolve_method", "text", "Back reference", "Resolved by rule", "citation_mentions.resolve_method"),
    _c("resolve_score", "m.resolve_score", "real", "Back reference", "Resolve score", "citation_mentions.resolve_score"),
    _c("resolved_by", "m.resolved_by", "text", "Back reference", "Resolved by", "citation_mentions.resolved_by"),
    _c("unresolved_why", "m.unresolved_why", "text", "Back reference", "Why unresolved", "citation_mentions.unresolved_why"),
    _c("max_flag", "m.max_flag", "text", "Quality", "Worst flag", "citation_mentions.max_flag"),
    _c("trust", "m.trust", "real", "Quality", "Trust", "citation_mentions.trust"),
    _c("n_fixes_on_lines", "m.n_fixes_on_lines", "int", "Quality", "Reader fixes on its lines", "citation_mentions.n_fixes_on_lines"),
    _c("n_misprints_on_lines", "m.n_misprints_on_lines", "int", "Quality", "Misprints on its lines", "citation_mentions.n_misprints_on_lines"),
]
REFERENCES_DEFAULT = ["mention_id", "stem", "kind", "printed", "pub_type", "authors", "year_parsed", "cited_work_id",
                      "work_times_cited"]

# ------------------------------------------------------------------ authors (persons)
PER_WITH = [CUR, INAME, TC,
            """nm AS (SELECT person_id, count(*) n_names, group_concat(full_form, ' · ') names FROM person_names
                GROUP BY person_id)""",
            """pa AS (SELECT person_id, count(*) n_authorities, group_concat(authority_id, ' ') authority_ids,
                  group_concat(heading, ' · ') headings, sum(n_records) n_records FROM person_authorities GROUP BY person_id)""",
            """asp AS (SELECT a.person_id, count(*) n_authorships, count(DISTINCT a.pub_id) n_publications,
                  count(DISTINCT c.pub_id) n_articles, group_concat(DISTINCT a.role_code) roles,
                  sum(a.is_corresponding) n_corresponding, min(pb.year_shown) first_year, max(pb.year_shown) last_year,
                  count(DISTINCT pb.journal_id) n_journals
                FROM authorships a LEFT JOIN cur c ON c.pub_id = a.pub_id LEFT JOIN publications pb ON pb.pub_id = a.pub_id
                WHERE a.person_id IS NOT NULL GROUP BY a.person_id)""",
            """pi AS (SELECT person_id, count(*) n_institutions, group_concat(name, ' · ') institutions,
                  group_concat(inst_id, ' ') inst_ids FROM (SELECT DISTINCT a.person_id, l.inst_id, n.name
                  FROM authorships a JOIN authorship_mentions am ON am.authorship_pk = a.authorship_pk
                  JOIN affiliation_mentions f ON f.mention_pk = am.mention_pk /*TW*/
                  JOIN affiliation_links l ON l.aff_pk = f.aff_pk AND l.level = 'org'
                  LEFT JOIN iname n ON n.inst_id = l.inst_id WHERE a.person_id IS NOT NULL) GROUP BY person_id)""",
            """pb AS (SELECT a.person_id, group_concat(DISTINCT b.email) emails, group_concat(DISTINCT f.country_code) countries,
                  count(DISTINCT b.mention_pk) n_bylines,
                  count(DISTINCT CASE WHEN b.is_corresponding = 1 THEN b.mention_pk END) n_corresponding
                FROM authorships a JOIN authorship_mentions am ON am.authorship_pk = a.authorship_pk
                JOIN byline_mentions b ON b.mention_pk = am.mention_pk JOIN cur c ON c.version_id = b.version_id
                LEFT JOIN affiliation_mentions f ON f.mention_pk = b.mention_pk /*TW*/
                WHERE a.person_id IS NOT NULL GROUP BY a.person_id)""",
            """co AS (SELECT a.person_id, count(DISTINCT b.person_id) n_coauthors FROM authorships a
                JOIN authorships b ON b.pub_id = a.pub_id AND b.person_id <> a.person_id GROUP BY a.person_id)""",
            """cw AS (SELECT person_id, count(*) n_works_cited, sum(n_citing_pubs) times_cited, sum(n_mentions) mentions_received
                FROM (SELECT DISTINCT ca.person_id, ca.cited_work_pk, tc.n_citing_pubs, tc.n_mentions
                      FROM cited_work_authors ca JOIN tc ON tc.cited_work_pk = ca.cited_work_pk
                      WHERE ca.person_id IS NOT NULL) GROUP BY person_id)""",
            """sv AS (SELECT person_id, sum(sup) n_supervised, sum(stu) n_supervisions_received FROM (
                  SELECT supervisor_person_id person_id, 1 sup, 0 stu FROM supervisions
                  UNION ALL SELECT student_person_id, 0, 1 FROM supervisions) WHERE person_id IS NOT NULL GROUP BY person_id)""",
            """mg AS (SELECT new_id, count(*) n_merged FROM merged_ids WHERE kind = 'person' GROUP BY new_id)""",
            ]
PER_FROM = """persons p LEFT JOIN nm ON nm.person_id = p.person_id LEFT JOIN pa ON pa.person_id = p.person_id
  LEFT JOIN asp ON asp.person_id = p.person_id LEFT JOIN pi ON pi.person_id = p.person_id
  LEFT JOIN pb ON pb.person_id = p.person_id LEFT JOIN co ON co.person_id = p.person_id
  LEFT JOIN cw ON cw.person_id = p.person_id LEFT JOIN sv ON sv.person_id = p.person_id
  LEFT JOIN mg ON mg.new_id = p.person_id"""
PERSONS = [
    _c("person_id", "p.person_id", "id", "Identity", "Person", "persons.person_id", "person"),
    _c("name", "coalesce(p.preferred_name_ar, p.preferred_name_lat)", "text", "Identity", "Name", "persons.preferred_name_*"),
    _c("name_ar", "p.preferred_name_ar", "text", "Identity", "Name (Arabic)", "persons.preferred_name_ar"),
    _c("name_lat", "p.preferred_name_lat", "text", "Identity", "Name (Latin)", "persons.preferred_name_lat"),
    _c("status", "p.status", "text", "Identity", "Status", "persons.status"),
    _c("source", "p.source", "text", "Identity", "Source", "persons.source"),
    _n("n_names", "nm.n_names", "Names", "Name forms (n)", "person_names"),
    _c("names", "nm.names", "text", "Names", "Name forms", "person_names.full_form"),
    _n("n_authorities", "pa.n_authorities", "Names", "Catalogue authorities", "person_authorities"),
    _c("authority_ids", "pa.authority_ids", "id", "Names", "Authority ids", "person_authorities.authority_id"),
    _c("headings", "pa.headings", "text", "Names", "Catalogue headings", "person_authorities.heading"),
    _n("n_catalogue_records", "pa.n_records", "Names", "Catalogue records", "person_authorities.n_records"),
    _c("birth_year_h", "p.birth_year_h", "year", "Life", "Born (Hijri)", "persons.birth_year_h"),
    _c("birth_year_g", "p.birth_year_g", "year", "Life", "Born (Gregorian)", "persons.birth_year_g"),
    _c("death_year_h", "p.death_year_h", "year", "Life", "Died (Hijri)", "persons.death_year_h"),
    _c("death_year_g", "p.death_year_g", "year", "Life", "Died (Gregorian)", "persons.death_year_g"),
    _n("n_articles", "asp.n_articles", "Output", "Articles (read)", "authorships on documents"),
    _n("n_publications", "asp.n_publications", "Output", "Publications (catalogue)", "authorships"),
    _n("n_authorships", "asp.n_authorships", "Output", "Authorships", "authorships"),
    _c("roles", "asp.roles", "text", "Output", "Roles", "authorships.role_code"),
    _n("n_corresponding", "pb.n_corresponding", "Output", "Corresponding author (n)", "byline_mentions.is_corresponding"),
    _c("first_year", "asp.first_year", "year", "Output", "First year", "publications.year_shown"),
    _c("last_year", "asp.last_year", "year", "Output", "Last year", "publications.year_shown"),
    _n("n_journals", "asp.n_journals", "Output", "Journals", "publications.journal_id"),
    _n("n_coauthors", "co.n_coauthors", "Output", "Co-authors", "authorships"),
    _n("n_bylines", "pb.n_bylines", "Output", "Bylines read", "byline_mentions"),
    _c("emails", "pb.emails", "text", "Contact", "E-mails", "byline_mentions.email"),
    _n("n_institutions", "pi.n_institutions", "Institutions", "Institutions (n)", "affiliation_links (org)"),
    _c("institutions", "pi.institutions", "text", "Institutions", "Institutions", "affiliation_links -> institution_names"),
    _c("inst_ids", "pi.inst_ids", "id", "Institutions", "Institution ids", "affiliation_links.inst_id", "institution"),
    _c("countries", "pb.countries", "text", "Institutions", "Affiliation countries", "affiliation_mentions.country_code"),
    _n("n_works_cited", "cw.n_works_cited", "Impact", "Their works cited", "cited_work_authors.person_id"),
    _n("times_cited", "cw.times_cited", "Impact", "Sum of times cited (per work)", "v_times_cited over their works, summed (an article citing 3 of their works counts 3)"),
    _n("mentions_received", "cw.mentions_received", "Impact", "Times cited (mentions)", "v_times_cited.n_mentions"),
    _n("n_supervised", "sv.n_supervised", "Impact", "Theses supervised", "supervisions"),
    _n("n_merged", "mg.n_merged", "Identity", "Ids merged into it", "merged_ids"),
]
PERSONS_DEFAULT = ["person_id", "name", "name_lat", "status", "n_articles", "n_publications", "institutions",
                   "times_cited", "n_coauthors"]

# ------------------------------------------------------------------ institutions
INS_WITH = [CUR, INAME,
            """nms AS (SELECT inst_id, count(*) n_names, group_concat(name, ' · ') names,
                  max(CASE WHEN script = 'Latn' THEN name END) name_lat FROM institution_names GROUP BY inst_id)""",
            """ia AS (SELECT l.inst_id, count(DISTINCT l.aff_pk) n_affiliations, count(DISTINCT a.person_id) n_authors,
                  count(DISTINCT c.pub_id) n_articles, min(pb.year_shown) first_year, max(pb.year_shown) last_year
                FROM affiliation_links l JOIN affiliation_mentions f ON f.aff_pk = l.aff_pk /*TW*/
                LEFT JOIN authorship_mentions am ON am.mention_pk = f.mention_pk
                LEFT JOIN authorships a ON a.authorship_pk = am.authorship_pk
                LEFT JOIN cur c ON c.pub_id = a.pub_id LEFT JOIN publications pb ON pb.pub_id = c.pub_id
                WHERE l.level NOT IN ('former', 'educated_at')
                GROUP BY l.inst_id)""",
            """ch AS (SELECT parent_id, count(*) n_children FROM institutions WHERE parent_id IS NOT NULL GROUP BY 1)""",
            """rl AS (SELECT id, count(*) n_relations FROM (SELECT from_id id FROM institution_relations
                  UNION ALL SELECT to_id FROM institution_relations) GROUP BY id)""",
            """mg AS (SELECT new_id, count(*) n_merged FROM merged_ids WHERE kind = 'institution' GROUP BY new_id)""",
            ]
INS_FROM = """institutions i LEFT JOIN iname n ON n.inst_id = i.inst_id LEFT JOIN nms ON nms.inst_id = i.inst_id
  LEFT JOIN institutions pi ON pi.inst_id = i.parent_id LEFT JOIN iname pn ON pn.inst_id = i.parent_id
  LEFT JOIN ia ON ia.inst_id = i.inst_id LEFT JOIN ch ON ch.parent_id = i.inst_id LEFT JOIN rl ON rl.id = i.inst_id
  LEFT JOIN mg ON mg.new_id = i.inst_id"""
INSTITUTIONS = [
    _c("inst_id", "i.inst_id", "id", "Identity", "Institution", "institutions.inst_id", "institution"),
    _c("name", "n.name", "text", "Identity", "Name", "institution_names (most seen, Arabic first)"),
    _c("name_lat", "nms.name_lat", "text", "Identity", "Name (Latin)", "institution_names script Latn"),
    _n("n_names", "nms.n_names", "Names", "Name forms (n)", "institution_names"),
    _c("names", "nms.names", "text", "Names", "Name forms", "institution_names.name"),
    _c("kind", "i.kind", "text", "Identity", "Kind", "institutions.kind"),
    _c("status", "i.status", "text", "Identity", "Status", "institutions.status"),
    _c("source", "i.source", "text", "Identity", "Source", "institutions.source"),
    _c("country", "i.country_code", "text", "Place", "Country", "institutions.country_code"),
    _c("city", "i.city", "text", "Place", "City", "institutions.city"),
    _c("parent_id", "i.parent_id", "id", "Hierarchy", "Parent id", "institutions.parent_id", "institution"),
    _c("parent_name", "pn.name", "text", "Hierarchy", "Parent", "institution_names"),
    _c("parent_kind", "pi.kind", "text", "Hierarchy", "Parent's kind", "institutions.kind"),
    _n("n_children", "ch.n_children", "Hierarchy", "Units under it", "institutions.parent_id"),
    _n("n_relations", "rl.n_relations", "Hierarchy", "Relations", "institution_relations"),
    _c("catalogue_authority_id", "i.catalogue_authority_id", "id", "Identity", "Catalogue authority", "institutions.catalogue_authority_id"),
    _n("n_affiliations", "ia.n_affiliations", "Output", "Affiliations linked", "affiliation_links"),
    _n("n_authors", "ia.n_authors", "Output", "Authors", "affiliation_links -> authorships"),
    _n("n_articles", "ia.n_articles", "Output", "Articles (read)", "affiliation_links -> authorships -> documents"),
    _c("first_year", "ia.first_year", "year", "Output", "First year", "publications.year_shown"),
    _c("last_year", "ia.last_year", "year", "Output", "Last year", "publications.year_shown"),
    _n("n_merged", "mg.n_merged", "Identity", "Ids merged into it", "merged_ids"),
]
INSTITUTIONS_DEFAULT = ["inst_id", "name", "name_lat", "kind", "country", "parent_name", "n_authors", "n_articles"]

# ------------------------------------------------------------------ journals
JOU_WITH = [CUR, JT,
            """tt AS (SELECT journal_id, count(*) n_titles, group_concat(title, ' · ') titles,
                  max(CASE WHEN form = 'catalogue-en' THEN title END) title_en,
                  max(CASE WHEN form = 'romanised' THEN title END) title_romanised FROM journal_titles GROUP BY journal_id)""",
            """iss AS (SELECT journal_id, count(*) n_issns, group_concat(DISTINCT issn) issns, max(issn_l) issn_l
                FROM journal_issns GROUP BY journal_id)""",
            """pu AS (SELECT jp.journal_id, group_concat(pb.name, ' · ') publishers, max(pb.country_code) publisher_country
                FROM journal_publishers jp JOIN publishers pb ON pb.publisher_id = jp.publisher_id GROUP BY jp.journal_id)""",
            """isu AS (SELECT journal_id, count(*) n_issues, min(year_greg) issues_from, max(year_greg) issues_to,
                  sum(is_special) n_special_issues FROM issues GROUP BY journal_id)""",
            """cat AS (SELECT p.journal_id, count(*) n_catalogue, count(c.stem) n_articles,
                  min(CASE WHEN c.stem IS NOT NULL THEN p.year_shown END) read_from,
                  max(CASE WHEN c.stem IS NOT NULL THEN p.year_shown END) read_to
                FROM publications p LEFT JOIN cur c ON c.pub_id = p.pub_id GROUP BY p.journal_id)""",
            """rm AS (SELECT p.journal_id, count(*) n_mentions, sum(m.kind = 'full') n_full FROM citation_mentions m
                JOIN cur c ON c.version_id = m.version_id JOIN publications p ON p.pub_id = c.pub_id GROUP BY p.journal_id)""",
            """cin AS (SELECT cited_journal journal_id, sum(n_citing_pubs) cited_by_articles, sum(n_mentions) cited_mentions,
                  sum(CASE WHEN is_self THEN n_mentions ELSE 0 END) self_mentions, count(DISTINCT citing_journal) n_citing_journals
                FROM v_journal_citation_pairs GROUP BY cited_journal)""",
            """cout AS (SELECT citing_journal journal_id, count(DISTINCT cited_journal) n_journals_cited
                FROM v_journal_citation_pairs GROUP BY citing_journal)""",
            ]
JOU_FROM = """journals j LEFT JOIN jt ON jt.journal_id = j.journal_id LEFT JOIN tt ON tt.journal_id = j.journal_id
  LEFT JOIN iss ON iss.journal_id = j.journal_id LEFT JOIN pu ON pu.journal_id = j.journal_id
  LEFT JOIN isu ON isu.journal_id = j.journal_id LEFT JOIN cat ON cat.journal_id = j.journal_id
  LEFT JOIN rm ON rm.journal_id = j.journal_id LEFT JOIN cin ON cin.journal_id = j.journal_id
  LEFT JOIN cout ON cout.journal_id = j.journal_id"""
JOURNALS = [
    _c("journal_id", "j.journal_id", "id", "Identity", "Journal", "journals.journal_id", "journal"),
    _c("code", "j.code", "id", "Identity", "Mandumah code", "journals.code"),
    _c("title", "jt.title", "text", "Identity", "Title", "journal_titles (chosen)"),
    _c("title_en", "tt.title_en", "text", "Titles", "English title", "journal_titles form catalogue-en"),
    _c("title_romanised", "tt.title_romanised", "text", "Titles", "Romanised title", "journal_titles form romanised"),
    _n("n_titles", "tt.n_titles", "Titles", "Title forms (n)", "journal_titles"),
    _c("titles", "tt.titles", "text", "Titles", "Title forms", "journal_titles.title"),
    _c("issns", "iss.issns", "id", "Identity", "ISSN", "journal_issns.issn"),
    _c("issn_l", "iss.issn_l", "id", "Identity", "ISSN-L", "journal_issns.issn_l"),
    _c("country", "j.country_code", "text", "Identity", "Country", "journals.country_code"),
    _c("databases", "j.databases", "text", "Identity", "Mandumah databases", "journals.databases"),
    _c("publishers", "pu.publishers", "text", "Publisher", "Publisher", "journal_publishers -> publishers"),
    _c("publisher_country", "pu.publisher_country", "text", "Publisher", "Publisher's country", "publishers.country_code"),
    _c("first_year", "j.first_year", "year", "Coverage", "First year", "journals.first_year"),
    _c("last_year", "j.last_year", "year", "Coverage", "Last year", "journals.last_year"),
    _n("n_issues", "isu.n_issues", "Coverage", "Issues", "issues"),
    _n("n_special_issues", "isu.n_special_issues", "Coverage", "Special issues", "issues.is_special"),
    _n("n_catalogue", "cat.n_catalogue", "Coverage", "Records in the catalogue", "publications"),
    _n("n_articles", "cat.n_articles", "Coverage", "Articles read", "documents"),
    _c("read_from", "cat.read_from", "year", "Coverage", "Read from (year)", "publications.year_shown"),
    _c("read_to", "cat.read_to", "year", "Coverage", "Read to (year)", "publications.year_shown"),
    _n("n_mentions", "rm.n_mentions", "References", "Reference mentions made", "citation_mentions"),
    _n("n_full", "rm.n_full", "References", "Full references made", "citation_mentions kind full"),
    _n("n_journals_cited", "cout.n_journals_cited", "References", "Journals it cites", "v_journal_citation_pairs"),
    _n("cited_by_articles", "cin.cited_by_articles", "Impact", "Cited by articles", "v_journal_citation_pairs"),
    _n("cited_mentions", "cin.cited_mentions", "Impact", "Cited (mentions)", "v_journal_citation_pairs.n_mentions"),
    _n("n_citing_journals", "cin.n_citing_journals", "Impact", "Citing journals", "v_journal_citation_pairs"),
    _n("self_mentions", "cin.self_mentions", "Impact", "Self-citations (mentions)", "v_journal_citation_pairs.is_self"),
]
JOURNALS_DEFAULT = ["journal_id", "title", "title_en", "country", "issns", "n_articles", "n_mentions",
                    "cited_by_articles"]

# ------------------------------------------------------------------ cited works
WRK_WITH = [TC,
            """wa AS (SELECT cited_work_pk, count(*) n_authors, group_concat(printed, ' · ' ORDER BY seq) authors,
                  group_concat(person_id, ' ' ORDER BY seq) person_ids, count(person_id) n_authors_linked,
                  group_concat(coalesce(died, died_hijri, died_greg), ' · ') died FROM cited_work_authors GROUP BY cited_work_pk)""",
            """wc AS (SELECT cited_work_pk, group_concat(CASE WHEN role = 'editor' THEN printed END, ' · ') editors,
                  group_concat(CASE WHEN role = 'translator' THEN printed END, ' · ') translators
                FROM cited_work_contributors GROUP BY cited_work_pk)""",
            """mb AS (SELECT cited_work_pk, count(*) n_members FROM cited_work_members GROUP BY cited_work_pk)""",
            """ed AS (SELECT cited_work_pk, count(*) n_editions FROM cited_work_editions GROUP BY cited_work_pk)""",
            """lk AS (SELECT cited_work_pk, target_pub_id, status, method FROM (SELECT l.*, row_number() OVER (PARTITION
                  BY cited_work_pk ORDER BY best DESC, status = 'accepted' DESC, score DESC) r FROM citation_links l)
                WHERE r = 1)""",
            """wr AS (SELECT subject_cited_work_pk cited_work_pk, group_concat(DISTINCT relation) relations, count(*) n_relations
                FROM work_relations GROUP BY 1)""",
            """yr AS (SELECT mw.cited_work_pk, min(p.year_shown) first_cited, max(p.year_shown) last_cited
                FROM v_mention_work mw JOIN publications p ON p.pub_id = mw.citing_pub_id GROUP BY mw.cited_work_pk)""",
            """mg AS (SELECT new_id, count(*) n_merged FROM merged_ids WHERE kind = 'cited_work' GROUP BY new_id)""",
            ]
WRK_FROM = """cited_works w LEFT JOIN tc ON tc.cited_work_pk = w.cited_work_pk
  LEFT JOIN wa ON wa.cited_work_pk = w.cited_work_pk LEFT JOIN wc ON wc.cited_work_pk = w.cited_work_pk
  LEFT JOIN mb ON mb.cited_work_pk = w.cited_work_pk LEFT JOIN ed ON ed.cited_work_pk = w.cited_work_pk
  LEFT JOIN lk ON lk.cited_work_pk = w.cited_work_pk LEFT JOIN publications lp ON lp.pub_id = lk.target_pub_id
  LEFT JOIN documents ld ON ld.pub_id = lk.target_pub_id LEFT JOIN wr ON wr.cited_work_pk = w.cited_work_pk
  LEFT JOIN yr ON yr.cited_work_pk = w.cited_work_pk LEFT JOIN mg ON mg.new_id = w.cited_work_id"""
WORKS = [
    _c("cited_work_id", "w.cited_work_id", "id", "Identity", "Cited work", "cited_works.cited_work_id", "work"),
    _c("title", "w.title", "text", "Identity", "Title", "cited_works.title"),
    _c("pub_type", "w.pub_type", "text", "Identity", "Type", "cited_works.pub_type"),
    _c("status", "w.status", "text", "Identity", "Status", "cited_works.status"),
    _c("authors", "wa.authors", "text", "Authors", "Authors", "cited_work_authors.printed"),
    _n("n_authors", "wa.n_authors", "Authors", "Authors (n)", "cited_work_authors"),
    _n("n_authors_linked", "wa.n_authors_linked", "Authors", "Authors linked to a person", "cited_work_authors.person_id"),
    _c("person_ids", "wa.person_ids", "id", "Authors", "Author ids", "cited_work_authors.person_id", "person"),
    _c("died", "wa.died", "text", "Authors", "Authors' death dates", "cited_work_authors.died"),
    _c("editors", "wc.editors", "text", "Authors", "Editors (tahqiq)", "cited_work_contributors role editor"),
    _c("translators", "wc.translators", "text", "Authors", "Translators", "cited_work_contributors role translator"),
    _c("first_author_key", "w.first_author_key", "text", "Authors", "First author key", "cited_works.first_author_key"),
    _c("year_printed", "w.year_printed", "text", "Publication", "Year as printed", "cited_works.year_printed"),
    _c("year_calendar", "w.year_calendar", "text", "Publication", "Calendar", "cited_works.year_calendar"),
    _c("year_hijri", "w.year_hijri", "year", "Publication", "Year (Hijri)", "cited_works.year_hijri"),
    _c("year_greg", "w.year_greg", "year", "Publication", "Year (Gregorian)", "cited_works.year_greg"),
    _c("edition_note", "w.edition_note", "text", "Publication", "Edition", "cited_works.edition_note"),
    _c("publisher", "w.publisher", "text", "Publication", "Publisher", "cited_works.publisher"),
    _c("place", "w.place", "text", "Publication", "Place", "cited_works.place"),
    _c("lang", "w.lang", "text", "Publication", "Language", "cited_works.lang"),
    _n("n_editions", "ed.n_editions", "Publication", "Editions", "cited_work_editions"),
    _n("times_cited", "tc.n_citing_pubs", "Impact", "Times cited (articles)", "v_times_cited.n_citing_pubs"),
    _n("n_mentions", "tc.n_mentions", "Impact", "Mentions", "v_times_cited.n_mentions"),
    _n("n_full", "tc.n_full", "Impact", "Full references", "v_times_cited.n_full"),
    _n("n_backrefs", "tc.n_backrefs", "Impact", "Back references", "v_times_cited.n_backrefs"),
    _c("first_cited", "yr.first_cited", "year", "Impact", "First cited (year)", "v_mention_work -> publications"),
    _c("last_cited", "yr.last_cited", "year", "Impact", "Last cited (year)", "v_mention_work -> publications"),
    _n("n_members", "mb.n_members", "Grouping", "Printed forms grouped", "cited_work_members"),
    _c("method", "w.method", "text", "Grouping", "Grouped by", "cited_works.method"),
    _n("n_merged", "mg.n_merged", "Grouping", "Ids merged into it", "merged_ids"),
    _c("catalogue_link", "lp.pub_id", "id", "Catalogue link", "Linked catalogue record", "citation_links.target_pub_id"),
    _c("catalogue_link_title", "lp.title_shown", "text", "Catalogue link", "Linked record's title", "publications.title_shown"),
    _c("catalogue_link_stem", "ld.stem", "id", "Catalogue link", "Linked article (read)", "documents.stem", "article"),
    _c("catalogue_link_status", "lk.status", "text", "Catalogue link", "Link status", "citation_links.status"),
    _c("relations", "wr.relations", "text", "Catalogue link", "Relations", "work_relations.relation"),
]
WORKS_DEFAULT = ["cited_work_id", "title", "authors", "pub_type", "year_printed", "publisher", "times_cited",
                 "n_mentions", "catalogue_link"]

ENTITIES = {
    "articles": dict(label="Articles", one="article", key="stem", cols=ARTICLES, default=ARTICLES_DEFAULT,
                     with_=ART_WITH, from_=ART_FROM, sort=("year", "desc"),
                     about="The articles read from the scans (the current version of each)."),
    "references": dict(label="References", one="reference", key="mention_id", cols=REFERENCES,
                       default=REFERENCES_DEFAULT, with_=REF_WITH, from_=REF_FROM, sort=("stem", "asc"),
                       about="Every reference an article makes: full, short, ibid / op. cit. and Quran, as printed and parsed."),
    "persons": dict(label="Authors", one="author", key="person_id", cols=PERSONS, default=PERSONS_DEFAULT,
                    with_=PER_WITH, from_=PER_FROM, sort=("n_articles", "desc"),
                    about="Persons: authors of the articles, catalogue authorities, cited authors linked to them."),
    "institutions": dict(label="Institutions", one="institution", key="inst_id", cols=INSTITUTIONS,
                         default=INSTITUTIONS_DEFAULT, with_=INS_WITH, from_=INS_FROM, sort=("n_authors", "desc"),
                         about="Universities, faculties, departments and other bodies the bylines name."),
    "journals": dict(label="Journals", one="journal", key="journal_id", cols=JOURNALS, default=JOURNALS_DEFAULT,
                     with_=JOU_WITH, from_=JOU_FROM, sort=("n_articles", "desc"),
                     about="Mandumah's journals: titles, ISSNs, coverage, what their articles cite and who cites them."),
    "works": dict(label="Cited works", one="cited work", key="cited_work_id", cols=WORKS, default=WORKS_DEFAULT,
                  with_=WRK_WITH, from_=WRK_FROM, sort=("times_cited", "desc"),
                  about="Cited-work cards: the printed references grouped into one book, article or thesis."),
}
for _e in ENTITIES.values():
    _e["by"] = {c["name"]: c for c in _e["cols"]}
    assert len(_e["by"]) == len(_e["cols"]), "duplicate column"
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", c) for c in _e["by"])

NUMERIC = {"int", "real", "year"}
OPS = {"contains", "not_contains", "eq", "neq", "empty", "not_empty", "gt", "gte", "lt", "lte", "between"}


class ExploreError(ValueError):
    """A request named something not in the lists (a column, an operator, an entity) or a bad value: a 422."""


# ------------------------------------------------------------------ the per-state tables
@functools.lru_cache(maxsize=200_000)
def _fold(s):
    """platform v2's folding, remembered: a filter folds the same cells on every request (528 -> ~60 ms for a
    `contains` over the 14k printed references)."""
    return fold(s) if s is not None else None


_lock = threading.RLock()
_states: dict = {}            # (path, mtime) -> dict(con, built: {entity: seconds}, lock)


def _state(path: Path) -> dict:
    k = (str(path), os.path.getmtime(path))
    with _lock:
        st = _states.get(k)
        if st is None:
            for old in [x for x in _states if x[0] != k[0] or x != k]:      # one state in memory at a time
                try:
                    _states.pop(old)["con"].close()
                except Exception:
                    pass
            con = sqlite3.connect(":memory:", check_same_thread=False, uri=True)
            con.create_function("fold", 1, _fold, deterministic=True)
            st = _states[k] = dict(con=con, built={}, counts={}, path=str(path))
        return st


def _build(st: dict, path: Path, entity: str) -> None:
    """Materialise one entity's table (x_<entity>) from the state, plus `_q`, the folded text of every column for
    the quick search."""
    e = ENTITIES[entity]
    con = st["con"]
    t0 = time.time()
    con.execute("ATTACH DATABASE ? AS r", (f"file:{path}?mode=ro",))
    try:
        sel = ",\n  ".join(f"{c['expr']} AS {c['name']}" for c in e["cols"])
        sql = f"CREATE TABLE x_{entity} AS WITH {', '.join(e['with_'])}\nSELECT {sel}\nFROM {e['from_']}"
        # experiment 68: an affiliation printed again in the other script (twin_of_aff_pk) is not counted twice
        twins = "twin_of_aff_pk" in {r[1] for r in con.execute("PRAGMA r.table_info(affiliation_mentions)")}
        sql = sql.replace("/*TW*/", "AND f.twin_of_aff_pk IS NULL" if twins else "")
        con.execute(sql)
    finally:
        con.commit()
        con.execute("DETACH DATABASE r")
    texts = [c["name"] for c in e["cols"] if c["type"] in ("text", "id")]
    con.execute(f"ALTER TABLE x_{entity} ADD COLUMN _q TEXT")
    con.execute(f"UPDATE x_{entity} SET _q = fold(" + " || ' ' || ".join(f"coalesce({c}, '')" for c in texts) + ")")
    con.commit()
    st["built"][entity] = round(time.time() - t0, 2)
    st["counts"][entity] = con.execute(f"SELECT count(*) FROM x_{entity}").fetchone()[0]


def table(path: Path, entity: str) -> tuple[sqlite3.Connection, dict]:
    if entity not in ENTITIES:
        raise ExploreError(f"unknown entity {entity!r}; one of {', '.join(ENTITIES)}")
    st = _state(path)
    with _lock:
        if entity not in st["built"]:
            _build(st, path, entity)
    return st["con"], st


def warm(path: Path) -> dict:
    for ent in ENTITIES:
        table(path, ent)
    return dict(_state(path)["built"])


# ------------------------------------------------------------------ queries
def _num(v, col):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ExploreError(f"{col}: {v!r} is not a number")
    return int(x) if x.is_integer() else x


def where(entity: str, q: str | None, filters: list | None) -> tuple[str, list]:
    e = ENTITIES[entity]
    parts, args = [], []
    if q and q.strip():
        parts.append("instr(_q, fold(?)) > 0")
        args.append(q.strip()[:200])
    for f in filters or []:
        if not isinstance(f, dict):
            raise ExploreError("a filter is {c, op, v}")
        c, op, v = f.get("c"), f.get("op"), f.get("v")
        col = e["by"].get(c)
        if col is None:
            raise ExploreError(f"unknown column {c!r} for {entity}")
        if op not in OPS:
            raise ExploreError(f"unknown operator {op!r}; one of {', '.join(sorted(OPS))}")
        num = col["type"] in NUMERIC
        name = col["name"]                     # from the list, never from the request
        if op == "empty":
            parts.append(f"({name} IS NULL OR {name} = '')")
        elif op == "not_empty":
            parts.append(f"({name} IS NOT NULL AND {name} <> '')")
        elif op in ("contains", "not_contains"):
            if v is None or str(v) == "":
                continue
            expr = f"instr(fold(CAST({name} AS TEXT)), fold(?)) > 0"
            parts.append(expr if op == "contains" else f"NOT coalesce({expr}, 0)")
            args.append(str(v)[:200])
        elif op in ("eq", "neq"):
            if v is None:
                v = ""
            if num and str(v) != "":
                expr = f"{name} = ?"
                args.append(_num(v, name))
            elif str(v) == "":
                expr = f"({name} IS NULL OR {name} = '')"
            else:
                expr = f"fold(CAST({name} AS TEXT)) = fold(?)"
                args.append(str(v)[:400])
            parts.append(expr if op == "eq" else f"NOT coalesce({expr}, 0)")
        else:
            if not (num or col["type"] == "date"):
                raise ExploreError(f"{name} is text: use contains / equals / empty")
            conv = (lambda x: _num(x, name)) if num else (lambda x: str(x)[:40])
            if op == "between":
                if not isinstance(v, (list, tuple)) or len(v) != 2:
                    raise ExploreError("between takes [from, to]")
                lo, hi = v
                if lo not in (None, ""):
                    parts.append(f"{name} >= ?")
                    args.append(conv(lo))
                if hi not in (None, ""):
                    parts.append(f"{name} <= ?")
                    args.append(conv(hi))
            else:
                if v in (None, ""):
                    continue
                parts.append(f"{name} {dict(gt='>', gte='>=', lt='<', lte='<=')[op]} ?")
                args.append(conv(v))
    return (" WHERE " + " AND ".join(parts)) if parts else "", args


def _cols(entity: str, cols) -> list[str]:
    e = ENTITIES[entity]
    if not cols:
        return list(e["default"])
    out = []
    for c in cols:
        if c not in e["by"]:
            raise ExploreError(f"unknown column {c!r} for {entity}")
        if c not in out:
            out.append(c)
    if e["key"] not in out:
        out.insert(0, e["key"])
    return out


def _order(entity: str, sort: str | None, desc: bool | None) -> str:
    e = ENTITIES[entity]
    if not sort:
        sort, d = e["sort"]
        desc = d == "desc" if desc is None else desc
    if sort not in e["by"]:
        raise ExploreError(f"unknown column {sort!r} for {entity}")
    d = "DESC" if desc else "ASC"
    # empties last whichever way, then the key, so pages are stable
    return f" ORDER BY ({sort} IS NULL OR {sort} = '') ASC, {sort} {d}, {e['key']} ASC"


def query(path: Path, entity: str, cols=None, sort=None, desc=None, q=None, filters=None, offset=0, limit=50) -> dict:
    t0 = time.time()
    con, st = table(path, entity)
    cols = _cols(entity, cols)
    w, args = where(entity, q, filters)
    order = _order(entity, sort, desc)
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    with _lock:
        total = con.execute(f"SELECT count(*) FROM x_{entity}{w}", args).fetchone()[0]
        rows = con.execute(f"SELECT {', '.join(cols)} FROM x_{entity}{w}{order} LIMIT ? OFFSET ?",
                           args + [limit, offset]).fetchall()
    return dict(entity=entity, columns=cols, rows=[list(r) for r in rows], total=total, offset=offset, limit=limit,
                n_all=st["counts"][entity], ms=round((time.time() - t0) * 1000, 1))


def group(path: Path, entity: str, by: str, q=None, filters=None, measure: str | None = None, limit=200) -> dict:
    """Counts per value of one column (and the sum of a numeric `measure` per value), biggest first."""
    t0 = time.time()
    con, st = table(path, entity)
    e = ENTITIES[entity]
    if by not in e["by"]:
        raise ExploreError(f"unknown column {by!r} for {entity}")
    if measure is not None and (measure not in e["by"] or e["by"][measure]["type"] not in NUMERIC):
        raise ExploreError(f"measure must be a numeric column of {entity}")
    w, args = where(entity, q, filters)
    m = f", sum({measure})" if measure else ", NULL"
    limit = max(1, min(int(limit), 1000))
    with _lock:
        n_groups, total = con.execute(f"SELECT count(DISTINCT coalesce({by}, '')), count(*) FROM x_{entity}{w}",
                                      args).fetchone()
        rows = con.execute(f"SELECT CASE WHEN {by} = '' THEN NULL ELSE {by} END v, count(*) n{m} FROM x_{entity}{w} "
                           f"GROUP BY v ORDER BY n DESC, v LIMIT ?", args + [limit]).fetchall()
    return dict(entity=entity, by=by, measure=measure, groups=[dict(value=r[0], n=r[1], sum=r[2]) for r in rows],
                n_groups=n_groups, total=total, ms=round((time.time() - t0) * 1000, 1))


def csv_rows(path: Path, entity: str, cols=None, sort=None, desc=None, q=None, filters=None, max_rows=250_000):
    """The whole current view as CSV (UTF-8 with a BOM, so spreadsheet programs read the Arabic), in chunks."""
    con, st = table(path, entity)
    cols = _cols(entity, cols)
    w, args = where(entity, q, filters)
    order = _order(entity, sort, desc)
    e = ENTITIES[entity]
    with _lock:
        rows = con.execute(f"SELECT {', '.join(cols)} FROM x_{entity}{w}{order} LIMIT ?", args + [max_rows]).fetchall()
    buf = io.StringIO()
    wr = csv.writer(buf)
    buf.write("﻿")
    wr.writerow([e["by"][c]["label"] for c in cols])
    yield buf.getvalue()
    for i in range(0, len(rows), 2000):
        buf = io.StringIO()
        csv.writer(buf).writerows(rows[i:i + 2000])
        yield buf.getvalue()


def meta(path: Path | None = None) -> dict:
    out = {}
    st = _states.get((str(path), os.path.getmtime(path))) if path else None
    for k, e in ENTITIES.items():
        out[k] = dict(label=e["label"], one=e["one"], key=e["key"], default=e["default"], sort=list(e["sort"]),
                      about=e["about"], n=(st or {}).get("counts", {}).get(k),
                      columns=[{x: c[x] for x in ("name", "type", "group", "label", "src", "ref")} for c in e["cols"]])
    return out


def parse_filters(f: str | None) -> list:
    if not f:
        return []
    try:
        v = json.loads(f)
    except ValueError:
        raise ExploreError("f must be a JSON list of {c, op, v}")
    if not isinstance(v, list) or len(v) > 30:
        raise ExploreError("f must be a JSON list of at most 30 filters")
    return v


def parse_cols(c: str | None) -> list | None:
    if not c:
        return None
    cols = [x for x in c.split(",") if x]
    if len(cols) > 200:
        raise ExploreError("too many columns")
    return cols
