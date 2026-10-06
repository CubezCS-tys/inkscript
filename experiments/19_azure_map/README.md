# 19 · Where in the archive does Azure's reading fail?

**Question.** Experiment 17 found Azure's letter errors rare on the ordinary body text of three books. Before anyone
builds a second reader, map the failure across the archive. Which kinds of page and print are weak?

**Method.**

1. *Documents* (`sample_docs.py`, `classify.py`, `meta.py`). The corpus listing (`aws s3 ls`, 1,013,912 documents)
   was saved to `out/listing.txt`. 160 documents were drawn at random, then 80 more (seed 19, then 20), all fetched to
   `out/docs/`. A document counts as born-digital when most of its pages pass the pipeline's own `born_digital()` rule
   (real fonts carry at least half as many words as Azure's `Dummy` layer). Two kinds count as scans and were judged:
   `scan` (only the Dummy font) and `scan+real-font` (typeset pages whose fonts give no usable text, or a scan with a
   stamped digital header). Journal, year and country come from the corpus's own MARC catalogue
   (`s3://…/metadata/metadata_final.xml.gz`, read as a stream; 233 of the 240 ids are in it).
2. *Words* (`strata.py`, `sample_words.py`). Every Azure word of a scanned document, minus words with no letter or
   digit, is given one stratum in priority order: sideways page, Latin, number, vowelled, page-1 title area (top 30% or
   large line), page-1 body, top strip (running heads), large print, small print in the lower half, body. Azure's
   `prebuilt-read` gives no roles, so place comes from line size and position. **Checked by eye: the geometry is rough.**
   "Small print" includes table cells, captions and a CamScanner watermark as well as footnotes. "Large print" includes
   signatures. Per document, up to 5 body words and 3 of each other stratum were drawn. Each word has the weight N/n of
   its (document, stratum) cell. Crops use experiment 17's v3 marking: the word's own line at 300 dpi, only the paper
   behind the word tinted, nothing drawn on the ink. Sideways pages are turned upright using Azure's page angle
   (clockwise).
3. *The judge* (`judge1.py`). Gemini is shown one reading, Azure's, without being told whose it is. It answers RIGHT,
   WRONG (and writes what the ink says), BOX (the yellow area does not hold one word) or UNSURE, plus whether the
   short vowels agree. Short vowels and kashida are ignored for the verdict. The print is not to be corrected. Settings:
   8 crops a request, temperature 0, JSON schema. Answers are cached and every request's cost is logged
   (`out/spend.jsonl`, with a running total). A request that would cross the $12 cap is not sent. Each request is tried
   three times at most.
4. *Calibration* (`calibrate1.py`). Gold set: on the owner's pages (experiment 12), 100 words marked right, shown as
   they are (a WRONG = false alarm), and 100 more shown with one mark changed (a RIGHT = miss). The changes are a dot
   group, ة/ه, ى/ي, a hamza, a dropped letter or an added alef. Archive set: 142 judged archive words from every
   stratum, shown with one mark changed and passed through the same two stages as the run.
5. *Run* (`run.py`). Flash judged all 2,971 words. Every word Flash did not call RIGHT (271) went to Pro, and Pro's
   verdict stands.
6. *By eye* (`out/look.json`). The agent (not the owner) looked at every one of the 64 letter errors on its crop and
   gave each a cause.
7. `analyze.py` → `out/summary.json`, `out/judged.json`; `make_report.py` → `out/report.html`.

```
.venv/bin/python sample_docs.py 160 && .venv/bin/python sample_docs.py 80 --more
.venv/bin/inkscript fetch --id-file out/ids.txt --out out/docs
.venv/bin/python meta.py && .venv/bin/python classify.py
PYTHONPATH=../../src .venv/bin/python sample_words.py
.venv/bin/python calibrate1.py gemini-3.8-flash && .venv/bin/python calibrate1.py gemini-3.1-pro-preview
.venv/bin/python run.py && .venv/bin/python calibrate1.py gemini-3.8-flash --archive
.venv/bin/python analyze.py && .venv/bin/python make_report.py
```

## Calibration (2026-10-06)

| judge | false alarms (100 right words) | misses (100 one-mark changes) | gave back the true word |
|---|---|---|---|
| gemini-3.8-flash | 5 | 2 (both ى/ي) | 90 |
| gemini-3.1-pro-preview | 5 | 1 (ى/ي) | 92 |

Both models raised the same 5 false alarms:

- 2 real misreads by the judge: مجلة read as محنة, and على read as عنى because of a dot from the line below.
- 3 artefacts where the tint missed something attached to the word: a leading و, a comma, and «(( quotes.

The misses are فى, which the owner marked right and both judges read as في (as in experiment 17). Flash costs half as
much, so it screened and Pro confirmed. **On the archive's own prints, two stages: 3 misses in 142** (2.1%): one dot
change in a handwritten heading (UNSURE), one dropped letter on a sideways map, one dot change in a vowelled word.
Every stratum missed 0 or 1 in 20. On the archive, Pro cleared 119 of Flash's 271 flags. A look at 12 of the cleared
words shows Pro was right: mostly a dotless final ى as printed, and punctuation.

## Result (2026-10-06)

**Documents.** 240 drawn: **101 (42%) born-digital**, 118 scans, 21 scan+real-font. Born-digital documents are nearly
all from 2010 onwards (90 of 101; 6 undated). Scans span 1930–2020s. 9 pages of 4,737 are sideways.

**Words.** 2,971 judged, from 139 scanned documents (578,852 words in all).

- **Letter errors: 64 by the judge, 1.55% of the archive's words** (weighted; 95% interval 0.62–2.79% by bootstrap over
  documents). Unweighted it is 2.2%, because rare strata were oversampled.
- Not counted as letter errors: punctuation only (19), Azure's box holding more or less than one word (38), and ink
  the judge could not settle (11).
- **By eye**, of the 64:
  - 31 are printed text read wrong (0.92%; Arabic alone 21, 0.61%, 0.14–1.26%);
  - 26 are ink that is not running text, which Azure turned into words anyway (specks, ornaments, handwriting);
  - 1 is the judge's error; 3 the ink does not settle; 3 are boxing faults.

| stratum (geometry) | judged | errors | weighted rate [95%] | share of words |
|---|---|---|---|---|
| sideways pages | 9 | 1 | 18% [0–33] | 0.2% |
| words Azure read as Latin | 206 | 18 | 6.9% [0.4–17.9] | 5.3% |
| large print | 112 | 4 | 1.9% [0.2–5.4] | 0.2% |
| vowelled words | 355 | 11 | 1.4% [0.4–3.1] | 2.0% |
| body text | 655 | 7 | 1.3% [0.3–2.8] | 77.7% |
| numbers & dates | 409 | 10 | 1.1% [0.1–2.7] | 5.4% |
| page 1 title area | 382 | 4 | 0.9% [0.0–2.7] | 0.7% |
| top strip | 170 | 2 | 0.9% [0.0–3.1] | 0.7% |
| page 1 body | 382 | 2 | 0.2% [0.0–0.8] | 4.7% |
| small print, lower half | 291 | 5 | 0.05% [0.01–0.12] | 3.1% |

The weights let one long document dominate a stratum. One partly handwritten document (0679-000-014-004, 17,296 words)
is 0.5 points of body text's 1.3%. Body text's 7 errors break down as 4 added hamza, 1 handwriting, 1 dot misread and
1 unsettled.

**By decade.** Pre-2000 documents: 2.8% [0.8–5.2] (75 documents). 2000 onwards: 0.65% [0.06–1.5] (63 documents).
The 1960s are the worst (7.2%, 8 documents). Old prints are where the added hamza and the handwritten and ornamental
material sit.

**Kinds and causes.**

| cause | count | Azure's median confidence |
|---|---|---|
| specks or stray punctuation read as words | 11 | 0.46 |
| calligraphy, ornamental titles, stamps, white on black | 10 | 0.48 |
| Latin: transliteration marks (Ī, ḥ, ö), maths, a reversed `S/RES/1564` | 10 | 0.84 |
| handwriting | 5 | 0.27 |
| an ordinary printed word misread (dots, dropped ت, ١٣ as 1r) | 5 | 0.76 |
| hamza added where the print has none (أهل for اهل; old prints) | 4 | 0.99 |
| the ﷺ ligature misread | 4 | 0.04 |
| superscript note numbers lost (read as shadda or tanwin) or misread | 3 | 0.26 |
| ى/ي | 3 | 0.56 |
| Persian code points (بین, لحکمھا) | 2 | 0.99 |

The Persian code points were also counted in code over every word: **542 of 578,852 words (0.09%) in 69 of 139
documents** carry one. The word looks right but breaks search.

**Confidence.** AUC 0.84. Flagging words under 0.8 would mark 7.0% of words and catch 73% of the errors (weighted);
1 in 6 flagged words is wrong. Under 0.9: 12.7% of words, 86% of the errors. What confidence catches is the not-text
material: specks, ornaments, handwriting and ﷺ all sit at a median confidence below 0.5. What it misses are the
errors a reader minds most: an added hamza and a Persian code point sit at 0.99, an ordinary misread at 0.76.

**Spend: $6.69** (list prices rounded up). Calibration $0.89, run $5.16 (Flash $3.99, Pro second opinions $1.17),
archive calibration $0.64. 3 Pro requests failed on truncated JSON; those 6 words kept Flash's verdict.

## What it means

- On printed Arabic, Azure is right about 99.4 times in 100 (0.6% wrong by eye; the interval reaches 1.3%). Its
  commonest real fault there is writing a hamza that old prints left out. That is a fault for fidelity, arguably not
  for search, and no look-alike checker would call it a misread.
- About half of all errors are not reading errors in text: Azure invents words from specks, ornaments, stamps,
  calligraphy and handwriting. A **second reader is the wrong tool for these**. The cheap remedy is to mark them, and
  Azure's confidence below 0.8 already finds most of them. So does a "Latin" word inside an Arabic page: 7 of the 18
  errors in that stratum were specks or ornaments, not Latin.
- A second reader would pay off on these:
  - **Pre-2000 scans.** The rate is about 4× the modern scans', and that is where the hamza, handwriting and
    ornaments are.
  - **Page 1 title areas, headings and running heads with decorative type.** Those stay with Gemini (D1/D16), and this
    supports that.
  - **Words with ﷺ or superscript note numbers.** These are a small, findable set: low confidence, next to a digit.
- Not worth one: ordinary body text and footnotes of modern scans.
- **Code-level fixes, no reader needed:** map Persian code points to Arabic (0.09% of words). Treat the 42% of
  documents that are born-digital as already done: they need no OCR at all.

**Limits.**

- The strata are geometry, not roles.
- The judge sees one reading and could be anchored by it. On archive prints it missed 2% of one-mark changes, but
  multi-letter errors were not tested.
- The by-eye causes are the agent's, not the owner's.
- Words Azure never output (missed ink) cannot be seen by a word-by-word judge.
- Intervals are wide: 64 errors, and a few long documents carry much of the weight.

Not done (rule of this task): `docs/` and `experiments/README.md` not edited. Suggested index line:
`| 19 | Where does Azure's reading fail? | 240 random docs: 42% born-digital; on 2,971 judged words of 139 scans
1.55% letter errors [0.6–2.8], printed Arabic 0.6%; half the errors are specks/ornaments/handwriting; pre-2000 4× worse;
confidence <0.8 catches 73% at 7% flagged | a second reader only for old prints and decorative/page-1 type; mark low-confidence; fix Persian code points |`
