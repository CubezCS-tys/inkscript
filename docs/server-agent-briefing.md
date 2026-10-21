# Briefing for the server agent (from the owner, 2026-10-21)

You are taking over development of this project on my server. Until today it was developed on my laptop by
Claude Code with many sub-agents. All the code and docs are in this repo. The data (results, databases, the
catalogue) is being copied from the laptop now, with `ops/pack_v2.sh`, over about a day. **Read this whole message
first, then read the files listed at the end, and only then do anything.**

## What we are building, in one sentence

**A Web-of-Science for the Arabic-speaking world, built on Mandumah's archive**: every article, thesis and journal
issue Mandumah holds is turned into a clean, structured, searchable, citable digital document, and those
documents are linked into an index of who wrote what, who cites whom, which institutions and journals, with every
fact traceable back to the ink on the scanned page.

## Who we are and what we have

- My father and I run this together. Mandumah (دار المنظومة) is the largest Arabic academic database: journals,
  theses, conference papers, going back decades. Much of it exists only as scanned print.
- **What we hold:**
  - **1,013,912 documents** in S3 that have both a PDF and Azure's OCR (Azure Document Intelligence). Bucket map:
    experiment 44.
  - Another **308,593** that are PDF only (`legacy/`).
  - **Mandumah's MARC catalogue: 1,558,415 records**, which name **3.2 million PDFs** (1.8M of them are
    dissertation chapters).
    - It is a 10 GB SQLite database at `~/data/marc/marc.db` (experiment 45).
    - **999$c is the unique key**; 001 is not unique.
    - It has an author authority file, which is gold for telling people apart.
  - Qdrant backups: `mandumah_v2`, 15.7M vectors from the current search engine. There are also MySQL
    `ai_search_feedback` dumps.
- **Private data rule:** the catalogue, the platform databases and the documents are Mandumah's private data.
  - They never go to GitHub.
  - They are never exposed on a public link.
  - The browse pages listen on 127.0.0.1 only.

## Why this is worth doing

The big citation indexes (Web of Science, Scopus, Dimensions, OpenAlex) barely see Arabic scholarship. Clarivate's
Arabic Citation Index exists but is shallow: metadata only, and none of the footnotes, which is where Arabic
scholarship does its citing. Mandumah has the depth no one else has. If we can extract it reliably, we can build
the index nobody else can.

We think of it as **five layers**, each one proven before we scale, each with a well-known model to copy:

| Layer | What it is | The model we copy |
|---|---|---|
| 1. Digitisation | the scan plus its text, faithful | JSTOR / Portico |
| 2. Structure | each article as structured XML: headings, paragraphs, notes, tables, equations, verse, pictures, references | PubMed Central (JATS) |
| 3. Publication | readable versions: web page, re-flowed PDF, layout PDF, Markdown, JSON | ScienceDirect / Atypon |
| 4. Metadata and index | clean title, authors, affiliations, journal, issue, year, pages; persistent ids | Crossref / Scopus |
| 5. Citation index and analytics | who cites whom, times cited, self-citation, authors, institutions, journals | **Web of Science**, Scopus, Dimensions, OpenAlex |
| (+) Data for AI | clean structured Arabic scholarly text | Semantic Scholar / CORE |

**Layer 1 is mostly given:** Azure's text exists for a million documents and is very accurate. We treat Azure's
words as the text and do not retype them. **The work is layers 2–5.**

## How the extraction works (layers 2–4)

1. **Azure** gives every word on every page with its box. Lines are numbered.
2. **Gemini 4 Argon** looks at the page images plus Azure's numbered lines. It answers **only in line ids**: which
   lines make a heading, a paragraph, a footnote, a table cell, a verse half, a picture caption; the reading order;
   which lines are noise (show-through, page furniture). It can also propose corrections to Azure misreadings.
   - It never types the text itself. When it did, it quietly "fixed" the author's misprints and added hamzas, so we
     stopped that.
3. **Our code rules** (`experiments/43_rehearsal/rules43.py` and others) build each article from Azure's words in
   Gemini's structure.
   - They repair what is safe: guillemets, verse halves, note links, table cells, swapped boxes.
   - They raise **flags** where something looks wrong.
4. **The masters**: each article becomes a **JATS XML** file (the structure) plus an **ALTO XML** file (every word
   with its box on the page). Every output format is generated from these two.
   - Every master is checked against the official JATS DTD and ALTO XSD.
5. **The judge**: Gemini looks again at flagged pages (and a random sample) and proposes fixes.
   - A fix is applied automatically only with **two keys**: the judge's confidence ≥ 0.85 **and** a code check that
     agrees.
   - Everything else is a proposal recorded for a person.
   - Patches rank person > judge > gemini-retry > rule, and are re-applied on every rebuild.
6. **Metadata** (title, authors, affiliations, year, pages) is taken from the page and checked against the MARC
   catalogue.
   - Disagreements are kept as a list for Mandumah.

**Rules that must not be broken** (all in `docs/decisions.md`):
- **D30: body text and abstract stay as printed.** A misprint is flagged and a correction proposed, never silently
  changed. Azure's misreadings *are* fixed, and the fix is recorded.
- **D33: metadata is corrected, the printed form is kept beside it, and every change is logged.**
- **Nothing is overwritten.** A correction is a new reading beside the old one.
- **Prompt v3.3 is the live prompt** (hash d6b2156150), with thinking LOW. HIGH cost 2.6× with no gain.

## The platform database (layer 5, Web of Science style)

Experiment 47, `experiments/47_platform_v2/DESIGN.md`. **Read it.** In short, picture **a light table**:

