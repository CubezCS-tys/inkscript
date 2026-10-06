# Decisions

Choices between alternatives, with the evidence. Newest last. If you are about
to undo one of these, the reason it was made is here; if the evidence has
changed, add a new entry rather than editing the old one.

**D1 · Gemini reads page 1 only; Azure reads the rest (2026-09-14).** The team
wanted Gemini only for the front page: title and author are what Azure gets
wrong and what Gemini gets right. Gemini's text is fitted into Azure's boxes
with order-tolerant matching (`ocr/align.py`). Covers refused by Gemini
(`RECITATION`) fall back to the top half, then to a title-and-author prompt.

**D2 · The glyph is the word's own ink, as a Type 3 font in scan pixels
(2026-09-17).** Glyph space is pixels at 300 dpi (FontMatrix does the
scaling), so outlines are stored unchanged; decimal 1/1000 units cost 19% more
bytes for nothing. Invisible over the scan (`.pdf`), visible alone
(`_vector.pdf`).

**D3 · Never draw one occurrence with another's ink (2026-09-17).** Measured:
a median 15% of pixels differ, six times the tracing error. The shape alphabet
is kept as knowledge (`/InkShapes`, `shapes.json`), not as a drawing shortcut.

**D4 · Chrome's engine is the verification target (2026-09-17/18).** MuPDF and
poppler are measured too but disagree with it on vowelled text. Chrome's line
reconstruction was read from pdfium's source and emulated
(`text.chrome_reads`); stored text is its exact inverse (`text.visual`).

**D5 · pypdfium2 pinned to 5.12.1 (2026-09-18).** 5.13 bundles pdfium 7999,
which had automatic line direction off; verifying against it produced a day of
wrong rules. The "words intact" metric ignores order, so "lines in order" and
"inversions" were added at the same time.

**D6 · 8 pt nominal size stays (2026-09-18).** Larger sizes help pdf.js
(Firefox) on half its lines and cost pdfium 0.1% of words. Chrome wins.

**D7 · Letters: cut only on real joins; then cut along the pen path
(2026-09-19/20).** A free column alignment put 90.9% of cuts within a stroke of
the join; Chrome's equal slices of an uncut glyph: 91.6%. So an unconstrained
cut bought nothing. Cuts were restricted to thin joins (D7a), then replaced by
points on the ink's centre line (D7b), which also handles a kaf whose arm
overhangs its neighbour. Every selection method is compared with equal slicing.

**D8 · Two witnesses choose the cuts: hard facts and the document's own atlas
(2026-09-20).** The atlas alone let big letters swallow small neighbours; the
facts alone leave plain letters undecided. Pictures are compared softened
(2 px) or a fine face's atlas is empty. The atlas update is damped (a full swap
flip-flopped). The atlas can confirm its own mistake (395 swapped `في`), so
facts from outside it must be able to overrule: a failed fact triggers a
second path start.

**D9 · Cut every piece that gets cuts; the witnesses' verdict is reported, not
enforced (2026-09-20, `CUT_ALL`).** About two thirds of rejected cuts were
right, and a wrong cut costs what an uncut piece costs (a highlight slightly
off). Coverage on the reference document went 63% → 95% of words. The verdict
counts are in each build report (`letters_why`).

**D10 · A letter's selection box is its stretch of the baseline; its ink may
overhang (2026-09-20).** As in a typeset font. Origin and advance come from
the cell, so Chrome highlights the cell while the kaf keeps its arm.

**D11 · The atlas is learned from a document's first 1,500 pieces; later pieces
are cut against it and reduced to outlines at once (2026-09-20).** Whole-canvas
pictures for every candidate cut reached 5.7 GB in one process and froze the
machine. Peak is now ~0.85 GB (5 pages) to ~1.6 GB (81 pages).

