# Experiment 73 progress: Desk showcase audit (2026-11-02)

- Read context (overview, story, exp 70 headline). Live release is R20261103T023001: 1,143 articles in the index.
- Test actor agent:showcase-audit (corrector) created; token kept in the agent's scratchpad only.
- Playwright walk of 39 views started at 1440x900 and 390x844; shots in out/audit_shots/.
- 23:50 Looked at pages 1-13 (desktop). Early findings: nav wraps to 2 rows on most pages at 1440 (85 px; 187 px on phone);
  0165 listed as "random sample" on /index-home and /journals; "1 read whole" stale; /articles says 700 (API limit) vs 1,143;
  /project says gate 2 pilot "being read" and $152/$456; gate1/ and the deck carry pre-librarian numbers (84 vs 11, 26 vs 3.8);
  /gate2/ is the pre-run selection page ("nothing has been run"); article header full of internal ids.
- 23:52 Lead: desktop only; phone walk stopped (its partial shots *_m.png ignored).
- 23:41 All 39 desktop views + 3 extra article views + 7 views at 1920 shot and looked at. /releases gave a 500 on first open (diff > 30 s, proxy hang-up), fine on retry.
- 23:55 AUDIT.md written: top 10 problems, page-by-page table, number disagreements, 7-screen shareholder path, must/nice/later changes with files.
