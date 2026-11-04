# Experiment 54: choosing gate 2's journals

**Question** (owner, approved 2026-10-22; free, no model or external calls). Which ten or so education journals
(EduSearch) should make up gate 2 of the Education Citation Index? The set should have about 2,000–3,000 articles, so
that "do education journals cite each other?" gets a real answer. The criteria, in order:
1. complete over a common span of years (scan, Word file or nowhere);
2. likely to cite each other;
3. spread over the Gulf, Egypt, the Levant and the Maghreb, with 0130 included;
4. research journals rather than magazines;
5. no journal over about 25% of the set.

**Answer.** The recommendation is ten journals, 2010–2025: **3,460 articles**.
- **1,660 come from scans** (38,913 pages), **1,768 from Word files**, and **32 are nowhere**.
- Expected cost **≈ $456**; worst case **≈ $633**.
- A cheaper set of five journals has 1,344 articles and costs **≈ $152**.

Owner's page: **http://127.0.0.1:8004/gate2/** (`out/gate2_selection.html`). It shows a year-by-journal grid
coloured scan / Word / nowhere, with the set highlighted and the cost.

## The recommended ten (★)

| code | journal | country | years | articles | scan / Word / nowhere | scan pages | expected cost |
|---|---|---|---|---|---|---|---|
| 0130 | مجلة الطفولة العربية | Kuwait | 2010–2025 | 301 | 126 / 175 / 0 | 2,441 | $30 |
| 0165 | مجلة الطفولة والتنمية | Egypt | 2010–2025 | 363 | 145 / 218 / 0 | 2,802 | $35 |
| 0011 | رسالة الخليج العربي | Saudi Arabia (Gulf bureau) | 2010–2025 | 326 | 130 / 196 / 0 | 2,983 | $36 |
| 0523 | مجلة الدراسات التربوية والنفسية | Oman (SQU) | 2010–2024 | 507 | 346 / 161 / 0 | 5,858 | $66 |
| 1001 | مجلة جامعة طيبة للعلوم التربوية | Saudi Arabia | 2010–2023 | 191 | 89 / 102 / 0 | 1,610 | $19 |
| 0246 | مجلة اتحاد الجامعات العربية للتربية وعلم النفس | Syria | 2010–2025 | 482 | 194 / 269 / 19 | 6,359 | $74 |
| 1182 | مجلة جامعة القدس المفتوحة للأبحاث والدراسات التربوية والنفسية | Palestine | 2013–2025 | 688 | 340 / 335 / 13 | 5,764 | $69 |
| 0097 | المجلة العربية للتربية | Tunisia (ALECSO) | 2010–2024 | 156 | 84 / 72 / 0 | 2,952 | $33 |
| 0840 | دراسات نفسية | Algeria | 2010–2025 | 198 | 82 / 116 / 0 | 1,490 | $18 |
| 0013 | دراسات نفسية | Egypt (Ranm) | 2010–2025 | 248 | 124 / 124 / 0 | 6,654 | $74 |

The years are the catalogue's first and last year with a research article inside 2010–2025. 1182 began in 2013.

**Regions:** Gulf 4, Egypt 2, Levant 2, Maghreb 2. The largest journal is 1182, at 20% of the set.

**Why these ten** (each journal's reasons are on the page):
- **Cited by 0130.** 0130's 126 read articles link, through the catalogue, to the nine others from 42
  article–journal pairs:
  - 0165: 10;
  - 0013: 7;
  - 0011 and 1182: 6 each;
  - 0523: 4;
  - 0246 and 0097: 3 each;
  - 1001: 2;
  - 0840: 1.
- **Shared authors.** The authority-id overlaps inside the set are large:
  - 0523–0246: 92;
  - 1182–0523: 66;
  - 0011–0523: 46;
  - 0097–0246: 38;
  - with 0130: 0523 35, 0165 33.

  People who publish in several of the set's journals are what makes citations between journals likely.
- **Research journals.** 87–100% of their records are «بحوث ومقالات», except 0130 itself at 79%.
- **Word files are the right files.** All 150 sampled Word files (15 a journal) open with the catalogue's title (see
  "Surprises").

