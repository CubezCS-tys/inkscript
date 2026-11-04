# Experiment 56 progress notes

- 13:00 read the Desk design, link47/biblio47 refresh_institutions, inst46, field guide. Release R20261023T005909.
- 13:05 marc_authority56.py: 2,410 corporate (110) headings, 2,085 (university, country, faculty) triples from 502 → out/marc_inst56.db (42 s, 18 MB).
- 13:08 build56.py: 659 packets (all affiliations of the 780 shown versions), 589 located on the scan (Azure lines) → out/packets56.jsonl.
- 13:10 authority56.py (hand-made authority, ~230 entries) + judge56.py (rule proposal + overrides) + decisions56.py (append-only JSONL).
- 13:14 batch 0 judged and committed (60 decisions).
- 13:15–13:25 batches 1–10 judged and committed (95 overrides in all, each with its reason; authority grew to 280 entries).
  Caught while judging: «جامعة الزيتونة» is also Libya's (shared names now need a printed country); «الهيئة العامة للآثار والمتاحف» is Yemen's, not Syria's.
- 13:25 finalize56.py: institution-level questions (same / split / country / parent / type / not an institution), authority, numbers. Gate 1 reproduced exactly (26 vs 3.8) with the machine's links; with the authority 25 vs 6.3.
- 13:28 decision ids made unique when an answer returns to an earlier one; the pass's working log moved to out/decisions56_draft_log.jsonl and the clean log rebuilt.
- 13:30 rules56.py (8 rules measured), sample56.py (30, stratified), scale56.py.
- 13:32 Desk: desk/librarian.py, librarian_verdicts table, web/pages/librarian.tsx, nav item; tests/test_librarian.py 6 passed.
- 13:35 test servers :8055 (schema test_librarian56) / :8054 (.next-librarian); screenshots out/shots/ looked at.
