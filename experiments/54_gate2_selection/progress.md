# Experiment 54 progress

- 2026-10-22: read CLAUDE.md, ideas (Education Citation Index), exp 52 and 53 READMEs, D36. Folder made.
- inventory54.py: 282,017 EduSearch research records 2000-2025 -> out/articles.tsv (54 s, 0.27 GB). 2005-2025: scan 162,816 (matches ideas.md), Word 92,832, nowhere 12,142. No record is legacy-PDF-only: every legacy stem also has a Word file.
- cited54.py on platform_v2.db (read-only): 126 current 0130 versions, 3,832 full references, 619 accepted catalogue links -> out/cited_by_0130.json.
- journals54.py: types, subjects, authority ids per journal (41 s, 70 MB) -> out/journals.json. rank54.py -> out/candidates.json (TF-IDF subject similarity added).
- Page estimate check: catalogue page ranges of 0130's 126 scans sum to 2,441; Azure pages were 2,439.
- wordcheck54.py (exp 53's first-page check, sample per journal, seed 5454): test on 0130 and 0165, 10/10 each match.
- Candidate costs computed (scan pages from catalogue ranges). Sizes: most Egyptian faculty journals are 600-4,000 articles in 2010-2025 and 35-80 pages an article, so they do not fit 10 journals in 2,000-3,000.
- Hubs 0085 (Kuwait, 982) and 0040 (Bahrain, 928) share the most authors with everyone (358 with each other) and are cited by 11 and 9 of 0130's articles, but each alone would be ~30% of a 3,000 set and ~$155: left out by the 25% rule.
- select54.py written (table, sets, cost, page; page54.css from gate1's look). Recommended (draft): 0130 0165 0011 0523 1001 0246 1182 0097 0840 0013 = 3,460 articles, ~$456 expected. Cheaper: 0130 0165 0011 0097 0840.
- next.config.js: gate2 added to both static-page rewrites.
- wordcheck54.py running on 37 candidates, 15 each (soffice, ~0.33 GB).
- Word check: one soffice batch hung 20 min (0082) and was killed; a watcher then killed any batch over 5 min. 328 files sampled. titlecheck54.py: page mismatches are almost all 1-3 pages off with the right title; only 0056 has wrong files. 0233 (7/15 page misses, all right title) would have been wrongly rejected by the page test alone.
- Final: recommended 0130 0165 0011 0523 1001 0246 1182 0097 0840 0013 = 3,460 articles (1,660 scan / 1,768 Word / 32 nowhere), $456 expected, $633 worst. Cheaper: 0130 0165 0011 0097 0840 = 1,344, $152.
- Page copied to the Desk (public/gate2/index.html), next build + restart.sh: /gate2/ and /gate2 200, /gate1/ still 200. Screenshot out/shot.png checked.
- README written; line added to experiments/README.md.
