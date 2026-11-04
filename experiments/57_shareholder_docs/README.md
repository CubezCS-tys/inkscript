# Experiment 57: documentation for the shareholders

**Question** (owner, 2026-10-28). The owner presented the platform and the deck to Mandumah's shareholders: "they
love the product", and they asked for documentation to read. Two PDFs, written in parallel by two agents from the
same sources, with real screenshots of the platform (the owner approved real screens: Arabic titles, author names,
scans; the documents stay among the shareholders):

- **Business document** (8–12 pages, non-technical): `business/`, PDF in `out/`.
- **Technical documentation** (20+ pages): `technical/`.

Both are **confidential**: they hold Mandumah titles, names and scans. Keep the PDFs, the screenshots and the HTML out
of commits and off public links. `out/` and `business/out/` are gitignored (`experiments/*/out/`); `business/img/` and
`business/business.html` are **not**, so leave them out of any commit (or add them to `.gitignore`).

## The business document (`business/`)

**Output:** `out/Mandumah_Citation_Index_Business_Overview.pdf`, 12 A4 pages, written 2026-10-28. Data status as of
2026-10-26 (the project page).

**Sections:** cover · 1 Executive summary · 2 The problem and the opportunity · 3 What Mandumah uniquely holds ·
4 What we built: two products from one dataset (islands → bridges → gates, with a diagram) · 5 Proof: accuracy,
gate 1, cost per article (tiles and bars) · 6 The platform: a guided tour (screens 1–7) · 7 Quality and trust (the
Desk, the field guide, the AI librarian; screens 8–9) · 8 Market and competition (table) · 9 How it could make money
(proposals) · 10 Roadmap and costs · 11 Risks and open questions · 12 Next steps and decisions needed · appendix:
glossary and 13 compact endnotes.

**Sources.** Every number comes from `experiments/49_correction_desk/desk/project/project.json` (the verified
project data), the pitch (`55_shareholder_pitch/story.md` and the deck `/pitch`), `docs/overview.md`, and the
READMEs of experiments 49, 52, 53, 54 and 56 (with `56_librarian_institutions/out/numbers56.json` and
`scale56.json`). Nuances kept: reference = outgoing, citation = incoming; gate 1 figures are the live platform's (32
citations inside the journal, 15.8% vs 2.4% held), with experiment 52's catalogue matcher (39, 16.9% vs 2.9%) as the
fuller, not-yet-wired figure; institutions 6.8× with the machine's links, about 4× with the librarian (proposals,
not applied); times cited counts only the 780 articles read; ARCI does carry references; prices, demand and server
costs not researched; Gemini's 1 December price doubling. Estimates and proposals are labelled on the page.

**Screens** (fresh, 2026-10-28, live Desk at :8004 on release R20261023T005909, 1440 px wide at device scale 2,
signed in as a test corrector `agent:docs-business`; opening `/work` leased task 1569 to it for 15 minutes):
`/index-home`, `/journals/J0130`, `/articles/0130-018-072-003?tab=text&view=beside` (scrolled to the two panes),
`/explore`, `/persons/A8STQEWEAV`, `/work`, `/project`, `/how-we-collect`, `/librarian`. The first attempt at the
article page returned a transient 500; a retry was clean.

**Build:**
```
PW=<a Playwright venv with chromium-1243>            # e.g. the scratchpad venv used on 2026-10-28
$PW/bin/python business/shots.py <token-file>        # raw screenshots -> business/img/*.png
$PW/bin/python business/shot_beside.py <token-file>  # the article beside its scan
49_correction_desk/.venv/bin/python business/crop.py # crops -> business/img/web/*.jpg (2000 px)
$PW/bin/python business/build.py                     # HTML -> out/...Business_Overview.pdf (A4, page numbers)
PYTHONPATH=49_correction_desk/.venv/lib/python3.12/site-packages \
  /home/appuser/inkscript/.venv/bin/python business/build.py --png   # pages -> business/out/pages/ (pypdfium2)
49_correction_desk/.venv/bin/python business/sheet.py 12            # contact sheet business/out/sheet.png
```
Fonts are local (Noto Sans, Noto Naskh Arabic); nothing is loaded from the network. Arabic is set in `<bdi lang=ar>`
so it stays right-to-left inside English sentences. Every page was rendered and looked at.

**Left out (could not be sourced):** any price, buyer, demand or revenue figure; server, storage-hosting and
correctors'-time costs (stated as not priced); the "313 of 314 filled reference fields right" figure from the
deck (STATUS gives 313/341 with 0 wrong; the document says only that the faults are empty fields, not wrong values).

## The technical documentation (`technical/`)

**Output:** `out/Mandumah_Citation_Index_Technical_Documentation.pdf`, **31 A4 pages**, written 2026-10-28; data as of
release `R20261023T005909` and the project page of 2026-10-26. Page renders for review: `out/tech_pages/page-NN.png`.

**Sections:** cover · contents (with page numbers) · 1 Summary and scope (incl. the inkscript ink-glyph PDF roots) ·
2 System overview · 3 Data sources · 4 The reading pipeline (prompt v3.5b fields, what the model may not do, code
rules, letter fix, masters, judge and patches, cost, accuracy and how measured) · 5 The Word route · 6 The platform
data model (two layers, ids, versions, table groups, schema diagram) · 7 Linking · 8 The Desk (architecture, records,
ownership, tasks/leases, detectors, releases, incremental checks, auth, tests, pages) · 9 Quality and verification ·
10 The AI librarian · 11 Metrics · 12 Operations and security · 13 Scaling (estimates, labelled) · 14 Known
limitations · 15 Technical roadmap · appendices A glossary, B decisions, C every platform table with row counts.

**Figures:** 6 inline SVG diagrams (flow, light-table layers, Desk architecture, release steps, gates) and 13 screens:
the schema page (:8003, three crops), "show me the ink", article beside the scan, All fields, a work task (reused
from the P2 walk-through: opening the live Work page would claim a task lease), project page, Explorer, field guide,
releases, librarian, index overview, journal J0130, author record.

**Build:** `technical/doc.html` (source; fonts Noto Sans / Noto Naskh Arabic / DejaVu Sans Mono, all local) →
`technical/build.py` (Playwright `page.pdf`, finds each section's page with pypdfium2, writes the contents, prints
again, renders PNGs; writes `technical/doc_built.html`). Screens: `technical/shots.py` (signs in as the corrector
`agent:docs-tech`, token read from a mode-600 file outside the repo; read-only pages only) and
`technical/schema_shot.py`. `technical/table_counts.json`: row counts read read-only from the release copy.

**Sources:** docs/overview, architecture, runbooks, decisions (D29–D36), glossary, STATUS, pipeline; READMEs of
experiments 41, 43, 44, 45, 47 (+ DESIGN.md, schema47.sql), 48, 49 (+ DESIGN.md), 51–54, 55 (caveats), 56;
`desk/project/project.json`; `desk/index_pages.py` (metric definitions); the field guide's `labels_to_review.md`.
Where sources disagree both figures are given (gate 1: 39 / 16.9% with probe A's matcher vs 32 / 15.8% linker-only;
institutions baseline 3.6 vs 3.8).

**Left out (could not be sourced):** server, storage and people costs (never priced); ARCI's current size; gate 3's
$43k derivation is shown as the project's own reconstruction; the full current Desk test count (47 is the last
recorded run, 2026-10-23).

**Private:** `technical/img/`, `technical/doc.html` and `technical/doc_built.html` hold Mandumah titles, names and
scans and are not gitignored: keep them out of commits.