**D12 · Blobs and text pieces are aligned by width when they do not pair off
(2026-09-20).** Touching runs, broken letters, attached punctuation. The exact
count match keeps its old behaviour; the alignment only runs on a mismatch.
Alef counts as a narrow letter, or a light face's alefs pull in their
neighbours' blobs.

**D13 · Corrections are dealt out over a word's glyphs; a shorter correction
is declined (2026-09-20).** A word is now several glyphs. A glyph cannot be
given no text: pdfium reads an empty ToUnicode entry back as the char code.

**D14 · Restoration never touches the faithful PDF (2026-09-20).** The owner
wants the vector PDF as "the original font as the text" and absolute accuracy.
Restored letters live in the typeface and, later, a separate restored edition.

**D15 · Outputs live in the repo's `out/` folders, gitignored (2026-09-20).**
The owner's Desktop had filled up; and relative paths were hard to find, so
paths given to the owner are absolute.

**D16 · Gemini keeps the whole front page; Azure keeps the rest (2026-09-21).**
The first page scored both ways (`1110-000-001-001` p1, 150 words, hand-marked:
`experiments/12_gold`) went to **Azure, 149/150, against Gemini's 146/150** —
Gemini added a dots error and two doubtful words, all of them in body text, while
the title and author words were identical and correct in both readings. The owner
kept D1 unchanged anyway, and the reason is the asymmetry rather than the count: a
wrong title or author is the error that hurts most in a bibliographic archive and
is unrecoverable without reopening the scan, while a dots error in body prose is
one word among thousands. The evidence is also thin and unrepresentative — one
page, and an *editorial* front page (a title line then 400 words of prose), which
is not the cover D1 was made for. **Do not narrow D1 from this measurement
alone.** What would justify revisiting it is a real cover page (title, author,
journal, date) scored both ways; candidates are in
[../experiments/12_gold/README.md](../experiments/12_gold/README.md).

**D17 · The archive first; the universal document tool later (2026-09-23).**
The owner wants, eventually, any document digitised — tables, equations,
figures — at "five sigma" fidelity. The order is settled: finish the Mandumah
archive first, then widen. Two reasons, both from measurements made on
2026-09-21/22. First, the archive is nearly done and is *provably* better than
what is being shipped today: on ten documents drawn at random from the live
upload, our layer returns 100.0% of words and 100.0% of lines in reading order
against Azure's 97.9% and 79.3% ([experiments/14_vs_azure](../experiments/14_vs_azure/README.md)).
Second, the two rules the project is built on do not survive the widening as
they stand: D3 ("every occurrence its own ink") has no meaning for an equation,
whose printed form is not its content, and a per-document alphabet is worth
nothing on a one-page invoice. Widening therefore needs a *new* rule about what
fidelity means for content that is not ink, and that is a design question to
open deliberately rather than drift into.

**What "five sigma" would have to mean.** At ~2,000 characters a page over
~2,000,000 pages, 5σ (1 in 3.5 million) still leaves about 1,100 wrong
characters in the corpus, and today's reading is nearer 2.8σ. No recognition
model closes that. The reachable version is not a corpus without errors but a
corpus where **every uncertain word is marked**, so a reader can trust the
unmarked text — the trust map in [ideas.md](ideas.md). Accuracy targets in this
project should be stated that way.

**D18 · Mark every output right-to-left; judge selection in a real Chromium
(2026-10-05).** On a new machine the owner's Chrome 154 jumped word to word and
copied lines backwards, while the pinned engine said 100%. A real Chromium 153,
driven by a script (drag, screenshot, copy), showed why: it no longer chooses a
line's direction, and reads every line left to right unless the document says
`/Direction /R2L` — typeset Arabic PDFs included. With the flag, selection is
letter by letter. The alternative, writing each line's glyphs right to left in
the stream, would keep Latin lines right but changes every run and the pen
logic; the flag is one key and the pin agrees with Chromium under it. Latin-
majority lines pay (words swapped). Taken as the quick fix the owner asked for;
the pin stays for `--verify`, but feel is measured in Chromium.

