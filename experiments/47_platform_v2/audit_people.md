# Audit: people and institutions in platform.db (experiment 47)

Date 2026-10-20. Read-only audit of `/home/yassine/data/platform/platform.db` (built by
`experiments/46_platform_db/`) and `/home/yassine/data/marc/marc.db`. Tables audited: `people`,
`person_names`, `article_authors`, `catalogue_authors`, `affiliations`, `institutions`,
`institution_variants`. Code read: `schema46.sql`, `load46.py` (`clean_person`, `name_score`,
`match_authors`, `rebuild_people`), `inst46.py`, `parse46.py` (contrib/aff parsing). Every number below
came from a query run today. Nothing was written to either database.

## What is there today

| table | rows | what one row is |
|---|---|---|
| article_authors | 413 (329 of 354 articles; 25 articles have no byline) | one printed byline name in one article, plus its catalogue match, plus the person it resolved to |
| people | 395 (347 `auth:<id>`, 48 `name:<folded>`) | one person, rebuilt from scratch on every load |
| person_names | 881 (411 printed, 363 catalogue, 107 latin) | one name form of a person |
| catalogue_authors | 429 | one 100/110/700 heading of the article's primary MARC record |
| affiliations | 247 (194 articles) | one `<aff>` of one byline name |
| institutions | 302 (134 organisations, 90 faculties, 78 departments) | one clustered institution |
| institution_variants | 316 | one printed spelling of an institution |

Match outcome of the 413 byline names: name 351, weak 17, none 15, no-catalogue 17, name-variant 9,
script-twin 4. Every person in the sample has 1 or 2 articles, so disambiguation at scale has not been
exercised yet; the catalogue checks below are what tell us how it will behave at 1M documents.

## What the catalogue already gives us (and that nobody else has)

Measured in marc.db (2,217,503 author headings, tags 100 / 110 / 700):

- 721,138 distinct authority ids. 720,741 of them (99.95%) carry exactly one folded name: **a Mandumah
  authority id is a cataloguer's decision "these headings are one person"**. Treat it like a claimed
  Web of Science profile (brief rec. 8).
- **Homonyms are already split by the cataloguer**: 14,225 folded names are shared by 2+ authority ids
  (e.g. «علي، احمد» 18 ids, «ابراهيم، محمد» 29 ids). A key built from the name alone merges them.
- **Latin forms for 232,070 authority ids** (1,081,405 headings carry `latin`; 100$g / $q). This is a
  ready-made Arabic↔Latin transliteration dictionary for matching Latin bylines and Latin citations.
- **Death dates in the heading** («، ت. 1414 هـ», «، ت. 2021 م»): 24,866 headings. These give
  life dates and catch classical authors printed as bylines (e.g. «الإمَام ابن القيم» → «ابن قيم
  الجوزية، محمد بن أبي بكر بن أيوب، ت. 751 هـ»: an edited text, not a modern author).
- **Supervisors**: 245,785 rows with role مشرف / Advisor / Supervisor / Super (mostly 700). With 502
  (169,600 dissertations: $b degree, $c university, $f faculty, $g country) this is an **academic
  genealogy** (supervisor → student → university → year) for the Arab world. No citation index has it.
  Our 347 authority people alone have 472 supervision rows and 8,987 catalogue records (median 8 each;
  215 people have 5 or more), so author profiles exist before we digitise any of their other papers.
- **Corporate authorities with hierarchy**: 2,347 authority ids on tag 110, 12,442 headings written
  «country. body. sub-body» (e.g. «العراق. جامعة البصرة. مركز دراسات الخليج العربي»,
  «لبنان. مركز دراسات الوحدة العربية. قسم التوثيق»). That is an institution parent/child list with ids.
- **Dissertation universities**: 502$c holds 448 distinct university names (الجامعة الاردنية 18,942
  theses, جامعة أم درمان الاسلامية 15,405, …): the seed list of Arab universities, already in Arabic.

On the page side, the masters already hold the **ink of every byline**: the ALTO has a `role.author`
TextBlock (418 in the 300 final masters) with box, line ids and word confidences (`WC`), and the JATS
`custom-meta id="p1b2"` carries the same line targets and any reader-fix (e.g. 0018-031-001-006:
Azure «المحار بين» → print «المحاربين» in the affiliation line). None of this reaches the people tables.

## Problems

