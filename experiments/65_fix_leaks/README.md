# Experiment 65: fix the leaks of the "nothing lost" audit (steps 1–3 of experiment 61's plan)

**Question** (owner-approved, 2026-11-02). Experiment 61 ([its README](../61_nothing_lost/README.md)) found 1,457
printed lines that reach no field, most of them because **our code** dropped or flattened what Gemini returned. Do
its fix plan: step 1, the mapping fixes M1–M7, rebuilt from the saved answers (free); step 2, fixed-format
identifiers by code on every line (free); step 3, prompt v3.6 (P1–P3, plus the lead's fix rule from experiment 66)
with a small paid check (cap $5). Measured by experiment 61's own audit; never change printed text (D30).

**Answer (2026-11-02).** Mapping leaks **953 → 292 lines** (−69%), lines only in generic text **1,457 → 805**,
accounted lines **99.665% → 99.815%** of 435,270; v3.5b (gate 1's prompt) 331 → **45**. Every block's text is
byte-identical before and after in all 780 masters (ALTO words and JATS blocks compared, plus a control build).
Identifiers found by code: 74 article DOIs (67 new `article-id`), 261 reference DOIs, 443 ISSN printings (57
`issn` added, 35 that fail their check digit listed only), 192 author e-mails, 7 ORCIDs, 16 phones, 793 URLs.
Prompt v3.6 returns the post, the article DOI, licence, section and every other printing of an author on all the
check pages; paid **$0.796** (cap $5). Nothing live was touched: a candidate DB
`~/data/platform_v2/candidate_fix61.db` holds the four rebuilt runs and passes the audit; the lead makes it live.

## What changed (files, functions)

**Step 1, mapping (M1–M7)** — the four current runs rebuilt from their saved answers into new folders
`experiments/43_rehearsal/out/<run>_fix61/` (`build65.sh`; the old runs untouched):

| fix | where | what it does |
|---|---|---|
| M1 post / rank | `meta43.names_pre` → `role_parts`, `split_role`; `leaks43.posts_in_bylines` | Gemini's role words that name no translator / reviewer / editor …: a role phrase («بقلم», "by", «اسم المؤلف:») → `role[@content-type="role-phrase"]`, an honorific → the printed name's `<prefix>`, the rest (a post or rank) → `role[@content-type="position"]`; a post printed at the start of a byline line that the answer left in no field («أستاذ مشارك بقسم …») → the same, by code |
| M2 the twin's parts | `meta43.keep_twin_parts` (names_pre Latin fold and enrich same_as), `meta43.fold_pairs` | every affiliation, e-mail, post and id of the name printed in the other script is kept in the person, `xml:lang`, the affiliation pointing at the one it translates (`aff/@rid`); the Latin fold now pairs each Latin name with its best consonant match (it used to pair neighbours: A, B, A′, B′ → B + A′ in 0130-027-105-003) and leaves to enrich's `same_as` the pairs the answer gives |
| M3 v2 rebuild | `lettersfix43.py plain --set a` | the 55 v2 masters rebuilt with today's rules, letter fix and moves (abstracts / keywords out of the body: 157 + 10 lines) |
| M4 bylines in the text | `leaks43.later_bylines` | a `p[@content-type="byline"]` naming an author links to it (`contrib/xref[@specific-use="printed-again"]`, 279 in 189 articles); a name there in the other script, matched by consonants, is the person's `string-name[@xml:lang][@specific-use="printed-again"]` (32); a closing place / date → `custom-meta` "signature" (27) |
| M5 subtitle | `leaks43.subtitle` (in `Master43.build`) | Gemini's subtitle kept as `<subtitle specific-use="in-printed-title">` when the title lines print it (115) |
| M6 honorific | `meta43.prefix_in_printed`, `role_parts` | the honorific as `<prefix>` of the printed `string-name` (494 in 392 articles), the string's text unchanged |
| M7 hyphen breaks | `refs43.citation ok()` (`HYPH_BREAK`) | a part broken at «Psychol- ogy» is the printed word; dropped parsed titles 297 → 225 |

**Step 2, identifiers by code** (`leaks43.find_all`, `identifiers`, `article_lines`): ORCID (ISO 7064 check; spaced
forms; a right-to-left-scrambled one accepted only when one order of its four groups is an ORCID printed elsewhere in
the article), DOI (the article's own told from reference DOIs by place: front matter, byline, title page, running
head / foot, a short line of its own; most frequent wins), ISSN (check digit; print / electronic), e-mail, URL,
phone (labelled or international; Arabic-Indic digits). Each is attached by position: the line names one author → the
nearest line above it in the same block naming one → the blocks before it → the e-mail's local part → the only author;
a running head's goes to the journal; a reference's stays with its reference (DOI into its element-citation); text in
the body is a mention. Homes: `contrib-id`, `contrib/email`, `contrib/uri`, `contrib/address/phone`,
`article-id[@pub-id-type="doi"]`, `article-meta/email | ext-link`, `journal-meta/issn`. Every identifier found,
attached or not, goes to **`<stem>.ids.json`** beside the masters with its page, Azure line, **ALTO TextLine id**,
block, place, owner and JATS home / id → platform table **`printed_identifiers`**. Lines code can catch: "how to cite"
(custom-meta), the journal's section over the title (`subj-group[@subj-group-type="heading"]`, 81), the licence /
copyright lines (`permissions`, 57 in 24 articles).

**Step 3, prompt v3.6** (`prompt43.PROMPT_V36`, `META_FULL_V36`, `ENRICH_*_V36`; `enrich43.check`; homes in
`meta43.names_pre` and `leaks43.v36`): P1 `authors[].position`; P2 enrich `doi`, `license`, `section`; P3 enrich
`printings` (any chunk); the lead's fix-rule bullet from experiment 66. Earlier versions unchanged. Details:
[43's README, "Prompt v3.6"](../43_rehearsal/README.md#prompt-v36-draft-2026-11-02-experiment-65-check-080-billed-log-10094).

**Platform** (`47_platform_v2`): `schema47.sql` new columns `byline_mentions.position`, `.contacts`,
`affiliation_mentions.lang`, `.twin_of_aff_pk` and table `printed_identifiers` (added to an existing DB by
`common47.migrate` on the next load); `parse47.contrib_extras` (position, role phrase, the twin's roles / posts /
prefix, contacts, printed-again links), `affiliations_v35` (lang, id, rid), `article_v35` (how_to_cite, signature,
journal_section, copyright, license, license_url, issn_printed → `metadata_assertions`), `printed_ids`; `load47`
(a twin's affiliation hangs on the twin's mention, `twin_of_aff_pk`; `printed_identifiers`; `_fix61` runs read their
source run's flags / raw / judge). Every reader returns nothing for a master without the new markup, so an old run
loads as before.

**Audit** (`61_nothing_lost`, outputs of experiment 61 untouched): `audit61.py --release DB --out DIR run|aggregate`
(and `AUDIT_RELEASE` / `AUDIT_OUT`), `raw_of` for `*_fix61` runs; `fields61.front_values` knows the new homes
(article DOI, ORCID / DOI printed forms, section, permissions, how-to-cite, signature, ISSN, contrib phone / uri) and
«doi», «orcid», «id» as labels; the platform reader takes `byline_mentions.position` / `.contacts`. The same code on
the old release gives experiment 61's numbers (1 line of 435,270 moves): `out/audit_before_check/`.

## Before / after (experiment 61's audit; `out/before_after.md`, `out/audit_after/audit.json`)

| prompt | articles | lines | b generic before → after | accounted before → after |
|---|---|---|---|---|
| v2 | 54 | 16,941 | 198 → 20 | 98.825% → 99.876% |
| v3.3 | 600 | 305,106 | 928 → 740 | 99.696% → 99.757% |
| v3.5b | 126 | 113,223 | 331 → 45 | 99.708% → 99.960% |
| **all** | **780** | **435,270** | **1,457 → 805** | **99.665% → 99.815%** |

| what it is | kind | lines (articles) before | after |
|---|---|---|---|
| author's post / rank | mapping | 273 (169) | **41 (28)** |
| affiliation | mapping | 196 (96) | **89 (48)** |
| abstract left in the body (v2) | mapping | 157 (10) | **1 (1)** |
| author name | mapping | 152 (94) | 115 (70) |
| honorific before a name | mapping | 79 (76) | **10 (10)** |
| closing signature | mapping | 51 (28) | 26 (12) |
| role phrase | mapping | 18 (17) | **1 (1)** |
| keywords left in the body (v2) | mapping | 10 (5) | **0** |
| e-mail | mapping | 7 (3) | **0** |
| the article's own DOI | not asked | 63 (61) | **6 (6)** |
| journal section (rubric) | not asked | 34 (34) | **0** |
| licence / copyright | not asked | 16 (8) | **0** |
| ORCID | gemini missed | 4 (1) | 1 (1) |
| body text typed «other» (no field expected) | not asked | 374 (97) | 364 (96) |
| table note / source (v3.3 does not ask) | not asked | 43 (8) | 43 (8) |
| every other row | | 53 | 47 |
| **by kind** | mapping / not asked / gemini missed | **953 / 556 / 52** | **292 / 437 / 46** |

Bilingual pairs (articles printing both scripts): affiliations both in JATS **33 → 89**, linked **28 → 87**, both
in the platform **33 → 89**; posts both in JATS **0 → 20**, linked **0 → 18**, platform **1 → 20**; names linked
89 → 97; abstracts and keywords 157 → 162 and 111 → 114 (the v2 rebuild). Answer values not in their field:
`authors[].role` 512 → 193 (the rest: honorifics, now the name's prefix, which the audit counts "elsewhere"),
`authors[].affiliation` 108 → 0, `subtitle` 115 → 0, `aff_parts.institution` 103 → 15, keywords 32 → 0.

**What is left, and why.** The 292 mapping lines are almost all v3.3 bylines printed in the text whose names are not
in Gemini's metadata (a co-author's English byline on page 18 that no answer names, an editor's signature, an
author's biography at the end): code cannot tell whose they are without guessing, which is P3's job in v3.6. The
"other" text (364) is body text Gemini typed `other` (event announcements, disclaimers): no field is expected. Table
notes (43) are v3.3's (v3.5b asks). Every number above is a line of print; none is a value Gemini returned that we
lost.

## Identifiers (`ids65.py` → `out/ids_summary.json`; platform `printed_identifiers`)

| kind | found | attached to | written into the JATS |
|---|---|---|---|
| DOI | 339 | article 74 (71 articles), reference 261, mention 4 | `article-id` 67 new (+4 already there); reference `pub-id` where an element-citation lacked it |
| ISSN | 483 | journal 443 (valid), reference 5; **35 fail their check digit** (listed only) | `journal-meta/issn` 57 (35 articles) |
| e-mail | 212 | author 192, journal 11, article 6 | `contrib/email` 10 new (the rest Gemini gave), `article-meta/email` 4 |
| ORCID | 7 | article 4 (0130-027-105-003: the answer named no author), mention 3 | `ext-link[@ext-link-type="orcid"]` 2 |
| phone | 16 | author 5, journal 3 | `contrib/address/phone` 5 |
| URL | 793 | reference 432, mention 240, journal 90, author 2, article 3 | `contrib/uri` 2, `ext-link` 3 |

Few ORCIDs: the 780 articles print 7, all in one article (gate 1); gate 2's education journals will print more, and
P3 attaches them to the right author. One finding beside the audit: with the printed DOIs in, `biblio47` raises
**53 catalogue reports "doi"**: Mandumah's catalogue holds its own DOIs («10.29343/1/0130-024-094-001») where the
publisher prints «10.29343/1-94-1».

## Proof that no printed text changed (`compare65.py`, `out/compare_*.json`)

| run | masters | ALTO words identical | JATS blocks identical | words (ALTO) | JATS DTD + ALTO XSD |
|---|---|---|---|---|---|
| j0130_final → _fix61 | 126 | 126 | 126 | 954,323 = | 126 valid |
| v33_300b_fix3_lettersfix → _fix61 | 300 | 300 | 300 | 1,122,369 = | 300 valid |
| v33_300_final_lettersfix → _fix61 | 300 | 300 | 300 (4 contribs: name as printed + new fields beside it) | 1,189,069 = | 300 valid |
| v2_55 control (today's code, `EXP65_OFF=1`) → _fix61 | 55 | 55 | 55 | 140,759 = | 55 valid |
| v2_55 (built 2026-10-18) → _fix61 | 55 | 26 | 22 | 140,759 = | 55 valid |

The last row is M3, not this experiment: the v2 masters predate the letter fix (539 words ی/ک → ي/ك, D30 reader
misreads) and fix round 3's code rules («((» guillemet halves); the control row shows our code adds nothing to it.
Letters fixed per run equal experiments 43 / 52's (331 / 829 / 1,059 words). Peak memory 0.81 GB (one build at a
time, nice 10).

## Prompt v3.6 check ($0.796 paid, cap $5; `out/v36_check2_compare.md`)

`run43.py --set e` (`sample65.json`: windows of saved articles), Standard: run 1 `v36_check` (10 pages, before the
fix bullet, $0.330), run 2 `v36_check2` (13 pages, final v3.6, $0.466; log $100.146 → $100.942).
- **P1**: every author with a printed post got `position` (0130-018-070-001 «أستاذ», «أستاذ مشارك», "Professor",
  "Associate professor", now apart from the affiliation; 0130-018-072-003 the owner's example both scripts).
  Non-contiguous joins («أ.د. / دكتوراه») are dropped by the substring check, as D30 wants.
- **P2**: DOI on all 4 pages that print one (0130-020-079-001, -080-001, 0130-027-105-003 with spaces normalised);
  section on the 0130 first pages; licence lines on 1152-013-001-004.
- **P3**: printings on all pages that hold one: the English twins on page 1, page 2's byline (0130-020-080-001), the
  summary page's two authors with ORCID, e-mail and the corresponding mark (0130-027-105-003), the Arabic names on
  0201-000-092-013 p14; 2461-003-001-005's corresponding marks.
- **Structure**: the same lines placed on every page (590 of 590; 575 with the same block type); types differ only on the lines the new keys
  are about (licence lines `other` → `paragraph`, corresponding-author notes `other` → `byline`, a rubric
  `header` ↔ `other`).
- **Fix rule** (looked at on the scan crops): the four bad fixes of experiment 66's examples are gone («حال» kept
  and flagged, «بنسبة» kept, the printed misprints «ثلك» kept, «بدعو» kept as `sic`), but on the faded
  1080-002-010-015 p8 v3.6 also dropped **four real fixes** («الاسيوى», «للعبودية», the printed «نرضته» / «يمنع»
  Azure had misread). 13 pages: fixes 47 (saved) → 36. Small sample: the bullet trades real fixes for safety on a
  bad scan; it needs a wider check (experiment 66's 270 judged fixes are the yardstick) before it goes live.
- Two code bugs it exposed were fixed before the rebuild (a name label taken as a post; the neighbour fold).

## Candidate DB and regressions

`~/data/platform_v2/candidate_fix61.db` (SQLite backup of `platform_v2.db` at 12:58, then `load47.py` of the four
`*_fix61` runs; `platform_v2.db`, the Desk releases and PostgreSQL were never written): 780 current versions (the
four `_fix61` runs), integrity ok, 0 orphans. Byline mentions 1,064 → 1,096 (twins printed again), with a post
401, contacts 260, titles 515 (346); affiliation rows 659 → 760 (137 in the twin's script, 136 linked);
`printed_identifiers` 1,850; new `metadata_assertions`: doi 71, journal_section 79, licence 15 + copyright 11,
how_to_cite 4, signature 14, issn_printed 35. `link47.py` was not run on it (it writes the shared link cache).

**Regressions: none found.** Text identical (above); every master DTD / XSD valid; tests: experiment 43 (65 + 12
new in `test_leaks43.py`), experiment 61 (7), repository suite and `tests/test_docs.py` pass. Things the lead
should know before going live:
- **Institutions (experiment 64)**: the twin's affiliations become rows (hung on the twin's mention, `lang` set,
  `twin_of_aff_pk` → the Arabic row). The institution linker sees ~100 more affiliation rows (English names of the
  same bodies); Desk decisions keyed on affiliation rows need re-matching on reload, and counts of affiliations should
  skip `twin_of_aff_pk IS NOT NULL` rows to avoid double counting.
- **Catalogue reports**: 53 new "doi" reports (above).
- `printed-on-the-page` string-names now hold a `<prefix>` element (text unchanged); any reader that took
  `string-name.text` rather than its full text would lose the honorific's part (parse46/47 use the full text).
- Experiment 66's guard (`d30guard43.py`) is not applied here; applying it changes text on purpose (408 refused
  fixes) and needs its own rebuild.

## What the lead runs to make it live (after experiment 64)

```
cd /home/appuser/inkscript
# 0. (if experiment 66's guard goes in first: apply d30guard.patch, then rebuild: bash experiments/65_fix_leaks/build65.sh)
# 1. back up the live DB (SQLite backup API, as before every load)
.venv/bin/python -c "import sqlite3; s=sqlite3.connect('file:$HOME/data/platform_v2/platform_v2.db?mode=ro',uri=True); d=sqlite3.connect('$HOME/data/platform_v2/platform_v2.before_fix61_2026-11-02.db'); s.backup(d)"
# 2. load the four rebuilt runs (the schema gains its new columns / table on the first one)
P=experiments/47_platform_v2
.venv/bin/python $P/load47.py --run j0130_final_fix61 --kind final
.venv/bin/python $P/load47.py --run v2_55_fix61 --kind sample
.venv/bin/python $P/load47.py --run v33_300b_fix3_lettersfix_fix61 --kind final
.venv/bin/python $P/load47.py --run v33_300_final_lettersfix_fix61 --kind final
.venv/bin/python $P/link47.py
# 3. the Desk release as usual (experiment 49), then the audit on it:
.venv/bin/python experiments/61_nothing_lost/audit61.py --release <new release.db> --out experiments/65_fix_leaks/out/audit_live run --workers 3 --force
.venv/bin/python experiments/61_nothing_lost/audit61.py --release <new release.db> --out experiments/65_fix_leaks/out/audit_live aggregate
.venv/bin/python experiments/65_fix_leaks/before_after65.py --after experiments/65_fix_leaks/out/audit_live/audit.json
```
Expect the candidate's numbers. Views / flags for the `_fix61` folders were not built (flags load from the source
run); `views43.py --masters <run>_fix61/masters` makes the Layout pages if wanted.

## Files

`build65.sh` (the rebuilds; `control` = `EXP65_OFF=1`), `compare65.py` (text proof), `ids65.py` (identifier and
field counts), `before_after65.py` (audit before / after), `compare36.py` (v3.6 vs saved answers), `sample65.json`
(the check pages, run43 set `e`), `progress.md`. Code: `43_rehearsal/leaks43.py` (new), `test_leaks43.py` (new),
`meta43.py`, `masters43.py`, `refs43.py`, `enrich43.py`, `prompt43.py`, `run43.py`, `lettersfix43.py`,
`pictures43.py`; `47_platform_v2/parse47.py`, `load47.py`, `schema47.sql`; `61_nothing_lost/audit61.py`,
`fields61.py`, `answers61.py`. Outputs (gitignored): `out/` (audits, comparisons, logs, the v3.6 check runs'
comparisons; `first_attempt/`, `second_attempt/` = the two rebuilds before the last fixes, 3.3 GB, can be deleted);
the masters in `43_rehearsal/out/*_fix61/`, the check answers in `43_rehearsal/out/v36_check*/`.