**D19 · The feeler's job is the cuts, not the reading (2026-10-06).** Where the
pen-path reader and Azure disagree, a calibrated Gemini 3.1 Pro judge sided with
Azure 789 times in 800 (experiment 17); across the archive Azure misreads 0.61% of
printed Arabic words on scans (experiment 19). So disagreement with the feeler is not
an uncertain-word flag (it would mark 28% of pieces to find ~1 error in 300). The
uncertain-word layer starts from Azure's own confidence (< 0.8 flags 7% of words and
catches 73% of errors) and exact checks (Quran quotations, experiment 20); the
feeler and the cutter serve letter placement, measured by the blind judge (18, 21).


**D20 · The document file is JATS for the article and ALTO for the page; the
Quran text ships with the code (2026-10-06).** The owner: "if I want to
recreate the documents that I'm trying to digitise, the biggest publishers in
the world use XML and I think it would be good to follow that." Publishers'
XML for journal articles is **JATS** (NISO Z39.96; version 1.4, 2024); its
*Archiving and Interchange* tag set is the one meant for digitised back
content, and it is what PubMed Central and Crossref take in. Experiment 20 had
chosen **TEI P5** because JATS has no standard place for a word's box on the
page, which is true: JATS describes the article, not the page. Libraries'
standard for exactly that missing half — OCR text with coordinates — is
**ALTO** (Library of Congress, v4.4). So each document now gets two files that
together hold what the TEI prototype held, each in the format its readers
expect:

- `<stem>.jats.xml` (JATS 1.4 Archiving DTD): front matter (Mandumah id,
  rubric, title, author, volume/issue as the id spells them, printed page
  range, page count, where every part came from), the body in reading order
  with sections, the footnotes linked from their markers, a reference list when
  a section is headed المراجع/المصادر, and every Quran quotation marked up and
  linked to `https://tanzil.net/#S:A`, with a closing list of the verses
  (Tanzil's text, credited) and how the print differs.
- `<stem>.alto.xml` (ALTO 4.4 XSD): every page, block, line and word with its
  box in scan pixels, Azure's confidence (`WC`), the trust mark and its reasons
  and the quotation as `TAGREFS`, the other reader's text as `ALTERNATIVE`,
  `BASEDIRECTION="rtl"` on Arabic lines. Word ids (`p3w0042`) are also written
  into the build's `shapes.json` placements, which hold each glyph's page and
  box in the same frame; each block points to its element of the JATS file
  (`xlink:href`, same id).

What TEI's prototype taught and kept: per-word ids stable for a given Azure
reading; three trust marks (verified / agreed / flagged) with named reasons;
paragraph roles by position rules, said to be guesses; stand-off Quran links;
the Azure text-element offset conversion. What it showed to avoid: one file
that is neither a publisher's article nor a library's page file. TEI with
word zones is a digital-edition format; publishers' pipelines expect JATS and
libraries' OCR tools (newspaper archives, Transkribus, eScriptorium exports)
expect ALTO, so two standard files reach more readers than one custom one. JATS has no direction attribute: the article is `xml:lang="ar"` with
text in logical order (custom-meta says so); ALTO has `BASEDIRECTION`. Both
validate against the official schemas, fetched at validation time into
`~/.cache/inkscript/schemas` (`enrich/schemas.py`).

The Quran text (Tanzil, CC BY 3.0, 0.5 MB gzipped) **ships in
`src/inkscript/data/quran/`** rather than being downloaded on first use: the
licence permits verbatim copies with the notice (kept, `NOTICE.md`); the text
is fixed (v1.1); the build must give the same result offline and on a server
(moving-to-a-server.md) and the tests must run without network. Downloading
would add a network failure mode for no gain.

**D21 · Corrections: exact sources, two judges on the ink, the text only
(2026-10-06).** The owner wants the text right without the faithful PDF ever
drawing anything else (D3, D14). `inkscript fix` (experiment 27) therefore
changes only what a glyph *maps to*:

- **Only exact sources propose.** A word of a Quran quotation that differs
  from its verse word by dots or letters is proposed the verse's word. The
  author's own wording (و/ف where the quotation starts, a word added, left out
  or changed, a confident reading that differs by a particle or ending), the
  print's spelling (ة/ت, ى/ي, داود/داوود, hamza seats) and the quotation's
  edges are *not* proposed: correcting them would rewrite what the author
  printed. Of the 290 differing words and gaps on the 20-document set, 194
  were proposed, 93 not (wording 73, spelling 18, edge 2), 3 were taken into
  merges.
