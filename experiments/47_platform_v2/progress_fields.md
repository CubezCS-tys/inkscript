# v3.5b fields into the platform (2026-10-22) — progress

Task: every extracted field visible in the platform (owner, 2026-10-22). Audit, schema + loader, reload, Desk. No calls.

- 18:29 read CLAUDE.md, 47 README/load47/parse47 (+ parse46.parse_article), 43 enrich43/meta43.enrich/refs43.v35_parts,
  43 README "Prompt v3.5" + "Letter fix", homes.json (235 fields). Reload agent: lettersfix loads done 18:21/18:25,
  link 18:27; progress file not yet "finished".
- 18:29 dev copy by backup API: /home/appuser/data/platform_v2/dev_fields.db (1.0 GB).
- 18:41-18:48 schema47.sql (+14 columns on 9 tables, 5 tables, 2 views), common47.migrate (an existing db gets the
  missing tables/columns/views; nothing dropped), parse47 v3.5b readers, load47 / biblio47 / link47 writers.
  Positional INSERTs into publications (biblio47) and cited_work_members (Desk release.py) made explicit.
- 18:52 audit_fields47.py -> out/field_audit.{json,md}: 235 fields, 124 with a filled slot; before 102 in, 5 partly,
  3 wrong (editors/translators read as co-authors; cited page vs the work's range), 14 missing.
- 18:55 test_ids47 (small, now + 11 j0130_final stems): identical in 86 tables (163 s, 0.14 GB).
- 18:55 coordinator: reload finished; link47 has the reload agent's old-card-id fix (kept: present in the file);
  load47 run_file kept; do NOT copy the reload agent's draft over platform_v2.db (owner's call).
- 19:00-19:10 dev reload (4 shown runs --force + link47, 2.7 min a run, 0.16 GB): orphans 0, but 88 card ids lost /
  86 new with no merged_ids: load47.delete_version dropped the cards' memberships, so link47 had no member to
  inherit an id through when a card's content key moved (editors no longer authors). Fix: delete_version keeps
  memberships / link evidence of mentions that come back (same mention_pk), gone_mentions() drops the rest.
  Desk tests: 18 pass, 1 fails (detector counts pinned at 62/154 before j0130). Dev copy redone from the live db.
- 19:16 dev reload 2 (membership fix): 2 cards merged with merged_ids rows; one wrong («An Introduction to Social
  Psychology», Hewstone et al. (Eds.) joined McDougall's book once the editors were no longer authors). Fix:
  link47 matches an author-less work by its editors. Dev reload 3: every active card id kept (0 lost, 0 new),
  merged_ids unchanged, links 900 / relations 398 unchanged; small test_ids47 identical (86 tables).
- 19:35 found: biblio47.refresh_institutions writes inst46's faculty into faculty_text (not NULL as the audit said),
  and separating the faculty out of org_text re-keyed 21 institutions (8 dropped without merged_ids). Fix: org_text
  as before, the reader's faculty in a new column faculty_printed. Dev reload 4 + test_ids47 --full started 19:40.
- 19:42 real db backed up (backup API) to /home/appuser/data/platform_v2/platform_v2.before_fields_2026-10-22.db (integrity ok)
- 19:53 real reload done (4 runs --force + link47; 2.7 min a run, peak 0.22 GB): orphans 0; checks47 orphans 0; card ids 0 lost / 0 new; audit rerun on the real db
- 19:55 Datasette :8003 restarted (README Serving command, /home/appuser paths); 28 canned queries
- 20:04 test_ids47 --full (1,746 s, 0.93 GB): A = B in 86 tables; A vs C one row: publisher «المجلس العربي/العربى للطفولة والتنمية» named by whichever journal loaded first (pre-existing, surfaced by adding j0130 to the test). biblio47: the smaller name is kept. Full test rerun started. Desk: release R20261023T005909 (24 decisions: 15 applied, 9 superseded, 0 orphaned, 0 conflicts), detect 66/290/21 found, 0 stale; API :8005 restarted; web built + restarted :8004; homes.html rebuilt and copied; Desk tests 19/19 (the detector test's 62/154 updated to 67/291: stale since j0130)
- 20:06 screenshots of the Article and Work pages (local Playwright, Node 20) in 49/out/v35_fields/: no page error; READMEs 47 / 49 / 51 written
- 20:33 test_ids47 --full rerun: A, B, C identical in 86 tables (1,698 s, 0.93 GB). Done.
