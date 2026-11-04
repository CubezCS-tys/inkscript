# Status

*Last updated 2026-11-02. Update this file whenever a headline number or a
"does / does not" changes; keep the date on every number.*

## Two paths: extraction, reconciliation, gate 2 (2026-10-23 to 2026-11-02)

The work runs on two paths ([overview.md](overview.md) "The picture: two paths, and gates"): **extraction** (each
article complete on its own: islands) and **reconciliation** (the same person, institution and cited work across
articles: bridges). The live list of what runs, is done and waits is the Desk's Plan page (`/plan`, data
`experiments/49_correction_desk/desk/plan/plan.json`).

**Live state (2026-11-02 20:30):** release **R20261103T023001** (experiment 70: gate 2's pilot, journal 0165, 363
articles added on top of experiment 68's go-live; every Desk decision replayed: 2,738 applied, 3 orphaned, 1 conflict,
the same as experiment 68's; /audit reads `experiments/70_gate2_pilot/out/audit_live`). The API must be restarted for
gate 1's random pool to leave 0165 out (`index_pages.WHOLE_JOURNALS`).

### Extraction (islands)

| | Result | Source | Date |
|---|---|---|---|
| **Nothing lost: the audit** (exp 61, $0) | every Azure line of the 780 current articles followed through Gemini's answer, the JATS master and the platform: **99.66% of 435,270 lines** in a field or set aside as not article text; 1,460 fell through, mostly the author block and mostly our code (508 returned posts flattened; English twins' affiliations dropped); false alarms 1 of 82 checked on the scans; fix list M1–M7 (code), P1–P4 (prompt); Desk `/audit` | [experiments/61_nothing_lost](../experiments/61_nothing_lost/README.md) | 2026-11-02 |
| **Leak fixes + prompt v3.6** (exp 65's fixes M1–M7 + identifiers by code, D45; $0.80 for the v3.6 check) | On the 780 articles, printed lines only in generic text **1,457 → 805** (accounted 99.665% → **99.815%**; v3.5b 331 → 45), mapping leaks 953 → 292; every block's text byte-identical; bilingual affiliations in JATS 33 → 89; by code: 74 article DOIs, 443 ISSN printings, 192 author e-mails, 7 ORCIDs | [experiments/65_fix_leaks](../experiments/65_fix_leaks/README.md) | 2026-11-02 |
| **The D30 guard** (exp 66, $0) | 24,528 Gemini fixes in the 780; 270 judged on the scans: **≈ 94% right**, ≈ 4.4% bad, ≈ 1.2% printed misprints overwritten. Rule: refuse when Azure ≥ 0.97 on every word, the edit changes Arabic letters and Gemini's word is a known word; the print stays, Gemini's word becomes a `model-suggestion` flag. Precision 69% [50, 83], recall ≈ 16% of all bad fixes, 0.5% of good fixes refused | [experiments/66_d30_guard](../experiments/66_d30_guard/README.md) | 2026-11-02 |
| **v3.6's fix-rule bullet** (exp 69, $3.16 of a $4 cap) | changes nothing measurable: fix overlap between the prompts (Jaccard ≈ 0.55) equals two runs of one prompt (0.54); judged bad fixes made again 25/48 with it and 25/48 without; **dropped**: v3.6 for gate 2 = v3.5b + P1–P3, the guard kept | [experiments/69_fix_rule_check](../experiments/69_fix_rule_check/README.md) | 2026-11-02 |
| **Go-live** (exp 68: exp 65's fixes + the guard, the four runs rebuilt as `*_fix61_d30`; $0) | **Live at 17:16, R20261102T231619** (the plan; exp 68's README, written at 17:10, still says "ready, not live"). The guard refuses **409** fixes, each a flag beside the printed word, none applied; no other text changed; all masters valid. Release: 2,738 decisions applied, 3 orphaned (two English lines now read inside combined lines, and their faculty row; nothing counted lost), 1 conflict (the October demo); audit **1,457 → 808** generic-only lines, **99.814%** accounted; affiliations counted 591 → 556 (35 English lines are now twins of their Arabic line, not counted twice); ids: every id a Desk decision names resolves except the one orphaned row | [experiments/68_go_live](../experiments/68_go_live/README.md), `out/golive_run.log` | 2026-11-02 |
| **Gate 2 pilot: journal 0165 whole** (exp 70; $23.29 of a $55 cap) | 363 articles 2010–2025: **145 scans** (v3.6, Batch, judge, retries; $0.0078 a page) + **218 Word-only** (exp 53's route + its text-only gemini-3.8-flash step, first run at scale: $1.20; 218/218 Word files are the right article); 363/363 valid; ten random pages 9 right / 1 minor / 0 serious, 0 words wrong; audit 99.981% of 0165's lines. **Do education journals cite each other? Yes:** 0130 → 0165 15 references (11 to articles read here, 6 of them from the Word route), 0165 → 0130 16, inside 0165 59; 0130 × 0165 share 17 authors (random same-size sets: 0.0) and 157 cited works (26.3); institutions only at chance. Release R20261103T023001 | [experiments/70_gate2_pilot](../experiments/70_gate2_pilot/README.md) | 2026-11-02 |

### Reconciliation (bridges)

The librarian: an AI curator (Claude as an agent, no API call, in experiments 56 and 62) settles the cards; a blind
second agent re-decides a stratified sample; disagreements are adjudicated; hard checks run by code; **only kinds
measured at ≥ 98% are applied, never "unsure"** (the owner, 2026-11-02: no routine checks for them).

| | Result | Source | Date |
|---|---|---|---|
| **Librarian, institutions** (exp 56, $0) | all 659 affiliations of the 780: 908 decisions; institutions 271 → 234 (proposal), with a country 42% → 95%, 16 bilingual twins joined; ≈ 1,200 tokens in / 330 out a packet | [experiments/56_librarian_institutions](../experiments/56_librarian_institutions/README.md) | 2026-10-23 |
| **Blind verification, institutions** (exp 63, $0) | 230 re-decided blind, 678 read openly, 18 code checks over all 908: **4 errors in 908 (99.6%)**; blind agreement 208/230; no cross-country, shared-name or parent-chain error; every kind ≥ 98% except medium merges (3/4); a model fault (7 two-country statements with one country) | [experiments/63_verify_institutions](../experiments/63_verify_institutions/README.md) | 2026-11-02 |
| **Institutions applied** (exp 64: 1,146 Desk decisions of `agent:librarian`; owner's D37–D39; $0) | Release R20261102T155701 (0 conflicts, 0 orphans): **242 institutions** (machine 271), **93% with a country** (42%), 70 in 2+ articles (54); 4 former posts, 4 "educated at", 21 links marked inferred. Gate 1, institutions in 2+ articles: **25 vs 6.3** (was 26 vs 3.8). Not applied: 10 unsure, 22 types. Unchanged by the go-live | [experiments/64_apply_institutions](../experiments/64_apply_institutions/README.md) | 2026-11-02 |
| **Librarian, cited works** (exp 62, $0) | 143,810 pairs examined, 2,605 decisions; blind rounds 138/156 then 153/160 agree; adjudicated precision same_work 98.5%, edition 100%, links with venue fit 99.1% (other links 76%, no_link 60%: held); recall ≈ 86%; five policy questions → D40–D44 | [experiments/62_librarian_works](../experiments/62_librarian_works/README.md) | 2026-11-02 |
| **Cited works applied** (exp 67: 1,581 Desk decisions of `agent:librarian`; owner's D40–D44; $0) | Release R20261102T174226 (2,741 applied, 0 orphaned, 1 conflict: the P1 demo's same_work): **9,137 → 8,850** cited works, cited by 2+ 209 → 288; gate 1 shared works 84 vs 10.85 → **118 vs 16.7**; held 6.24% → 6.6%. Held as proposals: 217 links not passing K1c, 700 different works, 84 no link, 21 unsure | [experiments/67_apply_works](../experiments/67_apply_works/README.md) | 2026-11-02 |
| **After the go-live** (live release R20261102T231619) | cited works **8,903** (+53 titles fix M7 now parses), cited by 2+ **291**, gate 1 shared works **121 vs 16.7**, held 6.63% (908 references); institutions 242 / 93% with a country / 70 in 2+ unchanged | [experiments/68_go_live](../experiments/68_go_live/README.md) | 2026-11-02 |
| **The production librarian** (exp 71: Flash 3.8, Argon, Sonnet 5.5, Opus 5.5 re-decide 522 verified decisions from the same packets; **$6.47** of a $10 cap: Gemini $3.27, Anthropic $3.19) | answering everything, no model reaches 98% on the 243 judgement items (Opus 95.2%, Flash 93.2%); Claude's "high" is calibrated (Opus 99.0% on 80% of items), Gemini's is not; 8 answer kinds ≈ 100% for every model. **Design: rules → Flash for the 8 strong kinds → Opus where it says high → the Desk: 99.1% precise on all items (98.9% on judgement items), 17% to a person, $2.97 per 1,000 decisions** ($3.37 on judgement items). Projected (estimate): gate 2 $13–16, the education slice $620–1,950, 1M documents $3.8k–21.7k. Caveat: the gold is Claude's own | [experiments/71_librarian_models](../experiments/71_librarian_models/README.md) | 2026-11-02 |
| **The first production librarian pass** (exp 72: journal 0165's new entities; rules → Flash 3.8 strong kinds → Opus 5.5 high → the Desk; **$4.35** of a $10 cap: Gemini $1.69, Anthropic $2.66) | live release **R20261103T063710** (5,040 applied, 0 orphaned, only the known demo conflict; exp 68's 3 orphans re-anchored): **2,302 Desk decisions** of `agent:librarian` (institutions 338, cited works 1,963, 1 person); of 2,619 items rules 28%, Flash 45%, Opus 13%, **to people 297 (11%: 294 tasks)**; hard checks clean, alarm 40/40 (Sonnet on Flash) and 346/350 (Flash on Opus); hand check 142 right / 3 minor / 1 wrong of 146, and two small kinds read in full and **held** (Flash rows-one-body 16/17, card ok 24/26). 0165: institutions 108 → 96 (with a country 59% → 80%), cited works 5,322 → 5,256, cited by 2+ 210 → 258, held 10.6% → 11.8%, shared with 0130 157 → 198 works. The lead's CBDD9P2BCR wrong join and 4 like it split. Candidate finder 103 → 133 of 138 | [experiments/72_librarian_0165](../experiments/72_librarian_0165/README.md) | 2026-11-03 |

### Evaluations, the Desk and the shareholders

| | Result | Source | Date |
|---|---|---|---|
| **AI-Search A/B** (the AI-Search session, offline, 12 articles; small sample) | right passage in the top 5: platform's chunks 62%, ours 72%, **ours with the kind filter 76% (+14 points)** | the Plan page, item `ab-aisearch` | 2026-10-30 |
| **Indra OCR** (exp 58, local CPU, $0) | words wrong on 34 truth pages **10.4% vs Azure 1.80%**; not a replacement; parked; weights licence (modified OpenRAIL-M) needs a legal reading | [experiments/58_indra_ocr](../experiments/58_indra_ocr/README.md) | 2026-10-30 |
| **Reducto** (exp 59, $4.61 list price inside free credits) | words wrong r-1 5.2% (3.5% with an "as printed" prompt) vs Azure 2.3%; retypes letters; two-column Arabic left column first 6/6; ~$191k per 1M documents; free tier: no zero retention, deletion failed. **Not adopted** | [experiments/59_reducto](../experiments/59_reducto/README.md) | 2026-10-30 |
| **Claude Opus 5.5 vs Gemini Argon as reader** (exp 60, **$30.78** of a $40 cap, Anthropic Batch) | proof pages right / minor / serious **15/42/3 vs Argon 42/18/0**; wrong words 21 vs 0 of 1,532; metadata 15 vs 25 of 30; $0.021 a page ($237k per 1M documents). **Keep Argon**; the lesson (refuse a "fix" of a clearly printed word) became the D30 guard | [experiments/60_claude_reader](../experiments/60_claude_reader/README.md) | 2026-10-31 |
| **The Desk** (exp 49) | pages since 2026-10-23: the index pages, Explorer, article beside its scan, Guide (2026-10-23), Librarian (2026-10-23), Project (2026-10-26), Pipeline (2026-10-30), Audit and Plan (2026-11-02); institution and cited-work decision operations (2026-11-02); **93 tests** in the Desk suite (exp 68's run, 2026-11-02; 19 on 2026-10-21, 47 on 2026-10-23) | [experiments/49_correction_desk](../experiments/49_correction_desk/README.md), exp 68 "Answer" | 2026-11-02 |
| **Shareholders** (exp 55 deck; exp 57 documents; $0) | the 12-slide deck at Desk `/pitch` (2026-10-23); the owner presented on **2026-10-28** ("they love the product") and was asked for documentation: business overview 12 A4 pages, technical documentation 31 A4 pages, PDF with real screens, confidential; wait for the owner's read | [experiments/55_shareholder_pitch](../experiments/55_shareholder_pitch/README.md), [experiments/57_shareholder_docs](../experiments/57_shareholder_docs/README.md) | 2026-10-28 |

### Gates

| | Result | Source | Date |
|---|---|---|---|
| **Gate 1** (exp 52) | done 2026-10-22 (numbers in the next section); with the librarian applied and the go-live: institutions in 2+ articles 25 vs 6.3, shared cited works 121 vs 16.7 | above | 2026-11-02 |
| **Gate 2 selection** (exp 54, $0) | finished 2026-10-22 19:07: ten journals (0130, 0165, 0011, 0523, 1001, 0246, 1182, 0097, 0840, 0013), 3,460 articles, **~$456 expected**, worst $633; a cheaper five 1,344 articles ~$152. Approved by the owner on 2026-11-02 with a £500 top-up, in the order fix → re-audit → one journal → nine more | [experiments/54_gate2_selection](../experiments/54_gate2_selection/README.md); the Plan, item `w-gate2` | 2026-11-02 |
| **Gate 2 pilot** (exp 70: مجلة الطفولة والتنمية, 0165, 363 articles = 145 scans + 218 Word files; prompt v3.6 + the D30 guard; hard cap $55) | **done** 2026-11-02 20:33, **$23.29**: live release R20261103T023001; 0130 ↔ 0165 citations 15 + 16, shared authors 17 vs 0.0 and shared cited works 157 vs 26.3 for random same-size sets; the other nine can follow as they are (with the fixes in the README) | [experiments/70_gate2_pilot](../experiments/70_gate2_pilot/README.md) | 2026-11-02 |
| **Gate 2, the other journals** (exp 74; hard cap $400) | **PARKED 2026-11-04** (owner, for another experiment) at **$365.23**: live release **R20261104T151029** (0 orphans); 1001, 0840, 0097, 0246 and 0130's Word years live with their librarian passes, 0013 live with its librarian verified but not applied; 0011 and 0523 read but held (the ten-page look found 3 and 5 wrong words); 1182's scans over the cap. Seven journals: 30 of 42 ordered pairs cite each other, shared authors and cited works 6–20× random, institutions at chance. Resume steps in the README | [experiments/74_gate2_full](../experiments/74_gate2_full/README.md); the Plan, item `gate2-rest` | 2026-11-04 |
| **Gate 3** (162,816 EduSearch articles) | about $43k now, about $86k after 1 December (estimate); the owner decides before 1 December | exp 54; the Plan, item `gate3` | 2026-10-22 |

**Spend (2026-11-02).**
- **Gemini log** (`experiments/43_rehearsal/out/gemini_spend.jsonl`, 4,167 rows, last entry 2026-11-02 19:43,
  still growing while the pilot runs): **$127.08** since the 2026-10-18 top-up. $100.15 up to 2026-10-22; on
  2026-11-02 the v3.6 check $0.80 (exp 65), the fix-rule check $3.16 (exp 69), and gate 2's pilot so far **$22.99**
  (scan reading $19.37, Word step $1.20, judge $2.42 by 19:43; still running). Experiment 71's Gemini $3.27 is in its own log
  (`experiments/71_librarian_models/out/spend71.jsonl`), experiment 72's $1.69 in
  `experiments/72_librarian_0165/out/spend72.jsonl`.
- **Credit:** the owner topped up **£500 on 2026-11-02** (the Plan, item `w-gate2`) on top of about £11 left; roughly
  **£480 left by estimate** after 2026-11-02's ≈ $30 of Gemini (log dollars → pounds + 20% VAT, as reconciled on
  2026-10-21). Check the console: the log is our record, not the bill.
- **Claude API:** **$36.63** (exp 60 $30.78 from `experiments/60_claude_reader/out/calls.jsonl`; exp 71 $3.19; exp 72
  $2.66 in `experiments/72_librarian_0165/out/spend72.jsonl`), out
  of the owner's $250 of Claude credits (`desk/project/project.json` timeline).
- **Reducto:** $4.61 at list price, inside the free credits (exp 59). Indra: local CPU, $0.
- **Caps:** each paid experiment has an owner-approved cap enforced in code before each batch: exp 60 $40, exp 65
  $5, exp 69 $4, exp 70 $55, exp 71 $10, exp 72 $10 (Gemini and Anthropic together). Gemini prices double after 1 December (Argon) and 1 January 2027 (Flash).

**Waits on the owner (2026-11-02, the Plan's "Needs you").** Make the GitHub repo `CubezCS-tys/inkscript` private
(**urgent**: still public, holds one real Mandumah article as a fixture); rotate the Reducto API key and the Desk
admin token (both shown in chat); ask Reducto to delete the 49 pages; read the shareholder documents; decide gate 3
before 1 December; remove the October demo decisions (one blocks a cited-work split); review the 70 flagged Guide
labels; the 21 re-minted cited-work ids; the Word route's small paid test; "unclear" references in a split; the
master tables' shape; commits since 2026-10-21; proposed deletions; older items (Work task wording, the 0732 / 0849
judge calls, which fields each corrector covers, the remote Desk's domain).

## Linking, the Desk, gate 1 and the Word route (2026-10-22)

The work turned from making each article right (islands) to connecting them (bridges), journal by journal, starting
with an Education Citation Index ([overview.md](overview.md), [ideas.md](ideas.md) "The Education Citation Index and
the Word route"). Reference = what an article cites (outgoing); citation = another article citing it (incoming).

| | Result | Source | Date |
|---|---|---|---|
| **Linking probes** (exp 48, the 600; an agent's judgement, no person checked) | ~2.9% of 9,775 references land on a work Mandumah holds (about a third of cited Arabic articles/theses), flat from 50 to 600 articles; about two-thirds are books and turath; ~86% have no record anywhere; back references 43/47 right; cross-article work cards 100/113 (errors from one author-less title rule: «الديوان» = six diwans); byline → person 50/50; 6/40 authority ids hold two people; OpenAlex matches 0/40 Arabic references; projected correction load ~16,800 h at 1M documents | [experiments/48_linking_probe](../experiments/48_linking_probe/README.md) | 2026-10-21 |
| **The Desk P1 + P2** (exp 49, correction backend) | append-only decisions, ownership, three detectors, releases; 19 tests passed then (P1 11; P2 adds 6 API tests and the coordinator's engine test; **93** by 2026-11-02, see above), Playwright walk-through PASS; web (Next.js) 127.0.0.1:8004, API (FastAPI) :8005, PostgreSQL `inkdesk` schema `desk` | [experiments/49_correction_desk](../experiments/49_correction_desk/README.md) | 2026-10-21 |
| **Extraction inventory** (exp 51, $0) | **235 fields** in 12 groups, counted in the 600 masters: 88 captured well, 47 partly, 43 text only, 57 not; 37 group-A gaps to add to the prompt first; 190 of 600 articles hold Azure's Persian ی/ک | [experiments/51_extraction_inventory](../experiments/51_extraction_inventory/README.md), page :8004/inventory/ | 2026-10-22 |
| **Prompt v3.5b** (v3.3 + the 37 fields in a separate "enrich" part, without v3.4's two content lines) | check on 12 articles / 114 pages beside v3.3: lines same type 90–100% per article (1010-006 90.1%, 0787 92.7%, the rest ≥ 97.5%), order 97–100%; gold differences 2382 12 (v3.3 17), 0747 38 (v3.3 44); v3.4's losses did not come back on their pages; **$0.01048 a page against v3.3's $0.00909 (+15%)**; check $1.20 (the v3.5 check before it $1.08). Used for gate 1 | `experiments/43_rehearsal/out/v35b_check/score.md`, `prompt43.py` | 2026-10-22 |
| **Letter fix** (Azure's ی/ک/ھ written as the printed ي/ى/ك/ه, under D30 as a recorded reader fix; $0) | first 300: **1,059 words in 106 articles**; exam: **829 words in 89 articles**; 300/300 + 300/300 valid; 295/300 identical to the controls once the fixes are undone; gate 1: 408 letters in 331 words | [experiments/43_rehearsal](../experiments/43_rehearsal/README.md) "Letter fix"; exp 52 | 2026-10-22 |
| **Gate 1: one journal** (exp 52, مجلة الطفولة العربية 0130, v3.5b + letter fix + judge) | 126 articles / 2,439 pp, 126/126 valid. Journal against same-size random sets of the 600 (mean of 20): authors with 2+ articles **16 vs 0.25**; institutions in 2+ articles **26 vs 3.6**; affiliations at a repeat institution 76% vs 14%; shared cited works **84 vs 11**; largest coupled group 48 vs 9; **39 citations inside the journal** (24 articles → 37 of its articles; 38 of 39 read right); **16.9%** of references held (600: 2.9%). Thin: co-authorship (1 pair), corresponding authors (0). Quality: 10 random pages beside the scan 9 right / 1 minor / 0 serious; judge 289 pages, 30 findings. **$24.24** ($0.192 an article, $0.0099 a page; cap $32) | [experiments/52_journal_gate1](../experiments/52_journal_gate1/README.md), page :8004/gate1/ | 2026-10-22 |
| **The Word route** (exp 53, $0, code only) | 0130's 2009–2016 Word originals: **139/139 masters valid** (JATS DTD); first page = catalogue's 139/139; 98/98 footnotes; 764 tables; 4,613 references; no printed pages past page 1 (estimates, flagged: D36); 17 of 23 Word files with a scan were another article (caught by the first-page test); a text-only Gemini step **$0.010 (Flash) – $0.028 (Argon) an article** vs scan ~$0.12–0.18 | [experiments/53_word_route](../experiments/53_word_route/README.md) | 2026-10-22 |
| **Platform v2 now** | **726 articles** (the 600 + gate 1's 126; 780 documents with experiment 41's 55), loaded into the main `platform_v2.db` (backup `platform_v2.before_journal0130_2026-10-22.db`); Desk release R20261022T231143, 287 "possible same work" tasks open | read-only count of `documents`, 2026-10-22 18:27; the session's notes | 2026-10-22 |
| **Gate 2 selection** (exp 54, $0) | finished 2026-10-22 19:07 (result in the 2026-11-02 section above, "Gates"): ten journals, 3,460 articles, ~$456 expected; page :8004/gate2/ | [experiments/54_gate2_selection](../experiments/54_gate2_selection/README.md) | 2026-10-22 |

**Spend.** The Gemini log (`experiments/43_rehearsal/out/gemini_spend.jsonl`, last entry 2026-10-22 15:55) stands at
**$100.15** since the 2026-10-18 top-up (£101.28 incl. VAT): $73.62 before, then the v3.5 check $1.08, the v3.5b
check $1.20 and gate 1 $24.24. About **£11 is left by estimate**; check the console. Gate 2 needs a top-up. *(Superseded: the owner topped up £500 on 2026-11-02; spend as of 2026-11-02 above.)*

**Ran overnight 2026-10-22/23** (all three finished: the reload gave release R20261022T233109, the fields load R20261023T005909, exp 54 its README; the Plan page): the 600 reloaded
with the letter fix into `platform_v2.db`, then a Desk release; the platform loader taught every v3.5b field
(developed on `dev_fields.db`); the gate 2 selection.

## The exam, the proof pack and the platform (2026-10-21)

**The pipeline** (experiment 43): Azure's words, Gemini 4 (Argon, prompt v3.3, thinking low, Batch) giving each
line its type and order, code rules, a judge that edits only through a logged patch layer, flags for a person.

| | Result | Measured on | Date |
|---|---|---|---|
| **The exam**: a held-out second 300 run with the pipeline frozen beforehand | 300/300 answered (3 of 491 first-round requests failed, all recovered by smaller chunks), 300/300 JATS DTD + ALTO XSD valid; $31.94 all in = **$0.106 an article, $0.0094 a page** (£0.096 / £0.0085 incl. VAT); 2 h 46 min launch → last answer (64 min of it a Windows reboot); judge on 599 pages: 110 findings, 14 applied automatically (two keys), 73 to the owner | 300 unseen articles, 3,404 pages (`experiments/43_rehearsal`, "The exam") | 2026-10-20 |
| **The proof pack** (an independent agent, seeded random draws, no paid calls) | pages beside the scan: right 35, minor 23, **serious 2** of 60; words 0 wrong of 1,532 (upper bound 0.25%); citations fully right 57/80, fields 313/341 right, 0 wrong; back references 15/20 right; metadata all fields right 18/30 | `out/v33_300b_final` (`experiments/43_rehearsal/out/proof/proof.md`; page http://127.0.0.1:8899/proof/proof.html) | 2026-10-20 |
| **Fix round 3** (the proof pack's failures fixed at their root, on a copy) | pages right **35 → 43**, serious **2 → 0** of 60; metadata all right **18 → 25** of 30; citations unchanged 57/80; $1.12 | `out/v33_300b_fix3` (README "Fix round 3"); 0529's flow charts fixed 2026-10-21 (a figure box given as [x0,y0,y1,x1]; only 0529 changed in the exam) | 2026-10-20/21 |
| **Platform v2** (experiment 47: the database of everything we hold, Web-of-Science style) | independent re-verify round 2: **11 of 11 checks pass**; its gaps fixed 2026-10-21 (publishers keyed on name + country, demo ink links that survive rebuilds, 4 back references); two clean builds in three step orders identical in 81 tables; 354 documents, 580 persons, 315 institutions, 3,080 cited works, 92 accepted catalogue links; served at http://127.0.0.1:8003/platform_v2 | `/home/yassine/data/platform_v2/platform_v2.db` (`experiments/47_platform_v2`, README + VERIFY.md) | 2026-10-21 |
| **Gate 1: one journal** (experiment 52; مجلة الطفولة العربية, prompt v3.5b + the letter fix, judge, platform copy `gate1.db`) | 126 articles / 2,439 pp (2010–2025 in the bucket = 2017–19 + 2023–25; the whole 195 priced over the $32 cap), 126/126 valid; **$24.24** ($0.0099 a page); against same-size random sets of the 600: authors with 2+ articles 16 vs 0.25, institutions in 2+ articles 26 vs 3.6, shared cited works 84 vs 11, largest coupled group 48 vs 9; **39 references inside the journal** (24 articles → 37 of its articles); **16.9%** of references land on a held work (600: 2.9%); thin: co-authorship (1 repeat pair), corresponding authors (0); 10 random pages beside the scan 9 right / 1 minor / 0 serious | `experiments/52_journal_gate1`, http://127.0.0.1:8004/gate1/ | 2026-10-22 |
| Platform v1 (experiment 46) | the first 300 (final), the 55 and the exam (run, final, fix 3) loaded with flags, patches and judge findings | `/home/yassine/data/platform/platform.db`, http://127.0.0.1:8002/platform | 2026-10-20 |

**Spend.** The Gemini log (`experiments/43_rehearsal/out/gemini_spend.jsonl`) stands at **$73.62** since the
owner's top-up of 2026-10-18 (£101.28 incl. VAT; about £35 left). The next step, about 3,000
articles at the exam's rate, would cost about **$320** and needs a top-up.

**Waits for the owner** (2026-10-21): the ~3,000-article step and its top-up; two judge calls (0732's bottom strip
unmarked as "another article" on pp3/6 only; 0849 p4's second show-through line, which the code key did not pass);
the v3.5 prompt test (v3.3 + v3.4's two content lines, without "compact JSON"); citation linking as the next big
focus; proposed deletions ([handoff.md](handoff.md) section 8). Development moves to the
owner's server next: [moving-to-a-server.md](moving-to-a-server.md), `ops/pack_v2.sh`.

## Stroke study (2026-10-18)

[Experiment 42](../experiments/42_stroke_recovery/README.md) reopens the
back-writing question with a local inspection/recording instrument. Calliar's
2,500 source drawings yield 7,507 validated words; 30 drawings rejected for
annotation mismatch. These are human retracings in prescribed character
order, not the original calligraphers' motion; word segmentation is supplied
by the annotations. The component-wise experiment-16 traversal covers 98.1%
of the controlled raster's ink within 1 px on average. No archive performance
is implied.

A fixed nearest-training-example control (2,000 train / 500 test words):
reference traces 31.8% exact, recovered paths 24.0%, rendered images 21.6%.
All are closed vocabulary; 170 unseen-text test words get 0% exact in all
arms. The initial 12-epoch CTC readers were undertrained (88.7-100% CER), so
they cannot rank representations. The completed 72-epoch extension gets
39.2% exact from reference traces, 12.2% from recovered paths, 1.8% from the
weak image baseline (CER 25.5% / 61.8% / 78.7%); reference gets 27/170
unseen-text words right. These repeated test results are exploratory, and
prescribed annotation order favours the reference representation.

Viewer and pointer recorder: `http://127.0.0.1:8842`. Raw event time, pressure
and tilt are retained when supplied, with pen/mouse/touch provenance. Captures
remain unassigned to train/test. No production pipeline change; zero paid
model calls and zero GPU rental. Work for the returning Claude session:
[codex-handoff.md](codex-handoff.md).

## What the PDFs do

| | Result | Measured on | Date |
|---|---|---|---|
| Words copy out intact in Chrome's engine | 99.99% (893,113 / 893,203) | 227 journals, 4,440 pages | 2026-09-20 |
| Lines come out in reading order | 99.95% (82,574 / 82,613) | same | 2026-09-20 |
| Words in which **every letter has its own selection box** | **97.8%** (711,485 / 727,514); typical document 98.4%, weakest tenth under 94.7% | the 193 scanned documents of the 227-journal set, rebuilt with the post-run fixes (3,465 pages) | 2026-09-22 |
| Lines in order, against other tools | ours 98–100%, Azure's own PDF 34–75%, ocrmypdf 2–16% | 3 documents (`experiments/07_engine_comparison`) | 2026-09-18 |
| Against the Azure PDFs being uploaded now | words 100.0% vs 97.9%, lines in order 100.0% vs 79.3%, letter boxes 5.88 vs 1.00 (Azure slices words evenly) | 10 random documents of the 21–22 Sep upload, 106 pages, 42,843 words (`experiments/14_vs_azure`) | 2026-09-22 |
| Test set of 30 documents | 34,959 / 34,959 words, 3,868 / 3,868 lines | `~/Desktop/native_pdfs` (built before the pen path; not rebuilt) | 2026-09-19 |
| 451-document sample | 99.98% words, ~99.9% lines (words only; no letters) | `docs/night-report-2026-09-18.md` | 2026-09-18 |
| Born-digital pages | detected and left alone (their junk-encoded fonts neutralised) | | 2026-09-18 |
| Reference document (the test fixture) | 1,246 / 1,246 words, 113 / 113 lines, 96.2% letter coverage, ~28 s, peak 0.85 GB | `tests/fixtures/0582-004-009-012` | 2026-09-20 |

An 81-page document builds in about 10 minutes at a peak of 1.6 GB.

| Letter highlight on the right letter (blind Gemini judge, strict) | 76.7% of letters on unseen pages after the alef fix (was 70.2%; Chrome's equal slicing 53.9%); fixture 62.2% (was 56.2%, equal slicing 58.2%) | 230 words, 981 letters (`experiments/18_boxes`, `21_better_boxes`) | 2026-10-06 |
| Azure's reading, judged on the ink | 1.55% of words wrong on scans [0.62–2.79], printed Arabic misread 0.61%; pre-2000 2.8%, after 0.65%; 42% of documents born-digital | 240 random documents, 2,971 words (`experiments/19_azure_map`) | 2026-10-06 |
| Reading from the pen path alone (the feeler) | 82.6% of unseen pieces read as Azure reads them (bigger reader, 97 books) | 4 books, held-out pages (`experiments/16_feel`) | 2026-10-06 |
| Document files beside the PDF (`--xml`): JATS 1.4 article + ALTO 4.4 page file | valid against the official schemas 20/20 + 20/20; title found 20/20 (was 14), author 16/20 (was 8), printed page range 18/20 | 20 scanned documents, 321 pages, 1960–2018 (`experiments/24_product`, `26_structure`) | 2026-10-06 |
| Article structure in the JATS, against a hand-read truth (precision / recall) | 10 documents (rules tuned on them): title 1.00/1.00 (was 0.88/0.70), authors 1.00/1.00 (0.80/0.44), headings 0.96/1.00 (0.00/0.00), footnote links 1.00/0.97 (0.67/0.13), endnote links 1.00/1.00 (–/0.00); running heads or page numbers left in the text 0 (was 15). 4 held-out documents, first pass: title 3/4, authors 2/3, headings 0.83/0.71, footnote links 1.00/0.94 | `experiments/26_structure` (`out/report.html`) | 2026-10-06 |
| Uncertain words marked (`--xml`/`--trust`, experiment 22's rule) | 7.9% of words flagged (pre-2000 prints 11.4%, from 2000 on 4.8%); on 22's judged sample the rule leaves 0.43% of unflagged words wrong | same set | 2026-10-06 |
| Uncertain words marked, with experiment 27's common-word refinement (now the rule) | **5.3%** of words flagged on the same set (was 7.9%); on 19's judged words 7.5% → 5.0% flagged, errors caught 50 → 50 of 61, 1 flag in 7.4 a real error (was 8.9), 0.42% of unflagged words wrong | same set; `experiments/27_corrections` | 2026-10-06 |
| Corrections from Quran verses (`inkscript fix`), judged on the ink by two blind judges | 194 proposed, 156 accepted, **147 written** into both PDFs' text, the ALTO, JATS and trust PDFs; the drawing pixel-identical; quotations equal to the verse 235 → 290 of 387; $0.80 for the set | same set (`experiments/27_corrections`) | 2026-10-06 |
| Quran quotations found and checked | 387, all linked to sura:verse; 235 equal to the verse, 152 differ (their words flagged) | same set | 2026-10-06 |
| `_trust.pdf` (hideable highlights, incremental update) | the original bytes first and the same text and character boxes in pdfium, 20/20; fixture 1,246/1,246 words, 113/113 lines on both copies | same set; `tests/test_enrich.py` | 2026-10-06 |
| **The whole product at scale** (`--vector --verify --xml --trust`, then `fix --apply`) | 205/205 built, 0 crashes, 0 timeouts; words intact 99.98% (868,741 / 868,897), lines in order 99.94%, letters selectable **97.75%** (median document 98.6%), flagged 4.89%, trust PDFs right 205/205, ALTO valid 205/205, JATS 204/205; title matching the MARC catalogue 148/204 (69/75 with a Gemini title file, 79/129 from the layout), catalogue authors found 107/214; 242 Quran quotations, 31 corrections proposed, 18 written, $0.125; 18.6 s a page (median document), peak 2.19 GB, 7 h 40 min on 3 workers | 205 scanned documents, 3,254 pages, 1932–2025, 172 journals, none of them tuning any rule (`experiments/28_scale`, `out/showcase.html`) | 2026-10-07 |
| Looking at the outputs (`inkscript view`, experiment 31) | the article's words linked to their box on the scan **99.85%** (900,130 / 901,457), non-furniture blocks placed in the article 46,525 / 46,525; a 48-page document opens in 0.9 s, a jump to page 40 in 0.2 s (Chromium, local server) | experiment 28's 205 documents | 2026-10-07 |
| Page furniture told from content (experiment 30) | blocks set aside on the 205 documents 9,815 → 6,742, "lone" ones with letters 470 → 267; on 140 old furniture blocks read by eye content kept 56/60 (93%, 84–97%), furniture still set aside 71/78 (91%, 83–96%); held out (60 blocks drawn afterwards) released blocks that are content 33/38 (87%, 73–94%); experiment 26's truth unchanged (0 furniture leaks) | experiment 28's 205 documents (`experiments/30_furniture_flags`) | 2026-10-07 |
| Block and page marks instead of flag floods (experiment 30: vowelled, handwritten, decorative) | flagged on documents over 50% vowelled 60.3% → 12.3%, handwritten pages 76.6% → 10.6%, all words 4.9% → 4.6% (under 5% vowelled unchanged); on 19's judged words flagged 5.0% → 4.3%, errors flagged word by word 50 → 45 of 61, flagged or inside a marked block 50 → 50; unflagged words outside marked blocks still 0.42% wrong | same 205 documents; 2,935 judged words (nothing paid) | 2026-10-07 |
| **JATS front matter from Mandumah's MARC catalogue, tied to the ink** (`--xml`, default when the index exists) | record for 204/205 documents; title 194 → **205** (on its printed words 194 → 202; the page alone matched the catalogue in 171/204), authors 147 → **205** (195 of 214 catalogue names found on the page; the page alone found 132), journal title 101 → 205, ISSN 0 → 89, year 66 → 205 (Hijri 10 → 76), pages 165 → 205, abstract 0 → 34, keywords 0 → 204, DOI 0 → 15, affiliations 26 → 50; honorifics as `<prefix>` (97); JATS 1.4 / ALTO 4.4 valid 205/205; no wrong record found, and of 204 neighbours' records given on purpose 0 were accepted; index 1.1 GB, 29 ms to open, 1.1 ms a lookup | the 205 documents of experiment 28 (`experiments/29_catalogue`) | 2026-10-07 |
| **The yardstick (gold set) for every reader** (experiment 34, D26) | 202 pages drafted and ready to correct: 185 documents, 159 journals, 1929–2025, 44 pages before 1970; tables 29, equations 14, Quran 22, vowelled 21, footnotes 43, mixed Latin 39, magazines 50; held out by journal 151 test / 51 dev; Gemini disagrees with Azure on 26% of 8,493 lines; correcting estimated at **13.6 h** (7.8–25); `inkscript view --gold`, `inkscript score`; nothing is gold until the owner corrects | `experiments/34_yardstick` (`out/report.html`), $12.40 | 2026-10-11 |
| **Derived editions from the master files** (`inkscript edition`, experiment 35): reading HTML, EPUB 3, layout-faithful PDF, one-column PDF, Markdown, dataset record | 205/205 built, 0 failures, 18 min on 2 workers, 0.63 GB a worker; printed words found, read back from the files: HTML/EPUB/Markdown/JSONL 99.99%, layout PDF 99.97% (every ALTO word, furniture too), one-column PDF 99.94% (digits aside: it renumbers notes); words in reading order in pdfium: layout 96.1%, one-column 93.6% (median document 99.3% / 99.0%; the rest mostly Latin lines in Arabic documents, D18); EPUB epubcheck-clean 21/21; Gemini judge on 36 pages, scan beside rebuild: same blocks 33 + 3 mostly, same order 36/36, overall 4/5 on 33 (planted faults: dropped paragraph 3/3, swapped 3/3, demoted heading 0/2); $0.39 | experiment 29's 205 masters, 3,254 pages (`experiments/35_edition`, `out/report.html`) | 2026-10-11 |
| **An open line reader of our own** (Kraken 7.1, fine-tuned; experiment 33) | born-digital lines: characters wrong 3.6% out of the box → **1.5%** (Kraken) / **1.3%** (PP-OCRv6), Azure 1.0%; scan-like copies 9.0% → 2.1% / 1.4%. Real scans, experiment 19's judged words wrong: 24.5% → **15.2%** / 15.5%, Azure 2.0% (body text 5.4% → 4.3%, Azure 1.1%); whole scanned pages against Azure's lines 13.4% → 8.2%, and **6.5%** with its line finder fine-tuned too (finds 95% of Azure's lines, was 93%; lines run together 2.4% → 0.6%). Owner's 2 gold pages (47 lines): Azure 0.8%, fine-tuned Kraken 2.7–2.8%. PaddleOCR-VL-0.9B (smoke test) reads lines about as well but invents and skips on pages | 4,089 born-digital test lines of 30 documents / 25 journals no training line came from; 2,894 judged words of 139 scanned documents; 139 scanned pages (`experiments/33_kraken`, `out/report.html`) | 2026-10-12 |
| **Our own parser on the hardest pages** (experiment 38, D29): Azure's words poured into dots.mocr's layout, tables, formulas and pictures, then JATS + ALTO and every edition | blind Gemini judge, scan beside old and new layout page: new preferred on **18 of 33** hard pages (55%, 38–70%), old 4, tie 11 (closeness 3.79 vs 3.36); a reviewer by eye on 44 pages: new 28, same 13, old 3; every Azure word placed once (13,481), none lost against Azure; gold word error order-free Azure 5.4%, new 5.5%; 15 pictures placed, 19 formulas checked on the crop and typeset (judged 3.89 vs dots' 3.47), 15 tables ruled but Azure's words in dots' grid judged 2.8 vs 3.4 for dots' own cells; **model correction off**: on gold 30 right, 34 wrong (word errors 85 → 89); JATS/ALTO valid 44/44; $3.08 | 35 hardest yardstick pages + 9 done gold pages (`experiments/38_parser`, `out/report.html`) | 2026-10-12 |
| Selection in current Chrome (Chromium 153, real browser, scripted drag) | letter by letter in reading order, lines copy out exactly, once the PDF is marked right-to-left; unmarked it jumped word to word | `0618-021-002-004` p3 | 2026-10-05 |

## What they do not do (known gaps)

- **Found at scale (experiment 28, 2026-10-07; patches proposed in `experiments/28_scale/patches/`, not applied):**
  on scans that carry a typeset header or caption, the source font's text stays beside ours (23 of 205
  documents; copied twice, often garbled; 70% of the set's order inversions); without a Gemini title file the
  title is right in 79 of 129 documents (since experiment 29 the catalogue gives it for 204 of 205); about 270 blocks of content (headings opening a page, captions,
  footnotes, table cells) are set aside as page furniture and missing from the JATS text; vowelled text, verse
  and handwriting flood the trust copy (over 50% vowelled: 60% of words flagged); `save(garbage=3)` is 65% of
  the slowest build; one JATS file had an empty `<fn-group>`. *(2026-10-07, experiment 30: furniture and the
  flag floods fixed — see the table above; still set aside wrongly: a logo's lettering read as a table, a table
  starting at the very top of a page, a calligraphic running head read differently on each page.)*

- **Latin-majority lines copy out with their words swapped** in current
  Chrome, the price of marking the document right-to-left (D18). Chromium also
  highlights the whole last line of a multi-line drag.

- **The text is Azure's reading** — since 2026-10-06 with every uncertain word
  marked (`--xml`/`--trust`; 5.3% of words on the product set since experiment
  27), and only words of Quran quotations corrected (`inkscript fix`: 147 on 20
  documents, each judged on the ink); everything else stays as Azure read it,
  and confident misreadings (an added hamza at 0.99) stay unmarked.
  "Words intact" means we preserved it, not
  that it is right. Page 1 is Gemini's. Making the text trustworthy is
  milestone 1 in [roadmap.md](roadmap.md). *First measurements, 2026-09-21
  (`experiments/12_gold`):* three sheets hand-marked word by word — `0005` p2
  (Azure, heavy clean face) **277 of 277 right**; `1110` p1, the set's weakest
  document, scored twice on the same ink: **Gemini 146 of 150** (the reading
  the PDF carries) against **Azure 149 of 150** (the reading Gemini replaces).
  D1 was kept unchanged all the same — [decisions.md](decisions.md), D16.
  Across the sheets 572 of 577 words are right, so the baseline any checker
  must beat — *change nothing* — is **99.1%**, and three of the five doubtful
  words were marked unsure from the ink itself, which no checker can settle
  either. Azure on the body text of a difficult face is still unmeasured.
- **Letter boxes: first measurement 2026-10-06 (experiment 18).** A blind Gemini judge (strict: accepts 49/60 boxes right by construction, 0/60 moved a letter) puts the cutter's highlight on the right letter for 70.2% of letters on unseen pages against 53.9% for Chrome's equal slicing, but not on the fixture (56.2% vs 58.2%); corrected for the judge's strictness about 83–86%. Weak spot: a joined final alef gets a sliver of a box (5/56 right). *Earlier:* **Letter boxes exist; their placement is not measured.** By eye about 85–90%
  of cuts sit right on the reference document; doubted cuts (about a third of
  them wrong) are still cut, because an uncut piece is no better. A
  hand-checked sample is milestone 2.
- Words carrying vowel marks are never cut into letters (pdfium reorders
  split vowelled words).
- Underlined words cut badly (the underline is glued to the ink).
- Fine slanted faces with overhanging kaf are weaker (`0690-012-001,012-028`).
- Tables: cells pdfium joins across rows. Firefox copies lines word-reversed
  at our 8 pt nominal size (`experiments/06`).
- `inkscript correct` cannot write a correction shorter than the word's glyph
  count in place (an empty ToUnicode reads back as the char code).
- *(Closed 2026-09-22.)* The fixes made after the first 227-journal run — the
  swapped `في`, alef splitting in a light face, hamza of a joined `أ`, dots
  under a swept-back tail — are now in `journals227_v3`. Letter coverage
  96.8% → **97.8%**; 29.4% of characters got a different box and 188 of 227
  documents moved by more than 5%, the biggest gainers being the faces the
  fixes were for (`0350` 91.4 → 96.1%, `0920` 87.5 → 94.6%, `1260` 92.7 → 98.1%).
  73 documents' page text string changed, all of it **where pdfium puts a line
  break** — a word that used to be split across one is now whole; words intact
  was identical old and new in every document sampled.

## In flight / where outputs are (this machine)

- **2026-11-02 evening:** gate 2's pilot (experiment 70, journal 0165) finished at 20:33 (release R20261103T023001;
  `experiments/70_gate2_pilot/README.md`); everything else listed below as running has finished. The live list is the Desk's `/plan`.

- **Correction tool v1 (2026-10-20)** for the owner on the Layout view of the 300:
  http://127.0.0.1:8899/correct/edit/index.html (kinds, noise, split / merge / order, note links, picture boxes, word
  fixes as misread or misprint); corrections → person patches → `correct43.py import` rebuilds the masters; tested end
  to end on 3 articles, 10 corrections, all as intended, valid, reversible
  ([experiments/43_rehearsal](../experiments/43_rehearsal/README.md) "Correction tool v1").

- **Second branch, the open reading stack (started 2026-10-11)**, beside the ink-as-text
  work, which stays alive ([vision.md](vision.md), [roadmap.md](roadmap.md)). Research and plan:
  [experiments/32_open_stack](../experiments/32_open_stack/README.md) (plan page:
  https://claude.ai/artifact/4sMPMdfjjnrkttPTHsE1kM). Running, each on its own worktree branch,
  outputs in the main checkout's `experiments/3x_*/out/`:
  - 33: Kraken on Mandumah lines, then fine-tuned on born-digital lines. First numbers
    (2026-10-11, out of the box): Arabic character errors on clean born-digital lines are
    Kraken 4.1%, Azure 1.75%; 9.6% on the same lines degraded; about 7% on real scans
    (against Azure's readings, so silver truth).
  - 34: the yardstick, merged; the owner is correcting (`inkscript view --gold`).
  - 36: the VLM bake-off (2026-10-12, D28; owner's page
    `/home/yassine/inkscript/experiments/36_vlm_bakeoff/out/report.html`). **dots.mocr** is the main open reader: characters
    wrong on the owner's 6 done gold pages 3.0% [1.7–4.6] (Azure 0.9%, flattered), born-digital pages
    5.5% [3.0–9.2] (Azure 3.1%), 13.7% different from Azure on all 202 yardstick pages; invented
    0.9 words per 1,000 outside tables, dropped 15.2, no runaway or given-up page; two columns in
    order 86.5%; vowel marks kept 60% (Azure 89%); tables judged 3.44/5, equations 2.42/5;
    2,807 pages/h, $0.17 per 1,000 pages on one RTX 5090. amad-vlm6 reads plain text best (1.5% /
    3.6%) but gives no layout; PaddleOCR-VL reads two-column Arabic left column first and invents;
    Qwen3-VL gives up on 23% of pages or loops. Kraken as checker flags 92–100% of the VLMs'
    inventions (precision 9–13% on good readers). dots' licence agreement (no "unauthorized
    digitization of publications", limits on training from its outputs) is for the owner to clear.
    Spent $1.62 (GPU $1.06, Gemini judge $0.56).
  - 35: the native edition, merged (below).
  - 38: the parser (Azure's words in dots.mocr's layout) on the hardest pages, done 2026-10-12 (D29); owner's page
    `/home/yassine/inkscript/experiments/38_parser/out/report.html`, per-page masters and editions in
    `experiments/38_parser/out/pages/<pid>/`. Nothing is running.
  - 39: the layout model (DocLayout-YOLO on Gemini Flash line labels), round 2 done 2026-10-14: 87.8% of the 44
    test pages' lines named like the Pro referee (round 1 87.7%, dots.mocr 84.4%); equations 0% → 78%, lists 54% → 68%,
    but footnotes 95% → 67% and verse 96% → 61% (the new pages were 63% table lines); with dots for tables and
    equations 90.5% (round 1 92.1%). Not good enough to replace round 1. Owner's page
    `/home/yassine/inkscript/experiments/39_ink_geometry/out/layout_model.html`. Nothing is running.
  - 40: Gemini 4 (gemini-4-argon) alone as the reader, done 2026-10-14, $13.34
    ([README](../experiments/40_gemini4_vlm/README.md), https://claude.ai/artifact/54SBuWQZQQosVQqyqEpE31): block
    types right 96.8% (Azure 74%, our layout model 84%); text about Azure's level but not faithful (fixes misprints,
    adds hamzas). Led to D30: the print as printed, misprints flagged (`span.sic`).
  - 41: Azure's words with Gemini's structure as line ids, 55 articles / 399 pages, done 2026-10-15, $10.72
    ([README](../experiments/41_azure_structure/README.md), https://claude.ai/artifact/AiqhFTZTvMF2or8W9Bi4mp): no
    chunk failed; words wrong on 34 truth pages Argon 1.55%, Flash 1.77%, Azure 1.80%; Argon for the edition, Flash
    for training labels. Reader and views of the 55 articles in `out/reader/`, `out/views/`. Owner's hand check
    2026-10-16: 0747 183/183 blocks right; the other four checked by eye, no faults. Gemini credit ran out 2026-10-15.
- **Experiment 43, code fixes before the 300-article rehearsal (2026-10-18, no calls)**: D33 metadata
  corrected with the printed form kept and logged (0355's cut title and author, 0422's title misprint), Layout-view
  overlaps over the 55 11 → 3, pictures inside a printed line as JATS `inline-graphic` (1769), 4 new flags, MathML
  names; prompt v3.2 candidate with parsed references (masters ready, not live; ~$1.7 more on the 300). 55/55 valid,
  gold 5/5 ([experiments/43_rehearsal](../experiments/43_rehearsal/README.md), section "Code fixes before the 300").
- **Experiment 43, the judge (2026-10-20, $2.10)**: a model looks at the scan beside our page and edits only through
  a patch layer (line ids, logged, reversible) when two keys agree (its confidence + a code check of the scan).
  Calibration on 30 pages with 11 known structural problems: Flash 4 caught (v1) / 7 (checklist prompt v2), Argon 9;
  Flash v2 on the 300's 498 flagged pages + 50 random ($0.0024 a page on Batch): 25 pages edited automatically
  (show-through, picture boxes, bylines, running heads), 23 to a one-page retry, 75 to the owner; two one-page
  Argon retries fixed a table split across columns and a page drawn as one picture. Masters in
  `out/v33_300_judged/` only; page http://127.0.0.1:8899/judge/judge_review.html
  ([experiments/43_rehearsal](../experiments/43_rehearsal/README.md), section "The judge").
- **Experiment 43, fixes from the 300 (2026-10-20, no calls)**: show-through kept out by ink strength (112 lines,
  0744's ~40 a page), whole-page "frame" pictures no longer swallow text (5 pages), a table over two columns drawn
  per part, «» from (( )) where the ink shows guillemets (101 chunks, unsure ones flagged), Latin line-end hyphens
  joined, free verse row by row, an advert as one picture, page ranges spanning the scan 161 → 294 of 299 (folios /
  catalogue, D33 log), section labels no longer titles; lost letters in vocalised verse flagged (114 pages, fix route
  a close-up retry); prompt v3.4 candidate (not live); 1764's MAX_TOKENS chunk can be re-asked in smaller chunks
  (`rechunk43.py`, one call). The 300 re-flagged: high 0.48 → 0.26 per 100 pages. 299/299 + 55/55 valid, gold 5/5
  ([experiments/43_rehearsal](../experiments/43_rehearsal/README.md), section "Fixes from the 300").
- **Experiment 43, fix round 3 on the exam (2026-10-20, $1.12)**: the proof pack's failures fixed on a copy
  (`out/v33_300b_fix3/`): table cells Azure never read now in their cells (46 left outside tables, unflagged → 44
  placed, 12 flagged high on 10 pages), honorifics out of 92 author names and 27 translators / supervisors /
  rapporteurs / reviewers no longer authors, 12 Hijri years marked with the Gregorian beside, 170 stray ")" before »
  → 0, letter / superscript note calls linked (2,823 → 2,847), 0529's glyphless renders redrawn with its fonts and
  re-asked. Proof sample: pages right 35 → 43, serious 2 → 0 of 60; metadata all right 18 → 25 of 30; citations
  unchanged 57/80. 300/300 valid, gold 4 same + 0747 better; http://127.0.0.1:8899/v33_300b_fix3/index.html
  ([experiments/43_rehearsal](../experiments/43_rehearsal/README.md), section "Fix round 3 (proof pack)").
- **The editions (2026-10-11, experiment 35)**: every derived edition of the 205 documents in
  `experiments/35_edition/out/editions/<id>/` (513 MB), the hand-made table/maths tests in
  `out/testmasters/`, the owner's page `experiments/35_edition/out/report.html`. Nothing is running.

- **The scale run (2026-10-07)**: 205 documents built with everything on and fixed in
  `experiments/28_scale/out/set/w0..w2/`; numbers in `summary.json`, the owner's page
  `experiments/28_scale/out/showcase.html`. Nothing is running.

- **The product set (2026-10-06)**: 20 documents built with `--vector --verify
  --xml --trust` in `experiments/24_product/out/set/w0..w2/`; numbers in
  `summary.json`, the owner's page `experiments/24_product/out/showcase.html`.

- *(Finished 2026-09-22: see "Closed 2026-09-22" above.)* **The rerun of the 227 journals** (started 2026-09-21,
  roadmap item 5): 3 workers into
  `experiments/09_pen_path/out/journals227_v3/`, watchdog up, `src/` must not
  be edited until it ends. It resumes by rerunning the same command
  (`experiments/09_pen_path/run_set.sh <azure> <frontpage> - <out> 3`, see
  [operations.md](operations.md)); when `summary.txt` ends `SET DONE`, compare
  the builds with `compare_boxes.py journals227 journals227_v3`.
- 227-journal run with letters (the "before" side of that comparison):
  `experiments/09_pen_path/out/journals227/` (`summary.txt`,
  `w0*/…_vector.pdf`, `w00/letter_coverage.json`); the first, pre-fix run is
  `journals227_first/`.
- Fonts built from two books are installed for the owner in
  `~/.local/share/fonts/` (Inkscript 0582 / 0565 Restored); sources in
  `experiments/11_typeface/out/`.
- Older deliverables: `~/Desktop/native_pdfs/` (30 documents),
  `~/Desktop/s3_native/` (47 documents) — built before pen-path letters.
- Storyboard artifact (version 4, published 2026-09-20; private to the owner until shared):
  https://claude.ai/artifact/MjTHoKev4bJLX6vHo4jdk3 — source `docs/storyboard/`, rebuilt by
  `docs/storyboard/rebuild.sh`, republished by passing that URL.
