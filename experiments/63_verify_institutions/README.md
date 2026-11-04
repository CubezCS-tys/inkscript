# Experiment 63: blind verification of the institutions librarian (experiment 56)

**Question** (owner, 2026-11-02). Experiment 56's librarian left 908 standing decisions about institutions
(which body an affiliation names, its country, its parent, which machine rows are one body, its type). The owner
wants to look only at urgent things: "I want most things to be already correct or some way of knowing we are
correct." Can the decisions be applied without the owner reviewing samples? Which kinds pass a 98% bar, and what
must stay a proposal?

**Answer.** Yes, almost all of them. All 908 were checked: 230 re-decided blind, the other 678 read through
openly, plus 18 checks run by code over all 908. **4 decisions are wrong (99.6%)**, two of them only in a second
field, and **one fault in the data model** (an affiliation holds one country, so 7 statements naming bodies in two
countries get only the first body's country). Every kind passes 98% on the full check, except `same_institution`
medium (one wrong of 4). The code checks found **no** body placed in the wrong country, no parent in another country,
no shared name (جامعة الزيتونة Libya / Tunisia) chosen without a printed place, and no broken parent chain. What the
owner still has to decide is policy, not errors: 7 cases below.

Nothing was applied to the platform, the releases or experiment 56. No paid call was made.

## Method

1. **Sample** (`sample63.py`, seed 63). 230 standing decisions (the newest per question, retired ones left out =
   908), stratified by kind × confidence (and rule / non-rule for the large affiliation stratum). Every medium and
   low stratum was taken whole: all 40 medium affiliation decisions, 16 medium countries, 13 medium parents, 4
   medium merges, 9 splits, 8 medium not-an-institution, 5 units kept apart, 10 unsure. High strata were sampled:
   affiliation 65 of 540 (50 rule-based + 15 judgement), countries 20 of 118, not-an-institution 12 of 62, merges 10
   of 26, parents 10 of 35, types 8 of 22.
2. **Blind re-decision.** For each item `out/blind63.txt` shows only what the librarian had: the printed statement
   and its parts, the article, journal and year, the author, the same author's other statements, the machine's rows,
   the catalogue hits. It does not show exp 56's decision, its reason, its authority ids, or the question key (which
   names a parent). I also looked up each journal's publisher and country in the release (`out/journals63.json`),
   as catalogue evidence. I wrote all 230 answers to `out/mine63.jsonl` **before** opening the key, froze a copy
   (`mine63_frozen.jsonl`, sha256 in `progress.md`), and only then compared (`sidebyside63.py`). World knowledge
   was used only when I would state it confidently, and it is marked in each answer.
3. **Adjudication** (`out/adjudication63.json`). Every disagreement was settled using the catalogue (journal
   publishers, MARC 502 thesis faculties in `marc_inst56.db`) and the printed page text (Azure lines of page 1 in the
   release, used in place of image crops). Each verdict is one of: *agree*; *both acceptable*; *exp 56
   conservative* (it held back a link it could have made, which never creates a false link); *minor error* (a
   second field wrong); *exp 56 wrong*.
4. **Hard checks over all 908** (`hardchecks63.py` → `out/hardchecks63.json`). These use their own place list
   (country names and cities that belong to one country only), not exp 56's matcher.
5. **Open read-through of the other 678** (`openreview63.py` → `out/openreview63.txt`, one line per decision;
   findings in `out/openreview63_findings.json`). This read was not blind. With the blind 230 it covers all 908.
6. **Numbers** (`stats63.py` → `out/numbers63.json`). Intervals are Wilson 95% on the blind sample.