**If the set must land at or under 3,000:** drop 1001 (3,269 articles, about $436) or 1182 (2,772, about $387).
1182 is the stronger Levant bridge, so drop 1001 first.

## The cheaper set (◆, about $150)

0130, 0165, 0011, 0097 and 0840 (Kuwait, Egypt, Saudi Arabia, Tunisia, Algeria), 2010–2025:
- **1,344 articles**: 567 scans (12,668 pages), 777 Word, 0 nowhere;
- **$152 expected** ($145 with Flash for the Word step), **$216 worst**.

It keeps the two childhood journals, the pan-Gulf one and the two Maghreb ones. It has no Levant journal: the
cheapest is 0246 at $74. The largest journal, 0165, is 27% of this set.

## Cost

| | ★ ten | ◆ five |
|---|---|---|
| scan pages × $0.0108 (v3.5b, judge included; gate 1 really cost $0.0099) | 38,913 → $420 | 12,668 → $137 |
| Word articles × $0.02 (exp 53: $0.010 Flash – $0.028 Argon, lean) | 1,768 → $35 | 777 → $16 |
| **expected** | **$456** | **$152** |
| Word with Flash ($0.01) | $438 | $145 |
| worst case (scans $0.014 a page, +30%; Word $0.05, full Argon call) | $633 | $216 |

- **Scan pages** are the catalogue's page ranges. For gate 1's 126 scans they sum to 2,441 pages; 2,439 were read.
- **Prices double** after 1 December (Argon) and 1 January 2027 (Flash).
- **Word-route work not counted here:** experiment 53's code build has no Word-route runner yet, and its text-only
  call is untested (the <$1 test is still pending).

## Method ($0; read-only on marc.db, platform_v2.db, /home/adminuser and experiments 43/44/47/52/53)

1. **The articles.** [inventory54.py](inventory54.py) lists every EduSearch research record from 2000 to 2025:
   282,017 records, in 54 s at 0.27 GB, written to `out/articles.tsv`. Each is given a route:
   - **scan:** a stem in exp 44's `ids_main.txt`;
   - **Word:** a Word original in exp 53's `word_files_all.txt`;
   - **nowhere:** neither.

   No record has a legacy PDF without a Word file. For 2005–2025 the split is scan 162,816 (the same as ideas.md),
   Word 92,832 and nowhere 12,142.
2. **What 0130 cites.** [cited54.py](cited54.py) reads `platform_v2.db` read-only: 126 current 0130 versions and
   3,832 full references. It counts the accepted best catalogue links by target journal (619 links), and the
   `source_title` of journal references by name (`out/cited_by_0130.json`).
   - Names shared by several journals, such as «مجلة كلية التربية» or «مجلة العلوم التربوية», are shown as
     ambiguous (~).
   - The most-named Arab journals after 0130 itself (39) are:
     - «مجلة كلية التربية» 19 (ambiguous);
     - «مجلة العلوم التربوية والنفسية» 17 (ambiguous: Bahrain and others);
     - «مجلة جامعة دمشق» 15;
     - «المجلة التربوية» 15 (ambiguous);
     - «دراسات نفسية» 11 (ambiguous: 0013 and 0840);
     - «الطفولة والتنمية» 14 in two spellings.
3. **The journals.** [journals54.py](journals54.py) collects, per journal (41 s):
   - record types for 2010–2025;
   - fields of study and subject terms;
   - Mandumah authority ids of the authors of its research articles, 2000–2025.

   [rank54.py](rank54.py) builds `out/candidates.json`. Fields of study cannot tell journals apart: almost all are
   «التربية والتعليم». So topic is a TF-IDF cosine over subject terms against 0130. Its top matches are 0165 (0.31),
   0232, 1029 and 0085.
