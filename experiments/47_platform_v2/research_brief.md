# Research brief — how the big scholarly databases model their data (for experiment 47)

Written 2026-10-20 by the researcher agent, from public documentation (URLs beside each claim). Where only
secondary sources (library guides) were found, that is said. No paid calls.

The question for us: what should platform v2 copy from OpenAlex, Web of Science, Scopus, Crossref, Dimensions and
PubMed/PMC, and where do **our extra data** (the scans with ALTO coordinates, the article masters with every footnote
in reading order, Mandumah's MARC catalogue of 1.56M records with cataloguer-assigned author authority ids, and the
1M+ Azure-read documents in S3) let us do better than they do?

## 1. What each system stores

### OpenAlex (the only one with a fully public data model)
- **Entities**: Works, Authors, Sources (journals/repositories), Institutions, Topics (replaced Concepts), Publishers,
  Funders, Keywords. Type-prefixed ids (W…, A…, S…, I…, T…, P…, F…); external ids kept in an `ids` object
  (doi, mag, pmid, pmcid, orcid, ror, issn_l, wikidata). <https://help.openalex.org/api-entities/works/work-object>,
  <https://help.openalex.org/how-to-use-the-api/get-single-entities>
- **Work**: ids, title, publication date, type, `authorships`, `primary_location` / `locations` / `best_oa_location`,
  `referenced_works` (list of W ids), `related_works`, `cited_by_count`, `counts_by_year`, `is_retracted`,
  `indexed_in`, `created_date`, `updated_date`.
- **Authorship is a link object, not an entity** (no id of its own): `author_position` (first/middle/last, print
  order), `author` (dehydrated: id, display_name, orcid), `institutions`, `countries`, `is_corresponding`, and the raw
  evidence beside the resolved values — **`raw_author_name`, `raw_affiliation_strings`, `affiliations`
  (each raw string → the institution ids it matched), `raw_orcid`**.
  <https://help.openalex.org/api-entities/works/work-object/authorship-object>
- **Locations = copies/versions** of one work: each with source, doi, landing/pdf url, `version`
  (submittedVersion / acceptedVersion / publishedVersion), licence, `raw_source_name`, `raw_type`, `provenance`,
  `native_id`, `merge_key`, `ingested_at`. <https://help.openalex.org/api-entities/works/work-object/location-object>
- **Dehydrated objects**: when an entity is embedded in another (author in an authorship, source in a location), only
  id + display name + key external id are copied; the full record lives once.
- **Merges**: duplicates are merged; the retired id keeps working (API answers 301 to the survivor), and the snapshot
  has a `merged_ids` folder (dated files: retired id → surviving id). Snapshot files are partitioned by
  `updated_date`; consumers apply changes by date. <https://docs.openalex.org/download-all-data/snapshot-data-format>
- **How it is built**: gather (Crossref, DataCite, PubMed, DOAJ, repositories, parsed PDFs) → match incoming records
  to existing works by DOI or metadata (enrich, else create) → author disambiguation (ML clustering on name,
  co-authors, affiliations, topics, citations, ORCID; an "unknown author" bucket for what cannot be clustered) →
  affiliation strings matched to ROR institutions → references parsed and matched to works, giving both
  `referenced_works` and `cited_by_count` → classifiers for topics → community curation for fixes. Provenance: which
  index a record came from; native ids vs wrapped vocabulary ids. <https://help.openalex.org/data/how-its-built.md>,
  <https://help.openalex.org/api-entities/authors/author-disambiguation>
- **Unmatched references are dropped** from `referenced_works` (it only holds W ids): OpenAlex has no "cited but not
  in the index" entity.

### Clarivate Web of Science
- **Two kinds of record**: *source records* (indexed items, full metadata) and *cited references* (every reference
  in every source record, indexed as printed: cited author, cited work/source title, year, volume, page, DOI). A cited
  reference that matches a source record becomes a link (counts in Times Cited); one that does not stays searchable
  as a reference only. <https://libguides.nie.edu.sg/cited-reference-search-in-WoS>,
  <https://sisu.ut.ee/woseng/cited-reference-search/>, <https://guides.lib.utexas.edu/citationsearching/findingcitedreferences>
