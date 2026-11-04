# Experiment 65 progress (fix the leaks of experiment 61, steps 1-3)

- 2026-11-02 10:05 started. Read exp 61 README/audit.json, exp 43 README (pipeline, v3.5/v3.5b, letter fix), the
  rebuild scripts (lettersfix.sh, build52.sh, final52.sh), load47. Code of 41/43/47 unchanged since 2026-10-22 20:04
  (all four current runs were built by it or by the HEAD snapshot + letters). Exp 64 is working in the Desk (49) now:
  no platform_v2.db / Desk / PostgreSQL writes here; parse47/load47 edits must be additive (new JATS markup only).
- 10:10-10:50 code: meta43 (M1 role_parts / split_role, M2 keep_twin_parts, M6 prefix_in_printed; v3.6 position),
  leaks43.py (new: M4 later_bylines, M5 subtitle, step 2 identifiers + <stem>.ids.json, P2-by-code article_lines,
  v3.6 homes), refs43 M7 (HYPH_BREAK), masters43 hooks (+ EXP65_OFF=1 switch for the control build), enrich43
  (v3.6 keys checked), prompt43 v3.6 (PROMPT_V36 / META_FULL_V36 / ENRICH_*_V36), parse47/load47/schema47
  (byline position / contacts, affiliation lang / twin_of_aff_pk, printed_identifiers, article_v35 new fields),
  audit61 --release/--out (+ raw_of for *_fix61) and fields61 new homes. Candidate DB copied (backup API):
  ~/data/platform_v2/candidate_fix61.db. Tests: test_leaks43 11 + the other 43 tests 65 pass.
- 10:58 v3.6 check (run43 --set e = sample65.json, 10 pages, Standard, cap $104 on the $100.146 log): 8 calls,
  $0.330 billed (log $100.476). Built (out/v36_check/build): it showed two code bugs, fixed before the rebuild:
  a name label («اسم المؤلف الرئيسي:», "Main Author Name:") taken as a post (now a role phrase), and names_pre's
  Latin fold pairing NEIGHBOURS (A, B, A', B' -> B+A'), now best consonant match, and left to enrich's same_as when
  the answer gives it. compare36.py -> out/v36_compare.md.
- 11:20 j0130 rebuild restarted with the fixes (build65.sh j0130).
- 11:30-12:05 lead's addition: v3.6 fix-rule bullet (experiment 66). Second paid check out/v36_check2 (13 pages = the
  10 + 1080-002-010-015 p8, 0130-020-079-004 p2, 1010-006-011-015 p6): $0.466 (log $100.942); total paid $0.796.
  Looked at the scan crops: v3.6 stops the four bad fixes (حال, بنسبة, ثلك, بدعو) and loses four real ones on the
  faded 1080 p8 (الاسيوى, للعبودية, نرضته, يمنع).
- 11:40 j0130 trial: audit on a scratch DB copy: v3.5b b-lines 331 -> 62. Fixes after it: posts printed at the start of
  a byline line (posts_in_bylines), «أ. د», bare «أستاذ» = rank, «د. / أستاذ …», DOI with spaces, signature date
  filter; audit: «doi», «orcid», «id» as labels and spaced variants of stored DOIs / ORCIDs (same code before/after:
  the old release scores the same, 1 line of 435,270 moves).
- 12:02-12:44 second full rebuild + load + audit: mapping lines 953 -> 299. Then found leaks43.fold's tashkeel
  class swallowing every Arabic letter (Arabic names never matched: e-mails / posts / later bylines fell back to
  weaker rules); fixed (escapes), names also matched letters-only («عبدالحافظ» / «عبد الحافظ»), e-mails Gemini
  already gave owned before the running-head rule. Third (final) rebuild from 12:50; candidate DB re-copied clean.
  Earlier attempts kept in out/first_attempt/, out/second_attempt/ (not loaded anywhere live).
- 12:50-14:20 final rebuild (j0130, v2, exam, first; all text identical, control identical), clean candidate copy
  loaded (4 runs, 0 orphans, integrity ok), audit after: mapping 953 -> 292, b 1,457 -> 805. README, D45, STATUS,
  experiments/README, 43's README (v3.6). Repository suite 111 passed / 7 skipped; experiment 43 / 47 / 61 tests pass.
