# Experiment 61: nothing lost — does everything printed end up in a proper field?

**Question** (owner, 2026-11-02, before spending about £500 on gate 2, ~3,460 articles). Prove that everything printed
and everything Gemini extracts ends up in a proper field. The owner's example, on 0130-018-072-003 page 1: the Arabic
affiliation «كلية علوم التربية - جامعة محمد الخامس - المملكة المغربية» is stored as an affiliation with its parts, but
the printed English affiliation "University of Mohamed V - Faculty of Education Sciences - Morocco" and the post "PhD
Student in Sociology" are not stored anywhere as fields.

**Answer (2026-11-02, $0, no model calls, read-only on every input).** On the 780 current articles,
**99.66% of printed lines (433,810 of 435,270) land in a field or are set aside as not article text**; 1,460 lines
fall through (1,458 only as generic text, 2 nowhere). The leaks are concentrated in the author block, and most of them
are **our code, not Gemini**: Gemini returned the value and the masters dropped or flattened it. Two code fixes (M1,
M2) cover the owner's example and the two largest leaks. What the prompt does not ask for and must be added before
gate 2: the author's post as its own value, the article's own DOI, the licence line, the journal's section (P1, P2;
P3 for bylines away from the title). False-alarm rate of the leak list, checked on the page images: **1 of 82 (1.2%)**.

## Method (`audit61.py`, `fields61.py`, `answers61.py`, `aggregate61.py`)

For every current version in the release DB `~/data/desk/releases/R20261023T005909.db` (780: j0130_final 126 on prompt
v3.5b, v33_300_final_lettersfix + v33_300b_fix3_lettersfix 600 on v3.3, v2_55 54 on v2):

1. **Line accounting, word by word.** Every Azure word of every page the version read (`pages_covered`; the 12 v2
   "windows" are offset to their scan pages) is matched to its ALTO String by box (`ink47.match_words`), with two
   fallbacks for the words the masters re-laid in mixed Arabic / Latin lines (same word in the ALTO line holding the
   Azure line's other words; the TextLine whose box holds the word). String → TextBlock → JATS element (`xlink:href` /
   id) → field (`fields61.jats_class`). Byline-like containers (`custom-meta front-matter-block`, `contrib`, a byline
   paragraph in the text) are split by matching their words against the specific values the JATS front holds (names,
   e-mails, roles, affiliations and their parts, history dates, keywords, titles…); a label beside a value («Email:»,
   «تاريخ القبول:») goes with the value. Generic body paragraphs (`p content-type="other" | "abstract" | "keywords"`)
   whose text a front field also holds count as stored (a title printed again on page 2). Buckets:
   **a** a specific field, **b** generic text only, **c** explicitly not article text (running head, page number, noise
   Gemini called noise, another article, show-through, ornament, picture junk), **d** nowhere. A line takes the bucket
   most of its words have. **b and d are leaks.**
2. **Kind of each leak.** **mapping** = Gemini returned the text (in a metadata / enrich value, or by typing the block
   abstract / keywords / byline) and our code dropped or flattened it: free to fix by rebuilding from the saved answers;
   **not_asked** = no prompt version asks for that field (read from `prompt43.py`, `fields61.ASKED`); **gemini_missed**
   = asked, printed, not returned. What a leaking line is (the field it should have gone to) comes from the answer key
   that holds it, else from `fields61.detect` (e-mail, ORCID, post / rank, affiliation, history dates, DOI, licence…).
3. **Answer accounting.** Every value of Gemini's answer (metadata, enrich, parsed reference parts, figure
   descriptions, fixes / sic / math / missed / ornaments / calls as counts) → **stored** in its JATS field /
   **elsewhere** (another field) / **flattened** (only inside generic text) / **dropped**, with the code's reason.
4. **Bilingual pairs** (title, names, affiliations, posts, abstracts, keywords): printed in both scripts? both stored?
   linked? both in the platform?
5. **Platform.** The same words through the release DB (`line_map` → `blocks` / `page_regions`, byline and affiliation
   rows); JATS element counts against platform rows; content columns no current article fills.
