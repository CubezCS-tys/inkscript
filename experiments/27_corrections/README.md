# 27 · Corrections from exact sources, judged on the ink, in the text only

**Question.** The product (experiment 24) flags 7.9% of words and corrects none. A Quran quotation that differs
from its verse is an exact second source: experiment 20 found 20 of 24 such words to be Azure misreadings. Can
those differences become corrections — proposed from the verse, accepted only when a judge looking at the scan
agrees, written into the PDF's *text* (never its ink), the ALTO, the JATS and the trust PDF? And can the flags
be made less noisy (about 1 in 7 is a real error) without losing the errors they catch?

**Answer (2026-10-06).** Yes, both. On the 20-document set of experiment 24:

| | |
|---|---|
| differences between a quotation and its verse | 290 words or gaps, in 152 quotations |
| **proposed** | **194** (126 letters, 64 dots, 4 merges); not proposed: 73 the author's wording, 18 the print's spelling, 2 quotation edges |
| accepted (Flash picked the verse's word, then Pro agreed) | **156** |
| **applied** — in both PDFs' text, the ALTO, JATS and trust PDFs | **147** (90 letters, 55 dots, 2 merges), in 15 documents |
| declined by the PDF | 9: 4 shorter than the word's glyphs (D13), 4 words with no glyph of their own, 1 whose glyphs did not read the printed word |
| turned down on the ink | 29 by Flash (13 the print reads as it is, 16 neither), 9 by Pro (3 / 6) |
| the faithful PDFs' drawing | **pixel-identical** on every page with a correction (pdfium render, both PDFs, 15 documents), the original bytes the file's prefix |
| nothing else moved in pdfium | on every corrected page, pdfium's words before and after differ only where a correction is: 252 changed spots (both PDFs), 0 unexplained; words intact 83,842 → 83,844 of 83,856 (corrected words counted with their new text); every correction's text found on its page, 147/147 |
| JATS / ALTO valid, trust PDFs read like the faithful ones | 20/20, 20/20, 20/20 |
| quotations equal to the verse | 235 → **290** of 387 |
| **words flagged** (product rule + the common-word refinement) | **7.9% → 5.3%** (6,677 → 4,421); Quran flags 244 → 97 |
| on experiment 19's judged words | flags **7.5% → 5.0%**, judged errors caught **50 → 50** of 61, 1 flag in 8.9 → **7.4** a real error, unflagged words wrong 0.43% → 0.42% |
| Gemini spend, everything | **$1.13** of the $6 cap (calibration $0.33, the set $0.80) |

The report for the owner is `out/report.html`: every applied correction on its ink, what the judges turned down,
the flag numbers as pictures, the PDF checks.

## Method

* **Proposals** (`src/inkscript/enrich/corrections.py`, `propose`). Every quotation `enrich/quran.py` finds; each
  difference of kind dots or letters is a candidate. Not proposed (the categories are printed with each skip):
  *wording* — و/ف where the author began the quotation, a missing word, a word not in the verse, a different word,
  and a confident reading (≥ 0.95) that differs by a particle or ending or is simply another word (ربهم/ربكم,
  دعوانا/دعواهم, الإسلام/المرسلين); *spelling* — the print's orthography, by a key that forgets final ة/ت, ى/ي,
  doubled و/ي, hamza and its seats and alefs (فطرة/فطرت, نعمة/نعمت, داود/داوود, مسؤولا/مسئولا, النبيئين); *edge* —
  a token with digits or a slash, a reading word much longer than the verse word, the first or last word of a
  quotation not close to its verse word. A **merge** — one box Azure read for several verse words that the
  alignment calls missing — is proposed as one correction whose text holds the words with spaces; when its letters
  are right only the spaces are added to Azure's own letters (إلاماشاء → إلا ما شاء). **Splits** (two boxes for one
  verse word) are not proposed: joining them would need a glyph with no text (D13). The corrected text keeps the
  word's punctuation and takes the verse's letters, with Tanzil's short vowels when Azure's reading was vowelled.