### P1. One table mixes three things: the printed mention, the catalogue match, and the person (high)
`article_authors` holds the printed name and email (what the page says), `catalogue_seq / catalogue_name
/ authority_id / name_score / match` (what the matcher decided), and `person_key` (the entity) in one row.
The match and the entity are overwritten on every load (`rebuild_people` does `DELETE FROM people` and
then `UPDATE article_authors SET person_key = …, match = match || '+variant'`). Consequences: a person
patch ("this byline is that person") has nowhere to live and would be wiped by the next load; there is
no `asserted_by` (link46 / person / judge), and no evidence. OpenAlex separates the authorship object
(raw name, position, raw affiliation strings) from the author entity; Web of Science separates the
printed author from the claimed profile.

### P2. A bilingual byline becomes two authors (high)
When a person is printed in Arabic and Latin, there are two `article_authors` rows. 10 articles have
more rows than distinct persons (e.g. 2205-000-024-006: 4 rows, 2 people; 1956-017-002-013: 4 rows,
2 people). `seq` is then not the byline position, the author count is wrong (24 `catalogue_disagreements`
of kind `count`, part of them from this), and the four `script-twin` rows are stored with
`name_score = 0.0`, i.e. a score that means "not compared" looks like "no match".

### P3. The name matcher misses the commonest Arabic pattern: print gives the short name, the catalogue the full nasab (high)
`name_score` is a character ratio of the whole folded string. 32 byline names that had catalogue
candidates ended `weak` or `none`. A token-subset test (printed tokens ⊆ catalogue tokens after
dropping titles, «بن/بنت», «ال», feminine ة/ية) recovers 14 of them, all of which look right by eye:
«راشد المحرزي» → «المحرزي، راشد بن سيف بن مصبح», «يسرى السناني» → «السناني، يسرى بنت جمعة بن
سعيد», «د. جابر عصفور» → «عصفور، جابر أحمد، ت. 2021 م», «الدكتور طه حسين» → «سلامة، طه حسين علي،
ت. 1973 م», «د. سعيد السريحي» → «الحربي، سعيد مصلح السريحي». 16 authority ids were known for rows that
stayed `name:`. «أمل الكيومي» vs catalogue «الكيومية، أمل» shows the feminine nisba too.
Latin bylines against Arabic-only headings fail completely: 0939-028-001-007 has 7 Latin bylines, all
`none`, while the record has 5 Arabic headings with authority ids («العتيبي، خالد طلال» = Khalid Talal
Alotaibi). The catalogue's 1.08M Latin forms are not used to learn transliteration.

### P4. `name:` keys merge homonyms and will not hold at 1M documents (high)
`person_key = 'name:' + folded name without spaces`. The catalogue shows 14,225 folded names held by
two or more distinct people. At 1M articles every «أحمد علي» without an authority match becomes one
person. Also `''` (empty string) is an authority id on 59 catalogue headings covering 53 different names
(«AL Dmour، Hani» … «ملال، مختارية»); the loader's `if a["authority_id"]` skips it today, but any
`GROUP BY authority_id` will make one 53-name person.

### P5. Corporate bylines, roles and initials are stored as people (medium)
9 of the 48 `name:` people are not persons: «رئيس التحرير», «أسرة التحرير», «وحدة الدراسات الاقتصادية»,
«اللجنة الوطنية العمانية لليونسكو», «إدارة المكتبات العامة بوزارة المعارف», «ادارة الشئون الاسلامية
بالوزارة», «مركز البحوث المالية والمصرفية», «بناة الأجيال», «مجموعة من المعقبين». The catalogue has these
as corporate authorities (e.g. 2631 «سلطنة عمان. اللجنة الوطنية العمانية لليونسكو», 140
«السعودية. وزارة المعارف. إدارة المكتبات العامة»), but `match_authors` excludes `is_org` headings from
matching. «هيئة التحرير» (authority 4322) is used on 54,668 catalogue headings across all journals: it
is a role, not an organisation, and must never become one entity.
Signature initials «ى . م» (0513-006-003-007) became a person; the catalogue resolves it to «مراد،
يوسف». That is a real, unique win (initials/pseudonyms resolved by a cataloguer) that the matcher
throws away because the string ratio is low.

### P6. Titles and ranks are deleted instead of kept (medium)
`clean_person` strips «د.», «أ.د.», «الدكتور», «Dr.», «Prof.» and the loader keeps only the stripped
form for keys; 83 of 413 printed names start with a title. The title is information (doctorate held at
that date, a rank, «القاضي», «الشيخ», «مولانا», «المستشرق الاسباني», «للقائمقام» = a military rank), and
it is also unreliable to strip by pattern: «دكتور زكى نجيب محمود» and «دكتور/ سامى نجيب» are not
stripped (display_name «دكتور زكى نجيب محمود», person_key `name:دكتورزكينجيبمحمود`), while «آمال
الشيخ» shows that «الشيخ» can be a family name. In affiliations `strip_role` discards the position
(«الاستاذ ب…», «مدرس القانون الدولى العام», «أخصائى التوجيه المهني») — the career timeline of the person.

