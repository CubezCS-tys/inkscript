# Experiment 48: shared brief for every probe agent

You are one of several agents running a breadth-first probe of the "Web of Science" direction of this project:
linking, identity and correction. Each probe answers four questions for its direction:

1. **Can we?** Does a method work on our data at all?
2. **How well?** Measure it against a **seeded random sample you judge yourself** by reading the evidence. Report
   right / wrong / unsure with counts and a 95% Wilson interval, and say plainly that you, an agent, judged it.
3. **What does it cost?** Time, memory, and any external calls.
4. **What is left for people?** How many decisions per article stay uncertain, and what a person would need to
   see to make each one. Project this to 1,000,000 documents and a team of 300 correctors who understand
   publishing.

Report failures beside successes, with the numbers and where they came from. Precision matters more than recall
here: for citation counts and h-index, a wrong link or merge is worse than a missing one.

## The project in three lines

Mandumah (دار المنظومة) holds about 1M scanned Arabic scholarly articles. Our pipeline turns each into a JATS +
ALTO "master" (structure + every word's box on the scan). The goal is a Web-of-Science-depth index: who cites
whom, the same person and work across articles, institutions, journals, then metrics.

## Data (all on this machine; read-only unless your brief says otherwise)

- **Platform v2** `/home/appuser/data/platform_v2/platform_v2.db` (SQLite). As of 2026-10-21 it holds **all 600
  sample articles**:
  - the first 300, run `v33_300_final`;
  - the exam 300, run `v33_300b_fix3`, loaded as kind final, so it is the shown version for its own stems;
  - the 55 (`v2_55`); and raw runs beside them.

  Use the shown versions: `versions.is_current = 1`. Design: `experiments/47_platform_v2/DESIGN.md`, schema
  `schema47.sql`, build notes `README.md`, independent check `VERIFY.md`. Useful tables: `citation_mentions`,
  `cited_works`, `cited_work_members`, `cited_work_authors`, `citation_links`, `work_relations`, `persons`,
  `person_authorities`, `person_names`, `byline_mentions`, `authorships`, `affiliation_mentions`,
  `affiliation_links`, `institutions`, `institution_names`, `journals`, `journal_titles`, `journal_issns`,
  `publications`, `catalogue_records`.

  **Open it read-only:** `sqlite3.connect("file:...?mode=ro", uri=True)`. Do not write to it.
- **Mandumah's MARC catalogue** `/home/appuser/data/marc/marc.db` (10 GB SQLite; 1,558,415 records). Open it with
  `?mode=ro&immutable=1`. Tables:
  - `records` (one per record; `rec` is the key; 999 $c is unique, 001 is not);
  - `authors` (name, name_folded, latin, role, authority_id);
  - `keywords`, `subjects`, `pdf_ids` (stem ↔ rec);
  - `fields` (every raw subfield);
  - `fts` (FTS5 over title, authors, keywords; Arabic-folding tokenizer).

  Notes: `experiments/45_marc_db/README.md`, helper `experiments/45_marc_db/marcq.py`.
- **The masters** (JATS + ALTO):
  - `experiments/43_rehearsal/out/v33_300_final/masters/` and `.../v33_300b_fix3/masters/`;
  - page images: `experiments/43_rehearsal/out/pages/<stem>_pNNN.jpg`.
- **Existing linker:** `experiments/47_platform_v2/link47.py`, which builds cited works, links, back references,
  persons and institutions. Read it before inventing something; your job is to measure, extend and stress it, not
  to duplicate it.
- **The proof pack's hand-scored citations** (independent agent, 2026-10-20):
  `experiments/43_rehearsal/out/proof/` (`cites_score.json`, `ibid_score.json`, `meta_score.json`).

## Rules (each has cost a day when broken)

- **Python:** `/home/appuser/inkscript/.venv/bin/python`.
- **Write only inside `experiments/48_linking_probe/`:** your code in `experiments/48_linking_probe/<probe>/` and
  your outputs in `experiments/48_linking_probe/out/<probe>/` (gitignored).
- **Never edit** `src/`, any other experiment, `CLAUDE.md`, `docs/`, or anything under `/home/appuser/AI-Search*`.
- **This server is production** (62 GB, the live search engine uses most of it). Keep your process under 2 GB of
  memory: stream, don't load the 10 GB catalogue into RAM, and use indexed lookups or FTS. Check `free -g` before
  any big step. Run one heavy job at a time. Never touch the services `rag-*`, `qdrant`, `mysql`, `redis` or
  `nginx`.
- **No paid calls.** No Gemini, OpenAI or other paid API. If a step would need a model to be good, design it,
  estimate its cost and say so; don't run it.
- **OpenAlex and Crossref are allowed** (owner, 2026-10-21) and **must be evident**:
  - Log every request (time, URL, status, what it was for) to
    `experiments/48_linking_probe/out/<probe>/external_calls.jsonl`.
  - Mark every result that came from them with `source: "openalex"` or `"crossref"`, in your data and in your
    report.
  - Be polite: at most 5 requests/second for OpenAlex, 2/second for Crossref; set a User-Agent of
    `inkscript-probe/0.1`. Do **not** put any email address in requests.
  - Send only citation strings or titles/authors, never document text.
  - Cache responses on disk.
- **Save as you go.** Write each finished result to disk as you produce it, so a stopped session loses nothing.
  Keep a `progress.md` in your out folder with what is done.
- **Private data.** The catalogue, the masters and the databases are Mandumah's private data: nothing goes to
  GitHub or any public link.
- **Commits:** none. The orchestrating session commits.

## What to hand back

1. `experiments/48_linking_probe/out/<probe>/results.json`: the headline numbers.
2. `experiments/48_linking_probe/out/<probe>/examples.json`: 10–20 real examples, good and bad, each with the
   evidence: the citation as printed (with stem, page and note id), and what it was matched to (catalogue rec /
   999$c, OpenAlex id, DOI).
3. `experiments/48_linking_probe/<probe>/NOTES.md`: method, results, failures, the human workload estimate, and
   what you would do next, in plain words.
4. A short final message: the answer to the four questions in under 300 words.
