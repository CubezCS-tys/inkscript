# Check log: the two shareholder documents (2026-10-28)

An adversarial check of every factual claim in `business/business.html` and `technical/doc.html` against the
project's sources. Backups of the HTML as they were before the check: `business/business.html.before_check`,
`technical/doc.html.before_check`. Data were read read-only (the release `R20261023T005909.db` opened `mode=ro`);
no paid call, nothing uploaded, no live service touched.

Format: claim → source → **verified** / **fixed** (how) / **unverifiable**.

## Business overview (`business/business.html`)

### Cover and 1 Executive summary
- 1,013,912 documents with scan + full OCR → exp 44 README; project.json n-archive → verified.
- 1.56 million catalogue records (1,558,415) → exp 45; n-catalogue → verified.
- 0 of 1,532 words wrong on 60 random pages of unseen articles → STATUS "The exam, the proof pack…"; n-words → verified.
- 64× repeat authors (16 vs 0.25) → exp 49 README "The index pages" (live, 64×); exp 52 → verified.
- ≈ $0.01 a page; gate 1 $0.0099 a page, $0.192 an article → exp 52 "Cost" → verified.
- "A web platform … the Desk lets about 300 correctors fix what the machine gets wrong" → exp 49: designed for ~300;
  P3 corrector pilot not run, no remote access (risk r-access) → **fixed**: "is built for about 300 correctors … (so far
  used only by the team; no corrector pilot yet)".
- "Every fact links back to the ink on the scanned page" → exp 49 README (All fields: 46 of 144 fields with ink;
  journal title/issue/year have no ink anchor yet); field guide → **fixed**: words, authors, affiliations and references
  link back to the ink they were read from.
- Accuracy: no serious errors after one round of fixes → STATUS (fix round 3: serious 2 → 0) → verified.
- Gate 1: 126 articles, journal cites itself 32 times (live platform) → exp 49 README; source note (39 with matcher) → verified.
- "All AI spend for the work so far was $100.15" → `gemini_spend.jsonl` recomputed: 3,070 rows, $100.146, but the log
  starts at the 18 Oct top-up; the credit had already run out once on 2026-10-15 (handoff.md, STATUS) → **fixed**:
  "All Gemini spend logged since the 18 October top-up, which covers the test of 300 articles and gate 1, was $100.15".
- Asks: gate 2 ten ≈ $456 / five ≈ $152 (estimate); gate 3 162,816 articles ≈ $43k / ≈ $86k after 1 Dec; pilot 5–10
  correctors and servers not priced → exp 54 "Cost"; project.json roadmap, money, next_steps → verified (estimates labelled).

### 2 The problem
- Scopus ~280 of 29,553 journals from Arab countries (Al-Fanar, May 2025) → exp 55 README Sources → verified (as their figure).
- ARCI 400+ journals, from 2015, 138,283 records 2015–2020 as of May 2022 → exp 55 (El-Ouahi) → verified.
- ARCI records include cited references → exp 55 "What could not be verified"; project.json source note → verified.
- AI-Search weak spots listed 21 Oct 2026 → exp 55 story.md; exp 50 → verified.

### 3 What Mandumah holds
- Heading "What Mandumah uniquely holds" and "Other services index the metadata …; Mandumah holds the full text of
  every article in the journals it carries" → section 8 itself lists e-Marefa and Al Manhal as full-text Arabic
  databases; exp 44: of 1,388,815 catalogued article ids 72% main + 22% legacy, 6% nowhere; exp 52: 0130 has 195 of 389
  in the main bucket → **fixed**: heading "What Mandumah holds"; "Citation indexes such as ARCI index …; Mandumah holds
  the full text of the articles … (94% of catalogued articles are in the archive, as scans or PDFs)".
