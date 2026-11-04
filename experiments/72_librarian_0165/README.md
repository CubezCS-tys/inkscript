# 72: the first production librarian pass — journal 0165's new entities

## Question

Experiment 70 loaded gate 2's pilot journal, 0165 «مجلة الطفولة والتنمية» (363 articles), and left its new
entities to the librarian: 239 persons, 76 institutions, 5,137 cited-work cards, 583 cited publications. Experiment
71 chose the production librarian (rules first → Gemini Flash 3.8 for eight strong kinds → Claude Opus 5.5 where it
says high → the Desk) but had only run it on a gold set. Here it runs for real: on 0165's institutions and
affiliations, its cited-work cards (same work, edition, different, split, not a work, links to Mandumah publications
including 0130 ↔ 0165 and 0165's own articles) and the obvious same-person cases, reconciled against the catalogue
of entities earlier passes decided (the "seen list"), verified without the owner, and applied as recorded Desk
decisions of `agent:librarian`.

Owner-approved (overnight mandate). Hard cap $10 of model spend, Gemini and Anthropic together, logged per call.

## Answer

**Done, for $4.35 of the $10 cap** (Gemini $1.69, Anthropic $2.66; every call logged). **Live release
`R20261103T063710`**: every Desk decision replays — 5,040 applied, 41 superseded, **0 orphaned** (experiment 68's
three orphans re-anchored by their owner), and only the known «المقدمة» demo conflict; every constraint holds,
0 foreign-key violations.
- **2,302 standing Desk decisions of `agent:librarian`** from this pass (2,277 that act + 25 reverts of a kind held
  after the fact, below): institutions 338, cited works 1,963 (incl. the lead's follow-up and the 25 reverts), one
  person; each carries
  its question, tier, model and confidence, rule and verification in `evidence.provenance`.
- **How the 2,619 items were settled** (1,873 model questions + 746 settled by rules): rules 746 (28%), Flash 1,173
  (45%), Opus 350 (13%), nothing to apply 51, fixed by hand in the follow-up 2, **to people 297 (11%)** — Desk tasks:
  88 possible-same-work pairs and 206 librarian questions (three pairs of questions share a subject), each with both
  models' answers.
- **Verification without the owner**: the hard checks of experiments 63 and 62 find nothing wrong (transitivity 0);
  the cross-family alarm agrees 40 / 40 (Sonnet on Flash) and 346 / 350 (Flash on Opus, the 4 being one body named
  two ways and same-work vs edition); **the hand check: 142 right, 3 minor, 1 wrong of 146 read (40 random + 106
  stratified), and every decision of Flash's two small kinds read in full**: "rows are one body" 16 / 17 and
  "card ok" 24 / 26 — **both held as proposals**; every other applied kind was 100% in what was read.
- **The lead's follow-up**: CBDD9P2BCR (al-Hiti, «ثقافة الأطفال», 1988) no longer holds al-Kaabi's three citations;
  they are on al-Kaabi's own card C34EFXV0F2 with their two editions. A scan for the same pattern found 4 more clear
  wrong joins, split (C8B5VY3Z4G, CJMAPFK28P, C18S7AC7QV, and CVDWKPANEQ from reading the card-ok decisions).
- **Before → after for 0165** (`out/numbers72.json`): institutions 108 → **96** (dirty machine rows such as «جامعة حلوان
  الأسبق» now resolved to their body), with a country 64 → **77** (59% → 80%), in 2+ articles 29 → 30; cited works
  5,322 → **5,256**, cited by 2+ articles 210 → **258**; references held 10.6% → **11.8%** (673 → 755 of 6,374);
  **shared with 0130: cited works 157 → 198, institutions 17 → 19**, authors 17, coupling edges 313 → 375.

## Method

### The seen list and the questions (code, no model)

**Institutions** (`inst72.py`).
- The authority: experiment 56's `authority56.AUTH` (280 bodies, their printed forms), experiment 64's four new
  bodies, and the Desk's own row for each body (its `define_institution` decisions).
- Experiment 56's packet builder (`build56`) on the live release: 1,089 printed affiliations, **329 in 0165**.
- Rules first, as experiments 56/63 measured them:
  - **R1 printed form**: the statement prints an authority form (the longest wins), one body, no former / degree
    word («سابق», «الأسبق», «دكتوراه», «طالب» …) and no second organisation word left once the form is cut out
    → that body. **167**.
  - **R6 no body printed**: a place or a position, no organisation word → not an institution. **50** («مصر», «شاعر
    وكاتب أطفال …-مصر», and the three bogus page lines exp 70 left: «خلفية», «خلفية الدراسة», a sentence).
  - The rest, **112**, go to the models, plus two institution-level question sets: **68** Arabic / Latin unit rows
    under one parent (twins like «كلية علوم التربية» / «Faculty of Education Sciences»), **4** unit rows with no
    parent.
- **The candidate finder, improved** (exp 71 found its retriever missed the right body in 35 of 160 questions).
  Measured on exp 71's 138 institution questions that name a body (`inst72.py finder-eval`):

  | finder | the right body among the candidates | candidates per question |
  |---|---|---|
  | exp 71: trigrams over names and repeated printed forms, top 8 | 103 / 138 (75%) | 7.9 |
  | **exp 72**: + a printed city / country → that place's universities (exp 56's R4 city table); + the journal's publisher; + a distinctive name word shared with an entry; + faculty-name hints (Arabic Language / Usul al-Din → Al-Azhar, Qaraouiyine, Imam, Umm al-Qura, IU; Dar al-Ulum → Cairo, Minia, Fayoum) | **133 / 138 (96%)**; 31 of the 35 exp 71 had to inject | 12.2 |

  The five still missed need world knowledge no table holds (a Berkeley centre printed as a literal translation, a
  Yale centre, a two-body Damascus line). Partly in-sample: the city table was learned on the same 780 articles.
  The machine's own rows for the statement are in every packet too, so a model can name a body the authority lacks.

**Cited works** (`works72.py`; experiment 62's code pointed at this experiment's `out/`, nothing in it changed).
- `build62` on the live release: 14,042 active cards, **5,322 cited by a 0165 article**.
- `catindex62`, the catalogue drawer (one pass over marc.db, 11.6 min, 0.75 GB), for the 5,322: accept 648,
  candidate 116, relation 121.
- `cands62`, the blocking, on all 14,042 cards (304,800 pairs examined, 1,929 kept), then kept only where a 0165 card
  is involved and no earlier answer exists: a standing Desk decision (22 links, 5 card shapes) or experiment 62's
  own pair answers (62 different works it held, not imported). One fix in this experiment's copy of the step: an
  author relation «weak» that exp 62's data never met.
- Rules first: **K1c** (title, author, year and venue fit → the record is the work) **516** links after review of
  duplicates; **P6** (a thesis and a journal article are two works) **9**, one of them a D43 pair (same title and
  author → the article is derived from the thesis); **C1** (a card titled with a journal's name is not a work) marks
  15 cards, whose action (drop / retitle / one per citation) is asked, since exp 62's action rule N1 is 89%.
- The rest: **1,689 questions** — 1,226 pairs, 37 splits, 54 not-a-work, 372 catalogue (accept 103, candidate 115,
  relation 111, read-article 32, link47's own link 11).

**Persons** (`persons72.py`, no model): two person ids with the same folded full name (3+ words), one signing 0165,
never in one article, no contradicting body. 12 pairs; read by hand.

### The models (`prompt72.py`, `ask72.py`, `decide72.py`)

- **Instruction**: experiment 71's (`prompt71.SYSTEM`, measured on its gold) unchanged, plus one paragraph with the
  owner's rules D37–D44 (degree university = educated at; former posts; a body inferred from the journal's publisher;
  Sahih Muslim bi-sharh al-Nawawi; DSM editions; chapters part of; thesis vs article; the same text in two
  journals), two answer fields for them (`roles` per body, `inferred`), and one catalogue option, `same_text` (D44).
  Version 72.1.
- **Tier 1, Flash 3.8 (thinking low, Batch) on every question.** Applied only for exp 71's strong kinds: links to a
  Mandumah record, different works, card ok / card split, set country, rows are one body, set parent, affiliation
  names no body. Flash's "different" on two rows needs nothing (they stay apart): 51.
- **Tier 2, Opus 5.5 (adaptive thinking, effort medium, Batch) on everything else.** Applied when it says high.
  Never applied: unsure, part_of, unit_only, a body outside the authority before the authority review.
- **The authority review** (`review72.py`, by hand: every statement read). Opus and Flash named 50-odd bodies the
  authority lacks («new:…» or a machine row). **29 accepted** as new authority entries `L-72-…` (names, type,
  country, the forms a rule may match, the machine rows), 2 refused (a project, an unprinted ministry). 22 are used by
  an applied decision. The reviewed forms then **corrected two R1 answers**: «جامعة القدس المفتوحة» had gone to Al-Quds
  University (exp 63's H18 trap); with the form added, the longer name wins.
- **Tier 3, the Desk**: every question not applied becomes a task with both models' answers.

### Spend (every call is a row of `out/spend72.jsonl`; the guard refuses a job whose worst case could pass $9.50)

| tier | questions | $ | $ per 1,000 |
|---|---|---|---|
| Flash 3.8, institutions (Batch; 5 Standard pilot) | 184 | 0.21 | 1.15 |
| Flash 3.8, cited works (Batch) | 1,689 | 1.48 | 0.87 |
| Opus 5.5, institutions (Batch) | 113 | 0.71 | 6.26 |
| Opus 5.5, cited works (Batch) | 492 | 1.90 | 3.85 |
| Sonnet 5.5, the alarm re-ask (Batch) | 40 | 0.06 | 1.52 |
| **total** | **2,518 answers** | **$4.35** of $10 (Gemini $1.69, Anthropic $2.66) | |

Opus on institutions costs more per question than on works: the packets carry up to 18 candidate bodies.

## Decisions, by kind and tier

Every question has one tier: the rule that settled it, Flash (a strong kind), Opus (high), or the Desk. Counts are
questions (`out/decisions72.jsonl`, `out/decisions72_summary.json`) and the Desk decisions they became
(`out/plan72.jsonl`).

**Institutions** (329 printed affiliations of 0165; 0 twin lines, which take their main line's bodies)

| question | rule | Flash applies | Opus applies (high) | no change | to people |
|---|---|---|---|---|---|
| which bodies a statement names | R1 167, R6 50 | names no body 3 | 68 (39 with a reviewed new body) | | 41 (Opus medium 36, unit only 4, not an institution medium 1) |
| two unit rows (Arabic / Latin) are one body | | ~~17~~ held (hand check 16/17) | | 51 (Flash: different) | 17; the lead's twin applied on its own evidence (1) |
| a unit row's parent | | | | | 4 (Opus unsure 3, medium 1) |

Desk decisions: `link_affiliation` 237 (R1 167, Opus 68, the 2 re-anchored orphans), `not_an_institution` 53,
`define_institution` 29 (8 authority bodies 0165 is the first to use: Benha, Kafr El-Sheikh, Ouargla, Moulay
Ismail, Sfax, the Saudi and Moroccan ministries of education, Egypt's ministry of health; 21 reviewed new bodies),
`set_inst_country` 17, `same_institution` 1 (the twin), `set_inst_parent` 1 (re-anchored orphan). Roles: 5 former
posts (D38), 3 degree-granting universities (educated at, D37), 239 current; 0 inferred from the publisher (Opus said medium on the two
«…الهيئة الاستشارية للمجلة» lines).

**Cited works** (5,322 cards cited by 0165)

| question | rule | Flash applies | Opus applies (high) | to people |
|---|---|---|---|---|
| a pair of cards (1,235 edges) | P6 9 (+1 D43 derived-from) | different works 1,020 | same work 105, edition 13 | 88 (same work medium 41, edition medium 30, unsure 9, part of 6, different medium 2) |
| a card that may hold several works (37) | | ~~card ok 26~~ held after the import (24/26), split 10 | | 1 (+24) |
| a card that may not be a work (54; 15 C1) | | | drop 18, retitle 17 (5 of them C1) | 19 |
| a card and a catalogue record (372 asked + K1c) | K1c 534 | the record is the work 141 | relation 91 (22 D43: the record is drawn from the cited thesis), no link 38 (nothing to apply) | 102 (relation medium 43, same text medium 30, link medium 11, no link medium 10, unsure 8) |

Desk decisions: `link_publication` 656 (K1c 516, Flash 140; 17 cards were asked twice — a read-article hit and the
drawer — and both answers agreed; one card's two answers disagreed and went to a person), `not_same_work` 1,021
(Flash 1,012, P6 9; 8 more were dropped from the plan because one side is a card no work count holds: a dropped web
site or exp 67's defined book), `same_work` 105, `edition_of` 13, `relate_publication` 91 (reviewed in 68, has
derived 20 and derived from 2 under D43, related 1), `relate_works` 1, `not_a_work` 35 (drop 18, retitle 17; two titles not taken because
the code cut them wrongly), `confirm_work` 26 (reverted after the import: the kind is held), `split_work` 10. Opus never said same_text with high confidence: the
30 D44 candidates are tasks.

**Persons**: 12 same-name pairs touching 0165; **1 applied** (`same_person`): «منى حسين الدهان» (AR846KS7BM) and
«منى حسين محمد الدهان» (A2AN262X2S), two catalogue authority records, both signing 0165 articles as a professor at
Ain Shams' Faculty of Specific Education. The other 11 pair a byline person with an authority record seen only in
citations (محمد حسن غانم ×2 records, هند خالد الخليفة, رشاد علي عبد العزيز موسى, علي عبد النبي حنفي, منى حسين الدهان's
third record «منى حسن») or differ in a letter (خالد صلاح حنفي / حفنى): proposals for people, in
`out/persons/pairs.txt`. **What persons need next**: a person-level question for the model (name + affiliation +
fields + co-authors, like the institution packets), and a Desk task kind for "authority record = byline person"; the
Desk's `same_person` already applies the answer.

**Experiment 68's three orphans, re-anchored** (`reanchor68`, by their owner `agent:librarian`, each superseding the
orphan): the two English lines that became twins of their Arabic lines now carry a `link_affiliation` on the twin's
key naming the Arabic line's bodies (Kuwait's ministry + PAAET; AIU + Alexandria); the parent of the vanished English
faculty row now sits on the row that holds that line, IZB3FM7D22 → AIU. Their three orphan tasks are answered.

## Verification (no owner review)

**1. Hard checks over every planned decision** (`verify72.py checks` → `out/checks72.json`).
- Institutions, experiment 63's `hardchecks63` run unchanged on this pass's 306 affiliation / row / parent decisions
  (its load step pointed at them): H1b 1, H7 1, H8 10, H14 2, H17 9, every other check 0. All read; **none is an
  error**: H1b is a statement naming two bodies in two countries (Alexandria + Umm Al-Qura, each with its own
  country); H7, H8 and H14 are notes on the authority that predate this pass (Zaytuna Libya / Tunisia; types; a
  catalogue country); H17 are links whose statement prints another form of the body (Moulay Ismail, Boumerdes,
  Médéa, Helwan in «بجامعتي حلوان و ٦ أكتوبر», the Saudi, Omani and Moroccan ministries, Egypt's ministry of health).
  Before the review, H18's trap was real twice: R1 sent «جامعة القدس المفتوحة» to Al-Quds University; fixed by the
  reviewed form (above).
- Cited works, experiment 62's `check62` on this pass's joins, splits and links plus exp 62's held different-work
  answers (consistency with the seen list): **transitivity 0**, death dates 0, type 0, catalogue 0; years 1 (a
  Hijri and a Gregorian year of one book); authors 8, all one name printed two ways (سكينر / سكنير, Karus / Kraus,
  Fit / Fite), a translator credited on one card (Joan Aiken's book translated by عبد التواب يوسف), or a corporate
  author (AAAS / Project 2061; IFES). None is an error.

**2. The cross-family alarm** (`verify72.py alarm` → `out/alarm72.json`, `out/alarm72.jsonl`).
- **Sonnet 5.5 on Flash's applied answers**: a random 2% of 1,217, raised to 40 (seed 7272): **40 of 40 agree**
  (37 different works, 2 links, 1 card ok). Disagreement rate 0% against the 5% alarm.
- **Flash on Opus's applied answers** (Flash answered every question first, so this costs nothing and covers all
  350): **346 of 350 agree** strictly; the 4 are two names of one reviewed body («وزارة الثقافة المصرية» /
  «وزارة الثقافة (مصر)», «مجمع اللغة العربية في ليبيا» / «… الليبي») and two same_work answered edition_of (both
  join). Lenient agreement 350 / 350. Rate 1.1%, under the alarm.

**3. The hand check** (`verify72.py sample`, `handcheck72.py`; verdicts in `out/handcheck72.jsonl`, by me, against
the printed text of each citation and statement and the catalogue record).
- **A random 40 of the 2,275 planned decisions** (body records and countries left out; seed 7240): **40 right**
  (21 different works, 10 K1c links, 4 Flash links, 1 Opus relation, 3 R1, 1 R6).
- Because a random 40 is mostly different-works and K1c, **106 more, stratified over every applied kind** (seed
  7241; every kind under 20 taken whole): 102 right, 3 minor, **1 wrong**.

  | kind | read | right | minor | wrong |
  |---|---|---|---|---|
  | Opus same work / edition | 10 / 5 | 9 / 5 | 1 (2000 vs 2001 printing: edition or same, both join) | |
  | Opus relation (incl. 4 D43) | 10 | 9 | 1 (reviewed_in where the review is of the next year's report: related) | |
  | Opus not a work (drop 8, retitle 7; 5 of them C1) | 15 | 14 | 1 (the title the code cut from the print: «… regulate their») | |
  | Flash split / card ok / link | 10 / 5 / 5 | all | | |
  | Opus affiliations (10 in authority, 8 reviewed bodies) | 18 | 18 | | |
  | **Flash rows are one body** | **17 (all)** | **16** | | **1**: «قسم الطفولة المبكرة» joined to «Childhood Studies Department», the translation of «قسم دراسات الطفولة» (a renaming from world knowledge, not printed) |
  | Flash names no body | 3 | 3 | | |
  | **Flash card ok, read in full** after the lead's report (the 5 above included) | **26** | **24** | | **2**: CBDD9P2BCR (al-Kaabi's 2011 book inside al-Hiti's 1988 one: the lead found it) and CVDWKPANEQ (Hammouda's «العلاج النفسي» 2011, printed «__________» under his previous entry, inside Abdullah's 2013 book) |
  | P6, P6 + D43, the person, the 3 re-anchors | 3, 1, 1, 3 | all | | |

- **Precision on the hand check: 142 right, 3 minor (the decision right, a label or a title off), 1 wrong of the
  146 sampled; 99.3% counting minor as right.** Every applied kind is at 100% in what was read **except Flash's
  "rows are one body", 16 / 17 = 94%: held as proposals** (`out/hold_kinds.json`): its 17 decisions are Desk tasks.
  The one merge the lead asked for (I1NW24RKQM «كلية علوم التربية» = IP0XR2KXSC «Faculty of Education Sciences») is
  applied on its own evidence — the two rows carry the two scripts of one printed line (0130-018-072-003) under one
  parent — as rule `twin68`, not as Flash's answer.
- **Then the lead found a wrong join on the shareholder path** (CBDD9P2BCR) that this pass had confirmed (Flash: card
  ok on a split question; the card view shows only 12 of 18 citations, and the two al-Kaabi ones visible print no
  author). Reading all 26 of Flash's card-ok answers found a second (CVDWKPANEQ): **24 / 26 = 92%, held as
  proposals** after the import — its 25 standing confirms reverted by their owner, 24 Desk tasks, the two cards
  split (below). The stratified 5 had all been right: a small kind needs a full read.
- Two minor defects were fixed before the import: the retitle titles that `plan67.item_title` cuts at a journal name
  found inside a word («Emot» in «emotions») or after a broken word («Psycho- logical») are not taken (the card keeps
  its title; 2 cards).
- Caveat, as in exp 71: the hand checker is Claude, the same family as Opus. The independent parts are the code
  checks, Flash's agreement on Opus's answers, and Sonnet's on Flash's.

## Applied, held, to people

| | institutions | cited works | persons | re-anchored | total |
|---|---|---|---|---|---|
| questions asked of the models | 184 | 1,689 | – | – | 1,873 |
| settled by a rule (no model) | 217 (R1 167, R6 50) | 525 (K1c 516, P6 9) | 1 (read by hand) | 3 | 746 |
| questions Flash settles (strong kinds) | 3 | 1,170 (card ok held: 26; one disagreeing card) | | | 1,173 |
| questions Opus settles (high) | 68 | 282 (38 of them no link: nothing to apply) | | | 350 |
| nothing to apply (Flash: two rows stay apart) | 51 | | | | 51 |
| fixed by hand in the lead's follow-up | | 2 (the card-ok cards CBDD9P2BCR, CVDWKPANEQ) | | | 2 |
| **to people** | **62** (17 of them the held rows kind) | **235** (24 the held card-ok kind) | 11 (listed; no task kind yet) | | **297 questions → 294 tasks** |
| **standing Desk decisions** | **338** | **1,963** (25 of them reverts) | **1** | (counted in institutions) | **2,302** |

Questions to decisions: one question can make several decisions (a link needs its body's record and country) and
some make none (no link; 8 different-works pairs where one card is a dropped web site or exp 67's defined book, so
nothing is held apart; 17 cards asked twice whose two answers agreed are one decision).

**Tasks, by kind** (the Desk's queue; `out/tasks72.jsonl`, each with both models' answers and the evidence):
- `possible_same_work` (the queue's own pair screen) **88**: same work medium 41, edition medium 30, unsure 9, part
  of 6, different medium 2;
- `librarian_question` **209 questions, 206 tasks** (three pairs of questions share a card): catalogue 102
  (relation medium 43, same text medium 30, link medium 11, no link medium 10, unsure 8), affiliations 41 (Opus
  medium 36, unit only 4, not an institution medium 1), card ok 24 (the held kind), rows one body 17 (the held
  kind), not a work 19, a unit's parent 4, a split 1, two disagreeing answers on one card 1 (C70RAZGS25: K1c chose
  the 2014 copy in «مجلة الطفولة والتربية», the print names «مجلة الطفولة والتنمية» 2015, Flash chose that).

**To a person: 297 of the 1,873 model questions (15.9%), 11.3% of all 2,619 items** counting what the rules
settled; exp 71 expected 17% over all items and 26% on judgement items.

## The lead's follow-up (2026-11-03, `scan72.py`, `fix72.py`, `dryfix72.py`)

**CBDD9P2BCR**, al-Hiti's «ثقافة الأطفال» (عالم المعرفة 123, 1988), held three citations of Fadhil al-Kaabi's «تكنولوجيا
الثقافة: دراسة في الأسس العلمية لثقافة الأطفال» (2011, دائرة الثقافة والإعلام، الشارقة), all on 0165-007-028-003 p25. The
machine had joined them as repeats inside the article through the phrase «ثقافة الأطفال»; this pass had then confirmed
the card (Flash), joined it with CKY1ACWX0J (Opus: another al-Hiti card) and kept it apart from al-Kaabi's own card
C34EFXV0F2 — each of those recorded the card with the three. Checked against Azure's own OCR of the page (lines 12,
17, 23: «٥- الكعبي، فاضل (٢٠١١) تكنولوجيا الثقافة …», «… راجع كتابنا : تكنولوجيا الثقافة …»; the article is al-Kaabi's,
"our book"). Decisions (all `agent:librarian`, rule `scan72`, by their owner):
- `split_work` CBDD9P2BCR → [the 15 al-Hiti citations] / [the 3 al-Kaabi ones] (superseding the confirm);
- `same_work` CBDD9P2BCR + CKY1ACWX0J and `not_same_work` C34EFXV0F2 / CBDD9P2BCR, re-made on the card without the
  three (superseding the two that had recorded them);
- `same_work` C34EFXV0F2 + the split-off card: **al-Kaabi's book now has 4 citations; al-Hiti's 16**; editions …967
  and …554 went with their citations (al-Hiti's card keeps only its 1988–1990 editions).

**The scan** (every 0165 member whose title is not its card's, dice < 0.6, and whose author contradicts, year is 3+
years off, or author is missing where every other member prints one): 9 members on 7 cards. Clear and split:
- C8B5VY3Z4G «جودة الحياة» (عمر 2014) ⊃ her 2008 «استخدام المدخل الإسكندنافي …» → split;
- CJMAPFK28P al-Maamari «التربية من أجل المواطنة …» (2014) ⊃ ناصر، إبراهيم «المواطنة» (2002) → split; its K1c link to
  al-Maamari's article W621974 re-made on the card without Nasser's citation (the dry run showed it would not hold);
- C18S7AC7QV Tibbitts & Fernekes «Human rights education» (2011) ⊃ Tibbitts «Understanding What We Do …» (2002) →
  split.
Not changed (one work): Piaget & Inhelder's «The Psychology of the Child» (1969, the English of «La psychologie de
l'enfant» 1966), Heward's «Exceptional children» (1992 / 2006 editions), Dewey's «Democracy and Education» (1916 /
1966). Rerun on the final release: only those three remain.

And the card-ok kind read in full (Verification): CVDWKPANEQ split too, Flash's card ok held.

Dry run in `test_e72dry` (release in the scratchpad): 0 orphaned, the known conflict only. Live: backups
`~/data/desk/backups/desk_schema_before_exp72fix_20261103T003208.{dump,sql}` and
`desk_schema_before_exp72fix2_20261103T003704.{dump,sql}`; releases `R20261103T063226` (the splits) and
**`R20261103T063710`** (the card-ok hold and CVDWKPANEQ), each 0 orphaned, 1 conflict (the demo).

## Before and after

All on the release DBs with experiment 70's measures (`measure72.py`, before = `R20261103T023001`, after =
`R20261103T063710`).

| journal 0165 | before (exp 70) | after |
|---|---|---|
| institutions (org level, current, every body a statement names) | 108 | **96** |
| … with a country | 64 (59%) | **77 (80%)** |
| … in 2+ articles | 29 | **30** (exp 52's first-body measure: 29 of 95; affiliations at a body seen in 2+ articles 69.4% → 73.7%) |
| countries | 14 | 14 |
| cited works its references land on | 5,322 | **5,256** |
| … cited by 2+ of its articles | 210 | **258** |
| references held (an accepted link to a Mandumah publication) | 673 of 6,374 (10.6%) | **755 (11.8%)** |
| shared with 0130: cited works / institutions / authors | 157 / 17 / 17 | **198 / 19 / 17** |
| coupling edges with 0130 (article pairs citing a common work) | 313 (74 × 98 articles) | **375 (81 × 105)** |

Why institutions fall while links rise: the machine had made a row of each spelling («جامعة حلوان الأسبق», «جامعة 6 أكتوبر
217», «وناقد ومحاضر بوزارة الثقافة»); the decisions link those statements to the body's one row. 19 rows still have no
country: bodies whose statements are held (Opus medium) or not in the authority.

## For the lead

- **Nothing to restart, nothing to rebuild.** No Desk code changed (`desk/` is untouched); the running API reads
  the newest release on every request, so it already serves `R20261103T063710`: the Explorer, the index pages,
  `/journals/J0165`, the tasks queue (`/work`: 88 possible-same-work pairs; the 206 librarian questions show in its
  generic view, they appear under "All"). Experiment 70's pending API restart (gate 1's random pool)
  is still pending.
- **Optional:** run the detectors on the new release so the queue also holds the probe B pairs this pass's
  blocking did not see (the Desk's detector finds 451 on the release before; the blocking covered 308):
  `cd experiments/49_correction_desk && .venv/bin/python -m desk.cli detect` (it also marks open tasks it no longer
  finds as stale). Not run here: it changes the whole queue, not only 0165's.
- **For the owner to decide** (nothing blocks): the 17 row merges and 24 card-ok confirms held as proposals; 30
  same-text (D44) candidates Opus would not call; whether to give `librarian_question` its own screens.
- **Reverting:** one decision — its owner `agent:librarian` or an admin reverts it (`POST
  /desk/api/decisions/{id}/revert`); the whole pass — revert the standing decisions whose `evidence->>'source_id'`
  starts with `E72:` and build a release; or restore `~/data/desk/backups/desk_schema_before_exp72_20261102T234159.dump`
  (`pg_restore -d inkdesk --clean -n desk <file>`) and set `copy_deleted_at` on releases `R20261103T055432`,
  `R20261103T063226`, `R20261103T063710` (the Desk then reads `R20261103T023001`). The platform database was not
  written.
- **Releases on disk: 11** (`--keep 11`, none pruned): the three of this pass (1.4 GB each) can be thinned to the last
  one later (proposed, not done).
- **Can be deleted (proposed, not done):** the throwaway schema `test_e72dry`; the scratch releases in this session's
  scratchpad (`dry72/`, 2.8 GB); `out/hc_extra.py` (a draft, moved to `handcheck72.py`).

## Lessons for gate 2's other nine journals

1. **The cost is small and predictable**: $4.35 for one journal of 363 articles (exp 71 projected $13–16 for all ten
   journals; this pace gives about $40–45 for the ten, because 0165's Word route and long reference lists make many
   cards). Opus is 60% of it. Batch jobs run 3–15 minutes; the import into the Desk takes ~12 minutes for 2,300
   decisions (ops.decide validates each against the release), the release ~1.5 minutes.
2. **The rules carry most of it**: 746 of 2,619 items (28%) needed no model; Flash settled 1,173 more (45%). Opus
   was asked 605 questions and applied 350.
3. **The authority is the bottleneck for institutions.** 69 of 112 affiliation questions named a body the authority
   lacked. Review the new bodies once per journal (here 29 bodies in about an hour); each review also adds forms
   that make the rules better next time (it corrected two R1 answers here). Before the nine: run the review on the
   bodies Opus names at medium too, so their statements can go through R1 in the next pass.
4. **Read the small kinds whole.** A random sample is dominated by different-works and K1c (31 of 40 here). Both
   wrong kinds were small and found only by reading every decision: Flash's "rows are one body" (16/17) and its
   "card ok" (24/26: the lead's CBDD9P2BCR, after a stratified 5 had all been right). For the nine: read every
   decision of the kinds under ~50 (row merges, parents, card ok, splits) before the import, and 10 of each large
   one. Card-ok questions should show the whole card (here 12 of 18 citations were in the packet).
5. **Rows-are-one-body questions need better packets.** Faculty and department twins should be asked only for rows
   whose statements are twins of one printed line (`twin_of_aff_pk`), not for every Arabic × Latin pair under a
   parent (68 questions, 51 "different", 1 wrong merge).
6. **Same text (D44) never reaches Opus's "high"**: 30 cards are tasks. A code rule could settle most: the same
   title and author, another journal named in the print, the record's journal in Mandumah.
7. **Two answers on one card** (a read-article hit and the drawer's record) disagreed once, and K1c was the wrong
   one (another journal, another year). K1c's venue test accepts half the journal's words: «مجلة الطفولة والتربية»
   passed for «مجلة الطفولة والتنمية». Tighten it to the distinctive words.
8. **Persons need their own question.** Twelve same-name pairs, one obvious; the rest pair a byline person with a
   catalogue authority record known only from citations. A person packet (names, bodies, fields, co-authors) and a
   task kind for it are the next step.
9. **Task kinds**: `librarian_question` shows as the Desk's generic task view; pairs use the queue's own
   possible-same-work screen. A screen per librarian question type (affiliation, catalogue, not a work) would make
   the 206 faster to answer.
10. **Run the import against the release it was planned on**, and check orphans in a dry run first: here the dry run
   found 8 decisions a drop of this same pass orphaned, and 37 tasks the standing check would have swallowed.

## Files

Scripts (run from this folder; the Desk's venv for everything but `ask72.py`, which uses the repo's venv with
`google-genai` and `anthropic`):
- `common72.py`: paths;
- `inst72.py`: packets (exp 56's builder), the candidate finder and its evaluation, rules R1 / R6, the questions;
- `works72.py`: cards, the catalogue drawer and the blocking (exp 62's code), rules K1c / P6 / C1, the questions;
- `persons72.py`: same-name pairs;
- `prompt72.py`: the instruction (prompt71 + the owner's rules) and the schema;
- `ask72.py`: Batch / pilot / collect, the spend log and the $9.50 guard;
- `review72.py`: the authority review (by hand, recorded as code: `REVIEW`, `REFUSED`);
- `decide72.py`: the tiers; `verify72.py`: hard checks, the alarm, the random sample, scoring;
  `handcheck72.py`: the stratified sample;
- `plan72.py`: the Desk decisions and the tasks; `import72.py`: through `desk.ops`; `dryrun72.py`: a throwaway
  schema `test_e72dry` and a scratch release; `golive72.sh`: backup, import, release, numbers;
- `measure72.py`: before / after;
- the lead's follow-up: `scan72.py` (title-phrase joins whose authors / years disagree), `fix72.py` (the splits, the
  re-made decisions, the card-ok hold and its tasks), `dryfix72.py` (a scratch release of the throwaway schema).

`out/` (gitignored): `inst/` (packets, authority72.json, review candidates, rule decisions, finder evaluation),
`works/` and `works0165/` (cards, catalogue drawer, packets), `questions/`, `answers/<model>.jsonl`,
`spend72.jsonl`, `batch_state72.json`, `batch/`, `decisions72.jsonl`, `plan72.jsonl`, `tasks72.jsonl`,
`checks72.json`, `alarm72.json[l]`, `handcheck72*.{json,jsonl,txt}`, `dryrun72_test_e72dry.json`,
`import72_<schema>.jsonl`, `release72.json`, `numbers72.json`, `persons/`, `logs/`.

Notes as the work went: `progress.md`.
