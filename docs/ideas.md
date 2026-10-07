# Ideas

Every idea that has come up, whoever had it, with what became of it and where
to pick it up. Newest thinking first inside each group. Add to this file the
moment an idea is voiced — not when it is built.

Status words: **built** (in the package), **experiment** (measured, not in the
build), **parked** (agreed worth doing, not started), **dropped** (tried; the
reason is recorded), **open** (voiced, not yet judged).

## Trusting the text (the biggest gap)

- **Every uncertain word marked: the trust map.** *built 2026-10-06*
  (`src/inkscript/enrich/trust.py`, `--xml`/`--trust`; measured in
  `experiments/22_trust`, set in `experiments/24_product`). Each word is
  verified, agreed or flagged with reasons: Azure confidence < 0.8 plus specks,
  ornaments, Latin on Arabic pages, Persian letters left in the text, Quran
  differences and (page 1) Gemini disagreeing. 7.6% flagged, 0.43% of
  unflagged words wrong on experiment 22's sample. *Parked:* the *strict*
  option (old prints at 0.9, hamza in hamza-omitting prints: 11.3% flagged,
  0.10% left wrong), and a second reader for confident misreadings (the added
  hamza at 0.99 escapes every free signal); paying a judge per flag (≈ $0.0026
  a word) on demand, not archive-wide. *Fewer false flags, built 2026-10-06
  (experiment 27):* a word flagged for its confidence alone is not flagged when
  it is common in the corpus (read confidently in ≥ 5 of 400 documents) and its
  confidence is ≥ 0.6 — flags 7.5% → 5.0%, no judged error lost. *Tried, not
  taken:* title words flagged only below 0.5 (no gain); the same word read
  confidently elsewhere in the document (smaller gain, loses an error).
  *Untested:* two independent readers agreeing — Gemini's page 1 already
  verifies (in the rule since experiment 22), but experiment 19's sample has
  no second reading, and the feeler agrees with Azure mostly where Azure is
  right (D19).
- **The Quran as a free second reader.** *built 2026-10-06*
  (`src/inkscript/enrich/quran.py`; experiment 20). Quotations found, linked to
  sura:verse (tanzil.net), checked word for word; an equal word is *verified*,
  a differing one *flagged* (20 of 24 such words on the ink were Azure
  misreadings). *Built 2026-10-06 (experiment 27, `inkscript fix`, D21):* each
  differing word that is not the author's wording or the print's spelling is a
  blind A/B question on the ink (Gemini Flash, then Pro must agree); on the
  20-document set 194 proposed, 156 accepted, 147 written into the text (PDFs,
  ALTO, JATS, trust PDF), ink pixel-identical. *Open:* other exact sources —
  hadith collections, the document's own repeated phrases, a cited reference
  list; the 4 shorter corrections D13 declines (a glyph may not be empty: a
  zero-width character would need a Chrome search test); splits.
- **The document as data: JATS for the article, ALTO for the page.** *built
  2026-10-06* (`src/inkscript/enrich/jats.py`, `alto.py`; D20). Replaces the
  TEI prototype of experiments 20/22 (*dropped* as the product format: neither
  publishers' nor libraries' tools read it; what it taught is kept, D20).
  *Structure read like a reader: built 2026-10-06* (experiment 26,
  `src/inkscript/enrich/structure.py`, D22): titles and authors from Gemini's
  title file aligned to Azure's words (else page 1's layout), headings from
  size + bold ink + numbering + space, notes linked from their markers,
  furniture by repetition. *Open:* Gemini title files exist for only 7 of the
  20 set documents — a title file for every document (one cheap call, or the
  catalogue's MARC title/author, experiment 19's `meta.py`) would remove the
  layout guess where it is weakest (an author printed above the title, a rubric
  glued to the title); markers Azure never read (a raised "9" lost) could be
  re-found on the ink beside the line; boxed inserts (an advertisement
  "إعلان" under an article) are still taken for a section; Azure
  `prebuilt-layout` roles remain untried; references split into fields
  (`element-citation`); a Crossref export from the JATS front matter.