6. **Check on the scans** (`verify61.py`): 3 leaks per (field, kind) row (83), cropped from the page images with the
   line outlined; the agent looked at every crop (`out/verify/sheet_*.jpg`); verdicts in `verdicts61.json`.

Run (about 70 s with 3 workers; peak ~100 MB a worker, measured with `/usr/bin/time -v`):

    .venv/bin/python experiments/61_nothing_lost/audit61.py run --workers 3 --force   # out/articles/<stem>.json
    .venv/bin/python experiments/61_nothing_lost/aggregate61.py                        # out/audit.json
    experiments/49_correction_desk/.venv/bin/python experiments/61_nothing_lost/verify61.py sample|score   # (Pillow)
    .venv/bin/python experiments/61_nothing_lost/audit61.py one 0130-018-072-003        # one article, printed
    .venv/bin/pytest -q experiments/61_nothing_lost                                    # 7 tests

The Desk shows it at `/audit` (experiment 49, `desk/audit.py`), from these files.

## Result: the totals

| prompt | articles | lines | a field | b generic | c not article text | d nowhere | accounted |
|---|---|---|---|---|---|---|---|
| v2 | 54 | 16,941 | 15,628 | 199 | 1,113 | 1 | 98.82% |
| v3.3 | 600 | 305,106 | 285,031 | 928 | 19,146 | 1 | 99.70% |
| v3.5b | 126 | 113,223 | 103,185 | 331 | 9,707 | 0 | 99.71% |
| **all** | **780** | **435,270** | **403,844** | **1,458** | **29,966** | **2** | **99.66%** |

In words: 3,271,773, of which 8,146 fell through (99.75% accounted). 435 of the 780 articles have at least one line
that fell through. One more ink problem, not a field leak: 0089-006-005-006 has 82 words of page 4 drawn on page 3 in
its ALTO (text and field right, the ink link on the wrong page).

## The leak table (lines that fell through, by field and kind)