- **Two judges, blind, on the scan.** Gemini 3.8 Flash first (cheap), then
  Gemini 3.1 Pro must agree. Calibrated on the set: printed word against a
  look-alike 36/36 both, "neither" 11/12 both; and the other direction — the
  print is the author's wording, not the verse — Pro 28/28, Flash 25/28 (it
  read only the part of a word the tint covered, a و outside it). A judge that
  leans to the Quran's word would pass the first test and fail the second; the
  pair is accepted only when both pick the verse.
- **Merges are corrected, splits are not.** One box Azure read as إلاماشاء can
  carry إلا ما شاء: the text is dealt over the word's glyphs with each space on
  the letter before it (the print's own letters are kept when they are right).
  Two boxes for one verse word stay as they are: joining them would take away a
  space the ink has, and a glyph cannot be given no text (D13). A correction
  with fewer letters than the word has glyphs is still declined (D13): 4 on the
  set, logged, left flagged.
- **One code path for the XML.** The corrections live in
  `<stem>.corrections.json`; `enrich` writes the applied ones into the faithful
  PDFs again (a no-op unless the PDF was rebuilt) and into the reading the
  ALTO, JATS and trust PDF are made from. Patching the XML files in place was
  the alternative; it would have been a second writer to keep in step with the
  first, and a rebuild would have lost the corrections.
- **Fewer false flags from a common-word list.** A word flagged for Azure's
  confidence alone is not flagged when it was read confidently in ≥ 5 of 400
  corpus documents and its confidence is ≥ 0.6: flags 7.5% → 5.0% of words, no
  judged error lost (50/61). The list ships with the code
  (`src/inkscript/data/lexicon/`, 22k keys, 89 KB). Tried and not taken: title
  words only below 0.5 (no gain, loses a handwriting error), the same word
  read confidently elsewhere in the document (6.3%, loses فى/في).

**D22 · The article's structure is read from several things a reader sees,
and Gemini's existing title file wins over the layout for title and authors
(2026-10-06).** Experiment 24's position rules (one rule per role) found a
title in 14 of 20 documents and an author in 8, invented a section from an
advertisement and linked 0 of the markers on the pages read by hand. Three
alternatives were open: Azure `prebuilt-layout` (a new paid call per page and
untested on these prints), the catalogue's MARC record (title and author only,
not tied to the ink), or reading the page as a reader does. Chosen: the third,
plus the Gemini title file *already in the bucket* (free; D1's asymmetry — a
wrong title is the worst error — applies), aligned to Azure's words so the
JATS lists the ink's word ids. Each decision combines cues (size, stroke width
from the scan, numbering, colon, space above, repetition across pages, place),
and every one was scored on a hand-read truth (experiment 26): 10 documents
for tuning, 4 held out and read afterwards. Gemini title files exist for 7 of
the 20 set documents; where none exists the layout decides and is weakest
(an author printed above the title stays a "rubric"). Notes must open with a
number and markers must match that number on the same page (or, for an
endnote list, in order through the text), so a link is rarely wrong: 0 wrong
links on either truth set; what is missed is mostly markers Azure never read.