- **Cited Reference Search** shows the *variants* of one cited work (misspelt author, wrong year/volume) as separate
  rows for the user to tick; WoS does not correct the citing paper's errors, so citations can be split between a
  matched record and its variants (one documented case: a variant held 209 citations, the majority).
  <https://facweb.ischool.illinois.edu/sigmetrics/2013-August/006696.html>
- **Author records / ResearcherID**: every algorithmically generated author record gets a ResearcherID; a researcher
  may *claim* it (claimed profile = verified publication list, ORCID sync); claims feed back into the ML
  disambiguation (Clarivate: "40+ data points"). Having an id ≠ claimed.
  <https://webofscience.help.clarivate.com/en-us/Content/wos-researcher-id.htm>,
  <https://clarivate.com/academia-government/blog/author-data-made-better-together/>
- **Organization-Enhanced**: a preferred organisation name with a curated list of variants (18,500+ institutions
  unified, 76M records, March 2024), parent/child units; the printed address is kept and searchable separately, and
  the two searches give different answers. Corrections go through a data-correction form.
  <https://clarivate.com/academia-government/blog/getting-the-full-picture-institutional-unification-in-the-web-of-science/>
- **JCR self-citation**: the journal impact factor is shown with and without journal self-citations; journals are
  suppressed for excessive self-citation or *citation stacking* (two journals citing each other unusually); thresholds
  are not published; since 2025 citations to retracted items are excluded from the JIF numerator.
  <https://clarivate.com/webofsciencegroup/wp-content/uploads/sites/2/2020/06/JCR-suppression-policy-2020.pdf>,
  <https://retractionwatch.com/2025/06/18/clarivate-impact-factor-suppression-list-2025-self-citation-stacking/>
- **Arabic Citation Index (ARCI)**: Clarivate + Egyptian Knowledge Bank (announced 2018), on the WoS platform, an
  Arabic interface over curated Arabic journals linked into WoS's cited references; no public data-model detail found.
  <https://clarivate.com/news/clarivate-analytics-partners-egyptian-knowledge-bank-power-first-arabic-citation-index/>,
  <https://arxiv.org/pdf/2101.12177>

### Scopus (Elsevier)
- **Author ID**: algorithmic profiles from name, email, affiliation, subject area, citations and co-authors; not 100%
  precise; the Author Feedback Wizard lets authors set preferred name, merge profiles, add/remove documents; changes
  applied after review. <https://elsevier.libguides.com/Scopus/author-profile>,
  <https://bristol.ac.uk/research-innovation-services/research-policy/scival/authorprofiles/>
- **Affiliation ID**: profiles built by matching affiliation text to name variants; a parent id and child ids per
  hierarchy; institution representatives can add alternate names (which re-link past and future documents) and remove
  wrong ones. <https://www.elsevier.support/scopus/answer/about-the-institution-profile-wizard>,
  <https://dev.elsevier.com/sc_affil_search_views.html>
- **CiteScore**: citations in a 4-year window (e.g. 2021–24) to documents of five peer-reviewed types published in the
  same window ÷ number of those documents; same document types in numerator and denominator.
  <https://www.elsevier.support/scopus/answer/what-is-citescore>

### Crossref
- Publisher-deposited metadata per DOI, including the reference list: each reference has a `key`, structured fields
  and/or an `unstructured` string, a `DOI` and `doi-asserted-by` (publisher vs crossref = who made the link).
  <https://www.crossref.org/documentation/retrieve-metadata/rest-api/>
- **Reference matching** (Tkaczyk): search-based matching with validation (SBMV) — query the bibliographic search
  with the whole reference string, keep candidates whose relevance score normalised by string length passes a
  threshold, then a validation score picks the target; thresholds tuned on a separate set to maximise F1. On 2,000
  real unstructured references: precision 0.981, recall 0.946, F1 0.963 (legacy parse-then-match: F1 0.925). Errors:
  bad target metadata, noisy strings, book matched instead of its chapter.
  <https://www.crossref.org/blog/reference-matching-for-real-this-time/>,
  <https://www.crossref.org/blog/what-if-i-told-you-that-bibliographic-references-can-be-structured/>
