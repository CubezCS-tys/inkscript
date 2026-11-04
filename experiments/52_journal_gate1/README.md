# Experiment 52 — gate 1 of the Education Citation Index: one journal, read whole

**Question** (owner, approved 2026-10-22, Gemini cap $32 on top of the log). Run one whole education journal,
2005–2025, through the full pipeline with prompt v3.5b. Then measure how dense the bridges are inside one journal:
people, institutions, shared cited works, citations inside the journal, links to Mandumah's catalogue. Is that
enough to justify gate 2, about 10 education journals?

**Answer.** Yes. Inside one journal every bridge but co-authorship is far denser than in a random set of the same
size.
- Authors write again.
- Institutions repeat.
- Cited works are shared seven times as often.
- A sixth of all references land on a work Mandumah holds.
- The journal cites itself: 39 references in 24 of the 126 articles point at 37 of its own articles.

Three bridges are thin:
- repeat co-authorship (one pair);
- citations between the articles of this run itself (10 links), because the bucket's gaps cut out the years in
  between;
- corresponding authors (none marked).

Gate 2 is justified. What gate 1 cannot measure is the bridges *between* journals, and that is gate 2's question.

Owner's page: **http://127.0.0.1:8004/gate1/** (`out/gate1.html`). The articles beside their scans:
http://127.0.0.1:8899/j0130_final/index.html.

## The set

مجلة الطفولة العربية (catalogue `journal_code` 0130, Kuwait), articles (`type = 'بحوث ومقالات'`) from 2005 to 2025.
- The catalogue lists 389. **195 are in the main bucket**, with 3,667 pages. All 195 were fetched; all pass the
  PDF/Azure checks.
- The bucket holds only 2005–2008 (69 articles), 2017–2019 (64) and 2023–2025 (62).

**Priced first** (`out/PLAN.md`):
- The dry run for all 195 says $35.06 expected. With the judge that makes about $42.8, over the cap.
- So, as instructed, the run covers **2010–2025: 126 articles, 2,439 pages**. Because of the gaps, 2010–2025 and
  2015–2025 are the same set: the articles of 2017–2019 and 2023–2025.
- The 69 articles of 2005–2008 are fetched (`out/sample52_all.json`) and would cost about $15 more.

## Method

The exam's sequence (experiment 43, "The exam: second 300"), with v3.5b. Every step's result and time is in
`progress.md`.

1. **run43** on Batch: `run43.py --set d --prompt v3.5b --thinking low --run j0130 --cap 103.30 --max-enqueued 2500000`.
   - It ran as 10 jobs, plus 5 more for the retries.
   - The first launch was killed by `watchdog52.sh` at 3.09 GB while building job 1. Nothing had been sent. run43 now
     drops each article's Azure JSON once its request is built, and jobs are cut at 2.5M tokens. Peak after that:
     2.0 GB.
2. **rechunk43** for the 2 MAX_TOKENS chunks:
   - 0130-020-080-001 pages 17–24;
   - 0130-025-099-004 pages 11–20.

   9 smaller requests, all STOP. **126/126 articles answered.**
3. **Masters** with today's rules and the letter fix (`lettersfix43.py plain --set d`; `build52.sh`): **126/126 JATS
   DTD + ALTO XSD valid**.
   - The letter fix changed 408 letters in 331 words: ی→ي 250, ک→ك 119, ی→ى 27, ھ→ه 9, ہ→ه 3. None was left
     unplaced (`out/j0130/letters_124.json`, `letters_2.json`).
   - The letter-fix agent's own builds were finished. Its first-300 control was still being rebuilt.
   - One article, 0130-020-080-001, was first invalid. v3.5's `enrich43` moved a table footnote's only paragraph into
     `table-wrap-foot` and left an empty `fn`. Fixed: such a footnote now moves whole, with its id, so the call in
     the cell still points at it.
4. **Flags** (rules 15232e3fc5).
5. **Judge**: Argon, judge v2, Batch, with the frozen two keys.
   - Pages: all 239 flagged pages plus 50 random unflagged ones (seed 5245), 289 in all.
   - Retries: all 5 retry pages were sent (seed 5247).
   - Screenshots: experiment 40's Playwright venv is not on this server, so `out/pwvenv` was made (playwright 1.63.0,
     matching the cached chromium-1243). `judge43` reads `JUDGE43_PW`.
6. **Patches** → `out/j0130_final` (`final52.sh`): 8 applied in 6 articles; 126/126 valid.
7. **Views**: `j0130` and `j0130_final` are symlinked in `experiments/41_azure_structure/out/views/`.
8. **Platform**:
   - `gate1.db` is a copy of `platform_v2.db`, made with SQLite's backup API.
   - Loaded there: `load47.py --run j0130 --kind base`, then `--run j0130_final --kind final`. The final run is shown
     for all 126.
   - Then `link47.py --db gate1.db --work out/link_work`; orphans 0. `platform_v2.db` was never written.
