# 22 · Uncertain-word marks: can a reader trust the unmarked text?

**Question.** D17 asks that every uncertain word be marked, so that a reader can trust what is not marked. D19 says
this layer starts from Azure's confidence and from exact checks. Which free signals should flag a word, and how
well do they do? What would a paid judge add? Where are the marks stored, and how does a reader see them without
the faithful PDF changing?

**Answer (2026-10-06).** Default flag: **Azure confidence < 0.8, plus four free signals** (a speck or stray mark,
an ornament/stamp/display type, a Latin word on an Arabic page, a Persian letter the build does not fold). A word
in a Quran quotation that differs from the verse is flagged too; one that equals the verse is *verified*.

| | default |
|---|---|
| words flagged | **7.6%** [5.6–9.9], about **21 words on an average 280-word page** (24 on pre-2000 scans, 20 on later ones) |
| judged errors caught | **51 of 62 (82%** [72–91]); weighted as the archive 74% [38–96] |
| wrong among unflagged words | **0.43%** [0.05–0.97] (with no marks at all: 1.55%) |
| flags that are real errors | 1 in 7 |

Intervals are 95%, from a bootstrap over documents. Report: `out/report.html`.

## Method

* **Truth** (`features.py`, `analyze.py`): experiment 19's 2,971 judged words from 139 random scanned documents.
  The verdicts were reused, not paid for again. An *error* is a letter error there (64), minus 1 the agent found
  to be the judge's own mistake, minus 1 Persian `ی` that `fold_letters` now fixes in the build. That leaves
  **62**. Rates use experiment 19's weights (N/n per document and stratum). Counts are given unweighted alongside,
  because the weights are lopsided: 4 added hamzas in body text outweigh all 26 non-text errors together.
* **Signals** (`signals.py`), all free, computed for every word:
  * Azure's confidence.
  * The 300-dpi scan inside the box: ink share and connected components.
  * Box height against the document's median word height, and box width per letter.
  * Words on the same Azure line, and whether the box sits at the page edge.
  * Latin letters on an Arabic page.
  * Persian code points left after `fold_letters`, which folds only ک/ی, so ھ ہ ے and others stay.
  * The ﷺ ligature, and a superscript note number read as a mark.
  * The catalogue year.
  * "Hamza-omitting print": Azure's bare ان/الى/اذا outnumber أن/إلى/إذا in the document.
  * The Quran check: experiment 20's `quotes.py`, copied and rerun over the 139 + 5 documents.
* **Rules** (`flag.py`). Each rule was scored for share flagged, errors caught (weighted and counted), the error
  rate left in unflagged words, and precision, plus a trade-off curve over the confidence threshold.

| rule | flagged | per page | caught (w) | caught (n) | left wrong |
|---|---|---|---|---|---|
| conf < 0.8 (exp. 19) | 7.2% | 20 | 74% | 43/62 | 0.43% |
| conf < 0.9 | 13.0% | 37 | 87% | 49/62 | 0.23% |
| 0.8 + Persian + Quran + speck + ornament | 7.4% | 21 | 74% | 48/62 | 0.43% |
| **default** (+ Latin on Arabic page) | **7.6%** | **21** | **74%** | **51/62** | **0.43%** |
| + pre-2000 prints at 0.9 | 10.8% | 30 | 87% | 53/62 | 0.22% |
| strict (+ hamza in hamza-omitting prints) | 11.3% | 32 | 94% | 54/62 | 0.10% |

**Why this default.** Over confidence alone, the speck, ornament and Latin signals add 8 of the judged errors
(specks, a stamp, Latin transliteration) for 0.4 points of flags. Raising the bar to 0.9 on pre-2000 prints takes
an old page from 24 to 45 flags, for 2 more judged errors. One of those 2 is a single body word whose weight
(1,093) makes the weighted curve jump. The hamza rule rests on 1 error. Both are kept as a *strict* option
(`#why.conf_old`, `#why.hamza` exist in the TEI taxonomy) and not used by default. The ﷺ and superscript signals
add nothing beyond confidence: all 7 such errors sit below 0.65. The Quran check cannot be scored on this sample,
because no judged word lies on a differing quotation word. Over all 578,852 words it flags 113 (0.02%), and
experiment 20 found 20 of 24 such words on the ink to be Azure misreadings.

