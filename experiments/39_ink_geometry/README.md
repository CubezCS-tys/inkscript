# 39 — Ink as geometry, and rivers of paper (2026-10-12)

**Question.** The owner, thinking about how to "attack" a document: what does the traced ink geometry (the
"liquid round the letters", `src/inkscript/geometry/trace.py`) look like on very different pages, and can the
white space between the ink, the "rivers of paper", find a page's columns and blocks without a model?

**Method.** Seven pages (the fixture and experiment 38's pages: vowelled, magazine, Quran, table, equations,
two columns) traced with `trace.page_blobs`, redrawn from the outlines alone and compared dot by dot
(`look.py`, `report.py`). Ten pages run through `rivers.py`:
- Ink is smeared sideways so each line becomes a bar.
- Tall thin channels of paper (at least 8 lines tall) are column gutters.
- Flat channels wider than 1.7× the page's own median line gap are breaks between blocks.
- Long printed rules are walls.
- The ink left between them is a block.

Captions were written after looking at every image (`rivers_report.py`). Nothing paid.

**Result.**
- **Geometry:** 830–1,983 shapes and 18k–49k corner points per page. Redrawn from the shapes alone, a page
  matches 95.0–97.5% of the scan's ink. What is missed is letter edges and the scanner's dark page border.
  Shapes are islands of ink, not letters.
- **Rivers, what they get right:**
  - columns on every two-column page;
  - body and references, split by a printed rule;
  - equations, footnotes and a table, each its own block;
  - a table's column gaps, which show as gutters;
  - the two halves of a verse.
- **Rivers, what they miss:**
  - a single column whose headings and footnotes are marked by size, indents or short rules rather than space;
  - bulleted points;
  - grey photos, which count as paper.

**The other senses** (`senses.py`, `senses_report.py` → `out/senses.html`). On the two pages where the rivers saw one block,
every Azure line was labelled from the ink and Azure's words alone, without using the page's hand labels and with no model.
- Signals from the ink: letter size, stroke thickness, spacing above, indents, a short rule.
- Signals from Azure's words: a leading dash, numbering, footnote numbers that match markers in the body.
- Every line came out right on both pages:
  - the header row;
  - paragraphs;
  - the numbered heading, with strokes 1.23× the page's own;
  - the verse;
  - the footnotes under the rule, with letters about 0.9×;
  - the bullets and their continuations;
  - the page number.
- This is a demonstration, not a measurement. The rules were tuned on these two pages in four rounds.

**What it changes.** It is a thinking aid for the owner's "map" idea: the ink is a model-free survey of the page.
The rivers give exact edges and columns; a model that sees the whole page names the blocks and covers what white
space does not show. Nothing in `src/` changed.

**Outputs** (gitignored):
- `out/report.html`: the geometry, scan beside shapes beside redraw, plus close-ups.
- `out/rivers.html`: the ten river pages.