**Limits.** I am the same model family as the librarian, so where a decision rests on world knowledge, our
agreement is not independent proof. That is why every world-knowledge agreement that could be checked was checked
against the catalogue or the page (for example, the Faculty of Fine Arts in Cairo belongs to Helwan: J0241's
publisher is Helwan University; the Faculty of Arabic Language in Mansoura belongs to Al-Azhar: MARC 502 lists it
under جامعة الأزهر). Exposure: before judging, I read exp 56's README (its "hard calls" name about 40 of the sampled
cases), and my first look at the decisions file printed 5 sampled decisions (S134, S152, S173, S205, S211). Blind
agreement is 168/184 (91.3%) on items I had not seen and 40/46 on exposed ones. On some exposed items I still
answered differently (S014, S173).

## Results

### Blind agreement and precision per kind (blind sample; strict = a wrong second field counts as an error)

| kind | conf | N | sampled | blind agreement | precision (strict) | 95% interval | exp 56 conservative | errors found (blind + open) | all-908 check |
|---|---|---|---|---|---|---|---|---|---|
| affiliation → institution | high | 540 | 65 | 100% | 100% | 94.4–100 | 0 | 1 (open: O351) | 99.8% |
| affiliation → institution | medium | 40 | 40 (all) | 92.5% | 97.5% | 87.1–99.6 | 2 | 1 minor (S107) | 97.5% |
| not an institution | high | 62 | 12 | 83.3% | 100% | 75.8–100 | 2 | 1 (open: O495) | 98.4% |
| not an institution | medium | 8 | 8 (all) | 50% | 100% | 67.6–100 | 4 | 0 | 100% |
| split a machine row | all | 9 | 9 (all) | 88.9% | 100% | 70.1–100 | 1 | 0 | 100% |
| merge machine rows | high | 26 | 10 | 100% | 100% | 72.2–100 | 0 | 0 | 100% |
| merge machine rows | medium | 4 | 4 (all) | 75% | 75% | 30.1–95.4 | 0 | 1 minor (S182) | 75% |
| set country | high | 118 | 20 | 100% | 100% | 83.9–100 | 0 | 0 | 100% |
| set country | medium | 16 | 16 (all) | 100% | 100% | 80.6–100 | 0 | 0 | 100% |
| set parent | high | 35 | 10 | 100% | 100% | 72.2–100 | 0 | 0 | 100% |
| set parent | medium | 13 | 13 (all) | 100% | 100% | 77.2–100 | 0 | 0 | 100% |
| set type | high | 22 | 8 | **25%** | 100% | 67.6–100 | 0 | 0 | 100% |
| unit kept apart | all | 5 | 5 (all) | 40% | 100% | 56.6–100 | 3 | 0 | 100% |
| unsure | low | 10 | 10 (all) | 80% | (never applied) | | 2 | 0 | |
| **all** | | **908** | **230** | **208/230 = 90.4%** | **228/230 = 99.1%** | **96.9–99.8** | 14 | **4** | **99.6%** |

By basis (all 908): rule-based 592 with 2 errors (99.7%); judgement / world / context / catalogue 316 with 2 errors
(99.4%).

Where we disagreed (22 of 230): in 14 cases exp 56 held back a link I would make at medium confidence. Most are the
same pattern: a department or college printed with no name («قسم التاريخ», «بالكلية», «رئيسة شعبة بحوث») in a journal
published by that very institution (KAU's faculty of arts, Imam University's Usul al-Din, CAPMAS, Helwan, Baghdad).
In 6 cases the *type* differed and both answers are acceptable. The type list has no value for a hospital, a union or
a regional education authority, so "school" vs "centre" vs "other" cannot be settled. Two are minor errors.
**In no case was exp 56's main claim wrong.**

### Hard checks over all 908

