# Hand-made test masters (experiment 35)

**These are not archive pages.** The 205 archive masters have no structured tables and no equations; the future
Kraken + VLM reading stage will write them. These two small articles were written by hand in the shape
`experiments/32_open_stack/research/02_formats.md` proposes, so every edition writer can be tested on tables and
maths now.

| id | pages | what it tests |
|---|---|---|
| `test-0001-table-math` | 2 × A5 | title, author, two headings, a footnote linked by `<xref ref-type="fn">`, a Latin citation and Western digits inside Arabic text, an `<inline-formula>` (MathML + LaTeX), two `<disp-formula>` with `<label>` and `<alternatives>` (MathML `display="block" dir="rtl"`, `<tex-math>`, `<graphic specific-use="scan-crop">`), one with a fraction, a sum with limits, sub- and superscripts; a table with a two-row header, a `colspan` and two `rowspan`s, row-header cells, cells in reading order |
| `test-0002-two-columns` | 1 × A4 | a two-column page (the right column is read first), an inline formula, a 4-column × 7-row table (two header rows with merged cells, a row-header column), a footnote |

Each article has the files a real master has: `<id>.jats.xml` (JATS 1.4 Archiving, MathML3; valid against the
DTD), `<id>.alto.xml` (ALTO 4.4; valid against the XSD), `<id>.pdf` (stands in for the faithful PDF: its page
renders as the "scan") and `<id>.crops/` (the scan crops the JATS `<graphic>` elements point at).

How they were made (`experiments/35_edition/testdocs/make_testdocs.py`): each page is typeset as HTML in Chromium
153 (Noto Naskh Arabic on a greyish paper, MathML for the formulas, a real HTML table), every word's box is
measured in the browser (`Range.getBoundingClientRect`), the page is screenshot at 288 dpi, blurred and given a
little noise, and stored as a grey JPEG at 2/3 of that inside the PDF. ALTO pixels are 288 dpi. The JATS is
written from the same spec; the text is the spec's, so every word is `trust.agreed`.

Conventions they follow (and the edition writers rely on):

- table: `<table-wrap id="p2t1">` with `<caption><p id="p2b4">`, then `<alternatives>` holding the scan crop
  `<graphic>` and the XHTML `<table>`; cell ids `p<page>t<n>c<row><col>` from the cell's place in the grid; in
  ALTO a `<ComposedBlock TYPE="table" ID="p2t1">` holding one `TextBlock` per cell (ID = the cell's id) and the
  caption's `TextBlock` (ID = the caption paragraph's id);
- display formula: `<disp-formula id="p1eq1">`; in ALTO an `<Illustration TYPE="formula" ID="p1eq1">` (no words);
- inline formula: `<inline-formula>` in the paragraph; in ALTO its symbols are `String`s of the paragraph's lines
  tagged `kind.formula` (an `OtherTag`), so a word check can tell them from text.

What did not validate as 02_formats wrote it: `<processing-meta>` is a child of `<article>` before `<front>`
(02 showed it inside `<front>`); `dir` is not an attribute of the JATS XHTML `<table>` (the direction comes from
`xml:lang="ar"`, and the cells are in reading order). `dir="rtl"` on `mml:math` is valid.

Regenerate: `.venv/bin/python experiments/35_edition/testdocs/make_testdocs.py` (needs a Python with playwright:
`PW_PYTHON`).