| what it is | kind | lines | articles | v2 / v3.3 / v3.5b (articles) | example |
|---|---|---|---|---|---|
| author's post / rank | mapping | 273 | 169 | 6 / 101 / 62 | 0130-018-072-003 1:30 "PhD Student in Sociology" (authors[1].role) |
| body text typed «other» (no field expected) | not asked | 374 | 97 | 7 / 85 / 5 | disclaimers, event announcements, JEL codes |
| affiliation | mapping | 196 | 96 | 2 / 44 / 50 | 0130-018-072-003 1:31 "University of Mohamed V - Faculty of Education Sciences - Morocco" |
| author name (closing signatures, second-language byline at the end, bylines on p2) | mapping | 153 | 94 | 5 / 87 / 2 | 0201-000-092-013 14:6 «ناصر نسيم عطية زهران» |
| honorific before a name («أ.د.»، «الدكتور») | mapping | 79 | 76 | 5 / 63 / 8 | 0089-006-005-006 1:5 «دكتور» |
| the article's own DOI | not asked | 64 | 61 | 0 / 9 / 52 | 0130-025-097-004 1:5 "Doi:10.29343/1-96-4" |
| journal section (rubric) | not asked | 34 | 34 | 0 / 0 / 34 | 0130 «المقالات»، «البحوث والدراسات» |
| closing signature / place and date | mapping | 51 | 28 | 0 / 20 / 8 | 2483-000-019-001 «تحريرا في : ٢٢ / ٥ / ٢٠٠٢» |
| role phrase (by, prepared by) | mapping | 18 | 17 | 2 / 13 / 2 | 0368-000-094-003 «ترجمه عن الانجليزية» |
| affiliation-like text | gemini missed | 15 | 14 | 0 / 12 / 2 | 0085-022-086-008 «الناشر: الهيئة العامة السورية للكتاب» (a reviewed book's publisher) |
| journal / volume / issue line | gemini missed | 19 | 13 | 1 / 11 / 1 | 1152-013-001-004 "2023, Volume:13,Issue 1." (how-to-cite line) |
| history dates | gemini missed | 11 | 9 | 0 / 7 / 2 | 2461-003-001-005 «تاريخ القبول: 16-01-2025» |
| abstract left in the body | mapping | 157 | 10 | 9 / 1 / 0 | 0767-010-002-007 p1 (v2 masters built before the move) |
| table note / source | not asked | 43 | 8 | 0 / 8 / 0 | 0470-021-037-015 "Source: Authors Computation with Eviews.12" |
| licence / copyright | not asked | 16 | 8 | 0 / 8 / 0 | 2280-006-001-014 "© 2024 … CC BY-NC 4.0" |
| keywords left in the body | mapping | 10 | 5 | 5 / 0 / 0 | 1148-041-116-018 (v2) |
| e-mail | mapping | 7 | 3 | | 0069-000-026-005 second e-mail of one author |
| ORCID, corresponding-author mark | gemini missed | 5 | 2 | 0 / 0 / 1 | 0130-027-105-003 p25-26: three ORCIDs on the English summary page |
| corresponding-author mark, phone / address, funding | not asked | 11 | 7 | v3.3 only | |

All rows with every example (stem, page, line, box, why): `out/audit.json` `leak_table`.

**Answer accounting** (values Gemini returned that are not in their field, `out/audit.json` `answers`):

| answer key | returned | not in its field | articles | why (code) |
|---|---|---|---|---|
| metadata.authors[].role | 544 | 508 | 382 | `meta43.names_pre` writes `<role>` only for translator / reviewer / editor / supervisor / rapporteur |
| metadata.authors[].aff_parts.city | 314 | 136 | 95 | the twin's (English) affiliation is dropped (M2); the rest are cities of affiliations stored as strings |
| metadata.subtitle | 213 | 114 | 114 | `masters41 Masters.front()`: no `<subtitle>` when it is inside the printed title lines |
| metadata.authors[].affiliation | 734 | 107 | 70 | `meta43.names_pre` (Latin fold) / `meta43.enrich` (same_as) keep the twin's aff only if the main contrib has none |
| metadata.authors[].aff_parts.institution / department / country | 1,420 | 236 | | same as above |
| enrich.authors[].affs[] (v3.5b) | 622 | 140 | | same as above (the twin's parts) |
| metadata.abstract / keywords (v2) | | 157 + 50 | 10 | v2 masters older than the abstract / keywords moves (M3) |
| parsed reference parts | 78,689 | 1,059 | | 297 titles, 123 pages, 110 years («د . ت»), 84 urls, 81 sources: `refs43.citation ok()` needs an exact substring, the masters de-hyphenate line breaks («Psychol- ogy») (M7) |

Counts: fixes 24,528 returned / 32,506 in JATS (the letter fix adds); sic 3,932 / 3,754; math 617 / 551; missed 203 /
110 (worth a look: half the «missed» lines Gemini returned are not in the JATS); calls 7,063 / 6,978; figure
descriptions 2,693 / 2,633.

**Bilingual pairs** (articles that print both an Arabic and a Latin form):

| pair | printed both | both in JATS | linked | both in platform |
|---|---|---|---|---|
| title / translated title | 156 | 153 | 153 | 152 |
| author names | 116 | 97 | 89 | 97 |
| **affiliations** | **104** | **33** | **28** | **33** |
| **posts** | **44** | **0** | **0** | **1** |
| abstracts | 162 | 157 | 157 | 157 |
| keywords | 114 | 111 | 111 | 112 |

Names: v3.5b 80 / 80 linked (same_as works); v3.3 only 9 of 35 linked. Affiliations and posts are where the second
script is lost.

**JATS → platform.** Almost everything that is a JATS field reaches a platform row. Short: printed translated titles
190 → 183 (11 articles), references 7,811 → 7,576 citation containers (20 articles, mostly v2 masters without parsed
references), kwd per article (10), history dates and the conference of 0130-019-073-004 (1). 26 platform columns are
never filled by a current article, among them `byline_mentions.is_corresponding` and `.ids` (no corresponding mark or
ORCID reached JATS: 0 in the masters), `affiliation_mentions.anchor_pk` (no affiliation has its ink anchor),
`publication_dates.day / month_name_printed / anchor_pk`, `citation_mentions.died / ms_library / ms_shelfmark /
ms_folio`, `figures.label` (`out/audit.json` `columns`).

## False alarms (checked on the scans)

83 leaks sampled (3 per row), 82 looked at (one page image missing on this machine): **1 false alarm (1.2%)** — a
3-letter title word printed in the byline area, which the title field holds. 17 more are real leaks with the wrong
"what it is" label (a disclaimer called a post, a translation source called a signature…); the kind and the leak are
right. Earlier rounds of this audit found and removed false alarms of four sorts, so the list above is the cleaned one:
labels left over beside stored values («تاريخ الاستلام:» when the date is stored), a title printed again on page 2,
Latin names with superscript marks («Faisal1»), and ALTO boxes re-laid in mixed-script lines. Score:
`out/verify/score.json`.

## Fixes, ranked (proposals; no pipeline code was changed)

**Mapping (free: rebuild the masters from the saved answers, then reload):**

1. **M1 — keep each author's post / rank as a field** (508 answer values, 382 articles; 273 lines in 169 articles). In
   `experiments/43_rehearsal/meta43.py` `names_pre`, the `if kind:` branch: when the role phrase is not a
   translator / reviewer / editor / supervisor / rapporteur and not an honorific, write `<role
   content-type="position">`; `47_platform_v2/parse47.py contrib_extras` then fills `byline_mentions.role_phrase` and
   `affiliation_mentions.position_title`.
2. **M2 — keep the twin's (English) affiliation, e-mail and post** (107 + 236 + 140 values, 70 articles; 196 lines in 96 articles;
   the owner's example). `meta43.names_pre` (Latin fold: `for e in la: if e.tag in ("email", "aff") and
   ar.find(e.tag) is None`) and `meta43.enrich` (same_as, the same line): append the twin's `aff` as a second
   `<aff xml:lang="en">`; `parse47.affiliations_v35` loads it as a second affiliation row. Then the bilingual
   affiliations go from 33 to ~104 of 104.
3. **M3 — rebuild the 54 v2 articles with today's code** (abstracts 157 lines, keywords, dates in the body).
4. **M4 — bylines printed in the text** (423 lines, 148 articles: closing signatures, an English byline on the summary
   page, author notes). `41_azure_structure/masters.py` keeps them as `<p content-type="byline">`; tag them as
   `<sig-block>` / extra `contrib` printings when their text matches an author (jats43.fill_slots).
5. **M5 — the subtitle as its own field** (114 articles; `masters41 Masters.front`).
6. **M6 — keep the honorific** (79 lines, 76 articles; `meta43.names_pre` when the role phrase is only an honorific).
7. **M7 — parsed reference parts at a hyphenated line break** (`refs43.citation ok()`, compare with the
   de-hyphenated text too).

**Prompt (before gate 2: the expensive part; each needs a small paid check first):**

1. **P1 — authors[].position** as its own exact-substring value. M1 saves what Gemini already returns in `role`; P1
   makes it reliable (Gemini also puts the post inside the affiliation string: «أستاذ مساعد مناهج الطفل بقسم…»).
2. **P2 — the article's own DOI, the licence / copyright line, the journal section** (64 + 16 + 34 lines; 0130 prints
   a DOI on every article since 2018 and Gate 2's education journals will too).
3. **P3 — every printing of an author** (the English byline on the summary page with ORCID and corresponding mark;
   0130-027-105-003 lost three ORCIDs that way under v3.5b).
4. **P4 — nothing to add for**: table notes and sources, corresponding author, ORCID, conference and book-review
   details leak only under v3.3, which did not ask; v3.5b does.

## Files

`audit61.py` (per article), `fields61.py` (folding, JATS classes, detectors, what each prompt asks), `answers61.py`
(answer, bilingual, platform accounting), `aggregate61.py` (corpus), `verify61.py` + `verdicts61.json` (the scan
check), `test_audit61.py`, `progress.md`. Outputs (gitignored): `out/articles/` (132 MB), `out/audit.json`,
`out/verify/`, `out/shots/` (the Desk page).