* **The judge** (`src/inkscript/enrich/judge.py`): experiment 17's method and its third crop (the word's own line
  at 300 dpi from the scan, the paper behind the word tinted, nothing on the ink), the printed reading and the
  proposal as A/B in an order fixed by a hash of the item, temperature 0, JSON schema, six crops a request; the
  prompt adds that vowelled Quranic script's marks are ignored, a small alef above counts as an alef, and two
  readings that differ only by spaces are judged on the printed words. Flash first; a proposal Flash accepts goes to
  Pro; both must pick it. Answers cached (`out/judge_cache.jsonl`), every request's cost in `out/spend.jsonl`, a
  request that would cross the cap is not sent, three tries at most.
* **Calibration** (`calibrate.py`). 48 Quran words of the set that the print, Azure and the verse agree on
  (conf ≥ 0.9, half vowelled), against a look-alike (dot group, hamza, ة/ه, ى/ي, a dropped letter) or two
  look-alikes: Flash 36/36 + 11/12, Pro 36/36 + 11/12 (the same miss: إيمانا printed without its hamza). Then the
  other direction (`--reverse`), which a judge leaning to the Quran's word would fail: 28 quotation words where the
  print is the author's wording or spelling, read by Azure at ≥ 0.95 — **Pro 28/28, Flash 25/28** (its three misses
  read only the part of the word the tint covered: a و outside it, ومن → من). Hence Flash first (half the price),
  Pro to confirm.
* **Applying** (`inkscript fix --apply`; `src/inkscript/pdf/correct.py`). The accepted text replaces the ToUnicode
  entries of the word's glyphs, dealt out letter by letter (a space rides on the letter before it), incremental
  save. Two fixes came out of this run: a glyph now belongs to the word when its *middle* lies in Azure's box (the old
  rule, 80% inside, left out letters that reach past the box: رفير → زفير read رزفير), and the glyphs must read the
  printed reading before they are changed, or the correction is declined. Then the pages with a correction are
  rendered before and after in pdfium and compared pixel for pixel (`verify_ink`), and `enrich` rewrites the ALTO,
  JATS and trust PDFs from the reading with the applied corrections laid over it (`corrections.overlay`).
