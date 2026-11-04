# Experiment 62 progress notes

- 09:02 read exp 56 (design reused), schema47 citation tables, link47 build_cited_works, detectors, probe B notes, exp 52 catalogue52/measure52. Release R20261023T005909: 780 shown, 9,757 full + 2,732 short + 1,212 back refs; 9,137 active cards.
- 09:05 catalogue62.py extract/classify (9,137 cards), match started in the background (probe A's matcher, ~0.15 s a card).
- 09:10 catalogue: probe A's per-card FTS ran at ~5–10 s a card on this server (random reads of the 10 GB marc.db under memory pressure): stopped. catindex62.py instead: one sequential pass over the 1.56M records (17 min, 1.07 GB peak) keeps 388,167 records that share >= 60% of some card's title words, then scores every card (probe A's thresholds restated). 841 accept / 183 candidate / 188 relation. Against experiment 52's probe A decisions on the gate-1 cards: 614 of 645 accepts identical, 3 to another record, 18 to candidate, 10 none; 18 new accepts.
- 09:25 cands62.py: blocking (fuzzy folded titles, one misprinted letter, author words dropped, short vs long, surnames, skeleton transliteration). Several rounds: float nondeterminism fixed; surname-based author relation (given names alone = "weak"); names one letter off only when 5+ letters. Final: 143,810 pairs examined, 1,015 candidate edges, 505 merge packets (482 clusters + cut edges), 88 split, 263 not-a-work, 1,224 catalogue. Desk detector's 290 pairs: 238 covered; the 52 missed read one by one: almost all different works by one author (true duplicates missed: about 2).
- 09:40–10:30 judging merge packets batch by batch (overrides62.json, each with its reason); tools62.py: seen list, card evidence, the note's body context (what «ديوانه» refers to), the catalogue drawer.
- 10:30–12:40 all 505 merge packets read (1,015 edges + 21 pairs the blocking missed), 88 split packets (+2 over-merged cards found while judging), 263 not-a-work, 383 catalogue candidates/relations/read-article hits, and the 227 catalogue accepts that were not exact on title+author+year (14 changed). overrides62.json: 704 calls, each with its reason.

## 2026-11-02 afternoon: verification instead of an owner sample

- finalize62 → numbers62.json (pinned release R20261023T005909); check62 → checks62.json: transitivity 0, death dates 0,
  years 0, type 0, catalogue 1 → an English title of an Arabic article (C7J0GDT6Y1 = CYWSYA0PVJ), fixed; authors 18
  (all deliberate name variants, e.g. «ابن حنى» = ابن جني).
- recall62: 150 random cards × the 6 nearest cards the blocking did not pair (810 read): 1 missed duplicate
  (a translated title, C0S06SQX8H = C2X8669N6Y); the blocking found 6 for the same cards → recall ≈ 6/7 (small sample),
  Desk detector pairs covered 238/290 (the 52 outside are mostly different works).
- blind62: 156 decisions, stratified (seed 6262), judged blind by a separate sub-agent from evidence only: 138 agree
  (88.5%). 18 disagreements adjudicated (adjudicate62.py): blind right 14, librarian right 3, both defensible 1.
- fixes from the adjudication and from re-reading the populations the errors came from: 13 blind cases, 2 review
  records linked as the work (found by rules62), 13 no_link → relation, 26 not-a-work actions (drop/retitle/one per
  citation) — then the authors check caught a chain the B044 fix made (Sahih Muslim = al-Nawawi), fixed.
- after: 8,850 works, 289 cited by 2+, gate 1 118 vs 16.65 (7.1×), held 7.47% (journal 18.14%).
- rules62: K1b (title+author+year match, record not a review, not thesis→article) reproduces 759/764 links (99.3%);
  C1 (journal-name card not a work) 73/73; P6 (thesis vs article → different) 12/12.
- scale62 → scale62.json. Round 2 blind (100 K1b links, 40 same_work, 20 not-a-work) running.
- blind round 1 adjudicated: blind right 14, librarian 3, both 1; fixes + population re-reads (26 not-a-work actions, 13 no_link → relation, 2 review records); authors check then caught the Sahih Muslim / al-Nawawi chain the B044 fix made.
- blind round 2 (160): 153 agree; 4 venue/form mismatches in links → re-read the 157 links where venue or form was in doubt, 11 → relation; rule K1c (venue fits) 696/698.
- APPLY rule, 5 escalations, scale62, Desk /librarian/works (module, page, tests: 90 Desk tests pass), screenshots in out/shots/, scratch servers stopped, test_works62 dropped. README written.
