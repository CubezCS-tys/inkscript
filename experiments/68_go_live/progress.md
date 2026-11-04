# Experiment 68 progress (take the extraction fixes live)

- 14:57 read 61/64/65/66/67 READMEs, build65, the patch; applied d30guard.patch (both parts); parse47 accepts
  `model-suggestion` (own layer); pipeline.py shows it with the flags. Tests 43 (84) + 47 + test_d30guard pass.
- 15:02-15:27 build68.sh: four rebuilds into *_fix61_d30 in parallel (peak 0.80 GB each), all valid.
  compare68.py: 409 refusals (408 simulated + 1), 0 unexplained text changes, all flags, none applied.
- 15:09 backups (platform_v2, link cache, desk schema 20261102T150931). Baseline dry run on the live reading
  reproduces R20261102T174226's fingerprint (b6c00dc8…) with the new release code.
- 15:31-15:55 load 1 into a copy: re-minted institution ids (99; 10 named by the Desk), 45 decided affiliation keys
  gone; dry run 62 orphans. Causes: inst46 cluster keys move with the twin rows and reloads give new aff_pks;
  English lines moved to the twin's mention; bylines renumbered by the Latin fold; 20 empty printed names (parse46).
- 16:00-16:55 fixes and reloads 2-6 (each on a fresh copy): biblio47 continuity into merged_ids (by place / text /
  word overlap; same body by name after a wrong AIU -> Alexandria carry in load 4), Reading.aff_moved_twin /
  aff_by_text, define_institution re-makes a vanished registered id as it was, a split stands on its remaining
  members, twin inheritance and twin-free counts; tests/test_twins.py; Desk suite 93 passed each time.
- 16:55 dry run on load 6: 2,738 applied, 3 orphaned (two English lines exp 65 reads as part of combined lines + the
  English faculty row they made), 1 conflict (demo «المقدمة»); numbers 242 / 225 / 70; cited works 8,903.
  Audit on the candidate: 1,457 -> 808 generic-only lines, 99.814%.
- 17:10 STOPPED before going live (the lead's rule: orphaned decisions). golive68.sh ready; README written.