- **Relationships**: typed links with a reciprocal — *intra-work* (isTranslationOf, isVersionOf, isPreprintOf,
  isReplacedBy…) vs *inter-work* (isPartOf, isReviewOf, isBasedOn, isSupplementTo, references…); the record holding
  the link is the "claimant"; cites/isCitedBy come implicitly from reference lists (Cited-by).
  <https://www.crossref.org/documentation/schema-library/markup-guide-metadata-segments/relationships/>

### Dimensions (Digital Science)
- Linked graph of publications, grants, patents, clinical trials, policy documents, datasets; backbone is Crossref
  DOIs + ORCID + open metadata, enriched by entity resolution and classification; organisations via GRID (now ROR,
  GRID retired publicly 2021, still used internally). No public detail on its reference matching.
  <https://arxiv.org/pdf/2112.08472>, <https://grid.ac/>

### PubMed / PMC and JATS
- JATS `<element-citation>` (structured) and `<mixed-citation>` (as printed) — tag as many parts as possible
  (surname, year, source, volume, fpage, article-title) so PMC/Crossref can make the link; `<pub-id>` holds a
  matched DOI/PMID. <https://jats.nlm.nih.gov/publishing/tag-library/1.3/element/element-citation.html>
- PubMed's batch citation matcher (ECitMatch) matches on a fixed key: journal | year | volume | first page | author.
  <https://rdocumentation.org/packages/reutils/versions/0.2.2/topics/ecitmatch>

### Identifiers
- **ROR** v2: names each with `lang` and types (ror_display, label, alias, acronym; no "primary" name — a label in
  every script); relationships parent/child/related (reciprocal), predecessor/successor; external ids (isni, wikidata,
  fundref, grid) with `all` + `preferred`; status active/inactive/withdrawn; admin created/last_modified.
  <https://ror.readme.io/docs/ror-data-structure>