9. **Measures**, with the same code on both sets:
   - `measure52.py` (probe C/D definitions; checked against the 600: 702/638 bylines, 113 shared works, coupling 76,
     all the same as experiment 48);
   - `catalogue52.py` (probe A's `classify`/`match`/`decide`, imported unchanged and pointed at gate1.db);
   - `detect52.py` (the Desk's three detectors, imported unchanged; tasks counted, nothing written, no PostgreSQL
     connection);
   - `fields52.py` (the v3.5b fields in the JATS).

   Besides the whole 600, the 600 was cut into **20 random sets of 126** (seed 5250), so the journal is compared
   with a random set of its own size.

Plumbing in experiment 43 (no change to any earlier output):
- set `d` in run43, pictures43, flags43, views43, judge43, patches43, summary43, retry43, rechunk43 and lettersfix43;
- the Azure-cache drop in run43;
- `JUDGE43_PW`;
- the `enrich43` footnote fix.

Experiment 47: `ink47.azure_paths` also reads `out/sample52_all.json` (one line).

## Results (journal, 126 articles, against the random 600 and against same-size random sets of 126)

| bridge | journal | random 600 | random 126 (mean of 20) |
|---|---|---|---|
| Authors with 2+ articles | **16 of 130** (they hold 50 bylines; أحرشاو 8, عبدالله 5) | 10 of 692 | 0.25 |
| Byline authors with an authority id | **99%** (162/164) | 91% | 92% |
| Repeat co-author pairs | 1 | 0 | 0 |
| Institutions in 2+ articles | **26 of 66** | 34 of 208 | 3.6 |
| Affiliations at an institution seen in 2+ articles | **76%** | 37% | 14% |
| References (Quran excluded) | 3,920 (31.1 an article) | 9,679 (16.1) | 2,079 |
| Cited works shared by 2+ articles | **84** | 113 | 11.3 |
| Largest group of articles joined by shared references | **48** (of 114 with references) | 76 (of 337) | 9.1 |
| **Citations inside the journal** | **39 links, from 24 articles, to 37 articles of the journal** (11 of them self-citations) | 1 link inside the 600 | — |
| References landing on a work Mandumah holds | **16.9%** (661 of 3,920; with link47's links 18.2%) | 2.9% | — |
| … among Arabic article, thesis and conference references | **62%** (631/1,026) | 31% | — |
| Desk tasks per article | 1.22 (154 tasks, 92 articles) | 0.37 | — |
| Desk tasks per 100 references | 3.9 | 2.3 | — |

More on these numbers:
- **Citations inside the journal.**
  - The cited articles span 1994–2024.
  - 15 of them are in the bucket (2005–2025). 9 are in this run, and 10 of the links point at those 9.
  - The 39 links were read one by one. 38 are right. One is wrong: link47 linked أحرشاو's «المدرسة ورهان
    الديمقراطية», but the printed reference names مجلة المدرسة المغربية.
  - 53 references name the journal. 17 of them found no catalogue record, so the true count is higher.
- **Self-citations.** 11 of the 39 links are an author citing their own earlier article. The count is a name match:
  two words of a byline name in the reference's first 60 characters.
- **Shared works are an undercount.** The Desk's «possible same work» detector finds 142 pairs touching the journal,
  for example «الانعكاسات التربوية لاستخدام الأطفال الألعاب الإلكترونيَّة…» printed in two wordings. Each pair a
  person confirms raises the 84.
- **Most-cited works.**
  - لسان العرب (9 articles);
  - DSM (4);
  - textbooks of educational statistics and measurement, each cited by 3: عبد الحفيظ & باهي, النبهان, جروان, الزيات;
  - «مجلة الطفولة العربية» as a cited work (4): references naming only the journal, joined by name. This is the kind
    of card the Desk's author-less task exists for.
- **Most frequent institutions.**

  | institution | articles |
  |---|---|
  | جامعة الإسكندرية | 8 |
  | جامعة الملك سعود | 7 |
  | وزارة التربية | 7 |
  | جامعة القدس | 7 |
  | جامعة حلب | 5 |
  | جامعة الخليج العربي | 5 |

  By country: Morocco 12, Saudi Arabia 7, Egypt 7.

**Books against articles** (probe A's classifier, share of cited works):

| type | journal | random 600 |
|---|---|---|
| journal articles | **49%** | 26% |
| books | 29% | 45% |
| theses | 9% | 4% |
| book chapters | 3% | 4% |
| conference papers | 3% | 3% |
| websites | 4% | 3% |
| classical works (turath) | **0.4%** | 5% |

An education journal cites articles and theses, which Mandumah holds. That is why the held share is six times the
600's.

**Quality.**
- **Flags** per 100 pages: high 0.86, medium 3.85, low 6.64. The exam after the judge: 0.53, 7.17, 12.22. 20 of
  the 21 high flags are tables with lost cells.
- **Judge**: 289 pages, **30 findings**. The pages split like this:

  | pages | judged | nothing wrong | two keys, applied | page retry | to a person |
  |---|---|---|---|---|---|
  | flagged | 239 | 216 | 2 | 5 | 16 |
  | random unflagged | 50 | 47 | 0 | 0 | 3 |

  - By type: wrong_kind 22, picture_box 4, table_box 3, text_not_on_scan 1.
  - All 5 page retries passed the code check and were applied.
  - 22 findings go to a person (20 of them «wrong kind»).
- **The model's fixes**: 7,638 in all, 599 of them flagged as misprints (sic). 86 articles carry the
  «many fixes» flag.
- **Ten random pages looked at beside the scan** by this agent (seed 5246; `out/look10_verdicts.json`):
  - **9 right, 1 minor, 0 serious**;
  - the minor one is 0130-025-100-003 p13: two numbered items overlap their neighbours in the Layout view; the text
    and structure are right.

**The new v3.5b fields** (final masters):
- **Document types**: research 111, editorial 3, report 3, other 3, conference_paper 2, book_review 2,
  interview 1, review 1.
- **References**:
  - editors in 121 references (42 articles) and translators in 77;
  - editions in 173;
  - a thesis's degree in 300 (320 thesis references);
  - access dates in 83, cited pages in 38, a year's calendar in 35.
- **Corresponding authors: 0.** The model returned no `corresp` mark.
- **Table notes**: 97, plus 9 «المصدر» lines.
- **Smaller fields**: figure kinds on 129 figures (chart 43, diagram 30, photo 17, cartoon 17, …); 3 conferences,
  3 thesis summaries, 3 reviewed books, 1 translation, 5 publisher notes, 2 scan problems.

## Cost (from the log; cap $32, absolute $107.90)

Log before $75.902, after **$100.146**: **$24.24 spent, $7.76 under the cap.**

| | spend |
|---|---|
| run (incl. the 9 rechunk requests, $0.52) | $21.92 |
| judge (289 pages, $0.0072 a page) | $2.08 |
| page retries (5) | $0.25 |
| **total** | **$24.24**: $0.192 an article, $0.0099 a page |

On the exam the cost was $0.0094 a page. These articles are long: 19.4 pages and 31 references each.

## What it means

The bridges a citation index lives on are journal-shaped. Inside one journal:
- people recur 60 times as often as in a random set of its size;
- institutions about 7 times;
- shared works about 7 times;
- the coupled group is 5 times larger.

Most of what it cites is held by Mandumah. Gate 2 should take about 10 education journals with overlapping years, so
that citations between journals and between consecutive years can be counted. Here the bucket's year gaps hid them.

Before scaling:
- the catalogue matcher should be wired into link47 (probe A's matcher finds 645 held works, link47's own links
  about 51 more);
- the «possible same work» queue should be worked;
- the bucket's coverage of each candidate journal should be checked first. This journal has 195 of 389 articles.

## Files

- **Code**:
  - `sample52.py` (the set);
  - `build52.sh` and `final52.sh` (masters, patches, flags, views, summary);
  - `judge_pages52.py`, `judge_summary52.py` and `retries52.py` (copies of the exam's);
  - `make_index52.py`;
  - `measure52.py`, `catalogue52.py`, `detect52.py` and `fields52.py`;
  - `gate1page52.py` (the owner's page);
  - `watchdog52.sh`.
- **`out/`** (gitignored; Mandumah text stays here):
  - `PLAN.md`, `sample52.json` (the 126), `sample52_all.json` (the 195), `fetch/` (881 MB), `dry_run*.json`;
  - `j0130/` (raw, rules, masters, views, flags, judge pages and summary, retries plan), `j0130_final/`;
  - `bridges_*.json`, `catalogue/` (works, classified, matches, decisions, results, inside), `detect_*.json`,
    `fields_*.json`, `look10*.json`, `spend.json`, `gate1.html`;
  - `pwvenv/` (Playwright for the judge's screenshots), `link_work/` (link47's cache for gate1.db).
- **Database**: `/home/appuser/data/platform_v2/gate1.db` (a copy; `platform_v2.db` untouched).
- **Desk page**: `experiments/49_correction_desk/web/public/gate1/index.html`, with `gate1` added to the rewrite in
  `next.config.js`. It holds Mandumah titles: keep it out of commits.