- 308,593 legacy PDFs, 98% with the publisher's Word file → docs/overview.md; exp 44 → verified.
- Platform pages reachable only on the local machine; model provider sees page images → docs/overview.md, story.md Q7 → verified.
- "never published on … a public code repository" → the code repository is on GitHub (`origin`); its visibility could
  not be checked from here (no `gh`) → **unverifiable** (left; the owner should confirm the repository is private).

### 4 What we built
- "Azure's OCR has already read every word of the archive" → Azure read the 1,013,912 main documents; the 308,593
  legacy PDFs have no Azure reading (exp 44, 53) → **fixed**: "every word of the 1,013,912 scanned documents".
- "It answers only with line numbers … Because it never types text" → prompt v3.5b metadata strings are copies of
  Azure text, the field guide found 52 of 659 affiliation strings typed by Gemini (exp 49 README, field guide) →
  **fixed**: answers with line numbers, does not retype the article's text; a few short strings (names, affiliations)
  are copied out by the model and the field guide tracks where they differ.
- JATS and ALTO; database; Desk re-applies decisions → overview.md, exp 49 → verified.
- Islands / bridges / gates, Garfield, precision; gate 1 done, gate 2 waiting → overview.md; project.json stage → verified.
- Product 1 "Every count opens on the printed page" → not every count has an ink anchor → **fixed**: counts lead to the
  articles behind them, each article opens beside its scanned pages.
- Product 2 "so the assistant quotes fewer wrong passages" → not measured: the offline A/B has not run (project.json
  w-ab, i-ab parked) → **fixed**: "should quote fewer wrong passages (not yet measured: the offline test has not run)".

### 5 Proof
- Checking agent, 60 pages of 300 unseen articles, 20–21 Oct → STATUS → verified.
- 0/1,532, upper bound 0.25%; 0/60 serious (2 before); 43/60 right (35 before); metadata 25/30 (18 before) → STATUS
  rows "proof pack", "Fix round 3" → verified.
- References 57/80 fully right, faults are empty fields not wrong values → STATUS (313/341 right, 0 wrong) → verified.
- Gate 1 random pages 9 right / 1 minor / 0 serious → exp 52 → verified.
- 126 articles 2010–2025, 2,439 pages, $24.24, 20 random sets of 126 from 600 → exp 52 → verified.
- Bars: 16 vs 0.25 (64×), 26 vs 3.8 (6.8×), 84 vs 10.85 (7.7×), 15.8% vs 2.4% → exp 49 "The index pages" (live) and
  the index screenshot → verified. With librarian 25 vs 6.3 (4.0×) → numbers56.json → verified (labelled proposals).
- 32 citations: 21 citing → 30 cited; matcher 39, 16.9% vs 2.9%, 38 of 39 right → exp 49, exp 52 → verified.
- Thin: co-authorship one pair, corresponding authors none → exp 52 → verified.
- $0.106 an article on the 300 (11 pages each), $31.94 → STATUS (3,404 pages / 300 = 11.3) → verified.
- Word route $0.01–0.03 estimate, 139/139 by code → exp 53 → verified (labelled).
- $100.15 tile "all AI spend for this work" → as above → **fixed**: "Gemini spend logged since the 18 Oct top-up".
- Storage, servers, correctors' time not priced → exp 55 → verified.

### 6 Screens (images in `business/img/web/`, each looked at)
- Header: release R20261023T005909, 780 articles, 10,150 pages, 3,520,337 words → exp 49; index screenshot → verified.
- 1 Index: 780, 13,695, 926, 271, 410, 9,137; gate 1 table; definitions on hover → screenshot shows exactly these → verified.
- 2 Journal J0130: 17 with 2+ articles, 31.1 per article, 15.8%, 32 / 1, h-index, yellow pilot note → screenshot →
  verified; **fixed** (clarified) that section 5's 16 is the byline-only count of the same thing (exp 49 README).
- 3 Article beside scan: boxes, hover, scroll together → screenshot and exp 49 → verified. "All fields … a crop of
  the ink" → only where the reading has an anchor (46 of 144) → **fixed**.
