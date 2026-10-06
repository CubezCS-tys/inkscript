# 20 · The document as data: Quran checks and a first TEI file

**Question.** Two parts, both deterministic (no paid API calls).

1. These journals quote the Quran. Can each quotation be found in Azure's reading, linked to its sura and verse,
   and checked word for word against the canonical text? Every word that differs is either a reading error or
   a choice made by the author, and either way it is a word a reader should not trust blindly (D17: "every
   uncertain word marked").
2. What should a file that describes a document *as data* look like (structure, every word with its box and its
   glyph in our PDF, the Quran links, trust marks), and can one be written and validated today?

**Answer.** 1,173 quotations were found in 74 of 215 documents. All of them are linked to a verse, and 14,145 words
of the reading were checked. **716 match the verse exactly after normalisation; 457 differ in 895 words.** Where the
author cites the sura, the match agrees 280 times out of 290 (274 to the verse). On the ink, 20 of 24 differing
words sampled at random are Azure misreadings. They concentrate in vowelled and Uthmani-script quotations, where
6.4% of words are flagged against 1.9% in unvowelled ones. Part 2: **TEI P5** was chosen. Five documents have a
`.tei.xml` that validates against `tei_all` with zero errors.

## Sources and licences

| What | Where it came from | Licence / terms | Kept at |
|---|---|---|---|
| Quran, plain text for matching | Tanzil Project, *Simple Clean* v1.1, `tanzil.net/pub/download/` (txt-2, with pause marks) | **CC BY 3.0**: copy and distribute verbatim; *changing the text is not allowed*; cite Tanzil and link tanzil.net; keep the copyright block | `out/quran/quran-simple-clean.txt` |
| Quran, vowelled, for display | Tanzil *Simple* v1.1 (same word count per verse as Simple Clean, checked: 6,236/6,236 verses) | same | `out/quran/quran-simple.txt` |
| Quran, Uthmani (downloaded, not used for matching; see method) | Tanzil *Uthmani* | same | `out/quran/quran-uthmani.txt` |
| Sura names | Tanzil `quran-data.xml` | CC BY | `out/quran/quran-data.xml` |
| TEI schema | `tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng` (built 2026-07-28) | BSD-2 / CC BY | `out/schema/tei_all.rng` |
| Validator | jing 20181222 (github.com/relaxng/jing-trang) | BSD | `out/schema/jing/` |

We use the Tanzil text without altering the downloaded files. Normalisation is a matching key computed at run
time, and every verse shown in the report and the XML is Tanzil's vowelled text, verbatim and credited. A
published edition must carry the attribution and link (the report footer and the TEI `respStmt xml:id="tanzil"`
already do).

## Method (Part 1: `quran.py`, `docs.py`, `quotes.py`)

* **Documents** (`docs.py`): every Azure JSON on this machine. That is the fixture, the four `14_vs_azure`
  tryout documents, the 160 in `16_feel/out/books/raw`, and **50 fetched for this experiment**
  (`out/fetched/`, ids in `out/fetch_ids.txt`). The fetched ones are 10 each from journals 0625, 0633 and 0631
  (Islamic magazines, chosen from a 61-title Gemini-title screen, `out/screen/`) and 4 each from 1232, 2657, 2440,
  2018 and 6795 (journals whose local documents quote the Quran heavily). 215 documents, 5,402 pages, 1.44 M words.
  `19_azure_map/out` did not exist.
* **Offsets.** Azure's offsets count *text elements* (grapheme clusters: a letter and its harakat count as one), not
  code points. On vowelled text the two diverge by hundreds of characters. `docs.text_elements` converts them, and
  every word of every document re-reads correctly at its offset (0 mismatches in 215 documents). `src/` does not
  convert offsets. That is harmless there because it uses offsets only to order words and paragraphs, but anything
  that slices `content` by offset needs this.
* **Normalisation** (`quran.norm`): harakat, Quranic signs, superscript alef and tatweel are removed. أ إ آ ٱ → ا,
  ى → ي, ة → ه, ؤ → و, ئ → ي, ء is dropped, Persian ک ی ہ (Azure emits them) become Arabic, and only letters
  are kept. On top of that, two looser keys: `noalef` (also drop every ا) so Uthmani-script quotations
  (العلمين, ءاتينك) match the imla'i text, and `skel` (the dotless rasm), which marks a difference as "dots only".
  The basmala Tanzil prefixes to verse 1 of suras 2–114 is left out of the sequence. Pause marks are dropped.
* **Finding** (`quotes.find_quotes`): every two consecutive reading words whose `noalef` key equals a Quran bigram
  is a seed. A banded alignment (band 6, x-drop) extends it both ways. Each word can match exactly, match by
  spelling (`noalef`), nearly match (letters or dots differ, similarity ≥ 0.5), be missing or extra, or be split
  or joined (Azure's "و لرسول", "ياأيها"). Ends are trimmed to the last match; a near-miss at an end is kept only
  when it is close and inside the same brackets. The best-scoring verse wins. On a tie the sura cited after the
  quotation wins, then the earliest; the others are kept as `also`. Then:
  * **inside ﴿ ﴾** (or hugging one): ≥ 60% of the verse words match and ≥ 3 match. A shorter one must fill its
    brackets (≥ 80% of the bracket's words, 2 matches suffice). Azure also reads the honorific signs ﷺ and
    رضي الله عنه as ﴿ ﴾, which puts ordinary prose between "brackets".
  * **elsewhere** (`(( ))`, «», {}, plain): ≥ 5 matching words and ≥ 75% of the verse span.
  * **a second pass** for bracket spans that no exact bigram seeds, because they are too damaged
    (﴿إِيَّكَ نَعْبُهُ وَإِنَّكَ نَسْتَعِينٌ﴾). It anchors on the span's rarest Quran word and accepts the match if
    it covers 80% of the span and 75% of the verse words match or nearly match.
* **Citation cross-check**: a sura cited right after the quotation, in the form `(البقرة: 24)`, `[هود: ١١١]`,
  `الحجر: ٨٧` or `(سورة يس، الآية 33)`. The name must be a sura name exactly.
* **Verdict per differing word** (`quotes.classify`): dots only, letters, a different word, extra in the
  reading, missing from the reading, or و/ف added or dropped at the start.

## Results (`out/quotes.json`, `out/report_stats.json`, `out/report.html`)

| | |
|---|---|
| documents scanned | 215 (74 with ≥ 1 quotation) |
| ﴿ ﴾ spans | 533, of which 478 hold a found quotation. Most of the other 55 are honorific signs misread as brackets, or hadith set in them |
| quotations found and linked to a verse | **1,173** (502 inside ﴿ ﴾, 671 in other marks or plain) |
| words checked against the verse | 14,145 |
| exact after normalisation | **716** (81 of them only via the Uthmani-spelling key) |
| differing | **457 quotations, 895 words**: 483 letters, 148 dots only, 169 extra in the reading, 35 missing, 35 a different word, 25 و/ف |
| citation agrees | sura 280 / 290, verse 274 / 290 |

**What the differences are.** I checked 24 "reading error?" words (letters or dots), drawn at random, against
the ink:

* **20 are Azure misreadings**: the printed word is the verse's word. Typical errors: the dagger alef of vowelled
  or Uthmani text read as a letter or dropped (لَحَٰفِظُونَ → لَفِظُونَ, أَدْرَىٰكُم → أَدْرَنَكُمْ, ءَاتَيْنَٰكَ
  → ءَانَيْنَكَ), dots lost under dense harakat (الرَّجِيمِ → الرَّحِيمِ, وَهُزِّي → وَهُرِّي, عَيْنَيْنِ →
  عَيْتَيْنِ), and letters dropped (اكتسبت → اكسبت, لِتَبْتَغُوا → لِتَغُواْ, وَالنَّهَارَ → وَالََّارَ).
* **3 are the author's wording**: a quotation starting mid-word (لما → ما), a paraphrase (بغير → غير), and
  a misquotation (تفعلوه printed as تفعلوا).
* **1 is a wrong alignment** (فنرى vs يغفر, in an unbracketed match).

Flagged words in vowelled quotations (> 0.3 harakat per letter): 515 of 7,998 (6.4%). In unvowelled ones: 116 of
6,147 (1.9%), and that figure includes the author's own variations. Experiment 17 found Azure's letter errors
rare on ordinary body text. **Vowelled Quranic text is where Azure is weakest**, and the Quran check catches
those errors for free. "Extra word in the reading" (169) is mostly the quotation boundary or author interpolation
(تعالى, verse numbers read as words, …). "Missing" is usually an author's ellipsis. Neither is a letter error.

Unbracketed matches: in a sample of 30, 26 are real verbatim quotations in `(( ))`, «» or {}. 4 are Quranic
wording used in prose (formulae such as له الملك وله الحمد, a paraphrase of Pharaoh's words), which count as
"differing" through wording, not reading. Bracket detection treats only ﴿ ﴾ as brackets, so `{…}` quotations
count as "elsewhere".

**Not done / limits.** No word has been corrected (D14: the faithful PDF is never altered). A flagged word is
a *candidate*. The dots and letters verdicts are reliable only inside the quotation's own brackets. Quotations
under 3 words outside brackets are not looked for. Variant readings (qirāʾāt) are not modelled, so a real
variant shows as "letters" (none seen in the sample). Azure joining three words into one is not handled
(it shows as missing and extra words).

## Part 2: the XML (`tei.py`; files in `out/tei/`)

**Format choice: TEI P5, not JATS.** JATS (NISO Z39.96) is the right *exchange* format for journal articles:
front, body, back, sec, fn, ref-list, and what Crossref and PubMed Central ingest. But it has no place for a
word's position on a page image. Word-level coordinates would need a private extension. TEI has all of this as
standard: `<facsimile>/<surface>/<zone points>` for boxes on the scan, `<w facs>` per word, `<pb>`/`<lb>`,
`<fw>` for running heads and page numbers, `<note place="foot">`, `@cert`/`@resp` for who said what,
`<taxonomy>` plus `@ana` for trust marks, `<listPrefixDef>` for short links (`glyph:17`, `quran:2:24`), and
`<standOff><listAnnotation>` for stand-off links such as the Quran ones. Its `<biblStruct>` maps one-to-one onto
JATS `<article-meta>`, so a JATS export (for Crossref) can be generated from the TEI later. The reverse is not
possible.

**What one file holds** (`out/tei/<stem>.tei.xml`, validated with jing against `tei_all.rng`: 0 errors on all five):

* **teiHeader**: the title and authors from Gemini's title file (`s3://…/<id>/<id>.gemini.title.json`, copied
  to `out/titles/`), marked `resp="#gemini"`. Only 4 of the 8 documents tried have one. Also the Mandumah id,
  volume/issue/page count parsed from the id (that the id's parts mean journal-volume-issue-article is a guess,
  said in a note), one `respStmt` each for Azure (model and API version), Gemini, inkscript, the position rules
  and Tanzil, the trust taxonomy, and the `glyph:` and `quran:` prefixes.
* **facsimile**: one surface per page (in 1/300 inch, the 300-dpi scan's pixels) and one zone per Azure word
  (its 4-corner polygon).
* **body**, in Azure's reading order. Azure `prebuilt-read` gives paragraph roles almost never (11 "title" in
  about 87,500 paragraphs of the first 165 documents), so roles come from **position rules** (`resp="#rules"`): page number (`fw type="pageNum"`),
  running head and foot (`fw`), footnote (`note place="foot"`: lower half, smaller letters, numbered or following
  one), and section heading (short paragraph, large letters, which opens a `div type="section"`). On page 1, the
  paragraph that matches Gemini's title becomes `head type="title"`, the author `byline/docAuthor`, and a large
  line above them `head type="rubric"`. Line breaks are `<lb/>` from Azure's lines. **Every word** is a `<w>`
  (`<pc>` for punctuation alone) carrying `xml:id` (`p<page>w<n>`, stable for a given Azure reading),
  `facs` (its zone), `cert` (Azure's confidence, `resp="#azure"`), `corresp="glyph:N"` (shapes.json
  `placements[N]`, the glyph of our faithful PDF that draws it), and `ana` (trust).
* **trust marks**: `#trust.agreed` means a second source agrees. So far that is the verse of a Quran quotation,
  or Gemini's page-1 reading in the fixture's PDF. `#trust.flagged` means a second source disagrees. Words with
  no mark have not been checked.
* **standOff**: one `<annotation motivation="identifying">` per quotation, targeting its words, with
  `<ref target="quran:S:A">`, the verse (Tanzil, vowelled), its status, one note per differing word, other verses
  with the same words, and the citation found in the text. One `<annotation motivation="assessing">` per word where
  Gemini and Azure read page 1 differently (fixture: كتابة/كتابُ and التيماء/السَّماءِ in the title. Azure
  misread the title, and the PDF carries Gemini's reading).

| document | words | linked to glyphs | roles found | quotations | agreed / flagged |
|---|---|---|---|---|---|
| 0582-004-009-012 (fixture) | 1,431 | 1,427 | 3 headings, 16 footnotes, 5 page numbers | 0 | 168 / 2 (Gemini p1) |
| 0618-021-002-004 | 4,178 | 4,119 | 14 page numbers, 7 footnotes, 2 headings | 0 | — |
| 1036-010-038-007 | 2,875 | 2,873 | 8 page numbers, 3 footnotes, 2 headings, 2 footers | 0 | — |
| 1005-000-001-002 (built here, `out/built/`) | 5,949 | 5,835 | 55 footnotes, 21 page numbers | 11 | 143 / 5 |
| 0642-029-001-016 (born-digital, no glyphs) | 6,939 | — | 75 footnotes, 36 page numbers | 32 | 136 / 42 |

`1005-000-001-002` (a scanned Islamic-studies article with quotations) was built with `inkscript native --vector`
so that one document shows glyph links and Quran links together: 24 pages, 19,969 glyphs, **13 min, peak 1.26 GB**,
one process. `0642` turned out to be born-digital: our build leaves its pages as they are, so it has no glyphs.

**Still empty or weak.** Journal title (empty: running heads are too rarely recognised to guess it), date,
page range within the issue, rights statement, author affiliations, references (`back/listBibl`), the abstract,
and trust marks for the >98% of words no second source has looked at yet. Paragraph roles are position guesses:
a layout model (Azure `prebuilt-layout` gives title, sectionHeading, pageHeader/Footer, footnote and pageNumber
directly) would replace the rules. Validation is RELAX NG only; TEI's Schematron rules (e.g. that every `#id`
pointer resolves) were not run. All pointers are generated from the same ids.

## What it means

* The Quran is a free second reader for the hardest text in the corpus. Vowelled and Uthmani quotations are where
  Azure is weakest (6.4% of words flagged), and they are also the text an Islamic-studies reader trusts most and
  checks least. Each flagged word could be resolved without AI: the verse shows what the word should be. A
  person, or a second model, only has to confirm that the ink says it. That fits D17: the corpus need not be
  error-free, but every uncertain word should be marked.
* Linking each quotation to `quran:S:A` is itself catalogue value (search by verse across the archive).
* TEI holds everything we know per word today, and has a defined place for each thing we will learn later
  (a second reading, a correction, a role from a layout model). The XML sits beside the PDF and never changes it.

## What I recommend next

1. Run `quotes.py` over the whole archive (it is cheap: seconds per document, no API) and send each flagged
   word with its verse word to a reviewer *as a yes/no question on the ink* ("does the print say لَحَٰفِظُونَ?").
   A confirmed word becomes a correction proposal (`inkscript correct`, D13). The faithful PDF changes only
   through that path.
2. Re-read vowelled Quranic spans with a second reader (Gemini, or Azure's `prebuilt-layout`/a newer model) to
   measure how much of the 6.4% each removes.
3. Make the TEI the place where trust accumulates: the `check` contradictions, the `numbers` second readings and
   corrections all map onto `@ana` and `standOff` annotations already defined here.
4. Get paragraph roles from Azure `prebuilt-layout` on a sample before trusting the position rules, and add a
   JATS export of the header for Crossref when the archive is published.

## Files

`quran.py` (Tanzil loading, normalisation, indexes) · `docs.py` (document list, Azure loading with
text-element offsets) · `quotes.py` → `out/quotes.json` · `crops.py` (300-dpi ink crops with PyMuPDF) ·
`tei.py STEM…` → `out/tei/<stem>.tei.xml`, `out/tei/summary.json` · `report.py --xml STEM` → `out/report.html`.
Validate: `java -jar out/schema/jing/jing-20181222/bin/jing.jar out/schema/tei_all.rng out/tei/<stem>.tei.xml`.

Index line for `experiments/README.md` (not added; other files untouched):
`| 20 | Can the Quran check Azure's reading for free, and what does the document look like as data? | 1,173 quotations in 74/215 documents, 716 exact, 895 differing words (on the ink 20/24 are Azure misreadings, mostly vowelled text: 6.4% vs 1.9%); TEI P5 per document, validates | trust marks from the Quran; TEI as the data layer |`