* **Fewer flags** (`lexicon.py`, `flags_eval.py`). Experiment 19's 2,971 judged words, 2,935 found in the product's
  own reading (`enrich.document.load`), signals computed by `trust.signals` with the ink on the scan; truth and
  weights as in experiment 22 (61 errors after the same exclusions). Candidate refinements of a flag raised by
  confidence alone: (a) title words and large type flagged only below 0.5; (b) a common word — read with
  confidence ≥ 0.95 in ≥ K other documents of 400 (experiments 19 and 16; the word's own document left out); (c) the
  same word read confidently ≥ N times elsewhere in the document. (b) at K = 5, conf ≥ 0.6 is the product rule now
  (`trust.refine`, list shipped in `src/inkscript/data/lexicon/`, 22k keys).

```
PYTHONPATH=src .venv/bin/python experiments/27_corrections/calibrate.py gemini-3.8-flash gemini-3.1-pro-preview --n 36 --go
PYTHONPATH=src .venv/bin/python experiments/27_corrections/calibrate.py gemini-3.8-flash gemini-3.1-pro-preview --reverse --go
.venv/bin/inkscript fix experiments/27_corrections/out/set/w0 …/w1 …/w2 --azure-dir experiments/24_product/out/azure \
    --apply --cap 6 --spend-log experiments/27_corrections/out/spend.jsonl --cache experiments/27_corrections/out/judge_cache.jsonl
python lexicon.py && python lexicon.py ship && python flags_eval.py features && python flags_eval.py
python reenrich.py && python skipped.py && python verify_set.py && python make_report.py
```

`out/set/` is a copy of experiment 24's set (its PDFs untouched there); `out/fix_set.log` the run.

## Results in detail

**Rule refinements on the judged words** (`out/flag_eval.json`):

| rule | flagged | n | caught | 1 flag in | unflagged wrong |
|---|---|---|---|---|---|
| product as of experiment 24 | 7.48% | 447 | 50/61 | 8.9 | 0.431% |
| **+ common word (≥ 5 documents) at conf ≥ 0.6 — taken** | **5.02%** | 370 | **50/61** | **7.4** | 0.420% |
| common word, conf ≥ 0.5 | 4.87% | 353 | 48/61 | 7.4 | 0.420% |
| title / large type only below 0.5 | 7.47% | 434 | 49/61 | 8.9 | 0.431% |
| same word confident ≥ 2× elsewhere in the document, conf ≥ 0.5 | 6.33% | 416 | 49/61 | 8.5 | 0.426% |

The errors the looser variants lose: فى read as في at 0.56 (a print's ى/ي, the corpus reads في everywhere), a
doubtful سالفة/والفة at 0.59, a handwritten title word at 0.54. Two independent readers agreeing could not be
measured: experiment 19's documents have no Gemini page 1, and the feeler agrees with Azure mostly where Azure is
right (D19); the rule keeps Gemini's page-1 agreement as *verified*, as before.

**What the judges turned down** is instructive. In `1232-007-008-003` (vowelled Quranic text, the most proposals:
88, 73 applied) Azure's word boxes sit up to half a word off the ink, and the judge, seeing the tint over the
neighbouring word, answered *neither* and wrote the neighbour (ثوابا, شهدآء, آبائك) — a refusal, as it should be.
"Printed reading" verdicts are the author's text after all: المسيطرون (the print's spelling of المصيطرون), تم for
ثم, جعلنا, المنتظر, ويخرج. Some *neither* answers wrote the proposal itself with different punctuation (قسورة ، for
قسورة)) or wavered (خلقوا); they were not accepted.

## What it means, and limits

* The Quran check now **corrects** rather than only flags: 147 words on 20 documents, 290 of 387 quotations equal
  to their verse. The faithful PDF still draws exactly what it drew; only what its glyphs map to changed, and the
  ALTO keeps Azure's reading beside the corrected one.
* **Precision rests on two judges and the calibration**; no person has checked the 147 (the report shows each on its
  ink for that). The calibration covers clean one-mark look-alikes and the author's wording, not every kind of
  damage.
* 9 accepted corrections could not be written: D13 (a shorter word than its glyphs) and words Azure boxed where no
  glyph is drawn. They stay flagged; the log says why.
* The common-word list is tuned in-sample on 61 errors (round thresholds, chosen on the trade-off table), and 12 of
  the set's 20 documents are among its 400 sources (their own words add at most one document to a count).
* The trust PDF's new "Corrected words" layer was checked in pdfium, not in a real Chromium.
* Lines in reading order, counted the build's way, read 7,568 → 7,564: that check finds a line by its words' text,
  and a corrected common word (ما, إن) can be credited to another line; the word-by-word comparison above shows
  that nothing but the corrected words changed.

## Files

`calibrate.py` · `lexicon.py` · `flags_eval.py` · `reenrich.py` · `skipped.py` · `verify_set.py` · `make_report.py` ·
outputs in `out/`: `set/w*/` (per document also `<stem>.corrections.json`), `calibration.json`,
`calibration_reverse.json`, `flag_features.json`, `flag_eval.json`, `skipped.json`, `verify_set.json`,
`reenrich.json`, `spend.jsonl`, `judge_cache.jsonl`, `report.html`. Code in `src/inkscript/enrich/corrections.py`,
`judge.py`, `trust.py` (`refine`), `pdf/correct.py`, `cli.py` (`fix`); tests in `tests/test_corrections.py`.