- 4 Explorer: 780 / 13,919 / 1,948 / 701 / 775 / 9,163, 335 columns (146+68+36+22+28+35) → screenshot, exp 49 → verified.
- 5 Author A8STQEWEAV: 18 publications (8 read, 10 catalogue), times cited 33, 7 citing articles, 6 his own,
  "1 without self-citations", h-index 0–2 → screenshot, exp 49, labels_to_review.md → verified. (The screen's header line
  "33 citing articles" is itself mislabelled; covered by the relabel item.)
- 6 Work task: four references on one card, crops, decision stored and re-applied → screenshot (task 1569) → verified.
- 7 Project map: gate 1 done, gate 2 "you are here", costs per step → screenshot → verified.

### 7 Quality and trust
- 287 "possible same work" tasks open after gate 1 → project.json i-same-work-queue; STATUS → verified.
- Decisions append-only, owned, admins, notes; catalogue errors go out as a list; misprints flagged → exp 49 DESIGN,
  decisions D30/D34, O-ownership, O-catalogue-list → verified.
- Field guide 335 columns, 70 flagged labels → project.json n-columns → verified. "so nothing ships under a wrong
  label" → the Explorer already shows and exports those labels in the pilot → **fixed**: "are to be fixed before the
  data goes beyond the pilot".
- Librarian 659 affiliations, 908 decisions, 662 rule-able, 10 unsure, 271 → 234, 42% → 95%, 16 twins, 30 sample →
  exp 56 README, numbers56.json, screenshot → verified. Proposals only → screenshot banner → verified.
- Screens 8 and 9 captions → screenshots → verified.

### 8 Market
- ARCI, ARCIF (1,272 of ~5,500, 956,000+ papers), Scopus 280 / 29,553, e-Marefa ~1,900, Al Manhal 475+, Shamaa 376
  periodicals ~94,000 works from 2007 → exp 55 README Sources (searched 23 Oct; Shamaa's and Clarivate's figures from
  search summaries) → verified as their own statements; the page already says "not independently checked".

### 9 Business models
- All labelled proposals; no pricing research → exp 55 → verified. search.mandumah.com exists → exp 50 → verified.

### 10 Roadmap and costs
- Gate 1 / 2 / 3 / archive scopes and costs → project.json roadmap → verified (estimates labelled).
- Gate 2: 1,660 scans, 1,768 Word, 32 nowhere; ≈ $456 (worst $633); five ≈ $152 (worst $216), no Levant → exp 54 → verified.
- Gate 3 from ≈ 4.57M pages × $0.0094 ≈ $43k (reconstruction); 92,832 Word-only → project.json gate3; exp 54 → verified.
- Librarian $53–198 education, $281–1,060 per million (estimate) → exp 56 Scale, scale56.json → verified.
- Storage ≈ 1.5 TB + 2–3.5 TB (estimate) → project.json r-scale → verified.
- Argon doubles after 1 Dec 2026, Flash after 1 Jan 2027 → exp 54 → verified.
- Credits: Google Cloud asked 26 Oct; Google.org MENA fund; research credits "academic, up to about $5k" →
  project.json timeline 2026-10-26 says "academic, up to ~$5k, non-commercial" → **fixed**: added "and non-commercial".