### P7. Roles are not normalised and not carried to the authorship (medium)
`catalogue_authors.role` holds the catalogue's free text: مؤلف 290, م. مشارك 48, Author 30, مترجم 11,
عارض 13 (9 of them on «هيئة التحرير»), Co-Author 5, مشرف 2, … In marc.db there are 25+ spellings
(Co-Author / Co.Author / Co - Author / Co-auth / co-Auth; Super / super / SUPER / Supervisor). The byline
row has no role at all, so a book review (عارض = the byline person reviews someone else's book) or a
translation counts as authorship.

### P8. No pointer from a person mention to its ink (medium)
`article_authors` and `affiliations` carry no block id, ALTO line ids, box or word confidence, although
the masters hold them (`role.author` TextBlock; `custom-meta` with `<target id="p1b2l1"/>`). 154
`blocks` rows of kind `byline` and 37 `contrib` exist but are not joined to the authors. So a person
cannot "show me the byline on the page", and a low-confidence byline (e.g. «الحميد» WC 0.684) cannot
lower the trust of the match.

### P9. Only one run per article; versions overwrite (medium)
`article_authors` PK is `(stem, seq)` and `affiliations` PK `(stem, author_seq, seq)`; `run` is a
column, not part of the key. 61 rows come from v2_55 and 352 from v33_300_final; the other runs'
bylines are gone. When v33_300b is loaded it will replace them. A byline that a later run reads
differently (or splits/merges) cannot be compared. `affiliations` hangs on the positional `author_seq`,
so a run that reorders the byline re-attaches affiliations to the wrong person.

### P10. People have no stable id, no merge record, no external ids (medium)
`person_key` changes when the match changes (`name:X` → `auth:Y` on a later load). There is no
`merged_ids` table, no ORCID/VIAF/Wikidata/ISNI columns, no life dates (the catalogue has them), no
`status`. Duplicate catalogue authorities are not visible: 19 of our 347 authority people share their
exact folded heading with another authority id; some are homonyms, some look like duplicate authority
records — 111978 and 111979, both «الرمادي، جمال الدين», both writing in «مجلة مصر المعاصرة» in
1963 and 1967. Those are a catalogue-error report for Mandumah, and need a "same person, two catalogue
ids" record without editing the catalogue.

### P11. Catalogue vs print disagreements on names are flagged but not kept as entity knowledge (low)
0747-001-003-001 prints «القاضى عبدالمقتدر …الدهلوى» and the catalogue says «الدهلوي، عبدالقادر ركن
الدين الشريحي» (عبدالمقتدر vs عبدالقادر); 0939-028-001-007 prints 7 authors, the catalogue lists 5.
They sit in `catalogue_disagreements` as free strings, not linked to the person or the authorship, so
a fix by a person cannot flow back to the person's names.

### P12. Cited authors are not linked to people (low today, high for the citation index)
`work_authors` (4,638 rows) has no person column. A simple name-key join already finds 34 cited works
whose author is one of our byline people; 20 of them are cited inside the same article (author
self-citation) and 14 in another article. Self-citation (brief rec. 6) needs cited-author → person.

### P13. Institutions: the key is a path, clusters split across scripts, countries are free text (high)
- `inst_key` embeds the parent: `fac:org:جامعهقاهره/كليهحقوق`, `dep:fac:…/…`. Re-parenting (or fixing
  the organisation) changes the id of every child. 16 rows hang on the placeholder `org:?`
  (`fac:org:?/كليهحقوق` — «كلية الحقوق» of *which* university is unknown, yet all such faculties of
  different universities collapse into one row).
- Cross-script merging only happens when the same person prints both in one article. So «Helwan
  University» (`org:helwanuniversity`) and «جامعة حلوان» are two institutions; likewise University of
  Basrah / جامعة البصره, Alexandria University / جامعة الإسكندرية, University of Mosul / جامعة الموصل,
  and «Université de Bejaia» / «Université Abderrahmane Mira de Bejaia» are two Latin rows. 27 Latin
  organisations, most of which have an Arabic twin.
- `institutions.country` is null on 212 of 302 rows and mixes ISO codes (EG, IQ) with printed text
  («Kingdom of Bahrain», «Algérie», «الجمهورية العربية السورية», «الجمهورية الجزائرية الديمقراطية
  الشعبية»).
- `source` is always `masters`: the catalogue's 2,347 corporate authorities and 448 dissertation
  universities are not used as the reference list, so every institution is a fresh string cluster.
- 44 affiliations have no organisation; several are positions, not places («مدير مالي ومستشار ضريبي»,
  «العضو المراسل من تونس», «(بغداد)»). The printed string is kept, good, but nothing says "position only".
- No renames/successors: e.g. catalogue 502$c has both «جامعة الرياض» and «جامعة الملك سعود» (the same
  university renamed in 1982); an index needs "predecessor of", not a merge.
- `institution_variants` has no language, script, type, or source; ROR keeps names typed (label /
  alias / acronym) with language and no primary.

### P14. Personal data (low, policy)
55 byline rows carry an email. Email is the strongest disambiguation signal we have, but it should be
kept as evidence, not published on a public profile without a policy.

## Proposed tables (v2)

Ids: stable prefixed ids minted once and kept in an **append-only id registry** that survives rebuilds
(the database is rebuildable, the ids must not be): `A…` person, `I…` institution, `M…` mention.
Natural keys in the registry: catalogue authority id for people who have one, catalogue corporate
authority id or ROR for institutions, `(stem, block_id, line span)` for mentions.

1. **persons** — one real person.
   `person_id TEXT PK ('A…')`, `status TEXT (active|merged|provisional)`, `preferred_name_ar`,
   `preferred_name_lat`, `birth_year_h`, `birth_year_g`, `death_year_h`, `death_year_g` (from the
   heading «ت.»), `orcid`, `viaf`, `wikidata`, `isni`, `source (catalogue|cluster|person)`,
   `created_run`, `updated_run`. Counts are views, not columns.
2. **person_authorities** — which catalogue authority ids belong to the person (usually one; two when
   the catalogue has a duplicate).
   `person_id FK persons`, `authority_id TEXT` (never '' — load '' as NULL), `heading`, `n_records`,
   `relation (same|duplicate-in-catalogue)`, `asserted_by`, `reason`; PK `(authority_id)`.
3. **person_names** — every form of the name, typed.
   `name_id PK`, `person_id FK`, `full_form` (as written), `script (ar|lat)`, `lang`,
   `form_type (printed|catalogue-heading|catalogue-latin|cited|transliteration|initials|pseudonym)`,
   `ism`, `nasab`, `nisba`, `laqab`, `kunya`, `family`, `n_seen`, `source`, `first_seen_stem`.
4. **byline_mentions** — one printed name as it appears on the page, never changed (D30).
   `mention_id PK ('M…')`, `stem FK articles`, `run FK runs`, `byline_pos INTEGER`, `printed TEXT`,
   `titles TEXT` (the stripped «د.», «أ.د.», «الشيخ», rank…), `name_text`, `script`, `email`,
   `block_id`, `alto_lines TEXT` (JSON line ids), `page`, `hpos`, `vpos`, `width`, `height`,
   `min_word_conf REAL`, `reader_fixes TEXT` (fix ids). PK is the mention id; unique
   `(stem, run, block_id, byline_pos, script)`.
5. **authorships** — one person's part in one article (bilingual twins = one authorship, two mentions).
   `authorship_id PK`, `stem FK`, `run FK`, `position INTEGER`, `role_code` (author|coauthor|translator|
   reviewer|editor|supervisor|interviewer|compiler|original-author), `role_raw`,
   `person_id FK persons NULL`, `inst_id FK institutions NULL` (corporate byline), `catalogue_rec`,
   `catalogue_seq` (FK catalogue_contributors), `is_corresponding`, `method` (authority-name /
   token-subset / transliteration / script-twin / initials-catalogue / person), `score REAL NULL`
   (NULL when not compared, never 0.0), `asserted_by (link47|person|judge)`, `evidence TEXT`.
6. **authorship_mentions** — joins mentions to their authorship. `authorship_id FK`, `mention_id FK`.
7. **catalogue_contributors** — replaces catalogue_authors: every 100/110/700 of every record of the
   article (not only the primary), with `tag`, `role_raw`, `role_code`, `authority_id`, `is_org`,
   `latin`, `death_note`.
8. **affiliation_mentions** — one printed affiliation, kept whole. `aff_id PK`, `mention_id FK`
   (not a positional author_seq), `printed`, `position_title` (what `strip_role` cut), pieces
   `org_text`, `faculty_text`, `dept_text`, `city`, `country_printed`, `country_code (ISO 3166)`,
   `kind (institution|position-only|place-only)`, ALTO pointer as in 4.
9. **affiliation_links** — affiliation → institution, possibly several levels.
   `aff_id FK`, `inst_id FK`, `level`, `method`, `score`, `asserted_by`, `evidence`.
10. **institutions** — one organisation, faculty or department.
    `inst_id PK ('I…')`, `kind (university|faculty|department|ministry|centre|academy|court|company|
    hospital|journal-board|other)`, `parent_id FK institutions NULL` (a column, not part of the id),
    `country_code`, `city`, `status (active|renamed|merged|closed|provisional)`, `ror`, `wikidata`,
    `catalogue_authority_id` (110 $9), `source (catalogue|masters|ror|person)`.
11. **institution_names** — replaces institution_variants. `inst_id FK`, `name`, `lang`, `script`,
    `type (label|alias|acronym|printed|catalogue-heading|dissertation-502c)`, `n_seen`, `source`.
12. **institution_relations** — typed, each with its reverse: `from_id`, `to_id`,
    `relation (parent|successor|predecessor|related)`, `start_year`, `end_year`, `source`, `reason`.
13. **supervisions** — the academic genealogy from the catalogue.
    `rec` (dissertation catalogue record), `c999`, `student_person_id`, `supervisor_person_id`,
    `degree` (502$b), `inst_id` (502$c/$f), `country`, `year`.
14. **merged_ids** — old id → surviving id for every entity type: `old_id`, `new_id`, `entity`,
    `date`, `reason`, `source (link47|person|judge)`; splits recorded as `new_id` rows pointing back
    with relation `split-from`.
15. **entity_patches** — person/judge decisions replayed on every rebuild (person > judge > link47):
    `patch_id`, `op (assign-mention|merge|split|add-name|set-role|set-parent|add-variant|not-a-person)`,
    `targets`, `payload`, `source`, `reason`, `created`, `status`.
16. **catalogue_reports** — what we send Mandumah, linked to entities: `kind (duplicate-authority|
    missing-author|name-differs|role-wrong|corporate-as-person)`, `rec`, `c999`, `authority_ids`,
    `stem`, `mention_id`, `evidence`, `status`.
17. Views, not tables: `person_works` (catalogue records + archive authorships per person),
    `person_affiliation_timeline` (affiliation + position title + article year), `self_citations`
    (cited-work author person = citing authorship person; needs `work_authors.person_id`).

## Migration notes

- Build from the same sources (masters + marc.db), no paid calls. Order: catalogue_contributors →
  persons/person_authorities from authority ids (one person per authority id, '' → NULL) →
  byline_mentions from `contrib` + the `custom-meta`/ALTO `role.author` block → authorships via the
  matcher → clusters for the unmatched → affiliations → institutions.
- Matcher, in order, each writing its own `method`: exact authority-name; token-subset with nasab /
  ال / ة / ية / title folding (+14 of 32 on today's data); transliteration via the catalogue's Latin
  forms (fixes the 7 of 0939-028-001-007); script twin (score NULL); corporate heading for organisation
  bylines; catalogue-only-candidate for initials (method `initials-catalogue`, low trust, review queue).
- Unmatched names: cluster only inside a block (same folded surname + first given name) and only with a
  second signal (shared co-author, institution, journal, email, subject); otherwise the mention gets a
  `provisional` person of its own. Never key by name alone (P4).
- Institutions: seed `institutions` from the 2,347 corporate authorities (split «A. B. C» into parent
  chain) and the 448 502$c names, then attach printed variants; cross-script merge by a small
  bilingual table (University ↔ جامعة, of/de ↔ —) plus city/country agreement, review the rest.
- Keep 46's columns readable by giving v2 a compatibility view `article_authors_v46`.
- ids: carry the registry file in `/home/yassine/data/platform_v2/` between rebuilds.
- Emails: keep in byline_mentions; exclude from any public export.

## What stays in files
Page images, figure crops and the ink PDF stay in files; the database keeps the pointer (stem, page,
block, ALTO line ids, box). Raw MARC stays in marc.db; the platform keeps headings and authority ids
it uses, with `rec`/`c999` to go back.

## Open questions for the owner
1. Should a classical author printed as byline of an edited text (ابن القيم, d. 751 هـ) be an
   authorship with role `original-author`, or should the editor/محقق be the author?
2. Do we treat a catalogue duplicate authority (111978/111979) as one person in our platform while the
   catalogue keeps two ids, and report it to Mandumah?
3. Is the academic-genealogy view (245,785 supervision rows) in scope for v2, or later?
4. Policy for publishing emails and titles (د., أ.د.) on person pages.
