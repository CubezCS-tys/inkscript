# Glossary

**Azure word / box** — one word of Azure Document Intelligence's reading with
its polygon on the page. The unit everything is matched to.

**Blob** — one connected component of ink, traced as outline polygons with
holes (`geometry/trace.py`). Dots and hamzas are their own blobs.

**Rule** — a long straight line (table border, underline) separated from the
ink before blobs are formed; never glyph ink.

**Run** — a stretch of letters the script joins: `المعجم` is two runs, `ا` and
`لمعجم`, because alef never joins the letter after it.

**Piece** — the ink of one run (or of several runs that touch in the ink),
with its text. The unit the letter cutter works on. One glyph unless it is cut.

**Letter-form** — a letter in one of its four shapes: isolated, initial,
medial, final. The atlas and the font are keyed by (letter, form). Lam-alef
(`لا`) is one unit.

**Pen path / trunk** — the centre line of a piece from its first letter's foot
on the baseline to its left end. Everything else hangs from a trunk point.
**Strip** — the piece unrolled along the trunk; a cut is a position on it.

**Candidate** — a thin place on the path where a cut is allowed.

**Facts** — what must be true of a letter's stretch whatever the typeface:
its dots and hamza, a tall stroke, a bowl below the baseline, not being a bare
connector. **Reliable** — a fact is enforced for a letter-form only if 85% of
its occurrences in this document show it.

**Atlas** — the document's own mean picture of every letter-form, learned from
its cut letters. **Likeness** — overlap of a letter with its atlas picture
(0–1, softened). **Rounds** — cut, rebuild the atlas, cut again.

**Verdict** — why the witnesses doubt a cut (`letters_why` in the build
report). Reported, not enforced (`CUT_ALL`).

**Cell** — a letter's stretch of the baseline in page x: its selection box.
Its **ink** may overhang the cell.

**Letter coverage** — share of Arabic words (2+ letters, no vowel marks) in
which every letter has its own box in pdfium. Says boxes exist, not that they
sit right.

**Equal slicing** — what Chrome does with an uncut glyph: the box divided
evenly among its characters. The baseline every cutter must beat.

**Words intact / lines in order / inversions** — the `--verify` numbers: a
word copies out from pdfium exactly; a line's words come out in reading order;
adjacent lines of a column swapped. Words intact ignores order.

**Stored (visual) form** — text written into ToUnicode so that pdfium's line
reconstruction gives the logical reading back (`text.visual`, inverse of
`text.chrome_reads`).

**Faithful PDF / vector PDF** — `<stem>.pdf`: the scan with invisible ink
glyphs over it. `<stem>_vector.pdf`: the glyphs alone, visible — "the original
font as the text".

**Born-digital page** — a page that already has real text; left alone. **Junk
font** — a typeset font whose encoding gives nonsense; its text is neutralised
with `/ActualText`.

**Shape alphabet** — shapes recurring across a document (`shapes.json`,
`/InkShapes`). Knowledge about the ink; never used to draw.

**Restored glyph / restored edition** — a letter voted from many printings
(exists, in the font); a page redrawn with such letters (an idea).

**Fixture / reference document** — `tests/fixtures/0582-004-009-012`, five
pages of a heavy old face; the document most things were tuned on, so its
numbers flatter.

**Trust mark** — one per word with a letter or digit (`enrich/trust.py`):
*verified* (a Quran verse or a second reader agrees), *flagged* with reasons
(low confidence, speck, ornament, Latin, Persian letter, Quran difference,
Gemini disagrees), or *agreed* (no signal). Written in the ALTO file and shown
in the `_trust.pdf`.

**JATS / ALTO** — the two document files `--xml` writes (D20): the article as
publishers keep it (JATS 1.4, `<stem>.jats.xml`) and every page, line and word
with its box as libraries keep OCR (ALTO 4.4, `<stem>.alto.xml`). Word ids are
`p<page>w<nnnn>`, block ids `p<page>b<n>`, shared by both files.

**Reference / citation** (owner, 2026-10-22, as Web of Science uses them). The direction matters.
- A **reference** is what *this* article cites: its outgoing list (WoS "Cited References"). On a screen it is
  "References (n)".
- A **citation** is another article citing *this* one: incoming (WoS "Times Cited", "Citing Articles"). On a
  screen it is "Cited by (n)". Times cited, h-index and impact factor count citations.
- Platform v2's internal names predate this rule and stay as they are:
  - `citation_mentions` holds the *references* printed in each article;
  - a `cited_works` card is one work as referenced by many articles;
  - its "times cited" is the number of articles whose references point to it.
- Screens, reports and docs use reference for outgoing and citation for incoming.

**Linking and correction (2026-10-21/22; the picture in [overview.md](overview.md)).**

**Island** — one article made complete on its own: its words as printed, structure, metadata and references
(extraction).

**Bridge** — a connection between islands: the same person, institution, journal or cited work across articles, or
a citation of one article by another. Judged by precision, since a wrong bridge corrupts every count above it.

**Gate** — a measured step of the Education Citation Index: gate 1 one journal (exp 52, done), gate 2 about 10
education journals (exp 54), gate 3 the full slice. Each measures bridge density and correction load first.

**Education citation index** — the first product slice (owner, 2026-10-22): education journals, journal by journal
and complete for a span of years, as Web of Science began in 1961; 162,816 EduSearch articles 2005–2025 in the bucket.

**The Desk** — the correction backend for about 300 correctors (exp 49): a people's sheet of decisions over the
machine's reading, with a task queue and releases; web on :8004, API on :8005, PostgreSQL `inkdesk`.

**Decision (append-only)** — one correction on the Desk (who, when, why, the evidence seen), keyed to stable ids,
never edited or deleted; a change is a new decision that supersedes it. "No" ("not the same person") is stored too.

**Owner of a decision** — the corrector who made it. Only they, or an admin, can supersede or revert it; anyone
else leaves a note. All correctors are equal; there is no second key or majority (owner, 2026-10-21).

**Task** — a question put to a corrector (e.g. "possible same work"), made by a detector, ordered by impact ×
uncertainty, leased so no two people take it.

**Detector** — code that runs on a release and writes tasks of one kind, only for subjects with no standing
decision.

**Release** — a build of the platform data: the machine reading plus every accepted decision, then checks. Metrics
and search read only releases.

**v3.5b** — the prompt used from gate 1 on (2026-10-22): v3.3's structural text word for word, plus the 37
inventory fields in a separate "enrich" part and the honorific line, without v3.4's two content lines; about 15% more
a page than v3.3.

**The Word route** — building the same JATS masters from the publisher's Word file instead of a scan (exp 53), for
years that exist only in S3 `legacy/`; page numbers past the first are estimates, flagged (D36).

**Letter fix** — Azure's Persian look-alike letters (ی ک ھ ہ ڪ) on Arabic pages written as the printed ي / ى / ك / ه,
each recorded as a reader fix with Azure's word kept (D30; exp 43, 2026-10-22).

**Work vs edition** — a *work* is an author plus a uniform title, and is what citation counts and h-index count; an
*edition* (translator, editor's تحقيق, publisher, place, year, edition number) is one form of it, and is the level a
catalogue record describes (exp 48 probe B).

**Document type** — what kind of item an article is (research, review, editorial, book_review, report,
conference_paper, thesis_summary, interview, news, …), read by v3.5b and written to JATS `@article-type`; before it
every master was "research-article".