### 11 Risks
- £11 left of £101.28 (estimate) → STATUS; project.json money.credit → verified.
- Diwan example (six poets' «الديوان» on one card) → exp 48; r-wrong-bridge → verified.
- h-indexes 0–2; Times cited relabel → exp 49 → verified.
- "70 … They are waiting for review before anything is shown or exported" → the pilot Explorer shows and exports them →
  **fixed**: "They wait for the owner's review; until fixed, the pilot's Explorer still shows and exports them."
- 17 of 23 Word files another article; page + title check → exp 53, exp 54 Surprises → verified.
- 195 of 389 in the main archive → exp 52 → verified.
- 6 of 40 authority ids → STATUS; r-authority → verified.
- 16,800 h, 56 h each (estimate) → exp 48; n-load → verified.
- Release a full copy; accounts and HTTPS needed → r-scale, r-access → verified.
- Model choice: stay with Argon until stakeholders consulted → project.json O-model, i-bakeoff → verified.

### 12 Next steps
- Recommendation the ten → exp 54 Answer → verified.
- Offline AI-assistant test on 12 articles ≈ $0.10 (estimate) → project.json w-ab → verified.
- Word-route test ~20 articles under $1 → w-wordtest → verified.

### Glossary and endnotes
- Definitions match exp 49 / index_pages wording; endnote paths exist → verified.

## Technical documentation (`technical/doc.html`)

### Cover, 1 Summary, 2 Overview, 3 Data sources, 4 Pipeline, 5 Word route (~185 claims; checker notes in the session scratchpad, checkA.md)
Verified (selection): all section-1 tiles (spend log 3,070 rows / $100.146, 18 Oct 15:41 → 22 Oct 15:55; 89 tables + 17
views in the release after excluding 4 FTS5 shadow tables; 14 Desk tables in schema.sql; 2 releases kept); repo started
Sept 2026 (first commit 2026-09-17); 99.99% / 893,203 words / 227 journals (STATUS); every code path in the components
table exists; ports and stores (docs/architecture.md); D30/D33/D34/D35 (docs/decisions.md); exp 44 and 45 numbers; 98.2%
of legacy stems with a Word file (302,961); 162,816 / 92,832 / 12,142; authority coverage 91% / 99%; 6 of 40; exp 19
figures; prompt v3.5b keys and block types vs PROMPT_V35B; hash d6b2156150; v3.5b check numbers; exp 41 Argon/Flash
comparison; D29 30 right / 34 wrong; letter-fix counts; judge calibration 9/11; two-key rule; patch precedence; gate 1
flag rates; exam and gate 1 costs; Batch prices; proof pack and fix round 3 numbers; every exp 53 number; exp 54's 25 of 30.

Fixed:
- "Every word, author, institution, reference and citation in the index can be traced back to the ink" → catalogue
  values and Word-route articles have no ink → now "read from a scanned page can be traced back to its ink …".
- "a correction backend for about 300 correctors" → planned team; no correctors yet (P3 pilot not run) → "built for a
  team of about 300 correctors (none working on it yet; the corrector pilot is P3)".
- Gate 1 "read whole for the years the archive holds" → exp 52 "The set": the archive holds 195 articles incl. 69 from
  2005–2008, left out over the cap → "read for 2010–2025, every article the archive holds in those years … (69 of
  2005–2008 left out for budget)".
- Tile "v3.5b $0.01048 a page" beside an all-in figure → $0.01048 is the run-only cost of the 12-article check (STATUS);
  all-in v3.5b is gate 1's $0.0099 (exp 52) → tile now gives gate 1 (v3.5b) $0.0099.
- "nothing is overwritten" / "releases are copies" → reloads rewrite platform_v2.db after a dated backup; only 2
  releases kept (architecture.md) → "nothing is overwritten without a dated backup"; "(the two newest are kept)".
- "--max-enqueued 2500000 … peak after the fix 2.0 GB" → run43 default 4.5M; 2.5M was gate 1's setting; the main memory
  fix was dropping each article's Azure JSON (exp 52 Method 1) → reworded.
- "It carries the 37 priority items" (and the glossary's "plus the 37 inventory fields") → prompt43.py lines 384–500:
  v3.5b = v3.5 without v3.4's two content lines x164, x178 → "35 of the 37 …" with the reason. (docs/architecture.md
  line 88 has the same over-claim; not edited, outside this experiment.)