**Caught by the default:** all specks (11), ornaments and stamps (10), handwriting (5), ﷺ (4) and superscripts
(3). Also 8/10 Latin errors and 4/5 ordinary misreads.

**What no free signal catches (11 of 62).** Azure gives every one of them a confidence of 0.81–0.99, and nothing
on the page looks odd:
* the **hamza Azure adds where an old print has none** (أهل for اهل at 0.99, أقصى for اقصى at 0.99, أنه for انه at 0.90): 3 of 4;
* an ordinary misread (الجزي for الخزي, 0.94);
* ى/ي (فى as في, 0.96);
* a Latin diacritic (Noldeke for Nöldeke);
* 2 boxing faults and 2 the ink does not settle.

Before 2000 the default leaves 1.00% [0.12–2.26] of unflagged words wrong. From 2000 on it leaves 0.00%: 17/20
caught, and the 3 misses carry almost no weight. **Old prints are where unmarked text is still not safe.**

## Paid confirmation (`confirm.py`, spend in `out/spend.jsonl`)

*Estimate from experiment 19's own verdicts on the flagged words (free).* The judge would clear **75%** of the
default's flags, leaving about 5 per page. The two stages of experiment 19 (Flash on every flag, Pro on the 30%
Flash doubts) cost **$0.0026 per flagged word**, measured on its run.

*Archive-wide:* about 587k scanned documents (1,013,912 × 139/240), 2.4 billion words and 186 million flags.
That comes to **≈ $480k**, about $240k with a batch discount, or $570k with Pro alone. The judge itself misses
about 2% of one-mark errors on archive prints (experiment 19).

*Tried on 60 flagged words* of the four scanned TEI documents (estimate $0.26, **spent $0.13**): 51 cleared,
7 confirmed wrong, 2 bad boxes. Of the 7, 5 are hamza questions (Azure added or dropped the hamza the print shows)
and 2 are punctuation. That matches the estimate (85% cleared on this sample).

## Stored: the TEI files (`tei.py`, `out/tei/`, `out/trust/<stem>.json`)

Experiment 20's `tei.py` was copied and extended; its files were not touched. Every `<w>` now carries exactly one
of three marks:
* `ana="#trust.verified"`: a Quran verse or Gemini's page-1 reading agrees;
* `#trust.agreed`: no signal raised a doubt;
* `#trust.flagged`, followed by its reasons, e.g. `#trust.flagged #why.speck #why.conf`.

Both taxonomies (`trust`, `why`) are described in the header, with the measured rates. A verse agreement overrides
a low confidence. Punctuation alone (`<pc>`) is not assessed, as in experiment 19. All five files validate against
`tei_all` (jing, 0 errors).

| document | words | verified | agreed | flagged | reasons |
|---|---|---|---|---|---|
| 0582-004-009-012 (fixture) | 1,431 | 168 | 1,016 | 62 | conf 61, ornament 2, gemini 2, speck 1 |
| 0618-021-002-004 | 4,178 | 0 | 3,695 | 235 | conf 222, speck 17, latin 5, persian 1, ornament 1 |
| 1036-010-038-007 | 2,875 | 0 | 2,539 | 139 | conf 135, speck 10 |
| 1005-000-001-002 | 5,949 | 143 | 4,782 | 433 | conf 423, speck 7, ornament 5, quran 5, latin 4, persian 1 |
| 0642-029-001-016 (born-digital) | 6,939 | 136 | 6,135 | 375 | conf 358, quran 30, speck 18 |

0642 is born-digital. Its PDF keeps the publisher's text, so its marks describe Azure's reading only.

## Shown: the report and a `_trust.pdf` (`make_report.py`, `trust_pdf.py`)

**`out/report.html`** (self-contained, light/dark, phone width; checked in Chromium at 1100 and 390 px). It
contains:
* the trade-off curves, weighted and counted;
* the rules table;
* crops of caught and missed errors;
* 8 whole pages with the flagged words tinted on the scan (hover or tap shows the reason) and Quran-verified words
  underlined in green;
* the paid trial, the TEI excerpt, and the PDF in Chromium.