- **ISSN-L**: one linking ISSN groups print and online ISSNs of a serial (= the first medium's ISSN); a daily table
  maps ISSN → ISSN-L. <https://www.issn.org/comprendre-lissn/regles-d-attribution/issn-de-liaison/>
- DOI (works), ORCID (people), ROR (organisations) are the external keys everyone carries as columns; internal ids are
  their own.

### ibid. / op. cit. / repeated references
- None of these systems documents resolving ibid./op. cit.: they work from reference lists, and WoS keeps each cited
  reference as printed. The rule itself (citation-style software, CSL "position" conditions): *ibid.* = the
  immediately preceding citation (possibly with a new locator); *op. cit.* / *loc. cit.* = an earlier citation of the
  same author, found by searching back. <https://acurio.ch/en/blog/ibid-op-cit-loc-cit-footnote-shortcuts.md>,
  <https://www.grammarly.com/blog/citations/ibid/>, <https://docs.citationstyles.org/en/stable/specification.html#position>

## 2. Patterns common to all of them

1. **Raw beside resolved, always.** OpenAlex: raw_author_name / raw_affiliation_strings next to author id /
   institution ids; WoS: printed address next to Organization-Enhanced, cited reference as printed next to the link;
   JATS: mixed-citation next to element-citation.
2. **Link objects carry the evidence.** Authorship (work × author × institutions × raw strings × position), affiliation
   (raw string → institution ids), reference (`doi-asserted-by`).
3. **Algorithm first, people correct, corrections feed back.** Scopus wizard, WoS claims, OpenAlex curation, Scopus
   institution representatives — and a merge never breaks an old id (redirect table).
4. **Cited-but-not-indexed is first class in WoS** (cited reference index with variants); OpenAlex loses it.
5. **Metrics are computed views** with documented windows and document types (JIF, CiteScore, with/without self-cites),
   never stored facts.
6. **Hierarchy for organisations** (parent/child) and **multilingual names without a "primary"** (ROR).
7. **Versions** of one work are locations/relations of one entity (OpenAlex locations; Crossref intra-work relations),
   not separate works.

## 3. Recommendations for platform v2 (what to do, and where our extra data change the answer)

**Citations**
1. Split *citation occurrence* from *cited work*. A `citations` table = one row per place a work is cited (note or
   ref, block, ALTO line ids/box, locator page, printed text). A `cited_works` table = one per distinct work cited in an
   article (the first full citation). «المرجع السابق»/«نفسه»/ibid./op. cit. become occurrences pointing to the first full
   citation (chains collapse at load), with `resolution_method` and `score` — never a work→work link.
2. Resolve back-references with the CSL position rule (ibid. = previous citation in the note stream, op. cit. = last
   earlier citation with the same author, else title words), using our note order and call positions in the masters —
   none of the big databases can do this, because they never see footnotes in order.
3. `citation_links` only for real links: cited work → archive article (stem) or → catalogue record (999$c), each with
   score, method, evidence, `asserted_by` (link47 | person | judge), best flag. Use Crossref's two-stage SBMV shape:
   full-text search of the catalogue FTS with the whole citation string, length-normalised threshold, then a
   validation score on author authority / year / title / journal; tune thresholds on the hand-checked links.
4. Keep unmatched cited works as a WoS-style **cited-reference index**: cluster the variants of one cited work across
   articles (normalised author + title key) so "times cited" can count non-archive works (books, manuscripts —
   most citations in Arabic humanities), and a person can merge/split variants as a patch.
5. Typed relations as Crossref does (isReviewOf, isPartOf, isTranslationOf; our link46 methods "catalogue-review-of",
   "catalogue-part-of" already are these) in one `work_relations` table with a reciprocal type, separate from citations.
6. Self-citation as computed views (author self-cite via shared person id between citing and cited work; journal
   self-cite via journal/ISSN-L), shown with and without, JCR-style; plus a citation-stacking view between journal pairs.

**People and institutions**
7. Make authorship a link table that holds printed name, catalogue name, position, corresponding flag, raw affiliation
   strings and matched institution ids (OpenAlex shape). Our advantage: the catalogue's authority ids are a human
   cataloguer's disambiguation — treat them like WoS *claimed* profiles (highest trust), and cluster only the rest.
8. Institutions: ROR-like record — names in Arabic and Latin with `lang` and type, no primary name; parent/child
   (university > faculty > department); status; external ids (ROR, wikidata) with provenance; keep every printed
   variant (WoS Organization-Enhanced) and let person patches add a variant, re-linking past rows.

**Identifiers, provenance, versions**
9. Stable internal ids per entity (prefixed, e.g. W/A/I/J), external ids as columns (DOI, ORCID, ROR, ISSN, ISSN-L,
   999$c — never 001). A `merged_ids` table (old → survivor, date, reason, source) so links never break.
10. Every value: `source` + `run` + `method`/`score` where inferred; corrections are patches (person > judge > gemini),
    D33 log kept; raw/printed columns never overwritten.
11. Versions: the same article in several runs (v33_300, _judged, _final, v33_300b) is one work with run-specific
    "locations"/renderings, as OpenAlex locations; `article_runs.current` stays the chooser.

**Scale (1M+ documents)**
12. Keep raw extraction (masters, Azure text in S3, MARC) as immutable files; the database is a rebuildable,
    normalised layer partitioned by load date like the OpenAlex snapshot (updated_date + merged_ids), loaded
    incrementally per run. Dehydrate embedded entities in any JSON export (id + display name only).
13. Metrics (times cited, CiteScore-style journal score over a 4-year window, h-index) are views/materialised tables
    recomputed per release, with the window and document types written next to the number.
14. Our unique evidence: every citation and name can point at the ink (page, ALTO line ids, box). Keep that pointer
    on every occurrence and link — it makes each link checkable by a person in one click, which none of the
    big databases offer.