4. **Are the Word files the right articles?** [wordcheck54.py](wordcheck54.py) samples Word-only articles
   (seed 5454): 15 a journal for the ★ ten, 0233 and 0139; 6 for the rest. 328 files in all.
   - Native `.docx` files are read in place. `.doc` files are converted by soffice into `out/wordcheck/`, with
     their own profile, at ≤ 0.33 GB.
   - One batch hung for 20 minutes and was killed, so 0082's sample is 1 of 6.
   - It applies exp 53's first-page test (the body's `pgNumType/@start` against the catalogue's first page).
   - [titlecheck54.py](titlecheck54.py) adds the share of the catalogue title's words found in the file's first
     3,000 characters.
5. **The sets, the cost and the page.** [select54.py](select54.py) writes `out/selection.json`, `out/candidates.md`
   (all 37 candidates) and `out/gate2_selection.html`. The page uses `page54.css`, gate 1's look plus the grid.

## The candidates (2010–2025)

37 journals, chosen from 522 EduSearch journals. A candidate needed:
- a research share of at least 60%;
- education or psychology among its fields;
- most years present;
- plus the hubs and the journals 0130 cites, whatever their size.

The full table is `out/candidates.md` and the page's last table. Its columns: country, years, catalogue count, scan,
Word, nowhere, research share, pages an article, authors shared with 0130, cited by 0130 (articles / by name), Word
check, cost.

Left out, and why:
- **0085 المجلة التربوية (Kuwait) and 0040 مجلة العلوم التربوية والنفسية (Bahrain).**
  - These are the strongest hubs: 55 and 65 authors shared with 0130, 358 with each other, and cited by 11 and 9
    of 0130's articles.
  - But they have 982 and 928 articles (about 30% of a 3,000 set each) and cost about $150 each.
  - They are the first additions if gate 2 can be bigger.
- **0139 مجلة جامعة دمشق (Syria).** Cited by 10 of 0130's articles, but 683 articles at 34 pages, about $169. 0246
  shares 139 authors with it at under half the cost.
- **0233 المجلة الدولية للأبحاث التربوية (UAE).** 435 articles, about $104, at 33 pages an article. It is the swap
  for 1001 if a UAE journal is wanted.
- **0151 المجلة الأردنية في العلوم التربوية (Jordan).** 207 of its 468 articles are nowhere.
- **Most Egyptian faculty-of-education journals.** 600–4,000 articles each, at 36–80 pages an article: 0054 alone
  would be about $474.
- **0990 and 1631 (Morocco).** Gaps of 3–6 years in the catalogue, and no citation from 0130.

## Surprises

- **Experiment 53's first-page test needs the title beside it.** In the ★ sample, all 150 Word files carry their
  catalogue title (at least 60% of its words; 136 of them 85% or more).
  - Yet only 141 start on exactly the catalogue's first page.
  - The other 9 are one page off (5) or have no page number (4).
  - Over all 37 journals the pattern holds. Of 30 page mismatches, 25 are 1–3 pages off, all with the right title.
    The other 5 are numbered from page 1:
    - 3 have the right title (0040, 1029, 0073);
    - only 0056's 2 are wrong files (0% of the title).
  - On its own, the page test would have thrown out 0233 (7 of 15 "different", all with the right title).
- **The set is two-thirds Word in the early years.** Every ★ journal's 2010–2016 and 2020–2022 are mostly Word, the
  same gaps as 0130 (the bucket holds roughly 2016–2019 and 2023–2025). Without the Word route there would be no
  common span, and no citations between consecutive years.
- **Egypt's journals are long.** At 40–80 pages an article they are the costliest per article. Gulf and Maghreb
  journals run 16–28 pages.
- **The budget.** The repo's last note on credit (commit 66318da) says about £35 is left. Even the ◆ set needs a
  top-up.

## Files

Under `out/`, gitignored:
- `articles.tsv`;
- `cited_by_0130.json`;
- `journals.json`;
- `candidates.json`;
- `wordcheck.json` and `wordcheck/` (the converted `.docx` samples, 55 MB; propose deleting them after
  review);
- `selection.json`;
- `candidates.md`;
- `gate2_selection.html`;
- `shot.png`.

Copied to `experiments/49_correction_desk/web/public/gate2/index.html`. `gate2` was added to both static-page
rewrites in `web/next.config.js`.