- **Three layers: ink deterministic, reading by a small model trained on the
  archive, trust by disagreement.** *open, 2026-10-05; owner: "save this, we
  will come back to it".* The ink stays exact and rule-based (tracing, text
  layer, letters). The reading stays Azure's, checked by a small line reader
  (Kraken-style CTC) trained per typeface family on Azure's readings bound to
  the ink — free training lines. A word is flagged where Azure, that reader and
  the letter-by-letter ink fit disagree; "perfect" becomes "every uncertain
  word marked" (D17). No VLM in the loop. Web research behind it (agent
  report, sources not all re-read): cutting before reading has never worked on
  real print — *Sayre's paradox*, the wall experiment 10 hit; Kraken on the
  20th-century journal al-Abhath reached 97–98.5% of Arabic letters from
  ~1,000 lines per typeface, better trained across typefaces
  (arxiv.org/abs/2402.10943); VLMs silently "correct" misspelled words, up to
  59% in one study (English, Chinese and Korean; arxiv.org/abs/2607.21617); no
  benchmark covers Mandumah-like scans, so the gold set (experiment 12) is the
  measure. First step: train Kraken on one typeface from Azure's readings,
  test whether it catches Azure's errors on gold-set pages.

- **A gold set, and the error taxonomy before the checker.** *experiment 12,
  2026-09-21: tools built, first page marked, method changed.* The first page
  (`0005` p2, heavy face) came back **277 words, 0 errors** — so whole-page
  marking cannot collect enough errors to classify (it would take ten thousand
  words), and the taxonomy now comes from the pools already enriched for error:
  the 1,399 contradictions and the 50,007 numbers (`candidates.py`). Whole
  pages are still the only way to measure the *rate*, so one page of the worst
  document is the next unbiased sample.* Nothing measures whether the
  reading is RIGHT — only that we preserved it. A page of every face type,
  every word judged, and each error given a class. The class decides the build:
  look-alike errors are what a checker can pose a hypothesis about; dropped,
  merged and invented words are invisible to one and need a coverage test
  instead (every word's ink accounted for, every piece of ink claimed). Also
  gives milestone 2 and any checker the ground truth they lack, and the
  baseline they must beat: *change nothing*.
- **The book's own orthography is not an error.** *open, from experiment 12.*
  Many printings never dot a final ya, never write hamza on an initial alef. A
  checker that corrects those rewrites the book into modern spelling at scale.
  The rule: learn each document's own practice and flag departures from *it*,
  never from standard Arabic — the atlas's "the document is the witness",
  applied to spelling.
- **A second opinion on Azure from the book's own letters — as a checker, not
  a reader.** *parked, milestone 1.* Cut a word by its known reading (we do
  that well), then ask whether the ink fits a look-alike reading better:
  one dot or two, `ة`/`ه`, `ى`/`ي`, `أ`/`ا`. Feeds the review-and-correct
  loop. Pick up from `experiments/10_atlas_reader/` (it has the per-letter
  scoring against stored examples) and `verify/second.py`.
- **Reading blind with the atlas** (owner, 2026-09-20: "trace the letters,
  record the history of the strokes and match against our database of letter
  strokes"). *experiment 10.* A held-out page read with no text: 41% of pieces
  agree with Azure; isolated letters 67%; joined pieces ~20% (you must cut
  before you can match and match before you can cut; tooth letters). Matching
  individual stored examples beat mean pictures by far (27% → 41%) — the
  "database" instinct was right. Not a replacement for Azure/Gemini; see the
  checker above.
- **Scope Gemini to the title and author, not the whole front page.** *open,
  2026-09-21.* On the one front page scored both ways Azure read the body text
  better (149/150 against 146/150) while the title and author were identical in
  both. The owner kept D1 as it is (D16) — a wrong title costs far more than a
  dots error in prose, and one editorial page is not a cover. What would settle
  it: a real cover scored both ways (`experiments/12_gold`).
- **Gemini labels the alphabet's glyphs instead of reading whole pages**
  (owner, 2026-09-19). *open.* Would give labels per shape, but does not solve
  where one letter ends (a geometry problem). Could label the restored
  typeface's glyphs cheaply as a cross-check.
- **A word whose ink is only partly assigned to it.** *open, found 2026-09-22.*
  61% of `extension` contradictions are a word whose blob signature covers only
  part of its ink (the leading `و` of `وعلى` never attached), so the
  contradiction is an artefact rather than a reading error
  (`experiments/12_gold`). The reading is right in these cases; the *layout* is
  wrong. Worth measuring: how often does a word lose a run, and does it cost
  anything visible in the PDF?
- **Gemini re-reads only what is doubtful.** *built:* numbers
  (`inkscript numbers`) and contradictions — same ink, different text
  (`inkscript check`, `inkscript second`); two readings against one become a
  proposed correction. Corrections are written into a finished PDF by
  `inkscript correct`.
- **Geometry as a better medium for LLMs** (owner's founding idea). *open.*
  Give a model the outlines/alphabet ids rather than pixels. Untested.

## Letters

- **Follow the pen** (owner, 2026-09-19/20: "a human can do OCR with their
  eyes closed… feel the strokes"). *built* — `geometry/penpath.py`,
  [letters.md](letters.md). 96.8% letter coverage at scale.
- **Read the word by feeling it: recognition from the pen path alone**
  (owner, 2026-10-05: someone writes a word on your back with a stick; without
  looking you track it, know the word, and know where each letter starts and
  ends). *experiment 16, 2026-10-05: 50.7% of pieces read blind from the
  path alone against 41% from the picture (exp. 10); isolated 76%, two
  letters 40%, five or more 0; a live page shows the pen, the feeling and the
  reading ([experiments/16_feel](../experiments/16_feel/README.md)). 2026-10-06, four books, held-out
  test: a small trained reader of the path (CTC, 714k parameters) reads 79.0% of pieces as Azure does,
  single letters 96%, five or more letters 36%; hand-built matching reached 65%. Experiment 17 (2026-10-06): where it disagrees with Azure, a Gemini 3.1 Pro judge sides with Azure 98.6% of 800 times — the feeler's reading is not a checker of Azure; its value is the cuts.* The machine version: unroll the ink into its pen path (as
  `penpath.unroll` already does), then hand a blind sequence model only the
  path — position, direction, curvature along it, dots as events — and let it
  output the letters *and* where each falls on the path. This is online
  handwriting recognition (the kind phones do from a stylus), which is far
  easier than reading a picture, fed with a path recovered from print. It
  does not break Sayre's paradox so much as dissolve it: cut and reading come
  out of one pass over the path. Hard parts: print has no true writing order
  (loops, retracing, where to start), and the back-reader also knows the
  language. Training data: every piece's path with Azure's reading. Bars to
  beat: experiment 10's 41% blind, and equal slicing for the cuts (D7). Also
  Thomas Milo's model of the script (DecoType: rasm, then dots, joins as their
  own stroke, the nib's dot as the unit) — tug.org/TUGboat/tb24-3/milo.pdf.
- **An atlas of pen paths rather than pictures.** *open.* Store each
  letter-form's typical centre line and match line against line; would
  tolerate stretching and slant where pictures do not. The data exists (every
  cut letter has its stretch of path).
- **Stroke-order animations as a reference** (owner offered to find some).
  *open.* Not needed so far: a loop lies inside one letter, so which way round
  it was drawn does not change the cut.
- **Cut at the join point, not a column.** *built* — it is what the pen path
  does; the vertical-column cutter (`geometry/letters.py`) is kept for its
  shared pieces. Columns were no better than Chrome's equal slices.
- **Vowelled words.** *parked.* Never cut, because pdfium reorders the pieces
  of a split vowelled word. Up to 6% of some documents. Needs an experiment on
  how to store marks with letter glyphs.
- **Underlines.** *parked.* Remove the rule from the ink before cutting; the
  rule-separation in `geometry/trace.py` only catches long rules.
- **Measure placement, not just coverage.** *experiment 15, tool built
  2026-09-27.* A blind paired trial: the same word cut both ways, tinted band by
  band, the reader says which is better without being told which is which. The
  bar is 50%, because equal slicing is free (D7). Also counts the words where
  letter selection is wrong *either* way — the honest ceiling on what
  letter-level highlighting delivers today.
- **The owner's hand-marked line** (word → letters selectable yes/no).
  *method, keep using.* One line found four bugs.

## The typeface and restoration

- **Type with a book's font** (owner, 2026-09-20). *experiment 11* —
  `experiments/11_typeface/make_font.py` builds an installable TTF with
  joining forms and lam-alef; [typeface.md](typeface.md).
- **Restore the letters from many printings** (owner: "enhancing the font to
  make up for the broken pieces"). *experiment 11.* Body voted from up to 15
  best printings, marks from the best one, joins on the document's band.
- **A restored edition of the page.** *prototype built 2026-09-21,
  experiment 13.* Third output beside the faithful PDFs: same layout, the page
  set in the book's own restored font. One page of `0582` exists and looks
  right — 157 KB against the faithful 522 KB, no image at all. It is the answer
  to the owner's "I want the PDFs to feel like `DuffyCN.pdf`": the faithful PDF
  never can, because D3 forbids the glyph reuse that makes a native file small.
  **The remaining piece is the text layer** — a page typeset by a layout engine
  is read backwards by Chrome (23% of words survive, against the faithful
  build's 100%), because nothing but this repo stores Arabic the way pdfium
  inverts it (`text.visual`). Finish it with `pdf/type3.py`'s writer emitting
  the restored font's glyphs. Never replaces the faithful PDF (D14).
- **The font as a debugger.** *method.* A wrong glyph means a systematic wrong
  cut in that book (found the swapped `في` and the unsplit alefs).
- Open font work: final `و` of 0565; forms a short document never prints
  (borrowed from relatives — could borrow from a *similar book's* font);
  digits and punctuation; mark positioning (GPOS); kerning of `فى`.
- **Sharp display atlas.** *parked.* The atlas at full resolution, examples
  aligned before the median — the readable form of "the document's alphabet".

## The PDF and other viewers

- **Shared alphabet across occurrences** (2026-09-17). *dropped for drawing,
  kept as knowledge.* Drawing one occurrence with another's ink costs a median
  15% of its pixels, six times the tracing error; so the alphabet labels the
  ink (`/InkShapes`, `<stem>.shapes.json`) and never replaces an outline.
- **"What if I don't care about size?"** (owner). Scale-normalised matching:
  the alphabet saturates within a document and resets between type weights —
  different weights are different alphabets (`experiments/03`).
- **Mark every PDF right-to-left (`/ViewerPreferences << /Direction /R2L >>`).**
  *built 2026-10-05 (D18).* Chromium 153 (pdfium ~8010; the owner's
  Chrome and Edge are 154) no longer guesses each line's direction: it read our
  lines and a typeset Arabic PDF (`0642`) with the words reversed, and a drag
  jumped word to word. With the flag, a real Chromium drag on `0618` p3 selects
  letter by letter in reading order. Cost: Latin-majority lines then come back
  word-reversed (`0618` p17) until they are stored the right-to-left way; the
  pinned 7947 reads the flagged file the same way, so `--verify` can still
  judge it. The pin no longer stands in for current Chrome — CLAUDE.md's rule
  needs revisiting with it. Test copy:
  `experiments/14_vs_azure/out/tryout_2026-10-05/native_r2l/`.
- **Firefox / pdf.js.** *decided: 8 pt stays.* A larger nominal size fixes half
  the lines there and costs pdfium 0.1% (`experiments/06`).
- **Junk-encoded typeset fonts → rebuild their ToUnicode from Azure**
  (`pdf/fontfix.py`). *built, switched off* until coverage ≥ 99.5%; meanwhile
  such text is neutralised with `/ActualText`.
- **Tables.** *parked.* Cells that pdfium joins across rows.
- Apple Preview: untested.

## Showing the work

- **Animation for the owner's father** ("the liquid thing, then the
  geometry"). *built* — `docs/demo/ink_to_text.html`.
- **Interactive storyboard as documentation** (owner, 2026-09-18; "a lot more
  visual so me and others can really understand", 2026-09-20). *built* —
  `docs/storyboard/` (`build.py` + `letters_data.py` + `template.html`,
  `rebuild.sh`). Fifteen chapters, every picture from real outputs: the idea,
  a real page, **follow the pen** (eight-step stepper on seven real words),
  **the atlas** sharpening round by round, **the swapped في**, how Chrome
  reads, the rules, **every document as a dot** (two runs), **type live in
  two books' fonts**, reading blind, what it does not do. Still open: a
  walk-through of one whole page being built, a restored-edition panel once it
  exists, and phone-width polish.

## Scale

- **Run the corpus.** *in progress.* 227 journals done twice; next a rerun
  with the post-run fixes and a per-document before/after of the boxes; then
  the 451 sample; the corpus is ~100,000 documents. See
  [operations.md](operations.md) for memory and resuming.
- **Speed.** About 7.6 s a page single-threaded, most of it the letter
  cutter's Python loops. Untouched: vectorising `best_cuts`, caching page
  geometry between the two passes.
  *2026-10-07 (experiment 28):* with `--xml --trust` a page takes 18.6 s (median
  document); on the slowest, 65% of the time is `save(garbage=3)`, not the cutter.
  `garbage=1` gives identical PDFs 40% faster (`experiments/28_scale/patches/`).
- **The whole product at scale** (experiment 28, 2026-10-07). *done once; patches
  proposed.* 205 documents, every decade: the faithful PDF holds; what broke is the
  source fonts' text left on rebuilt pages, titles without a title file, content
  set aside as furniture. Open from it, each needing a judged sample first:
  - **Furniture by the text block's frame, not the page's edge** — a lone block
    that is heading-sized, bold, a note, or inside a table stays content;
  - **Flags on vowelled text** — judge flagged vowelled words on the ink and set
    their confidence threshold from it (over 50% vowelled → 60% flagged now);
  - **A page-level "handwritten" mark** instead of hundreds of word flags.