| check | findings | real problems |
|---|---|---|
| H1 the affiliation's country differs from a country printed in the statement | 2 | 0. Both name two bodies in two countries (see H1b) |
| H1b a statement naming bodies in two countries carries one country | **7** | **7, a fault in the data model**: KISR + Cairo, Jordanian + Arab writers, Tanta + KAU, Bahrain + Mansoura, Tunisian writers + Cairo league, Toulouse + Madrid, Cairo + Sana'a |
| H2 / H3 one authority entry whose affiliations print two countries / a country other than the entry's | 0 | after fixing my own place list («وجدة» first matched «جدة») |
| H4 a merge whose rows print different countries | 1 | S182 (the «جامعتى القاهرة وصنعاء» row) |
| H5 bilingual twins whose printed cities differ | 1 | 0 (Kurdistan vs Erbil: the same place) |
| H6 a parent in another country / H12 broken parent chains | 0 / 0 | |
| H7 a name shared by bodies in two countries, chosen without a printed place | 0 | جامعة الزيتونة is used once, with «ترهونة، ليبيا» printed |
| H8 type contradicts the name's head word / set_type contradicts the authority | 10 / 0 | 0: branches typed faculty, hospitals typed centre, AAST typed university, regional academies typed ministry; all defensible |
| H9 a statement prints two bodies, fewer were decided | 0 | |
| H10 a not-an-institution / kept-apart / unsure line prints an authority form | 0 | (a wider head-word scan found O495, see below) |
| H11 set_country against the authority / against printed countries | 0 / 3 | 0: the printed country belongs to another body in the same statement |
| H13 split groups against the affiliation decisions / H15 merged-row members decided elsewhere | 0 / 0 | |
| H14 authority country against the catalogue's | 2 | 0: Libya's Zaytuna vs Tunisia's in the theses (expected); ARC (EG) vs 2 Libyan theses of a same-named centre |
| H17 links where the statement prints none of the entry's forms | 63 | read through: ministries resolved by country, «جامعة فاس», context and world calls; none wrong |
| H18 a longer university name around the matched form (the "Islamic University of Lebanon" trap) | 0 | |

### Errors found (all 908)

1. **O351, affiliation high, rule.** «عن صحيفة عرب نيوز» was linked to Arab News (SA). Page 1 reads «بقلم : ج شولز /
   ترجمة : عيسى بليله مهدي / عن صحيفة عرب نيوز»: this is a reprint source, not an affiliation. Its set_country (SA)
   rides on the same row.
2. **O495, not an institution, high, rule.** «السكرتير العام لجماعة علم النفس التكاملى» (1945) does print a body: the
   Integrative Psychology Society, which also publishes the journal J0513.
3. **S107, minor.** «كلية التربية - جامعتى القاهرة وصنعاء» → Cairo + Sana'a, but the country is YE only.
4. **S182, minor.** The machine row «جامعتى القاهرة وصنعاء» ("the universities of Cairo and Sana'a") was merged
   into Sana'a University as a "spelling variant". The affiliation keeps both universities, so no link is lost, but
   the merge record is not true.

## The apply rule

**For this pass (the 908 on release R20261023T005909):**

- Apply every standing decision except the 10 `unsure` ones, which are never applied. They stay unlinked with their
  reason.
- Correct the 4 errors above before applying. O351 becomes not-an-institution (and its set_country goes). O495 is
  linked to a new authority entry, Integrative Psychology Society (EG). S182's row is not merged into Sana'a (the
  affiliation keeps both universities). S107 is covered by the next rule.
- Take an affiliation's country from the authority, one per linked institution, not from the affiliation's single
  `country` field. This mechanical fix removes the 7 two-country cases (H1b).
- `set_type` (22): apply as *proposals only*. The types are not wrong, but they cannot be reproduced (blind
  agreement 25%), because the type list lacks hospital, union / society and regional education authority. Add those
  values first.
- Everything else, all kinds and both confidences, passes 98% on the full check of all 908 and the blind sample,
  and can be applied without the owner reviewing samples.

**For future passes (new journals, the Claude API at scale)**, where a full check will not be done:

- **Auto-apply** (measured ≥ 98%, with nothing contradicting it in the hard checks): affiliation → institution when
  the rule matched a printed form (basis `rule`, 509/510 = 99.8%); set country from the catalogue or world knowledge
  (134/134); set parent (48/48); split machine rows (9/9); merge rows by rule or world knowledge (26/26); not an
  institution by rule (51/52 = 98.1%). In every case, first run `hardchecks63.py`, and add one check: a
  not-an-institution line containing a body's head word (جماعة / جمعية / رابطة / نقابة …) is held.
