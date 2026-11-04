# Probe B: the same work across articles, and back references (experiment 48)

Data: `platform_v2.db` (read-only), shown versions; the JATS masters of `v33_300_final` and `v33_300b_fix3`.
No external or paid calls. Outputs: `experiments/48_linking_probe/out/b_works_and_backrefs/`.
**All verdicts here were made by me, an agent (Claude), from the printed citations and notes. No person has
checked them.** Intervals are 95% Wilson.

## Method

| step | script | output |
|---|---|---|
| dump every card, its members, and the mentions that count for it | `dump_cards.py` | `cards_dump.json` |
| distribution, top works | `dist.py` | `distribution.json` |
| over-merging sample, seed 4811, stratified: all 21 cards with 6+ members, 15 of 114 with 3–5, 15 of 775 with 2 | `sample_over.py` | `over_sample.txt` |
| detector: cards whose members print two non-overlapping author sets | `conflict.py` | `author_conflict_cards.json` |
| under-merging candidates: same author word + title equal / contained / similar after removing author words, «ابن», edition and volume marks | `under_cands.py` | `under_candidates.json` (154) |
| under-merging sample, seed 4812, 50 pairs | `sample_under.py` | `under_sample.txt` |
| census of all 113 cards cited by more than one article | `verdicts_cross.py` | `cross_article_judged.json` |
| back-reference sample, seed 4813, 61 stratified across link47's categories; notes read from the JATS `fn`s | `sample_backrefs.py` | `backref_sample.txt` |
| verdicts and summary numbers | `verdicts_b1.py`, `verdicts_b2.py`, `build_results.py`, `build_examples.py` | `b1_judged.json`, `b2_judged.json`, `results.json`, `examples.json` |

Cost: every script runs in under 1 s and under 70 MB. The work was reading the evidence: about 50 cards, 50 pairs,
113 cross-article cards and 61 back references, each with its notes.

## B1. The same work cited in different ways

**Distribution.** 5,478 cards. By members (full citations): 4,568 have 1, 775 have 2, 114 have 3–5, 21 have 6+.
Counting short forms and back references too: 4,115 / 867 / 355 / 141. By citing articles: 5,365 have 1, 73 have 2,
31 have 3–5, 9 have 6+. Only 339 of the 600 articles have any citation mention.

**Over-merging (two works on one card).**

| stratum | judged | right | wrong | serial |
|---|---|---|---|---|
| 6+ members (all 21) | 21 | 12 | 4 (19%, 8–40%) | 5 |
| 3–5 (15 of 114) | 15 | 12 | 3 (20%, 7–45%) | 0 |
| 2 (15 of 775) | 15 | 15 | 0 (0–20%) | 0 |

That puts about 27 of the 910 multi-member cards wrong. "Serial" means the citations name only a newspaper,
magazine or law-report series («اللواء», «مجموعة الأحكام», PSBA 1900): different items with no item title. They
are not works and should not get citation counts.

**The census of the 113 cross-article cards** (the ones that make co-citation and times-cited): 100 right, 1 mixed
(Ibn Khaldun's Muqaddima plus one editor's preface), 6 wrong, 6 serial. That is 88.5% right (81–93%). The errors
come from one cause. `build_cited_works` joins any two groups with the same title key when one side has **no author**
(`compatible()` is true for an empty set), and union-find then chains authors who have nothing in common through an
author-less member:

- «الديوان»: six poets' diwans on one card;
- «اللسان»: Lisan al-'Arab joined with Lisan al-Mizan;
- «المغني»: Mughni al-Labib joined with Ibn Qudama's al-Mughni;
- «التهذيب»: Tahdhib al-Tahdhib joined with Tahdhib al-Lugha;
- «بيانات غير منشورة»: "unpublished data" from two different bodies.

When every article on a card prints an author, 50 of 51 cards are right. When the join runs through an article
whose citation names no author, 50 of 62 are right. A second, smaller cause sits inside articles: `same_title`
accepts one title contained in another. That put six Egyptology works sharing "Late Middle Kingdom" on one card, and
joined Pomeau's «Beaumarchais» with Didier's «Beaumarchais ou la passion du drame».

