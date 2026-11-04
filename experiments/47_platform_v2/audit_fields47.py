"""Experiment 47, v3.5b fields (2026-10-22): which extracted field is in the platform database, and where.

For every field of experiment 51's homes.json, count the masters whose JATS (or ALTO) slot is filled — the 600 of the
two `_lettersfix` runs and the journal's 126 (`j0130_final`, prompt v3.5b) — and say where the platform database holds
it: before this work (the loader as of 2026-10-21) and now, with a row count from the database when one is given.

    .venv/bin/python experiments/47_platform_v2/audit_fields47.py [--db /home/appuser/data/platform_v2/platform_v2.db]
        -> experiments/47_platform_v2/out/field_audit.json, field_audit.md
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
HOMES = REPO / "experiments" / "51_extraction_inventory" / "out" / "homes.json"
SETS = {
    "600": [REPO / "experiments/43_rehearsal/out/v33_300_final_lettersfix/masters",
            REPO / "experiments/43_rehearsal/out/v33_300b_fix3_lettersfix/masters"],
    "j0130": [REPO / "experiments/52_journal_gate1/out/j0130_final/masters"],
}
XL = "{http://www.w3.org/1999/xlink}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
EC = "//element-citation"

# field id -> how its slot is counted: an XPath over the JATS (elements per article), ("alto", label), ("text", regex
# over the article's text) or None (no slot of its own: the field is a structure, a derived value or not in the files)
SPEC = {
    "x001": "//article-meta/title-group/article-title", "x002": "//title-group/alt-title[@alt-title-type='printed']",
    "x003": "//title-group/subtitle", "x004": "//trans-title-group/trans-title",
    "x005": "//title-group/alt-title[@alt-title-type='running-head']", "x006": "//journal-meta//journal-title",
    "x007": "//article-meta/volume", "x008": "//article-meta/issue", "x009": "//article-meta/pub-date/year",
    "x010": "//article-meta/pub-date/month | //article-meta/pub-date/season | //article-meta/pub-date/string-date",
    "x011": "//article-meta/fpage", "x012": "//article-meta/article-id[@pub-id-type='doi']",
    "x013": "//journal-meta/issn", "x014": "//article-meta/isbn | //journal-meta/isbn",
    "x015": "//journal-meta/publisher", "x016": "//custom-meta[meta-name='how-to-cite']", "x017": "/article[@xml:lang]",
    "x018": "//elocation-id", "x019": "//counts/page-count", "x020": "//pub-date[@date-type='reprint']",
    "x021": "//contrib-group/contrib", "x022": "//contrib//prefix | //contrib/degrees", "x023": "//contrib/name",
    "x024": "//contrib/name-alternatives/string-name[@xml:lang]",
    "x025": "//contrib/role | //contrib[@contrib-type and @contrib-type!='author']",
    "x026": "//contrib[@corresp] | //author-notes/corresp", "x027": "//contrib/email",
    "x028": "//contrib/contrib-id[@contrib-id-type='orcid']",
    "x029": "//contrib/contrib-id[@contrib-id-type!='orcid']",
    "x030": "//contrib-id[@contrib-id-type='mandumah-authority']", "x031": "//contrib/aff",
    "x032": "//aff/role | //contrib/role[@content-type='position']", "x033": "//aff/institution[@content-type='dept']",
    "x034": "//aff/institution[@content-type='faculty']", "x035": "//aff/institution[@content-type='orgname']",
    "x036": "//aff/addr-line[@content-type='city']", "x037": "//aff/country", "x038": "//institution-id",
    "x039": "//contrib[count(aff) > 1] | //contrib/xref[@ref-type='aff']", "x040": "//author-notes/fn",
    "x041": "//contrib[@equal-contrib]", "x042": "//contrib[@deceased]",
    "x043": "//contrib/bio | //fig[@fig-type='portrait']", "x044": "//contrib/collab", "x045": "//sig-block | //sig",
    "x046": "//history/date[@date-type='received']", "x047": "//history/date[@date-type='rev-recd']",
    "x048": "//history/date[@date-type='accepted']", "x049": "//article-meta/pub-date",
    "x050": "//pub-date[@calendar] | //pub-date[@iso-8601-date] | //history/date[@iso-8601-date]",
    "x051": "//permissions/copyright-statement", "x052": "//permissions/license", "x053": "//permissions/license",
    "x054": "//funding-source", "x055": "//award-id", "x056": "//funding-statement", "x057": "//back/ack",
    "x058": "//fn[@fn-type='coi-statement']", "x059": "//sec[@sec-type='ethics-statement']",
    "x060": "//sec[@sec-type='data-availability'] | //fn[@fn-type='con']",
    "x061": "//article-categories/subj-group[@subj-group-type='document-type']/subject",
    "x062": "/article[@article-type='review-article']", "x063": "//article-meta/conference",
    "x064": "//article-meta/product[@product-type='thesis']",
    "x065": "//related-article[@related-article-type='derived-from']",
    "x066": "//article-meta/product[@product-type='book']",
    "x067": "//related-article[@related-article-type='translated-from' or @related-article-type='translation-of']",
    "x068": "//custom-meta[meta-name='series-part'] | //related-article[@related-article-type='continues']",
    "x069": "//custom-meta[meta-name='incomplete']",
    "x070": "//subj-group[@subj-group-type='document-type']/subject[.='front_matter']",
    "x071": "//article-categories/subj-group[not(@subj-group-type='document-type')]", "x072": "//counts/ref-count",
    "x073": "//custom-meta[meta-name='counts']", "x074": "//article-meta/abstract",
    "x075": "//article-meta/trans-abstract", "x076": "//abstract/sec", "x077": "//kwd-group/kwd",
    "x078": "//kwd-group[@kwd-group-type='index']", "x079": "//kwd-group[@vocab='JEL']", "x080": "//abstract/title",
    "x081": "//sec/title", "x082": "//sec/label", "x083": "//sec[@sec-type='intro']",
    "x084": "//sec[@sec-type='problem' or @sec-type='questions' or @sec-type='hypotheses' or @sec-type='aims']",
    "x085": "//sec[@sec-type='literature-review']", "x086": "//sec[@sec-type='definitions'] | //def-list",
    "x087": "//sec[@sec-type='methods']", "x088": "//sec[@sec-type='results' or @sec-type='discussion']",
    "x089": "//sec[@sec-type='conclusions']", "x090": "//sec[@sec-type='recommendations']",
    "x091": "//back/app-group/app", "x092": "//glossary", "x093": "//body//p", "x094": "//list",
    "x095": "//disp-quote", "x096": "//disp-quote/attrib", "x097": "//named-content[@content-type='quote']",
    "x098": "//boxed-text", "x099": "//body", "x100": None, "x101": None,
    "x102": "//disp-quote[@content-type='epigraph']", "x103": "//speech | //speaker",
    "x104": "//*[@content-type='added']", "x105": "//code",
    "x106": "//fn-group[@content-type='footnotes']/fn", "x107": "//fn-group[@content-type='endnotes']/fn",
    "x108": "//xref[@ref-type='fn']", "x109": "//fn/label",
    "x110": "//fn[@fn-type='custom'][@custom-type='translator' or @custom-type='editor' or @custom-type='publisher']",
    "x111": "//table-wrap-foot//p[@content-type='table-note'] | //table-wrap-foot/fn | "
            "//fig/p[@content-type='figure-note']",
    "x112": "//p[@content-type='source'] | //table-wrap-foot/attrib",
    "x113": "//ref-list/ref/mixed-citation", "x114": "//fn//element-citation",
    "x115": EC + "[@publication-type]", "x116": EC + "/person-group[@person-group-type='author']/name",
    "x117": EC + "/comment[@content-type='death-date']",
    "x118": EC + "/person-group[@person-group-type='editor']",
    "x119": EC + "/person-group[@person-group-type='translator']", "x120": EC + "/edition",
    "x121": EC + "/year[@calendar]", "x122": EC + "/article-title | " + EC + "/source",
    "x123": EC + "/source", "x124": EC + "/series", "x125": EC + "/volume", "x126": EC + "/issue",
    "x127": EC + "/page-range[@content-type='cited-pages']", "x128": EC + "/publisher-name",
    "x129": EC + "/publisher-loc", "x130": EC + "/comment[not(@content-type)]",
    "x131": EC + "/pub-id[@pub-id-type='doi']", "x132": EC + "/ext-link",
    "x133": EC + "/date-in-citation[@content-type='access-date']", "x134": EC + "/pub-id[@pub-id-type='isbn']",
    "x135": EC + "/comment[@content-type='degree']",
    "x136": EC + "/conf-name",
    "x137": EC + "[@publication-type='manuscript'] | " + EC + "/institution[@content-type='library'] | " + EC +
            "/comment[@content-type='shelfmark'] | " + EC + "/page-range[@content-type='folio']",
    "x138": EC + "[@publication-type='archive']", "x139": EC + "[@publication-type='law']",
    "x140": None, "x141": None, "x142": "//xref[@ref-type='bibr']", "x143": "//xref[@ref-type='bibr']",
    "x144": EC + "[@publication-type='quran']", "x145": EC + "[@publication-type='hadith']", "x146": None,
    "x147": "//xref[@ref-type='fn']", "x148": "//table-wrap/table", "x149": "//td[@colspan or @rowspan] | "
    "//th[@colspan or @rowspan]", "x150": "//table-wrap/caption | //table-wrap/label", "x151": None,
    "x152": "//td[@content-type='added']", "x153": "//table-wrap[@orientation]", "x154": "//table-wrap/graphic",
    "x155": "//fig/graphic", "x156": "//fig/caption | //fig/label", "x157": "//fig/alt-text",
    "x158": "//fig[@fig-type]", "x159": "//fig//p[@content-type='text-in-figure']",
    "x160": "//fig/alternatives/table", "x161": "//fig-group", "x162": "//xref[@ref-type='fig' or @ref-type='table']",
    "x163": "//disp-formula", "x164": "//inline-formula", "x165": "//disp-formula/label", "x166": "//chem-struct",
    "x167": None, "x168": "//verse-group", "x169": "//verse-group[@content-type]", "x170": "//verse-group/attrib",
    "x171": "//disp-quote[@content-type='quran']", "x172": "//named-content[@content-type='quran']",
    "x173": "//named-content[@content-type='quran'][@specific-use]",
    "x174": "//named-content[@content-type='hadith']", "x175": None,
    "x176": ("text", "[ﷺﷻﷲ﷽]"), "x177": ("text", "صلى الله عليه وسلم|رضي الله عن"),
    "x178": ("text", "[ًٌٍَُِّْ]"), "x179": ("text", "[پچژگ]"), "x180": ("text", "[یک]"),
    "x181": "//body//*[@xml:lang][not(self::p)][not(self::sec)][not(self::title)]",
    "x182": "//named-content[@content-type='date']", "x183": "//named-content[@content-type='date']",
    "x184": "//named-content[@content-type='death-date']", "x185": None, "x186": ("text", "[Ͱ-Ͽ֐-׿܀-ݏ]"),
    "x187": ("alto", "ornament"), "x188": ("text", "ـ"), "x189": None, "x190": None,
    "x191": "//italic", "x192": "//bold", "x193": "//underline", "x194": "//sup", "x195": "//sub", "x196": "//sc",
    "x197": "//styled-content", "x198": ("alto-style", None), "x199": "//sec/title[@content-type]", "x200": None,
    "x201": "//custom-meta[meta-name='text-direction']", "x202": None, "x203": ("alto-graphical", None),
    "x204": ("alto", "pageHeader"), "x205": ("alto", "pageFooter"), "x206": ("alto", "pageNumber"),
    "x207": ("alto-printed-nr", None), "x208": ("alto", "otherArticle"), "x209": ("alto", "showThrough"),
    "x210": ("alto", "noise"), "x211": "//fig[@fig-type='logo']", "x212": "//fig[@fig-type='advert']",
    "x213": "//fig[@fig-type='stamp'] | //custom-meta[meta-name='stamp-lines']",
    "x214": "//custom-meta[meta-name='handwriting-lines']", "x215": "//sig | //fig[@fig-type='signature']",
    "x216": "//custom-meta[meta-name='scan-problem']", "x217": None, "x218": "//body//*[@xml:lang]",
    "x219": "//body//*[@xml:lang]", "x220": "//sec/sec", "x221": "//body//p", "x222": "//target",
    "x223": "//sec[@sec-type='literature-review']", "x224": "/article[@article-type='review-article']",
    "x225": "//disp-quote", "x226": "//xref[@ref-type='fn']", "x227": "//fn//element-citation",
    "x228": "//table-wrap/table", "x229": "//fig/alt-text", "x230": "//body//*[@xml:lang]", "x231": ("alto-wc", None),
    "x232": "//front", "x233": ("alto", "pageNumber"),
    "x234": "//named-content[@content-type='reader-fix']", "x235": "//named-content[@content-type='sic']",
}

# Where the platform holds each field. before = the loader of 2026-10-21 (load47 / parse47 / biblio47 / link47);
# now = after the v3.5b-fields work of 2026-10-22; sql = a count in the database of what landed (shown versions).
CUR = "versions v ON v.version_id = {t}.version_id AND v.is_current = 1"
PLAT = {
    "x001": ("metadata_assertions field title (printed)", None, None),
    "x002": ("metadata_assertions title form printed + corrected (D33)", None, None),
    "x003": ("metadata_assertions subtitle", None, None),
    "x004": ("metadata_assertions title_translated", None, None),
    "x006": ("metadata_assertions journal_title; journal_titles", None, None),
    "x007": ("metadata_assertions volume", None, None), "x008": ("metadata_assertions issue", None, None),
    "x009": ("metadata_assertions year; publication_dates (both calendars)", None, None),
    "x010": ("publication_dates (month from iso; printed string)", None, None),
    "x011": ("metadata_assertions fpage / lpage", None, None),
    "x012": ("metadata_assertions doi; external_ids scheme doi", None, None),
    "x017": ("metadata_assertions language; publication_languages", None, None),
    "x019": ("documents.scan_pages; versions.pages_expected", None, None),
    "x021": ("byline_mentions.printed / name_text; authorships; persons", None, None),
    "x022": ("byline_mentions.titles (from the printed string; no JATS prefix)", None, None),
    "x023": ("person_names (ism, nasab ... derived)", None, None),
    "x024": ("missing (the twin is folded into the Arabic contrib's name-alternatives; parse46 reads the main name "
             "only)", "byline_mentions row of script Latn with twin_of_pk -> the main mention; both in "
                     "authorship_mentions (one person)",
             "SELECT count(*) FROM byline_mentions b JOIN " + CUR.format(t="b") + " WHERE b.twin_of_pk IS NOT NULL"),
    "x025": ("missing (the printed contrib-type and role phrase: authorships.role_code comes from the catalogue only)",
             "byline_mentions.contrib_type, role_phrase",
             "SELECT count(*) FROM byline_mentions b JOIN " + CUR.format(t="b") +
             " WHERE b.contrib_type <> 'author' OR b.role_phrase IS NOT NULL"),
    "x026": ("missing (authorships.is_corresponding always 0)", "byline_mentions.is_corresponding; "
             "authorships.is_corresponding",
             "SELECT count(*) FROM byline_mentions b JOIN " + CUR.format(t="b") + " WHERE b.is_corresponding = 1"),
    "x027": ("byline_mentions.email", None, None),
    "x028": ("missing", "byline_mentions.ids (as printed); external_ids entity_kind A scheme orcid on the person",
             "SELECT count(*) FROM external_ids WHERE entity_kind = 'A' AND scheme = 'orcid'"),
    "x029": ("missing", "byline_mentions.ids; external_ids entity_kind A (scopus | researcherid | scholar)",
             "SELECT count(*) FROM external_ids WHERE entity_kind = 'A' AND scheme <> 'orcid'"),
    "x031": ("affiliation_mentions.printed; affiliation_links -> institutions", None, None),
    "x033": ("affiliation_mentions.dept_text", None, None),
    "x034": ("partly: affiliation_mentions.faculty_text is inst46's reading of the printed string; the reader's "
             "faculty slot was not read (parse46 joins it into org_text)",
             "affiliation_mentions.faculty_printed (the reader's faculty, apart from dept_text; org_text unchanged so "
             "the institutions stay the same) beside faculty_text",
             "SELECT count(*) FROM affiliation_mentions a JOIN byline_mentions b USING (mention_pk) JOIN " +
             CUR.format(t="b") + " WHERE a.faculty_printed IS NOT NULL"),
    "x035": ("affiliation_mentions.org_text", None, None), "x036": ("affiliation_mentions.city", None, None),
    "x037": ("affiliation_mentions.country_printed / country_code", None, None),
    "x039": ("affiliation_mentions (seq per author; an additional aff was read as a second one)",
             "affiliation_mentions.seq + assembled = 1 for an aff the reader gave in parts (aff content-type "
             "additional)",
             "SELECT count(*) FROM affiliation_mentions a JOIN byline_mentions b USING (mention_pk) JOIN " +
             CUR.format(t="b") + " WHERE a.assembled = 1"),
    "x040": ("notes (kind footnote; the author-notes home not told apart)",
             "notes.kind = 'author-note'",
             "SELECT count(*) FROM notes n JOIN " + CUR.format(t="n") + " WHERE n.kind = 'author-note'"),
    "x043": ("missing", "figures.fig_type portrait (the author's photo; no bio is filled)",
             "SELECT count(*) FROM figures f JOIN " + CUR.format(t="f") + " WHERE f.fig_type = 'portrait'"),
    "x046": ("publication_dates date_type received", None, None),
    "x047": ("publication_dates date_type rev-recd", None, None),
    "x048": ("publication_dates date_type accepted", None, None),
    "x049": ("publication_dates date_type published", None, None),
    "x050": ("publication_dates (calendar, pair_pk: both calendars)", None, None),
    "x057": ("blocks / sections (back matter)", None, None),
    "x061": ("missing (publications.type is the catalogue's 336 only)",
             "metadata_assertions field doc_type: form reader (the page) + form catalogue (MARC 336); "
             "publications.doc_type / doc_type_source (the shown one); catalogue_reports kind document-type",
             "SELECT count(*) FROM metadata_assertions WHERE field = 'doc_type' AND form = 'reader'"),
    "x062": ("missing", "as x061 (doc_type = review)",
             "SELECT count(*) FROM metadata_assertions WHERE field = 'doc_type' AND form = 'reader' AND value = 'review'"),
    "x063": ("missing", "metadata_assertions conference.name / conference.place / conference.date (form printed)",
             "SELECT count(DISTINCT pub_id) FROM metadata_assertions WHERE field LIKE 'conference.%'"),
    "x064": ("missing", "metadata_assertions thesis.degree / university / year / supervisor (form printed)",
             "SELECT count(DISTINCT pub_id) FROM metadata_assertions WHERE field LIKE 'thesis.%'"),
    "x066": ("missing", "metadata_assertions reviewed_book.* (title, authors, publisher, place, year ...)",
             "SELECT count(DISTINCT pub_id) FROM metadata_assertions WHERE field LIKE 'reviewed_book.%'"),
    "x067": ("missing", "metadata_assertions original.title / author / source / lang",
             "SELECT count(DISTINCT pub_id) FROM metadata_assertions WHERE field LIKE 'original.%'"),
    "x068": ("missing", "metadata_assertions series_part",
             "SELECT count(*) FROM metadata_assertions WHERE field = 'series_part'"),
    "x070": ("missing", "as x061 (doc_type = front_matter)", None),
    "x073": ("pages.wc_mean / wc_min; blocks.trust (from ALTO, not the custom-meta)", None, None),
    "x074": ("abstracts (form printed)", None, None), "x075": ("abstracts (lang)", None, None),
    "x077": ("publication_keywords; keyword_terms", None, None), "x080": ("blocks (role abstract)", None, None),
    "x081": ("sections.heading / level", None, None),
    "x091": ("blocks / sections (back matter)", None, None), "x093": ("blocks (role paragraph)", None, None),
    "x094": ("blocks (role list-item)", None, None), "x095": ("blocks (role quote)", None, None),
    "x098": ("blocks (boxed text: role paragraph, JATS id)", None, None),
    "x099": ("blocks.ord", None, None),
    "x100": ("blocks.page / last_page; block_parts (one per page)", None, None),
    "x104": ("blocks.text (the 'added' mark lives in the JATS only)", None, None),
    "x106": ("notes (kind footnote)", None, None), "x107": ("notes (kind endnote)", None, None),
    "x108": ("note_calls, note_call_targets", None, None), "x109": ("notes.label / label_int", None, None),
    "x110": ("missing", "notes.written_by (translator | editor | publisher; NULL = the author's)",
             "SELECT count(*) FROM notes n JOIN " + CUR.format(t="n") + " WHERE n.written_by IS NOT NULL"),
    "x111": ("blocks only (the note's paragraph, not tied to its table)",
             "figure_notes (kind table-note | figure-note | footnote) -> figures (the table or figure)",
             "SELECT count(*) FROM figure_notes f JOIN " + CUR.format(t="f") + " WHERE f.kind <> 'source'"),
    "x112": ("blocks only", "figure_notes kind source -> its table or figure",
             "SELECT count(*) FROM figure_notes f JOIN " + CUR.format(t="f") + " WHERE f.kind = 'source'"),
    "x113": ("citation_mentions (container ref-list) -> cited_works", None, None),
    "x114": ("citation_mentions (container note) -> cited_works", None, None),
    "x115": ("citation_mentions.parsed pub_type; cited_works.pub_type", None, None),
    "x116": ("citation_mentions.parsed authors; cited_work_authors", None, None),
    "x117": ("missing (parse46 keeps one comment in parsed.extra; not tied to the author)",
             "citation_mentions.died; citation_mention_people.died; cited_work_authors.died / died_hijri / died_greg",
             "SELECT count(*) FROM citation_mention_people p JOIN citation_mentions m USING (mention_pk) JOIN " +
             CUR.format(t="m") + " WHERE p.died IS NOT NULL"),
    "x118": ("WRONG (parse46 reads every name of the citation, so an editor became a co-author)",
             "citation_mention_people role editor; cited_work_authors role editor (authors no longer include them)",
             "SELECT count(DISTINCT p.mention_pk) FROM citation_mention_people p JOIN citation_mentions m USING "
             "(mention_pk) JOIN " + CUR.format(t="m") + " WHERE p.role = 'editor'"),
    "x119": ("WRONG (as x118: a translator read as a co-author)",
             "citation_mention_people role translator; cited_work_authors role translator",
             "SELECT count(DISTINCT p.mention_pk) FROM citation_mention_people p JOIN citation_mentions m USING "
             "(mention_pk) JOIN " + CUR.format(t="m") + " WHERE p.role = 'translator'"),
    "x120": ("partly: citation_mentions.parsed extra.edition; cited_works.edition_note from the representative only",
             "citation_mentions.edition; cited_work_editions (one row per edition of a work, each member points at "
             "its edition: cited_work_members.edition_pk); cited_works.edition_note",
             "SELECT count(*) FROM citation_mentions m JOIN " + CUR.format(t="m") + " WHERE m.edition IS NOT NULL"),
    "x121": ("partly: one year (parse46 kept the LAST year element: a second year replaced the first); "
             "cited_works.year_calendar guessed from the print",
             "citation_mentions.year_calendar + year2 (both values as printed); cited_work_editions.year_calendar / "
             "year2",
             "SELECT count(*) FROM citation_mentions m JOIN " + CUR.format(t="m") + " WHERE m.year_calendar IS NOT NULL"),
    "x122": ("citation_mentions.parsed; cited_works.title", None, None),
    "x123": ("citation_mentions.parsed source_title", None, None),
    "x124": ("citation_mentions.parsed series", None, None), "x125": ("citation_mentions.parsed volume", None, None),
    "x126": ("citation_mentions.parsed issue", None, None),
    "x127": ("WRONG for v3.5b (the cited page and the work's range share parsed.page_range: the last one won)",
             "citation_mentions.cited_pages (the page referred to) apart from work_pages (the work's own range)",
             "SELECT count(*) FROM citation_mentions m JOIN " + CUR.format(t="m") + " WHERE m.cited_pages_source = "
             "'cited-pages'"),
    "x128": ("citation_mentions.parsed publisher; cited_works.publisher", None, None),
    "x129": ("citation_mentions.parsed place; cited_works.place", None, None),
    "x131": ("citation_mentions.parsed doi", None, None), "x132": ("citation_mentions.parsed url", None, None),
    "x133": ("partly: parsed.extra date-in-citation", "citation_mentions.access_date",
             "SELECT count(*) FROM citation_mentions m JOIN " + CUR.format(t="m") + " WHERE m.access_date IS NOT NULL"),
    "x135": ("partly: parsed.extra comment (one per citation, overwritten)", "citation_mentions.thesis_degree",
             "SELECT count(*) FROM citation_mentions m JOIN " + CUR.format(t="m") + " WHERE m.thesis_degree IS NOT NULL"),
    "x136": ("partly: parsed.extra conf-name", "citation_mentions.conf_name / conf_loc",
             "SELECT count(*) FROM citation_mentions m JOIN " + CUR.format(t="m") + " WHERE m.conf_name IS NOT NULL"),
    "x137": ("partly: parsed.extra", "citation_mentions.ms_library / ms_shelfmark / ms_folio",
             "SELECT count(*) FROM citation_mentions m JOIN " + CUR.format(t="m") + " WHERE coalesce(m.ms_library, "
             "m.ms_shelfmark, m.ms_folio) IS NOT NULL"),
    "x140": ("citation_mentions.full_mention_pk (link47)", None, None),
    "x141": ("citation_mentions.full_mention_pk (link47)", None, None),
    "x147": ("note_calls (block, char offset)", None, None),
    "x148": ("figures kind table; table_cells", None, None), "x149": ("table_cells.rowspan / colspan", None, None),
    "x150": ("figures.label / caption", None, None), "x152": ("table_cells.text", None, None),
    "x154": ("figures.crop_key", None, None),
    "x155": ("figures (box, crop_key)", None, None), "x156": ("figures.label / caption", None, None),
    "x157": ("figures.alt_ar / alt_en; search_units", None, None),
    "x158": ("missing (figures.specific_use only)", "figures.fig_type",
             "SELECT count(*) FROM figures f JOIN " + CUR.format(t="f") + " WHERE f.fig_type IS NOT NULL"),
    "x159": ("figures.text_in_figure; search_units", None, None),
    "x163": ("figures kind equation (tex, mathml)", None, None),
    "x164": ("figures kind inline-equation", None, None),
    "x168": ("verse_lines", None, None),
    "x176": ("blocks.text (as printed)", None, None), "x177": ("blocks.text", None, None),
    "x178": ("blocks.text", None, None), "x179": ("blocks.text", None, None),
    "x180": ("text_corrections (layer azure-misread, the letter fix: Azure's word kept)", None, None),
    "x181": ("blocks.lang", None, None), "x186": ("blocks.text", None, None),
    "x187": ("page_regions role ornament", None, None), "x188": ("blocks.text", None, None),
    "x199": ("sections.level", None, None), "x201": ("blocks.lang", None, None),
    "x204": ("page_regions pageHeader; pages.running_head", None, None),
    "x205": ("page_regions pageFooter", None, None),
    "x206": ("page_regions pageNumber; pages.printed_folio", None, None),
    "x208": ("page_regions otherArticle", None, None), "x209": ("page_regions showThrough", None, None),
    "x210": ("page_regions noise", None, None),
    "x211": ("missing", "figures.fig_type logo", None), "x212": ("missing", "figures.fig_type advert", None),
    "x213": ("missing", "figures.fig_type stamp; page_marks kind stamp",
             "SELECT count(*) FROM page_marks p JOIN " + CUR.format(t="p") + " WHERE p.kind = 'stamp'"),
    "x214": ("missing", "page_marks kind handwriting (one row per line, its ink)",
             "SELECT count(*) FROM page_marks p JOIN " + CUR.format(t="p") + " WHERE p.kind = 'handwriting'"),
    "x216": ("missing", "page_marks kind scan-problem (page, problem)",
             "SELECT count(*) FROM page_marks p JOIN " + CUR.format(t="p") + " WHERE p.kind = 'scan-problem'"),
    "x218": ("blocks.lang", None, None), "x219": ("blocks.lang", None, None), "x220": ("sections.parent_id", None, None),
    "x221": ("blocks.role", None, None), "x222": ("ink_anchors; block_parts", None, None),
    "x224": ("missing", "as x061", None), "x225": ("blocks (role quote)", None, None),
    "x226": ("note_calls -> notes", None, None), "x227": ("note_calls -> citation_mentions", None, None),
    "x228": ("table_cells", None, None), "x229": ("figures.alt_ar / alt_en", None, None),
    "x230": ("blocks.lang", None, None), "x231": ("blocks.wc_mean / wc_min / trust; flags", None, None),
    "x232": ("blocks.role / sections", None, None), "x233": ("page_regions", None, None),
    "x234": ("text_corrections layer azure-misread", None,
             "SELECT count(*) FROM text_corrections c JOIN " + CUR.format(t="c") + " WHERE c.layer = 'azure-misread'"),
    "x235": ("text_corrections layer misprint", None,
             "SELECT count(*) FROM text_corrections c JOIN " + CUR.format(t="c") + " WHERE c.layer = 'misprint'"),
}


def alto_counts(path: Path) -> Counter:
    c = Counter()
    try:
        r = etree.parse(str(path)).getroot()
    except Exception:            # noqa: BLE001
        return c
    ns = {"a": r.nsmap.get(None) or "http://www.loc.gov/standards/alto/ns-v4#"}
    labels = {t.get("ID"): t.get("LABEL") for t in r.iterfind(".//a:Tags/*", ns)}
    for tb in r.iterfind(".//a:TextBlock", ns):
        for ref in (tb.get("TAGREFS") or "").split():
            if labels.get(ref):
                c["alto:" + labels[ref]] += 1
    c["alto-style"] = len(r.findall(".//a:TextStyle", ns))
    c["alto-graphical"] = len(r.findall(".//a:GraphicalElement", ns))
    c["alto-printed-nr"] = sum(1 for p in r.iterfind(".//a:Page", ns) if p.get("PRINTED_IMG_NR"))
    c["alto-wc"] = sum(1 for s in r.iterfind(".//a:String", ns) if s.get("WC"))
    return c


def count_masters():
    out = {}
    for k, dirs in SETS.items():
        per = {i: [0, 0] for i in SPEC}            # articles, elements
        n = 0
        for d in dirs:
            for f in sorted(d.glob("*.jats.xml")):
                n += 1
                root = etree.parse(str(f)).getroot()
                text = None
                ac = None
                for i, sp in SPEC.items():
                    if sp is None:
                        continue
                    if isinstance(sp, str):
                        m = len(root.xpath(sp))
                    elif sp[0] == "text":
                        if text is None:
                            text = " ".join(root.find("body").itertext()) if root.find("body") is not None else ""
                        m = len(re.findall(sp[1], text))
                    else:
                        if ac is None:
                            ac = alto_counts(f.with_name(f.name.replace(".jats.xml", ".alto.xml")))
                        m = ac.get(f"alto:{sp[1]}" if sp[0] == "alto" else sp[0], 0)
                    if m:
                        per[i][0] += 1
                        per[i][1] += m
        out[k] = dict(n=n, per=per)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="count what landed (shown versions) in this database")
    ap.add_argument("--cache", action="store_true", help="reuse out/field_audit_counts.json")
    a = ap.parse_args(argv)
    homes = json.loads(HOMES.read_text(encoding="utf-8"))
    cache = HERE / "out" / "field_audit_counts.json"
    if a.cache and cache.exists():
        C = json.loads(cache.read_text(encoding="utf-8"))
    else:
        C = count_masters()
        cache.write_text(json.dumps(C, ensure_ascii=False, indent=1), encoding="utf-8")
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True) if a.db else None
    rows = []
    for h in homes:
        i = h["id"]
        sp = SPEC.get(i)
        c6 = C["600"]["per"].get(i, [0, 0])
        cj = C["j0130"]["per"].get(i, [0, 0])
        filled = sp is not None and (c6[0] or cj[0])
        before, now, sql = PLAT.get(i, (None, None, None))
        if not filled:
            before = before or ("—" if sp is not None else "n/a")
            plan = ("no slot of its own in the files (a structure, a derived value or text-level)" if sp is None
                    else "nothing to load: the slot is empty in every master (the reader does not fill it yet)")
            now_ = now or before
        else:
            if before is None:
                before = "missing"
            now_ = now or before
            plan = ("loaded now (2026-10-22)" if now else
                    ("already loaded" if not before.startswith(("missing", "WRONG", "partly")) else "to do"))
        n_db = None
        if con is not None and sql:
            try:
                n_db = con.execute(sql).fetchone()[0]
            except sqlite3.Error as e:
                n_db = f"error: {e}"
        rows.append(dict(id=i, group=h["group"], field=h["field"], slot=h["slot"],
                         spec=sp if isinstance(sp, str) or sp is None else list(sp),
                         articles_600=c6[0], elements_600=c6[1], articles_j0130=cj[0], elements_j0130=cj[1],
                         filled=bool(filled), platform_before=before, platform_now=now_, plan=plan, db_count=n_db,
                         in_platform=bool(filled) and not now_.startswith(("missing", "WRONG", "—", "n/a"))))
    (HERE / "out" / "field_audit.json").write_text(json.dumps(dict(
        made="2026-10-22", sets={k: v["n"] for k, v in C.items()}, db=a.db, fields=rows), ensure_ascii=False,
        indent=1), encoding="utf-8")
    nf = [r for r in rows if r["filled"]]
    bef = sum(1 for r in nf if not r["platform_before"].startswith(("missing", "WRONG", "partly")))
    part = sum(1 for r in nf if r["platform_before"].startswith("partly"))
    wrong = sum(1 for r in nf if r["platform_before"].startswith("WRONG"))
    now_in = sum(1 for r in nf if r["in_platform"])
    L = ["# Field audit: every extracted field and its place in the platform database (2026-10-22)", "",
         f"Masters counted: the 600 of `v33_300_final_lettersfix` + `v33_300b_fix3_lettersfix` (prompt v3.3, rebuilt "
         f"with the letter fix) and the journal's {C['j0130']['n']} of `j0130_final` (prompt v3.5b). A field's count "
         f"is the number of articles whose slot is filled (elements in brackets). Made by `audit_fields47.py`"
         + (f"; database counts from `{a.db}` (shown versions)." if a.db else "."), "",
         f"- **{len(rows)} fields** in experiment 51's `homes.json`; **{len(nf)} have a filled slot** in at least one "
         f"master; {sum(1 for r in rows if SPEC.get(r['id']) is None)} have no slot of their own (structures, "
         f"derived values, text-level), the rest are empty in every master.",
         f"- **Before** (loader of 2026-10-21): {bef} of the {len(nf)} filled fields were in the database, {part} "
         f"partly, {wrong} wrongly (editors and translators read as co-authors; the cited page and the work's range "
         f"in one value), {len(nf) - bef - part - wrong} missing.",
         f"- **Now**: {now_in} of {len(nf)} are in the database.", "",
         "| id | field | JATS / ALTO slot | 600 | j0130 | platform before | platform now | plan | in db now |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if not r["filled"]:
            continue
        L.append(f"| {r['id']} | {r['field']} | `{r['slot']}` | {r['articles_600']} ({r['elements_600']}) | "
                 f"{r['articles_j0130']} ({r['elements_j0130']}) | {r['platform_before']} | "
                 f"{r['platform_now'] if r['platform_now'] != r['platform_before'] else '='} | {r['plan']} | "
                 f"{'' if r['db_count'] is None else r['db_count']} |")
    L += ["", "## Fields with no filled slot in any master", "",
          "Nothing to load for these yet: the slot is empty in all 726 masters, or the field has no slot of its own.",
          "", "| id | field | slot | why |", "|---|---|---|---|"]
    for r in rows:
        if r["filled"]:
            continue
        L.append(f"| {r['id']} | {r['field']} | `{r['slot']}` | {r['plan']} |")
    (HERE / "out" / "field_audit.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"{len(rows)} fields, {len(nf)} filled; before {bef} in / {part} partly / {wrong} wrong; now {now_in}")


if __name__ == "__main__":
    sys.exit(main())
