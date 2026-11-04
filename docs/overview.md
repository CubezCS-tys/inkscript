# The system today, in plain words (2026-11-02)

For the owner and any new teammate. Numbers carry their date and where they come from; the full tables are in
[STATUS.md](STATUS.md). How the parts are built and run, file by file: [architecture.md](architecture.md); step-by-step procedures:
[runbooks.md](runbooks.md). The live view of what is running, done and waiting is the Desk's **Plan** page (`/plan`).

## What we are making

**A Web of Science for Arabic scholarship, built on Mandumah's archive** (the owner's briefing,
[server-agent-briefing.md](server-agent-briefing.md)). One set of article files feeds two products:

1. **A better RAG** for ai.mandumah.com: clean chunks that know what a heading, a footnote or a reference is, so
   answers stop quoting running heads, emails and bare bylines as evidence. First evidence (2026-10-30, the AI-Search
   session's offline A/B on 12 articles, a small sample): the right passage in the top 5 for 62% of questions on the
   platform's chunks, 72% on ours, **76% on ours with the kind filter (+14 points)**.
2. **A Web-of-Science-style index**: who wrote what, who cites whom, which institutions and journals, times cited,
   h-index, with every fact traceable to the ink on the scanned page.

**What Mandumah has** ([experiment 44](../experiments/44_bucket_map/README.md), [45](../experiments/45_marc_db/README.md)):
- **The S3 archive:** 1,013,912 documents with a PDF and Azure's OCR; 308,593 more in `legacy/`, PDF only (98% of
  those have the publisher's Word file on the server).
- **The catalogue:** 1,558,415 MARC records with an author authority file, as a local database `~/data/marc/marc.db`.
- **ai.mandumah.com:** the live search and RAG (the AI-Search project, read-only for us).

All of it is private: never on a public link; every page listens on 127.0.0.1. **The GitHub repository
`CubezCS-tys/inkscript` is still public (checked 2026-11-02) and holds one real Mandumah article as a test fixture:
making it private is the most urgent item waiting on the owner.**

## The picture: two paths, and gates

The work runs on **two paths** (the Plan page's lanes "Extraction (islands)" and "Reconciliation (bridges)").

### Path 1: extraction (islands)

Each article made complete on its own: every word as printed, its structure (headings, paragraphs, notes, tables,
verse, pictures), its metadata, and its **references** (what it cites, outgoing).

- **Azure gives the words** and their boxes; nobody retypes the text.
- **Gemini 4 Argon gives the structure**, answering in Azure's line ids only (what each line is, in what order, the
  reference fields, the document type…). The prompt for gate 2 is **v3.6** = v3.5b + three additions from the audit
  (an author's post, the DOI / licence / section, other printings of an author); the "fix rule" bullet was tried
  and dropped because it changed nothing measurable ([experiment 69](../experiments/69_fix_rule_check/README.md)).
- **Code rules** build the article, repair what is safe and raise flags. Two of them guard the print:
  - **the letter fix**: Azure's Persian look-alike letters (ی ک ھ) written as the printed Arabic ones, recorded as
    reader fixes;
  - **the D30 guard** ([experiment 66](../experiments/66_d30_guard/README.md)): where Azure was sure of every word and
    Gemini's "fix" changes printed letters into another known word, the print stays and Gemini's word becomes a
    flagged suggestion beside it. About 94% of Gemini's 24,528 fixes are right; the guard refuses **409** of the bad
    ones on the 780 articles (precision 69%, about 16% of the bad fixes; the rest need an ink check, an open idea).
- **Fixed-format identifiers by code** (D45, [experiment 65](../experiments/65_fix_leaks/README.md)): ORCID, DOI,
  ISSN, e-mail, phone found on every line with their check digits, never by the model.
- **Masters:** JATS (the article) and ALTO (every word on the page), checked against the official DTD / XSD.
- **Nothing lost** ([experiment 61](../experiments/61_nothing_lost/README.md), [68](../experiments/68_go_live/README.md)):
  every printed line of the 780 articles was followed into a field. **99.81% of 435,270 lines** end in a proper field
  or are set aside as not article text (was 99.665% before the fixes); the Desk's **Audit** page shows it.

### Path 2: reconciliation (bridges)

The connections between islands: the same person, institution, journal or cited work across articles, and
**citations** (another article citing this one, incoming). A wrong bridge corrupts every count above it, so bridges
are judged by precision.

- **The linker** (experiment 47) makes the machine's bridges; the catalogue gives authority names and the held works
  a reference can land on.
- **The librarian** is an AI curator that walks the cards like a librarian at a catalogue: an evidence packet in, a
  structured decision out. Its passes are checked by a **blind second agent**, disagreements are adjudicated, and
  hard checks run by code. **Only decision kinds measured at 98% or better are applied, never "unsure"**; the rest stay
  proposals. The owner looks only at urgent items and policy questions (2026-11-02).
  - **Institutions** ([56](../experiments/56_librarian_institutions/README.md) →
    [63](../experiments/63_verify_institutions/README.md) blind check, 4 errors in 908 →
    [64](../experiments/64_apply_institutions/README.md) applied): the 780 articles name **242 institutions** (the
    machine had 271), **93% with a country** (was 42%), 70 in 2+ articles.
  - **Cited works** ([62](../experiments/62_librarian_works/README.md) → [67](../experiments/67_apply_works/README.md)
    applied → [68](../experiments/68_go_live/README.md) go-live): **9,137 → 8,850 → 8,903** works (the last +53 are titles
    the leak fixes now parse), 291 cited by 2+ articles (was 209).
  - **Owner rules** D37–D44 settle the policy cases: a degree is "educated at", not an affiliation (D37); a former
    post is marked former (D38); an unnamed body is filled from the journal's publisher, marked inferred (D39); a
    commented hadith collection counts for the collection (D40); a manual's editions are one work (D41); a chapter is
    its own work, part of the book (D42); a thesis and its article are two works (D43); the same text in two journals
    is linked to the one Mandumah holds, marked "same text" (D44).
  - **Every decision is a Desk decision** of `agent:librarian`: recorded, reversible, re-applied by every release.
- **The production librarian** ([experiment 71](../experiments/71_librarian_models/README.md), 2026-11-02): rules
  first, then **Gemini Flash** for the eight answer kinds where every model is near 100%, then **Claude Opus 5.5**
  for the rest, applied only when it says "high", the remainder to the Desk. On 522 verified decisions: **99.1%
  precise, 17% to a person, about $3 per 1,000 decisions** ($2.97 all items; $3.37 on the hard ones). Caveat: the
  gold was made by Claude too.

### Gates

Bridges are built journal by journal, like Garfield's first Web of Science (a fixed set of journals, complete),
starting with an **Education Citation Index**. Each gate measures how dense the bridges are and how much correcting
they need before we pay for the next one.

- **Gate 1, done (2026-10-22):** one journal, مجلة الطفولة العربية (0130), 126 articles, $24.24
  ([experiment 52](../experiments/52_journal_gate1/README.md)). With the librarian applied (2026-11-02): institutions in
  2+ articles **25 vs 6.3** for same-size random sets, shared cited works **121 vs 16.7**.
- **Gate 2, approved (2026-11-02):** ten education journals, 3,460 articles, about $456 expected
  ([experiment 54](../experiments/54_gate2_selection/README.md)). The owner's order: fix → re-audit → one journal → the
  nine others. **The one-journal pilot is running now** (experiment 70: مجلة الطفولة والتنمية, 0165, 363 articles =
  145 scans + 218 Word files, prompt v3.6 + the D30 guard, hard cap $55, about $40 expected; progress in
  `experiments/70_gate2_pilot/progress.md`). The nine others follow the owner's review of the pilot.
- **Gate 3:** the full slice, 162,816 EduSearch articles 2005–2025, about $43k now, about $86k after the 1 December
  price rise (estimate). The owner decides before 1 December.

## How the parts connect

```
 scanned page (S3) ──► Azure: every word + its box  (the text; never retyped)
                          │
                          ▼
         Gemini 4 Argon, prompt v3.6: answers in line ids only
         (each line's role, reading order, reference fields, document type...)
                          │
                          ▼
         code rules: build the article, repair what is safe, raise flags,
         the letter fix, the D30 guard, identifiers by code
                          │
                          ▼
         masters: JATS (the article) + ALTO (every word on the page)
         checked against the official DTD / XSD        ◄── the Word route
                          │                                (publisher's .doc → same JATS)
                          ▼
   platform database (the scan at the bottom, each run a sheet,
   a card index of people, works, institutions, journals) ◄── the catalogue
                          │
                          ▼
   the Desk: detectors and the librarian make decisions, correctors too
   (append-only, each with an owner)
                          │
                          ▼
   releases: machine reading + every decision, checked
                          │
                          ▼
   search (RAG chunks), metrics (times cited, h-index), the owner's pages
```

**Who does what.**
- **Gemini reads one article.** It sees the page images and Azure's numbered lines, and says what each line is and
  in what order. It never types the text (D30), and the guard keeps it from "fixing" what the author printed.
- **Code and the catalogue connect.** Our rules build the masters; the loader and linker (experiment 47) build the
  machine's bridges; the catalogue gives authority names, journal records and held works.
- **The librarian reconciles**, verified blind, applied only where it is measured at 98%.
- **People correct.** About 300 correctors who understand publishing, all equal. Each one *owns* the decisions they
  make; others leave notes and they settle it between themselves; an admin can fix anything. A pilot of 5–10
  correctors comes first (planned).

**The Word route** ([experiment 53](../experiments/53_word_route/README.md)). Many years of a journal exist only as the
publisher's Word file. Code alone turned 0130's 139 Word files into 139 valid masters. What Word lacks is the printed
page numbers after page 1, so those are estimates, flagged as estimates (D36). Gate 2's pilot is the first to run it
for real, with a Flash text-only step.

## The Desk and its pages

The Desk (experiment 49, [README](../experiments/49_correction_desk/README.md)) is the backend where everything can be
seen and corrected: append-only decisions, detectors, releases that re-apply every decision. Pages:

| Page | What |
|---|---|
| `/project` | the whole project at a glance: where we are, what waits on the owner, money, decisions (first page to open) |
| `/plan` | a timeline of everything: running, done, waiting on the owner, next; promises and releases (since 2026-11-02) |
| `/index-home`, `/journals`, `/institutions`, `/most-cited`, `/articles` | the citation index over the live release; each article beside its scan |
| `/explore` | the Explorer: every field of six kinds of record, sortable, exportable |
| `/how-we-collect` | the Guide: how each of the Explorer's 335 columns is collected (70 labels flagged for the owner) |
| `/librarian`, `/librarian/works` | the librarian's institution and cited-work decisions |
| `/audit` | nothing lost: every printed line followed into its field |
| `/pipeline` | one real page through the seven stages, animated on the scan |
| `/`, `/work`, `/works`, `/notes`, `/releases` | the correctors' Desk: tasks with the ink, work pages, notes, releases |
| `/pitch`, `/gate1/`, `/gate2/`, `/inventory/`, `/mindmap/`, `/views/…` | the shareholder deck, gate pages, the 235-field inventory, the mind map, articles beside their scans |

## Evaluations of other tools (2026-10-30/31)

- **Indra OCR** (Datalab, local CPU; [58](../experiments/58_indra_ocr/README.md)): 10.4% of words wrong against Azure's
  1.80%. Not a replacement; parked, and its licence likely rules it out.
- **Reducto** (hosted; [59](../experiments/59_reducto/README.md)): not adopted. It still changes letters (against D30),
  reads two-column Arabic left column first, and its free tier had no zero retention (49 pages were sent; deletion
  failed, so asking Reducto to delete them waits on the owner).
- **Claude Opus 5.5 vs Gemini Argon as the reader** ([60](../experiments/60_claude_reader/README.md), $30.78): **keep
  Argon**. Pages fully right 42/60 for Argon against 15/60 for Claude; 0 vs 21 wrong words. The side finding (Argon
  sometimes "fixes" a correctly printed word) led to the D30 guard.

## Shareholders

The owner presented the platform and the deck ([55](../experiments/55_shareholder_pitch/README.md), Desk `/pitch`) to
Mandumah's shareholders on 2026-10-28: "they love the product", and they asked for documentation.
[Experiment 57](../experiments/57_shareholder_docs/README.md) wrote both the same day: a 12-page business overview and a
31-page technical document, PDF, with real screens. They are confidential (Mandumah titles, names, scans) and wait
for the owner's read before they go out.

## Money (2026-11-02)

- **Gemini:** the log `experiments/43_rehearsal/out/gemini_spend.jsonl` stands at **$127.08** at 19:43 on 2026-11-02
  (it grows while gate 2's pilot runs): $100.15 up to 2026-10-22, then on 2026-11-02 the v3.6 check $0.80, the
  fix-rule check $3.16 and the gate 2 pilot so far ($22.99). The librarian model test's $3.27 of Gemini is in its own log.
  The owner **topped up £500 on 2026-11-02** on top of about £11 left; by estimate roughly £480 is left (check the
  console: the log is our record, not the bill).
- **Claude API:** $30.78 (experiment 60) + $3.19 (experiment 71) = **$33.97**, out of the owner's $250 of Claude
  credits.
- **Caps:** every paid experiment has its own owner-approved cap, enforced by the code before each batch (e.g. gate 2's
  pilot $55, the model test $10). Gemini prices double after 1 December (Argon) and 1 January 2027 (Flash).

## Where everything lives

| What | Where |
|---|---|
| The pipeline (prompt, rules, masters, judge, letter fix, D30 guard) | `experiments/43_rehearsal` (its README; outputs in `out/`) |
| The platform database | `/home/appuser/data/platform_v2/platform_v2.db` (experiment 47); backups in `backups/` |
| The Desk (correction backend) | `experiments/49_correction_desk`; web :8004, API :8005, PostgreSQL `inkdesk`; releases in `/home/appuser/data/desk/releases/` (live: R20261102T231619) |
| The plan and the project data | `experiments/49_correction_desk/desk/plan/plan.json` (written only through `desk.plan_cli`), `desk/project/project.json` |
| The catalogue | `~/data/marc/marc.db` (experiment 45) |
| What to extract, and where each field lives | [experiment 51](../experiments/51_extraction_inventory/README.md) (235 fields) |
| Spend | `experiments/43_rehearsal/out/gemini_spend.jsonl`, each experiment's own log (read them; never quote from memory) |
| Updates to the owner's phone | `~/bin/tg "text" [image]` sends a Telegram message (keys in the repo's `.env`, never printed) |

Everything the owner looks at goes through one tunnel, `ssh -N -L 9004:127.0.0.1:8004 prod`, then
`http://localhost:9004/` (use `localhost`, not 127.0.0.1, under WSL).

## The key decisions ([decisions.md](decisions.md))

- **D30** The text is the print as printed. A suspected misprint carries a flagged correction beside it; Azure's
  misreadings are fixed and recorded (the letter fix is one). The D30 guard enforces it against the model's "fixes".
- **D33** Metadata is corrected, with the printed form kept beside it and every change logged.
- **D34** A person's correction is a patch, never an edit to a master; it is re-applied on every rebuild.
- **D35** A table cell Azure did not read takes the model's reading, marked as added.
- **D36** Word-route page numbers are estimates, flagged as estimates.
- **D37–D44** The owner's reconciliation rules (above).
- **D45** Nothing printed is left as generic text when it has a field; identifiers are found by code.
- Since 2026-10-21 (the owner, experiment 49): decisions are append-only, "no" is stored too, every corrector owns
  their decisions, one key, no majorities; catalogue errors go out as a list, never into the catalogue. Since
  2026-11-02: agents verify each other; the owner looks only at urgent items.

## Where we are (2026-11-02)

- **Islands:** on 60 random pages of 300 unseen articles, 0 words wrong of 1,532, 43 pages fully right, 0 serious
  (proof pack + fix round 3, 2026-10-20/21). The extraction fixes went live on 2026-11-02 (release R20261102T231619):
  99.81% of lines in a field, 409 bad fixes refused, English twin affiliations no longer counted twice.
- **Bridges:** institutions and cited works reconciled by the verified librarian and applied (numbers above); the
  production librarian is designed (experiment 71).
- **The platform** holds 780 articles (the 600 random, gate 1's 126 and experiment 41's 54 shown).
- **Gate 2's pilot** on journal 0165 is running.

## What's next (from the Plan page)

1. Finish gate 2's pilot (0165), then the production librarian on its new people, institutions and cited works (cap
   $10, planned).
2. The owner's review of the pilot, then gate 2's other nine journals (about $456 for the ten, estimate).
3. Before scaling: the catalogue matcher in the linker, the same-work queue, each journal's coverage; the 217 cited-work
   links held below 98%; 22 institution types to re-decide; matching cited authors to the authority file.
4. A corrector pilot of 5–10 people; a dedicated server before gate 3.
5. Waiting on the owner (the Plan's "Needs you"): make the GitHub repo private (urgent); rotate the Reducto key and the
   Desk admin token shown in chat; read the shareholder documents; gate 3 before 1 December; and the older items
   listed in [handoff.md](handoff.md) section 000.