**Under-merging (one work on two cards).** I found 154 candidate pairs. In the sample of 50: 35 are the same work
(70%, 56–81%), 13 are not, 2 unsure. That makes about 108 true duplicates. By rule:

- stripped titles equal: 4 of 4;
- one title contained in the other, with the same author: 28 of 34 (4 no, 2 unsure);
- similar titles: 3 of 12.

What the true duplicates look like:

- a short title against the full one: «الموشح», «البداية», «الأحكام السلطانية», «نفح الطيب»;
- the author's name taken into the title: «المقدّمة» vs «مقدمة ابن خلدون», each on 6–7 articles;
- alternate classical titles: Irshad al-Arib = Mu'jam al-Udaba'; Tarikh al-Rusul = Tarikh al-Umam; al-Jami' al-Sahih = «الصحيح»;
- reprints and editions: Bates 1914/1970, Guilford 1956/1978, Obeidat 1988/2012.

26 of the 35 would add a link between articles, and 16 would make a new cross-article work. Fixing them moves the
cross-article count from about 101 up towards 150. My candidate search cannot find translated titles (Sillamy's
*Dictionnaire de psychologie* and its Arabic «المعجم الموسوعي في علم النفس» are two cards), so recall is unknown.

**Cross-article co-citation.** 101 true works are cited by 2 or more of the articles. 82 of the 337 articles that
have cards share at least one work; 67 of those form one connected group. Almost all of it is classical Arabic
humanities: lexica, biographical dictionaries, grammar, hadith. The Quran is kept outside the cards (216 mentions in
32 articles); counted by articles it is the most-cited work. Top 30 (in `results.json`): 25 classical books, 2 hadith
collections, 3 modern (al-Zirikli's al-A'lam, al-Mu'jam al-Wasit, Zaydan), and 2 that are not works (the diwan
over-merge and the magazine al-Adab). No modern journal article reaches the top 30. The first is the GAD-7 paper,
cited by 2 articles.

**Editions, volumes, translations: what the data show, and a proposed rule.** Cards today already gather editions
when the title key agrees (al-Aghani in three editions; al-Bayan al-Mughrib in two editions with different editors;
Hair 2013/2016). They also gather the parts of one multi-part book (Lange & Schäfer, Teil I, II and IV). They split
editions when a subtitle or a misspelling changes the key. Volumes with their own authors stay apart, which is right
(Pictet IV, de Preux III). A translation is cited under its translated title, so it is split from the original. A
FRBR-like rule:

1. **Work** = the creator (author) plus a uniform title. Every edition, reprint, editor's edition (تحقيق), volume and
   translation belongs to one work. Citation counts and h-index count works.
2. **Edition** (an expression or manifestation) = translator or language, editor, publisher, place, year, edition
   number. This is the level that links to a catalogue record (a MARC record is a manifestation). A translation is
   its own expression of the same work, and the translator is credited as translator, not as author.
3. **Part**: a volume or part is a locator. A part with its own author is its own work, joined by `is_part_of`.
4. **Not works**: a citation that names only a serial (journal, newspaper, law reports) with an issue or date and no
   item title becomes a *serial citation* attached to the journal, for journal-level counts only. Court decisions
   become a *legal decision* (court + date + number). Neither ever gets a cited-work card.
5. **Short generic titles** («الديوان», «الكتاب», «المغني», «اللسان», «التهذيب», «الكامل», «الخزانة») join across
   articles only through an author, or through a *classical works list*: uniform title, alternate titles, author,
   and the short names each one is cited by. That list is built once by people who know the field, a few thousand
   entries.

## B2. Back references at scale

The 600 have 1,096 back references in 129 articles: 992 resolved, 25 inside a parsed citation, 79 unresolved.
link47's unresolved counts (111/36/24) include the 54 v2_55 documents, whose 96 back references are all unresolved.

**Resolved (47 judged):** 43 right, 2 wrong, 2 unsure. That is 91.5% (80–97%), or 95.6% (85–99%) of the ones I could
decide. Weighted by category size: 95% right, about 1.3% wrong, so roughly 14 of the 1,017 resolved are wrong.
The two commonest categories (previous-mention 10/10, chain collapsed 9/10) and same-author-earliest (9/9) were clean.
Both errors were in the small categories:

