# Experiment 64 progress
- 2026-11-02T09:35:28-06:00 started: reading exp 56/63/49 docs
- 09:45 backups: ~/data/desk/backups/desk_schema_before_exp64_20261102T094457.{dump,sql} (pg_dump -n desk) and
  code_before_exp64/ (keys, ops, release, reading, db, index_pages, explore .py, schema.sql). Releases on disk before:
  R20261023T005909 (newest, the one the Desk reads; exp 56 ran on it) and R20261022T233109. Reading unchanged since.
- Finding: the Desk had NO institution ops at all (OPS: works, persons, back references only). To add: key kind aff:,
  ops define_institution, same_institution, not_same_institution, not_an_institution_row, set_inst_country,
  set_inst_parent, set_inst_type, link_affiliation (role current|former|educated_at, inferred), not_an_institution,
  unit_kept_apart. Former / educated-at links go to affiliation_links with level 'former' / 'educated_at' so every
  counter that reads level='org' (index, gate 1 via measure52, explore) leaves them out without new code.
- 09:57 imported 1146 decisions of agent:librarian into schema desk (import64.py, 22 s); log out/import64_desk.jsonl. Dry run before in test_e64dry: 1146 applied, 0 conflict.
- 09:57 release R20261102T155701 built (desk.cli release --keep 3): 1170 decisions, 1161 applied, 9 superseded (old),
  0 conflict, 0 orphaned, decisions_hold, fk 0 -> 0, 5,890 constraint checks, 18 s, 54 MB. No copy pruned (3 on disk).
- measure64: 242 institutions (exp 56 234: +7 unsure-kept machine rows, +4 new bodies, -3 now former/educated only),
  225 with a country (93%; 96% without the 7), 70 in 2+ articles, 591 affiliations; gate 1 25 vs 6.3 (index, measure52),
  25 vs 6.55 (exp 56's count). Live API (started 09:55:42, after the last code edit 09:54:54) already serves it.
- Tests: Desk suite 76 passed (5 min); repo tests/test_docs.py: mine fixed; 1 failure left from 65_fix_leaks (another
  agent's experiment without a README yet).
- Docs: D37-D39 (docs/decisions.md), STATUS.md row, Desk README "Institution decisions", exp 56 "What it changed",
  project.json timeline item, experiments/README.md line, this README.
- Left for the lead: test schema test_e64dry and the scratchpad dry-run copy (1 GB) can be dropped / deleted.