- **Proposal, then a sample check** (judgement, context, world): medium affiliation decisions, medium merges, units
  kept apart, set_type. Here the blind sample was 97.5% / 75% / 100% / 100%, but on small numbers, and it rests on
  world knowledge that one model family shares.
- **Never applied:** `unsure`.

## For the owner (7 cases; everything else can go ahead)

1. **Is the university where someone earned a degree an affiliation?** In 3 cases exp 56 linked it: «A Ph.D. ...
   from the University of Malaya and director of Palm Strategic Initiative Centre» → Malaya (the centre was not
   linked); «ماجستير ... بجامعة أم القرى» → Umm Al-Qura; «دكتوراه في النقد الأدبي كلية الآداب، جامعة القاضي عياض»
   → Cadi Ayyad. In 1 case it did not: «دكتوراه دولة ... كلية الآداب - الرباط» + CRMEF Settat → CRMEF only. Proposal:
   a degree-only line names no affiliation; where nothing else is printed, keep it as "degree from", not as the
   author's institution.
2. **Former posts (سابقا / السابق).** These are linked like current posts: Zagazig (former vice-president), Cairo
   (former professor, now KISR), AGU «(سابقا)», SQU «محاضرة سابقة», and «رئيس مجلس الوزراء اللبناني السابق» →
   Council of Ministers (Lebanon). Link them, link them marked as "former", or drop them?
3. **Fill an unnamed college or department from the journal's own institution?** Exp 56 did this for «بالمعهد»,
   «عضو المجمع» and «بالجامعة», but not for 10 similar lines: KAU (S069), Baghdad (S165), Helwan (S212), Imam Usul
   al-Din (S199), CAPMAS (S137), Ansar al-Sunna (S088, O479), the Cairo academy (O499), Dar al-Kutub (S201), and the
   Al-Azhar hospital whose abstract names Cairo (S116). Yes would add about 10 medium links. No would keep the
   rule as it is.
4. **O351** Arab News: a reprint source taken for an affiliation (correction proposed above).
5. **O495** Integrative Psychology Society: printed but not linked (correction proposed above).
6. **«جامعتى القاهرة وصنعاء»** (S107 / S182): link the affiliation to both universities with both countries; do
   not merge the row.
7. **Types:** add *hospital*, *union / society* and *regional education authority* to the type list, then re-decide
   the 22 types (the 7 hospital / CRMEF / union rows in H8 and set_type).

The 10 `unsure` need nothing from the owner. Two lean one way and could become medium links if wanted: S014
«مصلحة الضرائب» (all 123 catalogue headings are Egypt's; Egyptian journal) and S173 (the army, Egyptian journal and
author, 1957).

## Files

`sample63.py`, `sidebyside63.py`, `hardchecks63.py`, `openreview63.py`, `stats63.py`; `out/` (gitignored):
`blind63.txt|jsonl`, `sample63_key.json`, `mine63.jsonl` / `mine63_frozen.jsonl`, `journals63.json`,
`sidebyside63.txt`, `adjudication63.json`, `hardchecks63.json`, `openreview63.txt`, `openreview63_findings.json`,
`numbers63.json`. Progress notes: `progress.md`.

**Run it again** (read-only, under a minute; the blind answers are mine, not code):
```
python3 experiments/63_verify_institutions/sample63.py        # rewrites the sample and the blind views (seed 63)
python3 experiments/63_verify_institutions/sidebyside63.py > experiments/63_verify_institutions/out/sidebyside63.txt
python3 experiments/63_verify_institutions/hardchecks63.py
python3 experiments/63_verify_institutions/openreview63.py
python3 experiments/63_verify_institutions/stats63.py
```

## What it changed

Nothing in the platform, the releases, the Desk or experiment 56. It gives the go-ahead to apply exp 56's
decisions under the rule above, and a code gate (`hardchecks63.py`) for later passes.