- "fell from 1,887 to 85" → measured on the 600 only (exp 47 README) → "In the platform's 600 random articles …".
- Word route "flagged as estimates in JATS and in the platform" → Word-route masters are not loaded into the platform;
  build53 keeps the estimate in pdfmap.json with a JATS custom-meta note → reworded.
- "Owner's hand check 0747: 183/183" → that was on experiment 41's output (exp 41 README) → "on experiment 41's output".

Unverifiable by database count: 13,695 references / 9,137 cited works (index definitions; the release's raw tables
give 13,919 Explorer references and 9,163 cards) → consistent with exp 49 README and the index screenshot; accepted.

### 10 Librarian, 11 Metrics, 12 Operations, 13 Scaling, 14 Limitations, 15 Roadmap, Appendices A–B (~160 claims; checkC.md)
Verified (selection): all librarian numbers and rules R1–R7 (exp 56 README, numbers56.json, scale56.json; $198 vs 199.0
is rounding); metric definitions = DEFS in desk/index_pages.py; "computed only on releases" (exp 49 DESIGN); overview,
J0130 and A8STQEWEAV figures; ports table and 127.0.0.1 binding (architecture.md); tunnel command (host "prod" only);
runbook rules (2 heavy workers, Qdrant, kill by port); watchdog52.sh thresholds (3,072 MB / 10,240 MB); incident 08:38
server time 2026-10-23; web-live and sync-build.sh exist; NEXT_DIST_DIR; only /views/* framed; key/token files mode 600
(ls only, contents not read); dated backup file exists; Word-route, 16,800 h / 22,000 h, DESIGN §7 figures, Batch limits
5M / 500M, 10 jobs ~1 h 40 min; Google Cloud contact 2026-10-26; limitations 441/779, 265/769, 52/659, 70/335, 21
re-minted ids, 6/40, 195/389, ~10% headings, 406/701; dots.mocr licence (ideas.md, D29); roadmap = project.json
next_steps; glossary; D29–D36 and owner decisions (decisions.md, project.json).

Fixed:
- Judge row "flagged pages only ≈ $4k–$11k per million" read as extra cost → the exam's $0.0094 / $106k are all-in,
  judge included (exp 43 README 1393–1400; 1097–1100 are judge-alone) → "included in the rate above (the judge alone …)".
- Gemini read row: $43k (gate 3) rests on ~28 pages an article (4.57M / 162,816), $106k on 11.3 pages → added the page
  basis. **Same fix in the business doc** (roadmap note under the four stops), so the two figures do not look inconsistent.
- "about 32–34 GB available" → only 34 GB measured (2026-10-22; runbooks, operations) → "about 34 GB available on 2026-10-22".
- "masters build 0.38–1.5 GB" → exam masters peaked 1.9 GB (exp 43 README line 871), run43 2.0 GB → "0.38–1.9 GB, a Gemini
  run (run43) up to 2.0 GB".
- "web/restart.sh kills only the process on 8004" → the live copy is restarted via sync-build.sh / restart-live.sh →
  reworded. (docs/runbooks.md 101–105 is out of date on this; not edited.)
- "Restore = the same API in reverse …" → runbooks: "(not run here)" → "The planned restore (not yet rehearsed): …".
- "Switch [to PostgreSQL] … i.e. before gate 3" and §14 "must give way … before gate 3" → DESIGN §7: a turning point for
  the owner, not a default → "Gate 3 would cross the first threshold; the switch is the owner's decision".
- "corresponding authors (0 marked by the model, though printed in 10 of 600)" → 0 is gate 1's 126 (exp 52); the 10 are in
  the 600, read before the prompt asked (exp 51) → reworded.
- "persons whose byline has no ink anchor (95)" → exp 49 README counts 95 bylines → "the 95 bylines with no ink anchor".
- Rules table "R7 …; R8 … | 1 | 1" → R8 has only "caught 1 in the pass" → R8 on its own row.

Unverifiable: that the S3 key is read-only ("S3 read key") is not documented; left as written (it is how the docs name it).
Flagged for the owner, not changed (true, but disclosures he may want to weigh): development shares the server with
AI-Search production; the admin token was once shown in a chat and is not yet reissued; no backup of inkdesk yet.
- "nothing is … in git" (§2 principles, §12.2) → a real five-page Mandumah document is committed as the test fixture tests/fixtures/0582-004-009-012 (CLAUDE.md; git ls-files) → **fixed**: exception named. The business doc says only "never … on a public code repository": the repository is on GitHub and its visibility could not be checked → **unverifiable**, flagged for the owner.

### 6 Data model, 7 Linking, 8 Desk, 9 Quality, Appendix C (~160 claims; checkB.md)
Verified (selection), with the release `R20261023T005909.db` opened read-only: 93 table entries − 4 FTS5 shadow tables =
**89** (incl. search_fts and reconciliation_v46), **17 views**, **172** declared foreign keys (distinct key ids); Desk
**14** tables; all 89 row counts in `technical/table_counts.json` equal a fresh count(*) (runs 10, model_calls 5,169,
id_registry 11,831, merged_ids 16 … catalogue_reports 509); Appendix C groups sum to 89; citation_links 783 / 55 / 62;
work_relations 398; 126 twin bylines; 8,622 editions of 8,268 works (257 with several); 406 of 701 institutions without
country; Figure 4's anchor exists and reads «28. السابق نفسه.»; id scheme, 21-card gap (fix not applied live); shown-version
rule; precedence; load/link memory; Datasette 28 canned queries; probe results (50/50, 39/40, 100/113, 50/51, 35/50,
26/30, 18/20, 0/40, 56%, 39/50, 35/40, ~2.9%, 86%); 481 of 650; tasks 64 / 287 / 19 (letter-fix release after gate 1);
lease 15 min / 409; detector and release timings; R20261023T005909 15 of 24 applied, 0 orphaned, 0 conflicts; 66 vs 216
checks; cookie + X-Desk-Client; 47 passed in 307 s; walk-through PASS; 144 / 46 fields; Explorer 335 columns, 5–7 s /
87 MB; quality table figures; seeds 4346, 5246, 56, 5250; releases screenshot all 0 / 0.
Screens looked at by me (technical/img): article_fields (144 / 46, byline crops in both scripts, two institutions),
releases (cards 9,137 → 9,137, persons 1,948 → 1,947), work_task (P2 walk-through task, note "test; reverted after"),
ink (anchor and crop), schema_detail / schema_a (live platform_v2.db counts: id_registry 11,825, merged_ids 14 — the
live db, not the release; caption says "live row counts", acceptable), explore_refs, project_map, person_record.
No token, key or private hostname visible in any screenshot. (business article_beside shows the author's printed e-mail
on the scanned page: printed public matter, approved real scans; noted, not changed.)

Fixed:
- "12 test files" → tests/ holds 11 test_*.py (+ conftest, p2_walkthrough) → "11 test files".
- "12 refused malicious requests" → README: "12 refused requests" → "12 refused invalid or injected requests".
- "compares every table row by row: identical in 86 tables" → test_ids47.compare() skips event-log and search tables,
  compares ids on live ids; 86 comparisons (exp 47 README) → reworded; quality table likewise.
- "A small form (8 documents)" → 8 + 11 from j0130_final = 19 → fixed.
- "re-verify round 2: 11 of 11 (2026-10-21)" → VERIFY.md: 2026-10-20, "Pass, with minor gaps", before the exam / v3.5b /
  gate 1 loads → fixed.
- Back-reference rule order → link47.py 374–401: year filter first, title words 0.95, author alone 0.9 → reworded.
- Decision trigger "status move (once …)" → schema.sql 142–161: status along allowed moves, superseded_by set once;
  librarian_verdicts has the same guard → fixed.
- "Seven more task kinds are designed (… orphaned decision)" and §14 "seven task kinds" → release.py already raises
  orphaned_decision tasks → "six more"; orphaned-decision tasks noted as raised already.
- "The AI librarian addresses these" → proposals, not applied → "proposes fixes for these (not yet applied)".
- Labels "70 of 335" → field-guide JSON now has 69 failing: persons.times_cited renamed on 2026-10-28 05:29 → kept 70 with
  its date (2026-10-26) and noted 69 after the rename.
- Authors' "Times cited" status: `desk/explore.py` and `web/components/PersonRecord.tsx` were relabelled "Sum of times
  cited" on 2026-10-28 05:29, but the live screens (screenshots of 28 Oct) still show "Times cited" → in **both** documents
  the relabel is now described as done in code, not yet live (business: caption 5, risks, next steps; technical: §11
  caveat 3, §14 row, §15 roadmap).

Left: Figure 13's "persons 1,948 → 1,947" reports the screen faithfully, while count(*) gives 1,949 → 1,948 (the page
appears to count net of a merged person); not changed. "0 / 30 checked on 2026-10-28" (librarian) lives in PostgreSQL,
not opened → matches the business screenshot (Sample checked 0 / 30) → accepted.

## Cross-document agreement
Checked after the fixes: spend ($100.15, since the 18 Oct top-up), gate 1 (126 articles, 2010–2025, $24.24, 32 / 39,
15.8% / 16.9%, 6.8× / 4.0×), gate 2 and 3 costs (with the page basis of $106k now stated in both), the Desk "built for
~300 correctors, none yet", the authors' Times cited (relabelled in code 28 Oct, not yet live) and the 70 labels (dated
26 Oct), librarian (proposals, not applied), ARCI carries references, prices / servers / storage not priced, 1 Dec price
rise. Deliberate difference left: the business document uses only the live figures (3.8 baseline, 32 / 15.8%) with the
matcher's 39 / 16.9% as a note; the technical document gives both pairs and the 3.6 of exp 52 — explained in each.

## Rebuild
Both PDFs rebuilt with their build scripts (Playwright venv `experiments/52_journal_gate1/out/pwvenv`, chromium-1243):
business **12 pages**, technical **31 pages** (contents page numbers regenerated by build.py). Every page of both
rendered with pypdfium2 and looked at: layout clean, no overflow, no blank pages. (`business/out/pages/` still holds
stale page-13…18 PNGs from an earlier build; not deleted.)

## Update after the author-record fix (lead's message, owner-approved, 2026-10-28 ~05:35 server time)
The author record was fixed and re-shot: /persons/A8STQEWEAV now shows **Citing articles 7** (1 without self-citations)
first, then **Sum of times cited 33** (1 without self-citations); header "Citations received: 33 citations to 28 works
(33 mentions), counted per work"; the Explorer's Authors column is "Sum of times cited (per work)". New images:
business/img/web/person.jpg, technical/img/person_record.png (old ones kept as *.before_fix.png). Looked at the new
images: they show exactly this. This supersedes the "relabelled in code, not yet live" wording logged above.
- Business caption 5: now describes both counts (7 citing articles, 6 his own; sum of times cited 33, WoS's term) and
  that both count only the 780 articles read. Risks "Small counts": the relabel item became "an author's record shows both
  distinct citing articles and the sum of times cited per work". Next steps: the relabel item removed (done).
- Technical §11 caveat 3: both counts explained, with the note that the sum was labelled "Times cited" until 2026-10-28
  and relabelled that day (author record and Explorer). Figure 17 caption: both counts, re-shot 2026-10-28. §14 row
  "Author citations": relabelled on 2026-10-28, both counts shown. §15 "This week": relabel item removed. §9 field-guide
  row keeps "70 (2026-10-26), 69 after the relabel".
- Rebuilt: business 12 pages, technical 31 pages. Changed pages looked at (business 7, 11, 12; technical 20, 23–25, 28–29):
  clean.
