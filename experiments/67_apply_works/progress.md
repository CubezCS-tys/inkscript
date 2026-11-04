# Experiment 67 progress

- 2026-11-02 11:00 CST started: read exp 62 (README, decisions62, precision, rules, escalate, checks), exp 64 (README,
  import64, plan64), the Desk (ops, release, keys, reading, schema47 citation tables). Releases on disk:
  R20261022T233109, R20261023T005909, R20261102T155701 (exp 64; the Desk reads it). platform_v2.db unchanged since
  R20261023 (same size and mtime). Code backed up to ~/data/desk/backups/code_before_exp67/.
- Finding: the Desk had the P1 work ops only (split, same, not same, move, type, confirm). Added: key `pub:`, ops
  edition_of, not_a_work, define_work (phase 3), link_publication, relate_works, relate_publication (phase 10);
  catalogued-only publications from the record the decision carries (151 records read from marc.db at plan time).
- plan67: 1,589 → 1,581 decisions after merging the 7 cards with two not-a-work answers (finalize62's precedence)
  and holding 1 relation made moot by an edition_of + K1c link (CGWJPWHSMH / W873397).
- 11:20 dry run 1 (test_e67dry, a copy of desk's 1,170 decisions): 7 refused (two answers on one card), 9 conflicts:
  8 were the import's own order (a same_work / link on a card split earlier recorded the card's pre-split members),
  1 is real (the P1 demo's same_work on «المقدمة» vs exp 62's split). Fix: ops.pending_moves (what a decision records
  follows standing splits, moves, drops); a retitle's title holds only while the card is that card.
- 11:29 dry run 2: 1,581 imported, 0 refused; release 2,741 applied, 1 conflict (the demo), 0 orphaned, checks hold,
  fk 0. measure67: 8,850 works, 288 by 2+, 79 by 3+, gate 1 118 vs 16.7, held 6.64%.
- 11:31 backup: ~/data/desk/backups/desk_schema_before_exp67_20261102T113059.{dump,sql}. desk.cli init (review rules).
- 11:36 imported into desk (269 s, 0 refused); release R20261102T173613 (--keep 4, nothing pruned).
- Found on the pages: Sahih Muslim showed edition rows with 0 citations: a split / join left moved citations on the
  old card's edition rows (an old fault, now visible), and edition_of collapsed a side's distinct editions into one.
  Fix: Builder.carry_edition (a citation takes its edition along), edition_of per edition, card 1's citations that
  name no edition stay so. Releases R20261102T174053 (--keep 5) and **R20261102T174226** (--keep 6): 0 empty
  editions, 0 stale counts, 0 citations on another card's edition; same numbers.
- Live API (started 10:56, older code) reads R20261102T174226: overview 8,850 / 288 / 6.6%; most-cited; J0130 118
  shared, 16.84% held; Explorer. Screenshots in out/shots (CDP, signed in with the demo token).
- Docs: D40–D44, STATUS row, Desk README "Cited-work decisions", exp 62 "What it changed", experiments/README line,
  this README. Small screen edits: reverse relations on a work page, "held" wording, librarian banner note.
- 11:58 Desk suite 92 passed (6 min); tests/test_docs.py: only 65_fix_leaks (no README yet, another agent's) fails.