- **The scanned page is the bottom layer and never changes.** "Page 3, Azure words 120–131" is an **ink anchor**,
  a permanent address for a piece of ink.
- **Each extraction run is a clear sheet laid over the page.** Several runs lie side by side, and one is marked
  "shown".
- **Beside it is a card index of things:** publications, journals, issues, people, institutions, cited works
  (including books Mandumah doesn't hold).
  - **A mention is not an entity.** A printed name or citation is a mention, kept exactly as printed. A person or a
    work is an entity.
  - A link between them records how it was made, how sure it is, and who made it.
- **«المرجع السابق» / ibid. / op. cit.** resolve to the first full citation of that work in the article (chains
  collapsed) and count as another citation of that work. They are not links.
- **Counts such as times cited are never stored.** They are computed fresh from the links.
- **What only we can do:** "show me the ink" behind any value; a corrections ledger; metadata as printed beside as
  corrected beside the catalogue; a trust score on every value.

**Current state:**
- An independent checker passed v2 on **11 of 11 checks**, and the small gaps it found were fixed.
- **IDs are stable across rebuilds:** builds in different orders give identical results in all 81 tables.
- The older v1 database (experiment 46, `~/data/platform/platform.db`) holds all runs including the exam.

## Where we are (as of 2026-10-21)

**The path so far:**
- Experiments 1–39: the original "ink" PDF idea, open-source readers, layout models.
- Experiments 40–41 (15 Oct): Gemini on Azure lines wins.
- Experiment 43: the rehearsal, which is the main line now.

**Experiment 43:**
- **First 300 articles:** run, judged, fixed (`out/v33_300_final`).
- **The exam:** a second 300 the pipeline had never seen, with everything frozen beforehand (`out/v33_300b`).
  - 300/300 answered, 300/300 valid masters.
  - **Cost $31.94: about $0.106 an article.** At today's price that is about **£96k per million documents incl.
    VAT**. Gemini prices **double on 1 Dec 2026**.
- **The proof pack:** an independent agent drew random pages and checked them beside the scan
  (`out/proof/proof.md`).
- **Fix round 3:** the proof pack's failures fixed at the root (`out/v33_300b_fix3`). Accuracy now, on random,
  unseen pages:

| What | Now |
|---|---|
| Wrong words | **0 of 1,532** |
| Pages fully right | **43 of 60** (72%); the rest are small slips |
| Pages with a serious error | **0 of 60** |
| Articles with all metadata right | **25 of 30** (authors 29/30, pages 30/30) |
| Citations fully right | **57 of 80**: filled fields 313/314 right; the faults are missing fields |
| «المرجع السابق» resolved right | 13 of 15 in the v2 database, 0 wrong |

**Weakest areas:**
- citations, with fields left empty;
- small structure slips;
- italics, sub- and superscript, which Azure doesn't give;
- the remaining table flags.

## Where we are going

In order. **Each step needs my go**, and every paid step has a cap.

1. **Settle on the server.** Check the copy, run the tests, start the browse pages, look at results. *No paid
   calls.*
2. **My open decisions** (don't decide them for me):
   - **The ~3,000-article step:** about $320, which needs a top-up. It is the first real test at scale and gives
     tight accuracy numbers.
   - **Two judge calls:**
     - **0732:** keep the "another article" mark on the bottom strip everywhere?
     - **0849 p4:** should the second show-through line be removed?
   - **Prompt v3.5:** v3.3 plus only v3.4's two content lines, a small paid test. v3.4 fixed inline maths and lost
     letters, but shredded an advert and merged paragraphs twice.
3. **Citation linking: the next big focus.** It will:
   - join the same cited work across articles;
   - link cited works to Mandumah's own documents and the catalogue;
   - build people and institutions from the authority file;
   - then compute times cited, self-citation and coverage.

   This is what turns a pile of good documents into a Web of Science.
4. **Then scale:** 3,000 → the archive (about 1M documents), in waves, with a budget per wave. That will need
   outputs stored in a bucket rather than on disk, and a decision on running before the 1 Dec price rise.

## How to work with me

- **I think visually.** Show results as pages with real examples beside the scan, not tables alone. Describe a
  choice by what the result looks like, not by data structures.
- **Look before you report.** Open and look at the pages yourself before saying something is good. Counts and
  agents' spot checks have been wrong before.
- **Agents do the work; you orchestrate.** For long jobs, have agents save each result to disk as they go, and
  watch them for stalls.
- **Money:**
  - Gemini spend is read from the live log `experiments/43_rehearsal/out/gemini_spend.jsonl`, never from memory.
    It was **$73.62** since the 18 Oct top-up of £101.28 incl. VAT, so about £35 is left.
  - The budget in pounds = log dollars converted, plus 20% VAT.
  - **No paid call without my go and a cap.**
- **Deletions:** propose them; don't do them.
- **Don't push to GitHub without asking.**
- **Report honestly:** failures beside successes, with the numbers and where they came from.

## Read next, in this order

1. `CLAUDE.md`
2. `docs/handoff.md`: section 00 (since 15 Oct), then section 1
3. `docs/STATUS.md` (the top)
4. `experiments/43_rehearsal/README.md`: the headings, then "The exam" and "Fix round 3 (proof pack)"
5. `experiments/43_rehearsal/out/proof/proof.md` (once copied)
6. `experiments/47_platform_v2/README.md`, `DESIGN.md`, `VERIFY.md`
7. `docs/decisions.md` (D30–D35)
8. `docs/moving-to-a-server.md`: the "first hour" checklist

**Then tell me, in plain words:**
- what you understood the project to be;
- what state the server copy is in;
- what you would do first.

Don't change anything until I say so.
