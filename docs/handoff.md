# Handoff: where we are (as of 2026-11-02)

**Continuation, 2026-10-17:** Codex is working with the owner while Claude is
unavailable. Read [codex-handoff.md](codex-handoff.md) for the review, reopened
tracing discussion, current scope and subsequent work before resuming.

I am the Claude session that worked with the owner on the laptop up to 2026-10-13 (section 0 brought up to
2026-10-15, section 00 to 2026-10-21, section 000a to 2026-10-22, section 000 to 2026-11-02). I'm writing this for the next
session, on the owner's Ubuntu ssh server, which will have none of my memory. My private notes (the "memory" files) don't
travel with git, so everything in them that matters is written out here. Read this first, then `CLAUDE.md` and the
docs it lists. Where this file and an older doc disagree, this file is newer.

## 000. 2026-10-23 to 2026-11-02 (read first)

The plain overview is [overview.md](overview.md) ("two paths, and gates"); the numbers with dates are in
[STATUS.md](STATUS.md) "Two paths: extraction, reconciliation, gate 2". **The live record of what is running, done
and waiting is the Desk's Plan page** (`/plan`; data `experiments/49_correction_desk/desk/plan/plan.json`, written
only with `desk.plan_cli`, which every agent uses to start / beat / finish its item). The Project page (`/project`,
`desk/project/project.json`) is the owner's dashboard; its `as_of` is still 2026-10-26, so prefer the Plan where they
differ. This section is what a fresh session needs on top.

**The owner's model: two paths.**
- **Extraction (islands):** Azure's words + Gemini 4 Argon's structure in line ids (prompt **v3.6** for gate 2 =
  v3.5b + P1–P3; the fix-rule bullet dropped by experiment 69), code rules (the letter fix, the **D30 guard**,
  identifiers by code, D45), JATS + ALTO masters. Audit: **99.81% of 435,270 lines in a field** (live 2026-11-02).
- **Reconciliation (bridges):** the librarian (an AI curator) decides institutions and cited works; a blind second
  agent checks; only kinds at ≥ 98% are applied, never "unsure"; the owner's rules D37–D44 settle policy. Institutions
  271 → **242** (93% with a country); cited works 9,137 → 8,850 → **8,903** after the go-live. The production
  librarian (experiment 71): rules → Gemini Flash for 8 strong kinds → Claude Opus 5.5 where it says high → the Desk;
  99.1% precise on 522 verified items, about $3 per 1,000 decisions.

**What happened, in order.**
- **2026-10-23:** the Desk became the product's face for the shareholder demo (index pages, Explorer, article beside
  its scan, Guide with 70 labels flagged); exp 55 the pitch and the deck (`/pitch`); exp 56 the librarian's first
  pass on institutions (proposals).
- **2026-10-26:** the Project page. The owner sent Google Cloud's form about credits (no answer recorded).
- **2026-10-28:** the shareholder meeting: "they love the product"; exp 57 wrote the business (12 pp) and technical
  (31 pp) documents the same day. Confidential; they wait for the owner's read.
- **2026-10-30:** the AI-Search A/B (our chunks +14 points in the top 5, 12 articles); exp 58 Indra (parked); exp 59
  Reducto (not adopted); the Pipeline page.
- **2026-10-31:** exp 60, Claude vs Argon as reader: keep Argon ($30.78). Its side finding (Argon "fixes" correctly
  printed words) led to the guard.
- **2026-11-02 (one long day):** the owner said they will look only at urgent items, so agents verify each other.
  Exp 61 audit (99.66%), exp 62 cited-works librarian, exp 63 blind check of institutions (4 errors in 908), exp 64
  institutions applied (R20261102T155701), exp 65 leak fixes + v3.6, exp 66 the guard, exp 67 cited works applied
  (R20261102T174226), the Plan page, exp 69 fix-rule check, **exp 68 go-live at 17:16 (release R20261102T231619, the
  live one)**, then exp 70 gate 2's pilot started (17:22) and exp 71 the model test finished (19:37). The owner
  **topped up £500** and approved gate 2: fix → re-audit → one journal → nine more.

**Running now (2026-11-02 evening).** Exp 70, gate 2's pilot: مجلة الطفولة والتنمية (0165, Egypt), 363 articles =
145 scans + 218 Word files, prompt v3.6 + the guard, Argon Batch, hard cap $55 (absolute cap on the exp 43 log
$159.10), about $40 expected. No README yet; read `experiments/70_gate2_pilot/progress.md` and the Plan item
`gate2-pilot` before anything else, and do not edit the files it uses while it runs (experiments 43, 46, 47, 53, the
Desk). Planned after it: the production librarian on 0165 (`lib0165`, cap $10).

**Known disagreements between sources** (see the end of this list for what to trust):
- Exp 68's README (written 17:10) says "ready, NOT live"; the Plan, exp 70's progress and `68_go_live/out/golive_run.log`
  show it went live at 17:16. The live release's numbers equal the README's dry run (2,738 applied, 3 orphaned,
  1 conflict, 8,903 cited works, 99.814%).
- Exp 70's progress gives "run $20.57" for the scan reading; by the log that is the scan $19.37 + the Word step $1.20.
- The Project page's money panel and "stage" still say $100.15 / about £11 / gate 2 waiting (as of 2026-10-26).

**Waiting for the owner** (the Plan's "Needs you", 2026-11-02; replaces section 000a's list where they overlap):
1. **Make the GitHub repo `CubezCS-tys/inkscript` private (urgent).** It is public; it holds one real Mandumah
   article as the test fixture, and the shareholder documents say Mandumah data is never on a public repository.