**`out/fixture_build/0582-004-009-012_vector_trust.pdf`** is built from a fresh `inkscript native --vector` build
of the fixture. It adds 62 highlight annotations, one per flagged word. Each one's note gives the reason and
Azure's confidence. All of them sit in one optional-content layer, "Uncertain words". The file is saved as an
**incremental update**, checked in `out/0582-004-009-012_vector_trust_check.json`:
* its first 1,624,712 bytes are the original file, byte for byte;
* pdfium 5.12.1 gives the same text on all 5 pages and the same 7,691 character boxes;
* the build's own checks give the same numbers on both files: 1246/1246 words intact, 113/113 lines in order;
* `/Direction /R2L` is kept.

In a real Chromium 153 (`chromium.py`, copied from experiment 23), dragging across the flagged word الخيبة copies
it letter by letter, exactly as in the original. Hovering a highlight opens its note. **Chromium's note box draws
no Arabic** (the word came out blank), so the notes give the reason in English and leave the word out.

## What it means

* Confidence plus cheap geometry gets 82% of the judged errors at 21 flags a page, and leaves about 0.4% of
  unflagged words wrong (0.0% on modern scans). That is a usable first version of "trust the unmarked text" for
  post-2000 scans.
* It is not yet safe on old prints. Their remaining errors are confident misreadings, mostly an added hamza, and
  only a second *reading* finds them. Next step: a second reader, or the judge on pre-2000 body text, not more
  flags.
* 6 of 7 flags are false alarms. On the fixture they are mostly bare-alef words that Azure doubts *because* the
  print omits the hamza. Paying the judge would clear 75% of flags, but that costs about $0.5M archive-wide. Worth
  it per document on demand, not for the whole archive.
* The marks live in the TEI and, optionally, in a separate annotated PDF. The faithful PDF's bytes do not change.

## Files

`signals.py` (free signals per word) · `features.py` → `out/judged_signals.json` · `flag.py` (the rules, the
default) · `analyze.py` → `out/flag_eval.json`, `out/analyze.log` · `confirm.py` + `judge1.py` (copied from
experiment 19, cap $5) → `out/confirm.json`, `out/spend.jsonl` · `docs.py`, `quran.py`, `quotes.py` (copied from
experiment 20; `docs.py` keeps each word's page index) → `out/quotes.json` · `tei.py` → `out/tei/`, `out/trust/`
· `trust_pdf.py` → `*_trust.pdf` + check · `chromium.py`, `glyphs.py` (from experiment 23), `chrome_shot.py` →
`out/chromium/` · `make_report.py` → `out/report.html`.

```
.venv/bin/python quotes.py --out out/quotes.json --only $(cat out/judged_docs.txt) <the five stems>
.venv/bin/python features.py && .venv/bin/python analyze.py
.venv/bin/python tei.py 0582-004-009-012 0618-021-002-004 1036-010-038-007 1005-000-001-002 0642-029-001-016
.venv/bin/inkscript native --azure-dir F/azure --scan-dir F/input --frontpage-dir F/frontpage --out out/fixture_build --vector
.venv/bin/python trust_pdf.py out/fixture_build/0582-004-009-012_vector.pdf out/trust/0582-004-009-012.json F/azure/0582-004-009-012/0582-004-009-012.json out/fixture_build/native_pdf_report.json
.venv/bin/python confirm.py 15 --go && .venv/bin/python make_report.py
```

**Limits.**
* The signal thresholds were set by looking at these same 62 errors, so they are tuned in-sample. Speck and
  ornament use round numbers, and adding them moved the flag share by only 0.4 points.
* The weighted intervals are very wide (a few heavy words).
* Words Azure never output cannot be flagged.
* The Quran signal is unscored here.
* Hover in Chromium shows no Arabic.

Not done (rule of this task): `docs/`, `src/` and other experiments untouched; nothing committed. Suggested index
line: `| 22 | Can free signals mark every uncertain word? | conf<0.8 + speck/ornament/Latin/Persian/Quran: 7.6% flagged
(21/page), 51/62 errors caught, 0.43% of unflagged wrong (0.0% post-2000, 1.0% pre-2000); misses are confident added
hamzas; judge would clear 75% of flags at ≈$480k archive-wide | marks in TEI (#trust/#why) and an annotated _trust.pdf
(incremental, drawing byte-identical) |`
