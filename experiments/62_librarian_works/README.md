# 62: the librarian for cited works

## Question

Experiment 56 tested this for institutions. Here the question is cited works: can an AI curator, working beside the
machine's rules, settle the cited-work cards the way a librarian walks a card catalogue? The calls are:

- which cards are one work (misprints, short versus long forms, editions);
- which cards hold several works;
- which cards are not works at all (a journal's name, an issue);
- which cards are publications Mandumah holds.

A second question is how well this can be verified without the owner reviewing samples. The answer is a blind second
judgement, adjudication of every disagreement, and hard consistency checks.

## Method (2026-11-02, $0: Claude is the librarian, no API call)

Release: `R20261023T005909`, pinned in `norm62.release()`. It covers the 780 current articles: 9,137 active cards and
13,695 citations (the Quran and hadith excluded, as in experiment 52). The release, `marc.db` and experiment 52 were
read only.

1. **Cards.** `build62.py` dumps each card with its members (printed citation, parsed fields, note, body text), its
   links and its relations.
2. **Catalogue.** `catindex62.py` makes one sequential pass over marc.db's 1.56M records (17 min, 1.07 GB), keeping
   388,167 records. It scores every card with probe A's thresholds: 841 accept, 183 candidate, 188 relation. On
   gate 1's cards this matches probe A in 614 of 645 accepts.
3. **Candidates.** `cands62.py` builds the candidate pairs from:
   - folded fuzzy titles, with one misprinted letter forgiven;
   - short forms inside long titles;
   - author surnames, compared with a transliteration skeleton.

   It examined 143,810 pairs and kept 1,015 candidate pairs. These became 505 merge packets (clusters cut at 12 cards).
   The other packets are 88 split, 263 not-a-work and 1,224 catalogue packets.
4. **Judging.** Every packet was read using `tools62.py`: the card, the article's own text before the note call
   (which says what «ديوانه» is), cards already seen, and the catalogue.
   - Each call is in `overrides62.json` (752 calls, each with a reason).
   - `decisions62.py` writes `out/decisions62.jsonl`. It is append-only, and a changed answer supersedes the old one.
     Each decision carries its kind, reason, evidence ids, confidence, basis, whether the rule stood, and its size.
5. **Verification**, in place of the owner's 30-item sample:
   - **Blind round 1** (`blind62.py make` / `score`): 156 decisions drawn at random within each kind (seed 6262),
     written as evidence only. A separate sub-agent re-decided them without seeing the first answer.
   - **Adjudication** (`adjudicate62.py`): every disagreement was read against the print, the body text and the
     record, and the verdict recorded with which side was right. Each error then led to re-reading the population
     it came from.
   - **Hard checks** (`check62.py`), over all decisions:
     - transitivity;
     - authors with nothing in common;
     - death dates more than 5 years apart;
     - impossible years;
     - a thesis and an article in one work;
     - one work linked to two unlike records, or one record linked from two works.
   - **Rules audit** (`rules62.py`).
   - **Blind round 2** (`make2` / `score2`): 160 more decisions, drawn after the fixes, from the kinds that decide
     what can be applied (100 links, 40 same-work, 20 not-a-work).
   - **Recall** (`recall62.py`): for 150 random cards, the 6 nearest cards the blocking did not pair were read by
     hand (810 pairs).
6. **Results.** `finalize62.py` replays the standing decisions into the after-state. `escalate62.py` lists the cases
   for the owner. `scale62.py` makes the cost estimate.

## Result

**Before and after** (`out/numbers62.json`; proposals only, nothing applied):

| | machine | with the librarian |
|---|---|---|
| cited works | 9,137 | 8,850 |
| works cited by 2+ articles / 3+ articles | 209 / 58 | 289 / 79 |
| gate 1: the journal's works cited by 2+, vs random sets of 126 | 84 vs 10.85 (7.7×) | 118 vs 16.65 (7.1×) |
| citations to a work Mandumah holds (all / journal 0130 / random 600) | 6.24% / 15.82% / 2.43% | 7.34% / 18.06% / 3.07% |

The changes behind these numbers:
- 304 pairs joined, 86 of them as editions;
- 25 cards split (56 citations moved);
- 76 journal-name cards dropped, 178 retitled, and 6 split to one work per citation;
- 905 links to Mandumah made by the librarian;
- 32 of link47's links contradicted.

Most cited works after the librarian: لسان العرب 24 articles (23 before, joined with «اللسان»), المقدمة 12,
وفيات الأعيان 10, الكتاب 8, then معجم الأدباء, الكامل, معجم البلدان, القاموس, كشف الظنون and the DSM at 7 each.

**Decisions.** 2,605 stand.

| question | decisions |
|---|---|
| pairs | same work 218, edition 86, part of 1, different works 703, unsure 19 |
| cards | not a work 265, split 25, one work 63, unsure 1 |
| catalogue | links 913, relation 225, no link 84, unsure 2 |

- Confidence: about 1,650 high, 830 medium, 120 low.
- The proposing rule stood in 1,856 decisions; 749 needed judgement (world knowledge, the article's own text, the
  catalogue record).

**Verification** (`out/precision62.json`, `blind62_adjudication.json`, `blind62b_adjudication.json`):

- **Round 1:** 138 of 156 agree (88.5%). Of the 18 disagreements, the second judge was right in 14, the librarian in
  3, and both readings were defensible in 1.
- **Round 2:** 153 of 160 agree (95.6%). Of the 7 disagreements, the second judge was right in 4, the librarian in 1,
  and both were defensible in 2.
- **Measured precision** (both rounds, with adjudication):

  | kind | right | precision |
  |---|---|---|
  | same work | 64/65 | 98.5% |
  | edition of one work | 15/15 | 100% |
  | different works | 24/25 | 96% |
  | card split | 10/10 | 100% |
  | card is one work | 10/10 | 100% |
  | not a work: the verdict | 35/35 | 100% |
  | not a work: the action | 32/35 before the fixes, 20/20 after | 91.4%, then 100% |
  | links | 124/130 | 95.4% |
  | links passing rule K1c (title, author, year and venue fit) | 108/109 | 99.1% |
  | the other links | 16/21 | 76.2% |
  | relation | 12/12 | 100% |
  | no link | 6/10 | 60% (3 of the misses were relations, 1 a missed link) |

- **Unsure:** all 4 in the sample could be decided. The second judge was right in 3.
- **Fixes:**
  - all 18 adjudicated errors;
  - the not-a-work actions of 26 cards, from re-reading the 35 decisions where the action rule and an author test
    disagreed;
  - 13 no-link decisions turned into relations;
  - 2 review records that had been linked as the work (found by the rules audit);
  - 11 links whose venue or form did not fit, found by re-reading the 157 links where it was in doubt.
- **Hard checks, now:** transitivity 0, death dates 0, years 0, type 0, catalogue 0. The 18 author findings are one
  person printed two ways («ابن حنى» = ابن جني, yaagoubi = yaacobbi). Earlier runs of the checks caught three real
  errors, all fixed:
  - an English title of an Arabic article linked to another record;
  - the Sahih Muslim / al-Nawawi commentary chain that a fix had created;
  - the review records above.
- **Caveat:** the second judge is the same model. Agreement can hide a shared mistake, so these precisions are upper
  bounds. The checks and the rules audit are the independent part.

**APPLY rule (proposed):** apply a kind only when it is right in at least 98% of the sample; never apply unsure.

- **Apply:** edition_of, same_work (98.5%), split_card, card_ok, not_a_work (after the action fixes), relation, and
  links passing K1c (696 links).
- **Hold:**
  - the other 217 links: no clean measurement after the re-read;
  - different_work (96%): holding it loses nothing, because the two cards stay apart as they are today;
  - no_link: nothing to apply.

**For the owner: five questions** (`out/escalate62.json`, with Yes / No / Unsure on the Desk):

1. Is «صحيح مسلم بشرح النووي» Muslim's book or al-Nawawi's commentary?
2. Are the DSM's editions one work?
3. Is a chapter cited under its author's name a citation of the collective book?
4. Are a thesis and the article drawn from it two works?
5. When the same text appears in two journals, should the citation stay unlinked to the one Mandumah holds?

**Recall** (`out/recall62.json`):
- In the hand-read sample, the blocking missed 1 duplicate, a translated title («Children's Literature as Science and
  Art» = «أدب الأطفال علم وفن»), against 6 it found for the same cards: about 86% (small sample, an upper bound).
- 238 of the Desk detector's 290 "possibly the same work" pairs were in front of the librarian. The 52 outside are
  mostly different works by one author.

**Hard calls:**
- al-Tabari's history under its two titles;
- Ibn Khuzayma's «الصحيح» ≠ Sahih Muslim (they share only the nisba);
- «كتاب العين» ≠ Sibawayh's «الكتاب»;
- «تقريب التهذيب» ≠ «تهذيب التهذيب»;
- «الخزانة» with a volume and page in a grammar article = al-Baghdadi's «خزانة الأدب»;
- «ديوانه» resolved to Abu Nuwas by the article's own text;
- «ثلاثة أسئلة صعبة» = كمال السيد's «عمال التراحيل: ثلاثة أسئلة صعبة», in an article on عمال التراحيل;
- mixed cards split: «علم النفس التربوي» (3 books), three Musnads, a "Late Middle Kingdom" card holding 8 works;
- journal-name cards («مجلة الطفولة العربية» holding 4 different articles).

**Rules learned** (`out/rules62.json`; kept when a rule reproduces the librarian's answer at least 98% of the time):

| rule | reproduces | kept |
|---|---|---|
| K1c: title, author, year and venue fit → the record is the work | 696/698 | yes |
| C1: a card titled with a journal's name is not a work | 73/73 | yes |
| P6: a thesis and a journal article are different works (a relation) | 12/12 | yes |
| K1b: as K1c, without the venue check | 748/764 (97.9%) | no |
| P1: same title + same author → one work | 82/91 | no |
| P4: authors contradict → different works | 141/157 | no |
| P8: a short generic title with the author unknown → do not join | 99/138 | no |

The ones not kept show where judgement is needed: «سر صناعة الإعراب» printed under «ابن حنى», and a thesis versus its
article.

**Scale** (`out/scale62.json`):
- **Per judged question:** about 2,430 tokens in for a pair, 1,775 for a catalogue question, and 300–470 out (at 2.5
  characters a token, an assumption).
- **Growth:** cards and distinct works grow about linearly with articles (n^1.01: most works are cited once). Candidate
  pairs grow as n^1.39 until the blocking caps them.
- **Batch list price, rules first, judgement only to the model:**

  | | Opus 5.5 | Sonnet 5.5 | Haiku 4.5 |
  |---|---|---|---|
  | gate 2 (3,460 articles) | $30–40 | $16–21 | $8–10 |
  | education (162,816) | $1.5k–5.8k | $0.8k–3.0k | $0.4k–1.5k |
  | 1M documents | $9k–67k | $5k–35k | $2.5k–18k |

  In each cell, the low figure has pair questions growing like cards; the high figure uses the fitted n^1.39.

**Desk:** `/librarian/works` (experiment 49: `desk/librarian_works.py`, `web/pages/librarian/works.tsx`,
`experiments/49_correction_desk/tests/test_librarian_works.py`). It shows:
- the proposals-only banner and the before/after numbers;
- the precision per kind against the 98% mark, and the APPLY rule;
- every disagreement and who was right, and the checks;
- the rules and the scale estimate;
- the five escalated cases, the only ones with Yes / No / Unsure (append-only table `librarian_works_verdicts`, made
  by the module itself);
- every decision, with filters.

Screenshots are in `out/shots/`.

## What it changed

`src/` was not touched. In the Desk, one new module, one page and one test file were added, plus one include line in
`desk/api.py`.

**Applied on 2026-11-02 by [experiment 67](../67_apply_works/README.md).** The owner kept the APPLY rule and answered
the five questions with five rules for the whole index (D40–D44 in `docs/decisions.md`):
1. «صحيح مسلم بشرح النووي» counts as Sahih Muslim, al-Nawawi's commentary its edition (D40). The different_work
   D62-42695029d1f3 became an edition_of; the edition_of D62-816f18302505 (that card and al-Nawawi's «شرح صحيح مسلم»)
   was not applied.
2. The DSM's editions are one work, each edition kept (D41).
3. A chapter cited under its own author is its own work, part of the collective book (D42): the same_work
   D62-b54b601d5028 became two chapters of a book made for them.
4. A thesis and the article drawn from it are two works, related, derived from (D43).
5. The same text in two journals is linked to the one Mandumah holds, marked same text (D44): 9 cards.

1,581 decisions of `agent:librarian` were imported through the Desk's `ops.decide` (each carrying this experiment's
decision id, basis, confidence, the blind rounds that sampled it and the rule), and release `R20261102T174226` was
built from them: 8,850 cited works, 288 cited by 2+ articles, gate 1 118 vs 16.7, 6.6% of references held (this
experiment's 7.34% counted all 913 links; 217 are still proposals). Still proposals: the 217 links outside K1c,
different works, no link, every unsure. The Desk page's banner says so.