- **same-author+year**: an op. cit. *inside* a full citation (Tejera, in Roldán et al. eds., op. cit.) that refers
  to its container;
- **same-author-latest**: «Cabestan et A. Tomes, *Sartre*, op. cit.», where the book's title "Sartre" was taken for
  the author.

The proof pack's sample (older linker, 20 back references: 15 right, 1 wrong, 4 missed) is consistent with this. Its
"missed" Mujawir case is now resolved right.

**Unresolved (14 judged):** 5 correctly unresolved (no earlier full citation exists, or it is a court decision), 9
misses (64%, 39–84%). Why they were missed, and the rule that would fix each:

- «Id, p. 957» is not a marker, so it broke the chain. Rule: add «Id»/«Id.»/«ن.م».
- The hint swallowed the next citation in the same note («الرافعى، المرجع السابق … - أيضا مذكرات …»). Rule: cut the
  hint at «- أيضا», «؛», «وانظر».
- One earlier work by the whole name («عبد الوهاب المسيري»), refused because of stray words. Rule: when the whole
  name has exactly one earlier work, take it.
- A corporate author with a varied name. Rule: page continuity for corporate authors (the same p. 60 is cited earlier).
- An Arabic spelling of a Latin-script author («جاكندوب» = Jakendoff). Rule: name transliteration (medium effort).
- A full citation inside an explanatory note («The Wretched of the Earth» inside a note about Fanon), which breaks
  three later markers. Needs the parser to read citations inside explanatory notes.
- A full citation present but not matched («Sartre, une vie pour la philosophie»). Parser.

Also seen: a sigle defined in a note («Nous désignerons cette édition sous le sigle S.R.C.») is not tied to its
full citation. Ten later «Ibid.» go to the right short form, but the work card does not know it is Scarron's Roman
comique. Rule: read sigle definitions.

## B3. What is left for people

Per 600 articles today:

- **Back references:** about 189 decisions (79 unresolved plus 110 resolved at score ≤ 0.75), about 0.3 per article.
  These are concentrated in the 129 articles that use back references (about 1.5 each).
- **Grouping:** about 220 decisions (154 candidate merges, 62 cross-article joins through author-less members, 21
  author-conflict cards, overlapping), about 0.37 per article. After the rules above: about 140 and 150.

What one screen needs:

- **A back reference:** the ink crop of the marker's note, the 3–5 notes before it, and up to three candidate earlier
  citations. Each candidate shows its first full citation's crop, page, and the pages cited so far, with the author
  name highlighted in both. One key per choice: A / B / C, "not cited earlier in this article", "not a bibliographic
  work".
- **A merge:** the two cards side by side, each with title, authors, years and editions, and 2–3 member crops with
  the citing article's title and field. Choices: "same work", "same work, other edition or translation", "different".
- **A suspect card:** its members' crops grouped by printed author, with a split tool.

Projection to 1,000,000 documents (guesses from 600, not measured at scale):

- **Back references:** 230k–320k decisions at about 20 s each, which is 1,300–1,800 person-hours.
- **Grouping:** 0.4M–2M decisions at about 40 s each, which is 4,400–22,000 person-hours. The rate grows with the
  corpus because there are more cards to collide with. It falls sharply if the classical works list absorbs the
  generic titles, since decisions are then made once per work, not once per article.
- **Audit:** a 1% check of automatic links, about 580 hours.

300 correctors at 5 productive hours a day give 1,500 hours a day, so all of this is roughly 4–16 working days. The
people are not the bottleneck. Precision of the automatic part is.

## What I would do next

1. In `build_cited_works`: no cross-article join through a member with no author unless the title is ≥ 3 words or
   is on the classical works list. Type serial-only citations as serial. Re-run the census. I expect 100 of about 101
   cross-article cards right.
2. Build the classical works list (uniform and alternate titles plus short names) from the cards and the MARC
   catalogue's uniform titles. Then merge the "contained + same author" pairs automatically only when the shorter
   title is a prefix of the longer and the first-author key is the same and uncommon (28/34 today, which needs
   tightening). Send the rest to the merge queue.
3. The five back-reference rules above (Id, hint cut, whole name, corporate page continuity, sigles), then re-judge
   a fresh seed.
4. Add a work/edition layer to the schema (rule above) before the catalogue links multiply.
