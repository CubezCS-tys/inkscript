# Experiment 72: progress

- 2026-11-02 21:10 CST: started. Read exp 71 (design), 62/56/63/64/67/68/70, D37–D45. Release on which the pass is made:
  R20261103T023001 (live, after exp 70).
- 21:35: `works72.py cards`: 14,042 active cards on the release, 5,322 cited by a 0165 article (exp 70's count);
  the Desk's possible-same-work detector finds 451 pairs on it (17 s, 0.24 GB).
- 21:36: catalogue drawer (exp 62's catindex62, one pass over marc.db) started for the 5,322 cards.
- 21:50: institutions: `inst72.py packets` (exp 56's builder on the live release: 1,089 printed affiliations, 329 in
  0165). Candidate finder (`finder-eval`, on exp 71's 138 institution questions that name a body): old retriever
  103/138, new 133/138 (31 of the 35 exp 71 had to inject). New = trigrams + place (printed city / country ->
  that place's universities, exp 56's R4 city table) + journal publisher + shared distinctive name words +
  faculty-name hints (Arabic Language / Usul al-Din -> Al-Azhar, Qaraouiyine, Imam, Umm al-Qura, IU; Dar al-Ulum ->
  Cairo, Minia, Fayoum). Partly in-sample (the city table came from the same 780).
- `inst72.py build`: 329 affiliations -> 167 R1 (printed authority form, one body, no former/degree word, no second
  organisation word left), 50 R6 (a place or a position, no organisation word), 112 to the models; + 68 Arabic /
  Latin unit-row twin questions, 4 unit rows with no parent.
- 22:05: prompt72 (= prompt71 + the owner's rules D37-D44 + `roles`, `inferred`, option same_text). Flash pilot
  (5 Standard, $0.011) then Flash Batch on the 179 institution questions ($0.20). Flash applies 20 (17 rows are one
  body, 3 names no body); 51 "different" rows need nothing; 113 to Opus (Batch submitted, worst case $2.52).
- catalogue drawer done: 11.6 min, 0.75 GB; 5,322 cards: accept 648, candidate 116, relation 121.
- persons72: 12 same-name pairs touching 0165; one obvious (منى حسين (محمد) الدهان: two catalogue authority records,
  both signing 0165 at Ain Shams' Faculty of Specific Education); the others pair a byline person with an authority
  record seen only in citations -> proposed for people.
- 22:20: Opus (Batch) on the 113 institution questions ($0.71) and the 492 work questions (2 jobs, $1.90). Authority
  review by hand (`review72.py`): 29 bodies accepted (22 used by an applied decision), 2 refused; the reviewed forms
  corrected 2 R1 answers («جامعة القدس المفتوحة» had gone to Al-Quds University: exp 63's H18 trap).
- 22:45: tiers (decide72 final): of 1,873 questions Flash applies 1,217, Opus 350, 51 need nothing, 255 to people.
  Plan (plan72): 2,321 Desk decisions; two answers on one card that disagree (C70RAZGS25: K1c chose the 2014 copy
  in «مجلة الطفولة والتربية», the print names «مجلة الطفولة والتنمية» 2015) -> a person.
- 23:00: hard checks: institutions H1b 1, H7 1, H8 10, H14 2, H17 9, all read: none wrong (two bodies in two
  countries; pre-existing authority notes; judgement links that print another form). Works: transitivity 0, years 1
  (Hijri/Gregorian), authors 8 (one name printed two ways, a translator, a corporate author): none wrong.
- Alarm: Sonnet on 40 of Flash's 1,217 applied (2% -> min 40, seed 7272): 40/40 agree. Flash (asked first) on all
  350 of Opus's applied: 346 agree; the 4 are one body under two names (2) and same_work vs edition_of (2).
- Hand check: random 40 of the plan (seed 7240): 40 right. Stratified 106 more over every applied kind (seed 7241):
  102 right, 3 minor, 1 wrong — Flash's "rows are one body" 16 of 17 (read all 17): **held** as proposals
  (`out/hold_kinds.json`); the twin the lead named (I1NW24RKQM / IP0XR2KXSC) applied on its own evidence. Two
  retitle titles cut wrong by plan67.item_title («Emot» inside «emotions», «Psycho- logical») -> no title taken.
- 23:20: dry run 1 failed at the tasks (a task's `about_decision` must be a decision uuid); fixed, dry run 2 running.
- (clock times from here are real; the ones above are approximate) 23:41: dry run 3 (`test_e72dry`): 2,297 of this
  pass's decisions imported, 0 refused; release R20261103T052117 (scratch): 5,035 applied, 12 superseded (exp 68's 3
  orphans among them, re-anchored), **0 orphaned, 1 conflict (the known «المقدمة» demo)**, constraints hold, FK ok,
  33,028 constraint checks, 0.09 GB. Tasks: 37 librarian questions were skipped by add_task's standing check (another
  decision on the same card) -> `check_standing=False` for them; re-run in the test schema: 185 librarian
  questions + 88 possible-same-work pairs.
- 23:42: live: `golive72.sh` started.
- 23:57: live import done (`import72.py`, 12.5 min): 2,297 decisions, 0 refused, 273 tasks, exp 68's 3 orphan tasks
  answered. 00:01: release **R20261103T055432**: 5,035 applied, 12 superseded, 0 orphaned, 1 conflict (the demo).
  Measures: institutions 108 -> 96, with a country 64 -> 77, cited works 5,322 -> 5,253, held 10.6% -> 11.9%, shared
  with 0130: works 157 -> 199, institutions 17 -> 19.
- 2026-11-03 00:10: the lead reports CBDD9P2BCR (al-Hiti «ثقافة الأطفال» holds al-Kaabi's 2011 book, 0165-007-028-003
  p25). Checked against Azure's OCR. This pass had confirmed the card (Flash card ok) and recorded it twice more (a
  join, a not-same). `scan72.py` (same pattern over 0165's cards): 9 members on 7 cards; 3 more clear. `fix72.py`:
  4 splits, the 3 decisions re-made on the card without the split-off citations (validated against the release the
  pass was planned on, R20261103T023001), al-Kaabi's citations joined to his card C34EFXV0F2. Dry run 1 found
  CJMAPFK28P's K1c link recorded the split-off citation: re-made. Dry run 2: 0 orphans. Live 00:32: backup,
  release **R20261103T063226** (0 orphans, the demo conflict).
- 00:35: read all 26 of Flash's card-ok answers: 24 right, 2 wrong (CBDD9P2BCR; CVDWKPANEQ, Hammouda's 2011 «العلاج
  النفسي» printed «__________» inside Abdullah's 2013 book). The kind is held: 25 confirms reverted by their owner, 24
  tasks, CVDWKPANEQ split. Dry run, then live 00:37: release **R20261103T063710** (5,040 applied, 41 superseded, 0
  orphaned, 1 conflict). Final measures in README.