2. **Rotate keys shown in chat:** the Reducto API key, and the Desk admin token (printed once on 2026-10-21).
3. **Ask Reducto to delete the 49 pages** sent in exp 59 (the free tier's delete call failed).
4. **Read the shareholder documents** before they go out (exp 57).
5. **Gate 3 before 1 December** (about $43k now, about $86k after; estimate).
6. **Remove the October demo decisions?** One blocks a cited-work split («المقدمة» shows 13, not 12); needs an admin.
7. Review the Guide's 70 flagged labels; the 21 re-minted cited-work ids (keep or restore); the Word route's small
   paid test (about 20 articles, under $1); "unclear" references in a split; the master tables' shape; commits since
   2026-10-21 (nothing from experiment 48 on is committed; check for private data first); proposed deletions; older
   items (Work task wording, the 0732 / 0849 judge calls, which fields each corrector covers, the remote Desk's
   domain).
8. Parked ideas, nothing to start without the owner: a local model as a librarian tier (the owner is reading up);
   Gemini Carbon when public; an ink check for the bad fixes the guard misses; re-reading the 600 with v3.6.

**Money (2026-11-02).** Gemini log $127.08 since the 2026-10-18 top-up (19:43, growing with the pilot); credit roughly
£480 left by estimate after the £500 top-up; Claude API $33.97 of the owner's $250 credits (exp 60, 71). Details and
caps: [STATUS.md](STATUS.md) "Spend (2026-11-02)". Every paid step has its own owner-approved cap enforced in code.

**How to see everything.** One tunnel, from the owner's Windows/WSL machine:
`ssh -N -L 9004:127.0.0.1:8004 prod`, then `http://localhost:9004` (use `localhost`, not 127.0.0.1, under WSL).
The Desk's admin
token is in `/home/appuser/data/desk/owner_token.txt` (to be rotated: item 2). Pages: `/project`, `/plan`,
`/index-home`, `/journals`, `/institutions`, `/most-cited`, `/articles`, `/explore`, `/how-we-collect` (Guide),
`/librarian`, `/librarian/works`, `/audit`, `/pipeline`, `/pitch`, the correctors' `/`, `/work`, `/works`, `/notes`,
`/releases`, and the static `/gate1/`, `/gate2/`, `/inventory/`, `/mindmap/`, `/views/…` (table in
[overview.md](overview.md) "The Desk and its pages"). After a code change in `desk/` the API must restart; a web
change needs a rebuild of the live copy (`/home/appuser/data/desk/web-live`; experiment 49's README).

**Telling the owner.** `~/bin/tg "text"` (or `tg "caption" image.png`) sends them a Telegram message; the keys are in
the repo's `.env` and are never printed.

## 000a. 2026-10-21/22 (history; section 000 above is newer)

The plain overview of the whole system is [overview.md](overview.md); the numbers with dates are in
[STATUS.md](STATUS.md) "Linking, the Desk, gate 1 and the Word route (2026-10-22)". This section is what a fresh
session needs on top.

**What changed.** Extraction was declared "in a good place" (2026-10-21) and the work turned to linking: the bridges
between articles (people, works, institutions, journals, citations) and the people who correct them.
- **Exp 48, linking probes** (the 600): only ~3% of references land on a held work; two-thirds are books and turath;
  identity links are precise (byline → person 50/50). Cited works must be counted as entities of their own.
- **Exp 49, the Desk** (P1 + P2 built, 19 tests): the correction backend for about 300 correctors. Decisions are
  append-only, "no" is stored, detectors make tasks, releases re-apply every decision.
- **Exp 50, the mind map** of Mandumah's products, AI-Search and this repo (553 nodes).
- **Exp 51, the extraction inventory:** 235 fields; the owner said "add all 37" priority gaps → prompt **v3.5b**
  (v3.3 + the 37 in a separate part, without v3.4's two content lines), checked on 12 articles, +15% a page.
- **The letter fix** (exp 43): Azure's Persian look-alike letters written as the printed Arabic ones, recorded as
  reader fixes (D30). 1,059 + 829 words in the 600.
- **Exp 52, gate 1:** one education journal (0130, 126 articles, $24.24). Bridges far denser than random; 9/10
  random pages right, 0 serious. The owner: "that's what I'm talking about".
- **Exp 53, the Word route:** 0130's 139 Word files → 139 valid masters by code; page numbers past page 1 are
  estimates, flagged (D36).
- **Exp 54, gate 2 selection:** started on the evening of 2026-10-22 (no README yet; `progress.md`).
- The journal is loaded into the main `platform_v2.db`, now 726 articles.

**The owner's decisions and how they work now.**
- **Two products on one set of masters:** a much better RAG for ai.mandumah.com, and a Web-of-Science-depth index.
  Not for universities ranking their staff; the aim is absolute quality. Global scope.
- **All correctors are equal, and each owns their decisions:** one key, no second checks, tie-breaks or majorities.
  A corrector who disagrees leaves a note; the two settle it. Admins (the owner) can fix anything. Gold is only a
  quiet accuracy gauge. Languages Arabic, English, French; remote team; the Desk has its own accounts. Catalogue
  errors go out as a list for Mandumah's cataloguers, never into the catalogue.
- **Education Citation Index first, gated, journal by journal** (after Garfield's 1961 start): gate 1 one journal,
  gate 2 about 10 education journals over the same years, gate 3 the full slice (162,816 articles, ~$43k now,
  ~$86k after 1 December). Measure bridge density and correction load at each gate. "Hold our horses."
  Identity stays global (authors publish across journals).
- **The Word route** is approved, with flagged page estimates (D36); prefer scans where they exist.
- **Books and turath as the bridge:** an open hypothesis, to re-measure as more is parsed, not a rule.
- **"The platform is my backend, everything viewable and observable"**: every extracted field should be visible in
  the platform and the Desk.
- Model choice: the owner may ask stakeholders about a bake-off (Argon, Flash, Claude, GPT); likely to stay with
  Gemini 4 Argon. Do not start one without their go.

**Running or ran overnight 2026-10-22/23** (three agents; they may have finished; check their logs before
anything else):
1. **The letter-fix reload:** the 600 reloaded with the letter fix into `platform_v2.db` (backup
   `platform_v2.before_lettersfix_2026-10-22.db`), then a Desk release, the detectors and the tests. A release was
   being built at 18:31 on 2026-10-22.
2. **Gate 2 selection** (exp 54, free): its draft picks ten journals, 3,460 articles, ~$456 expected; the Word
   first-page check on 37 candidates was running. Its page will be at `/gate2/`.
3. **The platform loader for the v3.5b fields** (exp 47): developed on `dev_fields.db`, waits for the reload, backs
   up (`before_fields`), reloads, then updates the Desk's Article and Work pages, the Datasette queries and the
   homes table.

**Waiting for the owner** (2026-10-22; replaces section 00's list where they overlap):
1. **The AI-Search offline A/B** on the 12 chunked articles: their OK.
2. **"Unclear" references in a split:** give them their own unlinked card (recommended) instead of leaving them on
   Book 1's card.
3. **A top-up for gate 2** (about £11 is left by estimate after $100.15 since 18 Oct; check the console), and their
   review of gate 2's selection.
4. **The Word route's small paid test:** about 20 articles, text-only, Flash against Argon, under $1.
5. **Commits:** nothing in experiments 48–54 is committed. Before committing, check for private data (judged
   samples with reference text or catalogue records into gitignored `out/`; the Desk's gate1 page holds Mandumah
   titles; `web/node_modules` and `.next` ignored).
6. **A "from the catalogue" column** on the homes table (`/inventory/homes.html`), offered.
7. Still open from before: the Work tasks' wording (they found them confusing); the 0732 / 0849 judge calls;
   installing `latex2mathml` in the server venv (exp 43 "Prompt v3.5": without it no article with an equation builds
   into masters there; the letter fix used a private copy in `out/lettersfix/pylib`).

**How to see everything.** One tunnel, from the owner's Windows/WSL machine:
`ssh -N -L 9004:127.0.0.1:8004 prod`, then open `http://localhost:9004` (use `localhost`, not 127.0.0.1, under WSL).
The Desk's admin token is in `/home/appuser/data/desk/owner_token.txt` (reissue it before P4: it was printed in chat
once).

| Page | What |
|---|---|
| `/` | the Desk: Overview, Work tasks, Article / Person / Work pages, releases |
| `/views/…` | the articles beside their scans (Layout pages; e.g. `/views/j0130_final/index.html`), passed through to :8899 |
| `/gate1/` | gate 1's results page |
| `/gate2/` | gate 2's selection (once experiment 54 writes it) |
| `/inventory/` | the 235-field extraction inventory |
| `/inventory/homes.html` | where each field lives: JATS, ALTO or the platform |
| `/mindmap/` | the product mind map |
| `/mockup/` | the Desk's first mockup |

Datasette over the platform is on :8003 (`/platform_v2`) if it is running and that port is tunnelled too
(`-L 9003:127.0.0.1:8003`).

## 00. Since 2026-10-15 (as of 2026-10-21; history)

The owner topped up Gemini on 2026-10-18 and the work turned from experiments into a **product rehearsal**:
Azure's words, Gemini 4 (Argon, prompt v3.3, thinking low, Batch) giving each line its type and order, code rules,
a judge that edits only through a logged patch layer, flags for a person, and a database of everything we hold.
Numbers with their dates are in [STATUS.md](STATUS.md) "The exam, the proof pack and the platform".

- **Exp 42, stroke recovery** (Codex, 2026-10-17/18; [codex-handoff.md](codex-handoff.md)): an instrument for the
  reopened back-writing question; no production change, $0.
- **Exp 43, the rehearsal** (`experiments/43_rehearsal`, README is long: read its section headings first).
  - The first 300 articles: run, judge (step A), free fixes (B), final (F): `out/v33_300_final`.
  - **The exam** (step G): a held-out second 300, pipeline frozen beforehand (stamp in `out/overnight_plan.md`):
    300/300 answered and valid, **$31.94 = $0.106 an article, $0.0094 a page**; `out/v33_300b` (raw run),
    `out/v33_300b_final` (fixes + judge patches).
  - **The proof pack** (step P, an independent agent, seeded draws, no calls): `out/proof/proof.md`, page
    http://127.0.0.1:8899/proof/proof.html. 60 random pages: right 35, minor 23, serious 2; words 0 wrong of 1,532;
    citations fully right 57/80 (0 wrong fields); back references 15/20; metadata all right 18/30.
  - **Fix round 3** (the proof's failures fixed at the root, on a copy, $1.12): `out/v33_300b_fix3`, views
    http://127.0.0.1:8899/v33_300b_fix3/index.html. Same 60 pages: **right 43, minor 17, serious 0**; metadata
    all right **25/30**; citations unchanged. 2026-10-21: 0529's flow charts fixed (`rules43.swapped_box`, `fd8efa5`).
  - Correction tool v1 (D34): http://127.0.0.1:8899/correct/edit/index.html.
- **Exp 44, bucket map**: 1,013,912 documents in the main bucket (PDF + Azure JSON), 308,593 more in `legacy/` (PDF
  only). Draws are filtered by `experiments/44_bucket_map/out/ids_main.txt`.
- **Exp 45, the MARC catalogue as a database**: `~/data/marc/marc.db` (9.5 GB, 1.56M records, FTS5),
  Datasette :8001.
- **Exp 46, platform v1**: `~/data/platform/platform.db`, Datasette :8002; holds the 300, the 55 and the exam with
  flags, patches and judge findings.
- **Exp 47, platform v2** (Web-of-Science style, the scan under every value): `~/data/platform_v2/platform_v2.db`,
  Datasette :8003 with an ink viewer. Independent re-verify round 2: **11 of 11 checks pass**; its gaps fixed
  2026-10-21 (`48d2494`): publishers keyed on name + country, ink links that survive rebuilds, 4 back references.
- **Spend:** `experiments/43_rehearsal/out/gemini_spend.jsonl` = **$73.62** since the 2026-10-18 top-up of £101.28
  (incl. 20% VAT; budget = log dollars → pounds + 20%, reconciled within 1%), so about **£35 incl. VAT is left**
  (check the console). Nothing bigger than a small test without the owner's go.

**Waiting for the owner (2026-10-21):**
1. The ~3,000-article step: about **$320** at the exam's rate; needs a top-up.
2. Two judge calls: 0732 (the judge unmarked the bottom strip as "another article" on pp3/6 only; it stays so on
   25 blocks of pp1–13) and 0849 p4 (the judge named two show-through lines; the code key passed one).
3. The v3.5 prompt idea: v3.3 + v3.4's two content lines without the "compact JSON" line, to learn which line caused
   v3.4's repeat losses (adverts shredded, paragraphs merged).
4. Citation linking (works cited across articles, «المرجع السابق») as the next big focus.
5. Proposed deletions: section 8.
6. **Development moves to the owner's Ubuntu server** (`prod`, user `appuser`): section 7 and
   [moving-to-a-server.md](moving-to-a-server.md). The owner does every server step.

**What's served on the laptop** (start commands in moving-to-a-server.md): :8899 the views (a plain http.server in
`experiments/41_azure_structure/out/views`, whose run folders are symlinks into `experiments/43_rehearsal/out`),
:8001 marc.db, :8002 platform.db, :8003 platform_v2.db.

## 0. 2026-10-13 to 2026-10-15 (history)

Three experiments and one decision landed on 2026-10-14/15. The headline: **Gemini reading structure on top of
Azure's words works**, and the owner now has two roads to choose between (end of this section).

- **Exp 39, layout model round 2** (commit `2fe141a`; section 4 has the steps that were run).
  - Overall flat: **87.7% → 87.8%** of the 44 test pages' lines named like the Pro referee.
  - Gained: equations **0% → 78%**, lists 54% → 68%.
  - Broke: footnotes **95% → 67%**, verse **96% → 61%**. The new training pages were 63% table lines, which drowned
    the rest. With dots.mocr for tables and equations: 90.5% (round 1 92.1%).
  - **Round 1 stays the best model.** GPU $1.94 (2.3 h, RTX 5090). Report, same URL:
    https://claude.ai/artifact/MYoVS8BUMfS3xkEJ2BAxeA.
  - Decision **parked**: rebalance the training mix and train round 3, or move on to the order specialist.
- **Exp 40, Gemini 4 (gemini-4-argon) alone as the document reader** (`545183b`, `experiments/40_gemini4_vlm`).
  - Five approaches, **$13.34**. Report: https://claude.ai/artifact/54SBuWQZQQosVQqyqEpE31.
  - Structure far ahead of everything else: **96.8%** of block types right, Azure 74%, our layout model 84%.
  - Its text is about Azure's level but **not faithful**: it fixes misprints and adds hamzas. So it reads the
    structure, not the words.
- **D30** (`fbeec99`, `docs/decisions.md`): the digital text is the print as printed.
  1. Printed text kept; suspected misprints carry a flagged correction (`span.sic`), never replace it.
  2. Azure's misreadings (text that differs from the ink) are fixed.
  3. Old and Quranic spelling untouched.
  - The owner agreed to all three.
- **Exp 41, Azure's words + Gemini's structure** (`1fb3ced`, `experiments/41_azure_structure`).
  - Gemini sees the page and Azure's lines and answers with **line ids only** (type and order per line), so it
    can't rewrite words. 55 articles, 399 pages, Argon vs Flash, **$10.72**. Report:
    https://claude.ai/artifact/AiqhFTZTvMF2or8W9Bi4mp (`out/report.html`).
  - The format holds: no chunk failed. A quarter of the 17,137 lines were dropped as noise, some wrongly (below).
  - Words wrong on 34 truth pages: **Argon 1.55%**, Flash 1.77%, Azure alone 1.80%. The models agree on 94.7% of
    types and 99.5% of order.
  - Choice: **Argon for the edition, Flash for training labels.**
  - Prompt gaps to fix in any next run: list vs body, endnotes, and "a line with words is never noise".
  - Cost per million documents: **Argon about $120k batch, Flash about $46k batch**. Gemini prices double on
    Dec 1 / Jan 1, so these go up.
  - **In progress:** a reader for the 55 articles, `experiments/41_azure_structure/reader.py` (uncommitted) →
    `out/reader/`.
- **Mistral OCR 4.1 annotations** (`1112ceb`, `experiments/32_open_stack/research/05_mistral_annotations.md`): not a
  line labeller; a candidate for the pictures specialist.
- **Chandra 2: skipped.** 68% on Arabic on its own benchmark, and its licence forbids competing with Datalab.

**Open decisions for the owner:**
1. Hand-check 5 articles from exp 41 (`experiments/41_azure_structure/out/handcheck/`).
2. Then: pay Gemini to process the archive, or use Flash labels to train our own specialists.
3. Round 3 of the layout model or move to order (above, parked).

**Money then:** the Gemini credit ran out on 2026-10-15; the owner topped up on 2026-10-18 (section 00). **0 Vast instances.**

## 1. The owner, and how to work with them

**How they think**
- They think in **physical pictures**: liquid flowing round letters, strokes felt on your back, "the map", "rivers of
  paper". Those pictures have been the right design more than once. Describe choices by what the result looks like,
  not by data structures.
- They **understand visually**. Deliver every result as a page with real examples (scan beside output, before and
  after, the ink itself), with the headline numbers on it. Publish it as an Artifact and give the link. Keep the chat
  summary short. Tables support the page; they never replace it.
- They want to **stop and think at turning points**. Don't fill the pause with experiments. Since 2026-10-12 they've
  been thinking abstractly about how to "attack" a document. In their words: "I dont want to finalise on a plan until
  i can feel it in my mind". Answer their questions and run only the tests they ask for. Don't turn their thinking into
  a plan or roadmap until they say it feels right.

**How work gets done (2026-10-13)**
- **Agents do the hands-on work; the owner and I orchestrate.** Their words: "from now on let agents do the work please
  you and me are high level orchestartors". They run several projects in parallel and want this conversation kept
  for decisions.
  - Hand execution (scripts, runs, GPU rentals, scoring, reports) to background agents, each with a self-contained
    brief: caps, rules, files, and what to report back.
  - I check results, publish reports and talk with the owner.
- **Specialists are attacked one at a time** (the owner's choice on 2026-10-13: "for now lets leave it sequential").
  Layout is first. Don't start another specialist until they ask.
- **Initiative is welcome inside an approved cap.** When an agent turned "a few minutes of GPU" into a bigger
  comparison, they said "i like that type of proactivity". Say what changed and why when reporting. The caps
  themselves always need their approval.
- **Agents save every item to disk as they go**, and skip items already saved. On 2026-10-12 a session-limit stop
  lost nine reviewers' finished work, and the owner objected: "the review cant start over otherwise im just losing
  credits for no reason". Their Claude plan is a real, limited cost.
  - Keep units small.
  - Before resuming, check what was saved.
  - Warn the owner before heavy multi-agent runs.

**Money**
- **Report spend at every step.** The Gemini credit is shared with their other projects. On 2026-10-13: "if we need
  more gemini I will add more I just wanted to be ontop of things". Keep a cap for each experiment, and ask before
  going past it.
  - Gemini: about $20 per experiment is acceptable ("no 20 is good"). Every Gemini agent gets a hard cap, a cost
    estimate before each batch and a running spend log.
  - Prefer a cheaper model when calibration shows it's about as accurate.
- **GPU rental is cheap.** "GPU renting is cheap man": a two-hour training run cost $1.70. The real cost is Gemini
  labels and the owner's Claude usage.

**Other standing rules**
- **Edition font.** They looked at the editions on 2026-10-12, said "I hate that font" (Markazi Text in the PDFs,
  Noto Naskh on the web and in the e-book), and picked **Scheherazade New** (SIL, OFL) from a 16-font sheet
  (`experiments/35_edition/out/fontsheet/index.html`).
  - The switch is still to do: `src/inkscript/edition` (`fonts.py`, `html.py`), regular and bold, in every edition.
  - Unanswered: headings in Scheherazade bold, or a contrasting font?
  - Check its Latin coverage, and record the change as a decision.
- **Deletions:** propose them, never do them.
- **Disk:** on the laptop the WSL disk lives on Windows C:, 96 GB free on 2026-10-13. Pause big runs below 50 GB free.
  `~/.cache/pip` (14 GB) and `~/.cache/huggingface` (11 GB) could be cleared there. On the server, just watch `df -h`.

## 2. The big picture

- **A year of chasing perfect OCR.** The owner has worked since September 2025 to get perfect OCR of Arabic journal
  scans for Mandumah. The project began as *ink-as-text* (experiments 1–31): each printed word or letter becomes a
  Type 3 glyph traced from its own ink, which selects and searches in Chrome. That vision **is not dropped**; never
  call it abandoned.
- **On 2026-10-12, after exp 38, they said they don't see "the light at the end of the tunnel".** That started the
  abstract "attack" thinking in section 3.
- **The reframe (2026-10-11/12).**
  - Their words: "Azure is what we have to be dependent on for now because we've already got all the text"; "more
    than a million documents that are sitting in S3" (`s3://mandumah-source-docs/<id>/<id>.{pdf,json}`).
  - The goal is to become "our own sort of document parser": rebuild each document natively, respecting columns,
    images, tables and equations, out to JATS/XML, PDF and editions. The output is for reading online, printing and
    AI training.
  - On 2026-10-12 evening: "from now we should assume that azure is the gold truth as it just simplifes life instead
    of getting into its 1% errors". **Text is settled. All effort goes to structure.** Don't propose text-correction
    work (LLM correction, diffusion fill-in) unless they reopen it.
- **Exp 38 → D29** (`docs/decisions.md`).
  - Our own parser keeps Azure's words and takes layout, order, tables, formulas and pictures from dots.mocr.
  - A blind Gemini Pro judge preferred the new layout page on 18 of 33 hard pages (old 4, tie 11); a Claude reviewer
    preferred it on 28 of 44 (old 3).
  - No Azure word was lost.
  - Model correction of the text stays off.

## 3. The attack on a document: specialists

The owner's picture is a team of specialists, each doing **one job** and handing off. They connect through **the map**
(the page's ink) and **the master copy** (the one rebuilt document). The owner on training them: "remember to not step
on the toes of other specialists… we just need to connect and train all these experts". Each specialist is
deterministic, a model, an agent, or a mix. Measure first, use a model where recognition is needed, and consult an
agent (Gemini) only on hard or disputed cases.

| # | Specialist | Job | Kind | Status (2026-10-13) |
|---|---|---|---|---|
| 1 | Reader | the words | Azure (prebuilt-read: words, lines, paragraphs; no roles, tables or figures) | done: treated as truth |
| 2 | Map | every island of ink, traced | deterministic | built (exp 39) |
| 3 | Layout | what each line/region is | model (+ rivers for edges) | round 1 is the best model; round 2 done 2026-10-14, not better (section 0) |
| 4 | Order | which block is read after which | model + rules | not started (Azure's order today) |
| 5 | Style | bold, size, centring, indents | deterministic + model | not started |
| 6 | Tables | rows, columns, merged cells; Azure's words into cells | model | not started (layout hands off "table") |
| 7 | Equations | maths as LaTeX/MathML | model | not started (layout hands off "equation") |
| 8 | Pictures | cut out figures, link captions | map + model | not started |
| 9 | Whole document | running headers, the book's heading style, footnotes and tables across pages | deterministic + agent | not started |
| 10 | Writer | writes the master copy once | deterministic | exists in exp 38 form |
| 11 | Auditor | checks against the map: unclaimed ink, ink claimed twice, disagreements; sends only those spots to Gemini or a person | deterministic | idea; I suggested running it alongside, the owner chose sequential |

The order they lean on each other (not a plan): layout first, because it hands work to tables, equations and
pictures. Order and style need layout's blocks. Whole document needs all of them. Writer and auditor connect
everything. The auditor would also give a timeline that doesn't depend on Gemini ("ink left unclaimed: X% → Y%").
The offered test "count unclaimed islands on the 44 pilot pages" was **not approved**.

### What exp 39 measured (all in `experiments/39_ink_geometry/`, README has the detail)

- **The map** (`geometry/trace.py`, report `out/report.html`).
  - How: Otsu threshold, rules lifted out, each connected component traced as a polygon with holes
    (`approxPolyDP` 0.6 px).
  - Redrawn from the shapes alone, a page matches **95.0–97.5%** of the ink.
  - It didn't help *read* text (the letter atlas never beat Azure). Its value is as a model-free survey that every
    other specialist pins to.
- **Rivers of paper** (`rivers.py`, `out/rivers.html`; the owner liked it).
  - How: ink smeared sideways; tall thin paper channels are gutters; gaps wider than 1.7× the page's median line gap
    are block breaks; long rules are walls.
  - Finds: columns on every two-column page; equations, tables and references set apart; a table's column gaps and a
    verse's halves.
  - Misses: single-column headings and footnotes, bullets and grey photos.
  - The owner on regions: "both". A whole-page model names the blocks; the rivers and the map give exact edges.
- **The other senses** (`senses.py`, `out/senses.html`): labels each Azure line from ink measurements and text
  patterns, with no model. The measurements: letter size, stroke thickness, line pitch, indents, a short rule above
  the footnotes, footnote numbers matching markers in the body, dash bullets, the verse gap, top-row furniture.
  - On the two pages it was tuned on, every line was right. The owner: "literally perfect on those two pages". I
    warned it was tuned there.
  - Untuned on the 44 pilot pages (Gemini Pro referee, $0.52): **47%** overall, 72% on plain single-column text.
  - It breaks on: columns (verse false alarms), tables (footnote cascade), numbered lists, bottom furniture, varied
    headings. Report: `out/layout_score.html`.
- **dots.mocr** (a VLM with a few billion parameters, exp 36), its block types on the same lines: **80.5%** vs the
  rules' 34.6%.
  - By kind of page: plain 89%, tables 92%, equations 88%, columns 70%, decorative 22%.
  - Weak on lists (19%), verse (0%, no such label) and headings (57%).
  - The owner then: "use model on everything if we can find a good small and cheap one".

### The layout model, round 1 (2026-10-13)

- **Labels.** 2,700 pages from 228 documents (`train_pages.py`; at most 40 per document; none from the 44 pilot
  pages' documents). Gemini 3.8 Flash labelled every Azure line, about $0.0045 a page; it agrees with Pro on 92.7% of
  lines.
  - Eleven labels: furniture, heading, body, list, verse, footnote, references, caption, table, equation, other.
  - "references" was added because Flash and Pro mostly disagreed on reference lists.
- **Model.** DocLayout-YOLO (YOLOv10 fork, DocStructBench weights, about 20M parameters, about a hundredth of
  dots.mocr), fine-tuned to detect each line box with its label at 1280 px (`make_yolo.py`, `gpu/`).
  - Split by document: train 2,508 pages, val 185 (22 documents), test = the 44 pilot pages labelled by Gemini 3.1
    Pro (`out/score_test`).
- **Run.** One RTX 5090 on Vast, 2.0 h, **$1.70**. Training stopped itself at epoch 52 and kept epoch 32 (val mAP50
  ≈ 0.69). The library's final step crashed (see section 6); predictions ran on the laptop CPU from the saved weights
  (`predict_local.py`, 1.5 s a page, 1 GB peak). Weights: `out/gpu/out/run/weights/best.pt`.
- **Score on the 44 test pages** (2,075 lines, `score_yolo.py`): **model 87.7%**, dots.mocr 84.4%, rules 39.5%.
  - By kind of page: plain text 95%, decorative 95%, columns 86%, tables 86%, equations 74%.
  - By label: body 96%, verse 96%, footnote 95%, table 89%, furniture 87%, references 78%, heading 64%, list 54%,
    **equation 0%** (only 77 equation lines in training).
  - On labels dots.mocr can say at all, **dots is still better**: 91.7% vs 88.0%, mostly tables and equations.
  - The model wins overall through verse, reference lists and lists.
  - **The model's label, but dots.mocr's wherever it says table or equation: 92.1%.** That's the "connect the
    specialists" idea on a small scale.
- **Report:** https://claude.ai/artifact/MYoVS8BUMfS3xkEJ2BAxeA (`out/layout_model.html`, `report_yolo.py`).
- **What I told the owner about distillation.** A small student copies a big teacher on one narrow job. Four catches:
  1. It copies the teacher's consistent mistakes; only random slips wash out. The ceiling is Gemini's own
     consistency: Flash and Pro agree on only about 93% of lines.
  2. It can only learn from what it sees. It sees pixels only, no words and no other pages. Lists and headings need
     words (أولاً، (١)، الفصل) and the whole book.
  3. Variety beats volume.
  4. "Perfect" needs a rulebook: is quoted dialogue body or verse?
  - My guess for round 2: 93–95% against Pro, beating dots on every label.
- **Next ideas after round 2** (from the same talk, not approved):
  - **Give the model the words.** A small second step using Azure's text plus the senses' measurements, for lists
    and headings.
  - **Whole-book consistency.** Headings look the same throughout one book.
  - **Stretch the Gemini money.** dots.mocr on a rented GPU pre-labels pages, and Gemini judges only where dots and
    our model disagree.

## 4. Round 2: what was run (done 2026-10-14; results in section 0)

Kept for the record; all steps below were done and committed in `2fe141a`.


Goal: steps 1 and 2 of the plan the owner approved. **Step 1:** equation and table pages. **Step 2:** the pages the
round-1 model is least sure of. **Caps:** Gemini total for exp 39 **$19** (round 1 spent $11.92, so up to about $7
more); GPU **$3** this round.

Done:
- **`more_pages.py`.** 150 new documents (30 each) from journals 1541, 0527, 0700, 1016 and 2483. These carry
  equations, and **none of them has a page in the 44-page test set**, so a jump in the equation score is honest.
  - Only Azure's JSON was fetched first: 5,211 pages, 294 with ≥2 maths lines, 600 with ≥2 table-row lines.
  - Outputs: `out/more/kinds.json` and `out/more/azure/`.
  - Why new documents: the yardstick pool was used up (only 315 unused pages left, one with maths).
- **`round2.py candidates` and `draft`.** 1,752 candidate pages from 221 documents (the maths and table pages, 600
  others, and the pool's leftovers), drafted into `out/round2/pages/`.
- **`predict_local.py round2`.** The round-1 model over every candidate. **Complete: `out/round2/pred.json` has all
  1,752 pages** (checked at the time of writing).

Then (done 2026-10-14):
1. `../../.venv/bin/python round2.py select`: all maths pages, then the least sure, N=1450 → `out/round2/chosen.json`.
   Look at a few chosen pages first.
2. `../../.venv/bin/python round2.py label`: Flash labels → `out/round2/labels/`. `round2.py` sets the cap to $19.
   Don't raise it without the owner.
3. `ROUND2=1 ../../.venv/bin/python make_yolo.py` → `out/train/yolo2/` (round-1 val documents stay val, plus 10% of
   the new documents). Check that the equation count rises well above 77.
4. GPU training into `out/gpu2/`, same hyperparameters as round 1, starting from the DocStructBench weights (not
   round 1's best.pt), so the two rounds compare cleanly.
5. Predict val and test, run `score_yolo.py` (→ `out/score_yolo2.json`), and rebuild `report_yolo.py` as round 1 vs
   round 2 side by side. Say the equation score on the 8 equation test pages explicitly.
6. Update the README and the `experiments/README.md` row, commit, push, and republish the report at the same URL.

The round-2 agent's script changes (committed with round 2):
- Modified: `gpu/gpu_end.sh`, `gpu/gpu_run.sh`, `gpu/gpu_wait.sh`, `gpu/train.sh`, `make_yolo.py`,
  `predict_local.py`, `report_yolo.py`, `score_yolo.py`.
- New, from me: `more_pages.py` and `round2.py`.
- The GPU scripts were adapted for round 2 (`GOUT` env for the output folder, the fuse patch, `save_period`). Some
  `make_yolo.py` and `predict_local.py` edits are mine (ROUND2 / round2 modes).

Round 2 was resumed by one background agent with the steps above, the caps, the GPU rules (section 6) and "report back:
round 1 vs round 2 by page kind and label, the model+dots number, spend, GPU hours, 0 instances, commit hash; be
honest if round 2 is not better".

## 5. Spend so far

- **2026-10-22 to 2026-11-02:** Gemini log $100.15 → **$127.08** (gate 1 $24.24 on 2026-10-22; on 2026-11-02 the
  v3.6 check $0.80, the fix-rule check $3.16, gate 2's pilot $22.99 so far); exp 71's own log Gemini $3.27; Claude API
  $30.78 (exp 60) + $3.19 (exp 71); Reducto $4.61 at list price inside free credits. Top-up £500 on 2026-11-02.
  Current figures: [STATUS.md](STATUS.md) "Spend (2026-11-02)".
- **2026-10-18 to 2026-10-21:** Gemini **$73.62** on the experiment 43 log (rehearsal, judge, the exam $31.94,
  fix round 3 $1.12). Experiments 44–47 cost $0.015 (S3 listing) and nothing else.
- **2026-10-14/15:** exp 39 round 2 GPU **$1.94**; exp 40 Gemini **$13.34**; exp 41 Gemini **$10.72**. The Gemini
  credit ran out on 2026-10-15.

- **Exp 39 Gemini: $11.92** (round-1 labels, the test referee, small scoring runs).
  - Logged in `experiments/39_ink_geometry/out/gemini_spend.jsonl`.
  - Enforced by `experiments/38_parser/common.py:gemini()`, which refuses any call whose worst case would cross
    `common.CAP` and caches answers in `out/gemini_cache.jsonl`.
  - `score_layout.py` points `SPEND`/`CACHE` at exp 39's `out/` and sets CAP 15; `round2.py` raises it to 19.
- **Exp 39 GPU: $1.70** (instance 55640758, 1.99 h at $0.852/h), logged in `out/gpu/gpu_spend.jsonl`.
- **Earlier:** exp 33 spent $2.64 of a $10 GPU cap; Vast credit was about $20 after that, so check the balance.
  Exp 38 spent $3.08 Gemini.

## 6. Vast.ai GPU rental

- **CLI.** On the laptop it lives in its own venv: `~/.local/venvs/vast/bin/vastai`. It isn't on PATH, and the
  scripts call it by that path. On the server: `python3 -m venv ~/.local/venvs/vast &&
  ~/.local/venvs/vast/bin/pip install vastai`.
- **Key.** It lives in `~/.config/vastai/` (mode 600). **The owner types it** (`vastai set api-key …`). Never print,
  cat or read it, and never ask for it in chat.
- **SSH key for the machines:** on the laptop, `~/.ssh/id_ed25519_vast`. On the server, make a new one and add it to
  the Vast account (`vastai create ssh-key`), or copy it if the owner prefers.
- **Scripts.**
  - `experiments/39_ink_geometry/gpu/`:
    - `gpu_offers.sh`: filters offers (CUDA ≥12.8, disk ≥60 GB).
    - `gpu_run.sh`: rents, link test, setup, upload of a packed tar, starts training.
    - `setup.sh` and `train.sh`.
    - `gpu_wait.sh`: waits for `train.done`/`train.failed`, fetches, then destroys.
    - `gpu_end.sh`: destroys and logs cost.
  - Exp 36 (`experiments/36_vlm_bakeoff/gpu/`) has the same pattern for dots.mocr.
  - Some of these scripts hard-code `/home/yassine/inkscript` (section 7).
- **Guard.** `ops/vast_guard.sh` destroys any instance older than 6 h (`MAX_MIN`, raised from 3.5 h by the owner) or
  with its GPU idle 30 min. It checks nvidia-smi over ssh, because Vast's `gpu_util` lags. Log:
  `~/.config/vastai/guard.log`.
  - Start it with `(setsid nohup bash ops/vast_guard.sh >/dev/null 2>&1 </dev/null &)` in its own call, then verify.
  - Restart it after every reboot.
- **Rules (strict):**
  - Datacenter / secure-cloud machines only, because Mandumah pages go on them.
  - RTX 5090 (about $0.85/h), or a 4090 if none passes; reliability ≥99.5%; inet up and down ≥300 Mb/s.
  - Right after renting, test about 20 MB of upload. Destroy if it's under 0.5 MB/s. The laptop's own upload is only
    about 1.1 MB/s, so a server with better upload should help.
  - Estimate cost first, log spend, and keep to the cap for each experiment.
  - Destroy (not stop) with **`vastai destroy instance ID -y`**. Without `-y` it waits for a confirmation and,
    unattended, aborts.
  - Confirm **`vastai show instances` = 0** at the end of every job and in every report.
- **Traps learned:**
  - **`pkill -f PATTERN` kills itself** when the calling shell's command line contains the pattern. This happened
    locally (exit 144) and over ssh (`ssh host "pkill -f 'gpu/train.sh'"` killed the remote shell). Check with `ps`
    in a separate call; use exact patterns.
  - **doclayout_yolo** fuses Conv+BN before predict and final validation, then crashes in its dilated block
    (`'Conv' object has no attribute 'bn'`). Patch first: `import doclayout_yolo.nn.tasks as T;
    T.BaseModel.fuse = lambda self, verbose=True: self`.
  - Pass `save_period=-1`. Round 1 saved every 10 epochs and fetched a 1.2 GB `result.tgz`.
  - Setup on the image needed: `pip install doclayout-yolo huggingface_hub`, a forced reinstall of
    `opencv-python-headless`, `apt-get install libxcb1 libgl1 libglib2.0-0`, `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1`,
    a patched `check_amp`, and batch 8 with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` (batch 16 ran out of
    memory at 1280 px).

## 7. Moving to the server (rewritten 2026-10-21)

**All development moves to the owner's Ubuntu server** (ssh alias `prod`, user `appuser`, home `/home/appuser`,
950 GB free). The owner does every server step. The full guide, with sizes, the path fix and the numbered steps
with what to expect after each, is [moving-to-a-server.md](moving-to-a-server.md). In short:

- **Git holds** code, docs, tests and the bundled fixture. **`ops/pack_v2.sh`**, run from the laptop, copies the rest:
  every `experiments/*/out`, `~/data/marc/marc.db`, `~/data/platform`, `~/data/platform_v2`, `~/.cache/inkscript`
  and the agent's notes. That came to **67.7 GB** in the 2026-10-21 dry run, likely an overnight copy or longer at
  about 1 MB/s upload. The most needed folders go first. The copy is resumable and skips what is already there.
- **Never copied:** `.env`, `~/.aws`, `~/.ssh`, `metadata_final.xml` (it is in the bucket), the experiment venvs and
  39's `result.tgz`. The owner types the keys on the server.
- **Paths.** Experiments 40–47 find their files from their own location and `Path.home()`. The `/home/yassine/...`
  paths live in data:
  - 225 absolute symlinks (the views run folders among them);
  - `sample43*.json`;
  - the platform databases' file columns.
  Fix A is `sudo ln -s /home/appuser /home/yassine`. Fix B, with no sudo, is `python3 ops/relocate_home.py --apply`.
- **Browse pages on the server:** the same four as on the laptop (:8899 views, :8001 marc.db, :8002 platform.db,
  :8003 platform_v2.db), all on 127.0.0.1. Reach them from the laptop with an ssh tunnel to local ports 9899 / 9001
  / 9002 / 9003.

**Venvs to rebuild on the server** (not copied; only when that work resumes):
```
# exp 39's CPU venv for the layout model
python3 -m venv experiments/39_ink_geometry/out/venv
experiments/39_ink_geometry/out/venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
experiments/39_ink_geometry/out/venv/bin/pip install doclayout-yolo huggingface_hub opencv-python-headless
# exp 33 (Kraken: out/env), exp 40 (out/venv), exp 16 (out/torchenv): see each experiment's README
```
Run Claude Code inside tmux so it survives disconnects: `tmux new -s inkscript`, and later
`tmux attach -t inkscript`.

**After any reboot** (laptop or server):
- restart the four browse pages (moving-to-a-server.md, step 6);
- restart `ops/vast_guard.sh` if a GPU might be rented;
- check that each page answers.

## 8. Open items waiting on the owner

*The current list (2026-11-02) is section 000 "Waiting for the owner" and the Desk's `/plan`; the items below are of
2026-10-21 and some are settled.*

- **Proposed deletions** (not done; list of 2026-10-21):
  - `experiments/39_ink_geometry/out/gpu/result.tgz` (1.1 GB, already unpacked beside it).
  - The every-10-epoch checkpoints in `out/gpu/out/run/weights/` (only `best.pt` matters).
  - `~/data/platform_v2/`: old builds and drafts `platform_v2.db.bak-20261020-fix0`, `.bak-20261020-fix1`,
    `.fix1-draft`, `.fix1-draft2`, `.fix2-draft` (with their `-shm`/`-wal`), `link_cache47.json.bak-*`,
    `metrics47.json.bak-*`: about 1.6 GB. Keep `.bak-20261021-fix2` (the db before the 2026-10-21 follow-up).
  - `~/data/platform/platform_before_fk.db`, `platform_fk_build.db` (118 MB, build leftovers).
  - `~/data/marc/slice/` (1.1 GB, the test slice used while building marc.db).
  - Windows C: had 29 GB free on 2026-10-21.
- **Edition font switch** to Scheherazade New (section 1), plus the heading-font question.
- **Exp 37 (edition review) is paused** for the owner's evening session: 20 of 205 documents reviewed, 64 issues.
- **Exp 41 hand-check, then archive-by-Gemini vs Flash labels for our own specialists** (section 0).
- **Layout round 3 (rebalanced) vs moving to order** (section 0, parked).
- **Gemini credit is about £35 incl. VAT** (2026-10-21: log $73.62 since the 2026-10-18 top-up of £101.28): the
  ~3,000 step needs a top-up. The newer list is in section 00.
- **The auditor test** (count unclaimed islands on the 44 pages): offered, not approved.
- **The server move itself**: [moving-to-a-server.md](moving-to-a-server.md), `ops/pack_v2.sh` (section 7).
