# Experiment 86: a public scoreboard for our line reader

**Question (lead, owner-approved 2026-11-05).** How does our own Arabic line reader score on public benchmarks, next
to the published numbers for Gemini, GPT-4o, Azure and Nuqta? The benchmarks are used **for testing only**. We never
train on them and never tune a setting on them.

**Status: done (2026-11-05/06, overnight).** Spend: **$0**. Everything ran on the local CPU (niced, 2 threads), with
no GPU and no paid API. Exp 89's final reader (**v7-28M**, `../89_final_reader/FINAL_READER.json`, sha256 ce8ea07c…)
was added on 2026-11-06, together with its 8M runner-up v7 (called **v7s** here).

**Framing.** Our reader reads **one printed line** at a time. It was trained only on Mandumah academic journal lines,
labelled from Azure, plus synthetic display-face lines from v5 onwards:
- v3 (exp 83);
- v6r (exp 85);
- v5 (exp 84: 50 display faces and white-on-dark lines);
- v7-28M (exp 89: 28M parameters, from scratch, v6r's labels and v5's synthetic lines);
- v7s (exp 89's 8M v7, fine-tuned from v6r).

Handwriting, manuscripts and scene text are not its job. They are listed below only as a reference.

![scoreboard](out/look/bench86_v7.png)

Picture: `out/look/bench86_v7.png`. The first version, `out/look/bench86.png`, showed v5 and v3.

## Result

### KITAB-Bench, printed subsets

The measure is the official CER (% of characters wrong), from KITAB-Bench's own scorer. Lower is better. The 95%
interval resamples items.

| subset (n) | **ours v7-28M** | v7s | v5 | v6r | v3 | Gemini-2.0-Flash | Azure OCR | GPT-4o | Nuqta-4B ‡ | Qari |
|---|---|---|---|---|---|---|---|---|---|---|
| PATS, 8 fonts, lines (500) | **1.00** (0.80–1.22) | 1.18 | 1.20 | 1.41 | 1.49 | 1 | 3 | 23 | 1.1 † | 0 |
| ISI-PPT, slide lines (500) | **3.08** (2.15–4.20) | 3.14 | 3.19 | 3.36 | 3.41 | 6 | 98 | 8 | 3.2 | 52 |
| SynthesizeAr, rendered + vowelled (500) | **5.86** (4.83–6.91) | 7.24 | 7.41 | 10.64 | 10.90 | 7 | 10 | 9 | 3.6 | 4 |
| ArabicOCR, paragraphs * (50) | **0.10** (0.05–0.16) | 0.06 | 0.05 | 0.11 | 0.14 | 0 | 1 | 6 | 2.1 | 1 |

WER, same scorer (published WER is quoted where the paper gives it):

| subset | v7-28M | v7s | v5 | v3 | Gemini | Azure | GPT-4o |
|---|---|---|---|---|---|---|---|
| PATS | 4.4 | 5.0 | 5.1 | 6.3 | 2 | 10 | 30 |
| ISI-PPT | 10.6 | 11.0 | 11.1 | 12.0 | 15 | 98 | 18 |
| SynthesizeAr | 21.2 | 26.0 | 27.1 | 36.6 | 17 | 27 | 20 |
| ArabicOCR * | 0.8 | 0.6 | 0.5 | 1.1 | 2 | 11 | 26 |

Our two other measures (CER %):
- **strict**: punctuation ignored; marks, hamza, ى and ة kept as printed (exp 85's `sform`, which is exp 81's
  scorer fix);
- **folded**: exp 81's folded form, with marks, hamza, ى/ة and punctuation folded.

| subset | v7-28M strict | v7-28M folded | v7-28M lines exact (folded) | v5 strict | v5 folded | v3 strict | v3 folded |
|---|---|---|---|---|---|---|---|
| PATS | 1.15 | 1.00 | 74% | 1.36 | 1.19 | 1.70 | 1.48 |
| ISI-PPT | 2.97 | 1.82 | 84% | 3.13 | 1.96 | 3.31 | 2.14 |
| SynthesizeAr | 11.90 | 5.56 | 48% | 13.55 | 7.07 | 19.28 | 10.61 |
| ArabicOCR * | 0.10 | 0.10 | 74% | 0.05 | 0.05 | 0.14 | 0.14 |

Notes on the tables:
- \* ArabicOCR is paragraph images. We cut the lines with our own simple splitter (`prep86.split_lines`), read them
  top to bottom, and joined them. The benchmark gives no line boxes, so the split is part of our pipeline here.
- ‡ Nuqta's numbers are its own runs, from its model card ("images as given", KITAB's scorer copied unchanged). The
  card discloses contamination: 234 KITAB test images (all KHATT-paragraph pages, all 10 HistoricalBooks pages, 13
  Muharaf, 11 KHATT lines) were in its training. † On PATS, "114 [of 500] texts also appear in our training data".
- Every other published number is from the KITAB-Bench paper (arXiv 2502.14949, Table 9). The paper prints them as
  fractions to 2 decimals (0.01 = 1%), so a published "0" means < 0.5%.
- Azure's ISI-PPT value of 0.98 is published as is; it looks like a failed run rather than a reading.

**Where we stand:**
- **PATS and ISI-PPT (printed lines in ordinary faces):** level with the best published systems. v7-28M is at 1.00%
  and 3.08%. We beat Azure and GPT-4o, and match Gemini-2.0-Flash and Nuqta-4B within noise.
- **ArabicOCR:** clean rendered paragraphs, near perfect for every reader. Its 50 items give only 5–30 wrong
  characters, so the readers cannot be ranked on it.
- **SynthesizeAr:** our weakness, though shrinking. Display and calligraphic faces cost us.
  - Each step adds display-face training: v3 10.9%, v5 7.4%, v7-28M 5.9%. That puts v7-28M ahead of Gemini (7%),
    Azure (10%) and GPT-4o (9%), but still behind Nuqta (3.6%) and Qari (4%).
  - Our strict CER is high (11.9%) because SynthesizeAr is fully vowelled (30% of its characters are marks). Our
    reader writes marks only as Mandumah print shows them, and mostly leaves them out here. The official scorer drops
    marks, so this does not count there.
- **v7-28M is our best reader on every line subset.** The 28M size helps most where the faces are unfamiliar:
  - SynthesizeAr: 5.9% against v7s's 7.2%;
  - the out-of-scope sets below.

  v6r (the hamza rule) is level with v3. That is expected: the official scorer folds hamza.

### KITAB's line set ("ourslines")

- 378 printed document pages with ground-truth line boxes; 7,447 text lines (tables skipped).
- We cut each line from its given box.

| | v7-28M | v7s | v5 | v6r | v3 |
|---|---|---|---|---|---|
| official CER, all lines | 16.7 | 17.0 | 16.8 | 16.7 | 16.8 |
| official CER, single-line boxes only (7,260; 187 boxes span several lines) | 14.9 | 15.2 | 14.9 | 14.9 | 14.9 |
| strict CER | 14.1 | 14.5 | 14.2 | 14.2 | 14.3 |

**This number does not measure reading. It measures the benchmark's references.**
- The references are the PDFs' text layers, and most are damaged:
  - the lam-alef ligature is stored backwards ("ال يقل" for «لا يقل», "االستئناف" for «الاستئناف»);
  - numbers and dates are in visual order ("16 9 1437" for 1437/9/16);
  - some fonts have broken encodings that come out as gibberish ("الصللةة يلغ ريلر للص");
  - one page is Hebrew.
- **I looked at 40 random lines where v3 and the reference differ** (strict form; `out/audit/`). The reference was
  wrong on 39 of the 40. v3 matched the print on 34. Its 6 misses:
  - 2 word spaces;
  - 1 missing first alif;
  - الفلة for الفئة;
  - 2 lines whose box cut off the line's start.
- Folding لا/ال on both sides (a diagnostic only) takes 2 points off.
- The published line-recognition numbers cannot be compared with ours:
  - EasyOCR 0.20, Tesseract 0.66, Surya 0.87 (Table 3) are end to end, with each system's own line detection;
  - KITAB's `lines-eval/metric.py` computes recognition only for the item with `idx == 0` (`if d['idx'] != 0:
    continue`), that is, on the first page alone.

### Out of scope (reference only: our reader was never meant for these)

| subset | v7-28M CER | v7s | v5 | v3 | Gemini | Azure | Nuqta ‡ |
|---|---|---|---|---|---|---|---|
| HistoryAr, manuscript lines (200) | 42.4 | 44.3 | 43.1 | 43.9 | 28 | 24 | 17.7 |
| ADAB, handwritten words (200) | 24.0 | 27.8 | 28.4 | 28.0 | 19 | 99 | 22.6 |
| EvArEST, scene-text words (800) | 14.2 | 15.1 | 15.0 | 16.1 | 18 | 32 | 13.6 |

EvArEST is word crops from photos of signs. That it is level with Gemini says more about short words in bold faces
than about scene text.

### Skipped because of licence terms

These are non-commercial or research-only. Exp 79 records Online-KHATT as non-commercial; KHATT is the same lab's
academic licence; Muharaf is CC BY-NC-SA 4.0 (`aamijar/muharaf-public`); Hindawi is CC BY-NC 4.0
(`alielfilali01/Hindawi-Books-dataset`).
- The sets: KHATT lines, KHATT paragraphs, Online-KHATT, Muharaf, Hindawi. HistoricalBooks was skipped too: it is
  manuscript pages with no line boxes.
- They were downloaded and read before the licence check finished. Their numbers are **not** on the scoreboard.
- With the owner's approval, the lead deleted their data, crops and readings on 2026-11-06. Do not download them
  again.

## Licences

| benchmark | where | licence / terms (exact) | used |
|---|---|---|---|
| KITAB-Bench code + scorer | github.com/mbzuai-oryx/KITAB-Bench @ 06183eb | **MIT** ("Copyright (c) 2025 Ahmed Heakl") | scorer reproduced verbatim (`score86.preprocess_arabic_text`); torchmetrics' CER/WER match ours to the last digit on 3 subsets |
| KITAB-Bench data | HF `ahmedheakl/arocrbench_*` (14 sets, not gated) | No licence field on 13 cards. `arocrbench_khatt` says `license: mit`, but KHATT's own terms are academic. Each set's terms are its source's. | evaluation only, nothing redistributed |
| PATS (KITAB's 500 of PATS-A01) | KFUPM, faculty.kfupm.edu.sa/ics/muhtaseb/ArabicOCR/PATS-A01.htm | no licence stated on the page; its papers say "freely available to interested researchers" | yes, KITAB's 500-line sample |
| PATS-A01 full (2,766 lines × 8 fonts) | same page | as above | **not obtained**: the image archives (`A01-*.rar`) return KFUPM's "File Download Blocked … in accordance with company policy" page. Only the ground-truth text files came down (`data/pats_a01/`). The owner can fetch the archives by hand. |
| ISI-PPT | gitlab.com/rex-yue-wu/ISI-PPT-Dataset | no licence stated; "please kindly cite our paper" | yes |
| SynthesizeAr, ArabicOCR, HistoryAr, the KITAB line set | KITAB only | no licence found | yes (evaluation only) |
| EvArEST | HF Melaraby/EvArEST-* | BSD-3-Clause | yes (reference) |
| ADAB | IEEE DataPort | CC BY 4.0 (exp 79's DATASETS.json) | yes (reference) |
| Online-KHATT / KHATT / Muharaf / Hindawi | see above | non-commercial / CC BY-NC(-SA) | **skipped** |
| APTI (word images, 10 fonts) | diuf.unifr.ch/diva/APTI | "freely available for the scientific community" (paper) | **not obtained**: the site no longer resolves, and the only HF entry (`benhachem/APTI`) is empty |
| Nuqta's numbers | HF SalahALHaismawi/Nuqta-Arabic-OCR-4B @ 6a8cdd6 | Apache-2.0 (card) | quoted only |

## Method

**1. Data (`dump86.py`).**
- The 14 KITAB parquet files were fetched straight from Hugging Face. `dump86.py` writes each image byte for byte,
  with one ground-truth jsonl per subset.
- The ground-truth column is the one the official `ocr-eval/eval.py` reads.
- Everything is under `data/`, which is gitignored.

**2. Our reader's input (`prep86.py`).** Exp 77 cuts a line from Azure's polygon: height h, PAD_V·h above and below,
PAD_H·h at the ends, scaled to height 48. A benchmark image has no polygon, so the step is:
- find the line's ink box: Otsu threshold, coordinates trimmed at the 1st and 99th percentiles of the ink pixels;
- turn it into the polygon Azure would have drawn, using medians **measured on exp 77's own dev crops (8,196 of our
  lines, never a benchmark)**: polygon height = 1.28 × ink height, centre 0.03·h higher, ends 0.25·h / 0.16·h
  beyond the ink (`out/calib86.json`);
- cut with `common77.cut_line(test=True)`.

Per image:
- RGBA is laid on white, and colour goes to grey;
- light-on-dark images are inverted: PATS 55, ISI-PPT 78, EvArEST 428;
- the border is extended in the image's own ground colour.

Per subset:
- **KITAB line set:** each 'line' box gives the ink box inside it. 134 boxes have no ink of their own and score as
  empty readings.
- **Paragraph images:** a row-profile splitter.
  - Its first version found only 2 "lines" on pages whose lines touch, and read 6 Hindawi pages as empty.
  - I added a cut at the profile's minima, one per line pitch. The pitch comes from the profile's autocorrelation.
  - This was checked by looking at the boxes (`out/look/split_13.png`), not at a score. It did not change ArabicOCR
    (205 lines before and after).
- Right to left: `train77.py infer` unchanged (flip, then CTC, then `from_visual`).

**3. Reading (`read86.sh`).**
- `train77.py infer --workers 0 --threads 2` under `nice -n 19 ionice -c3`, on CPU at 8–60 lines/s.
- Weights:
  - v3: `../83_reader_scale/out/weights/v3/best.pt`;
  - v6r: `../85_disputes/out/host/run_v6r/best.pt`;
  - v5: `../84_display_fonts/out/weights/v5/last.pt`;
  - v7-28M: `../89_final_reader/out/weights/v7_28m/last.pt`;
  - v7s: `../89_final_reader/out/weights/v7/last.pt`.
- Same model code, same 462-class charset.

**4. Scoring (`score86.py`).**
- official: KITAB's `preprocess_arabic_text`, verbatim, then corpus CER and WER (torchmetrics' definition).
- strict and folded: as above.
- A 1,000-draw item bootstrap for the official CER.
- Missing crops count as empty readings.
- Published numbers are in `published86.json`, with their sources.

## Caveats

- **Conventions.**
  - The official scorer drops vowel marks and folds أإآٱ→ا, ة→ه, ى→ي, but keeps punctuation, digits and Latin.
  - Our reader writes digits as printed. ISI-PPT and the KITAB line set use Western digits.
  - ISI-PPT has Latin (2.4% of characters), Hebrew, and Persian or Urdu letters, which our charset lacks. On its 436
    lines without them, v5 scores **1.63%** (diagnostic).
  - ISI-PPT and the KITAB line set write mixed Arabic/Latin lines in visual order. Our reader writes logical order.
  - ISI-PPT prints «ﷺ» as a glyph, and its truth expands it to صلى الله عليه وسلم.
- **The published numbers are other people's runs**, at their dates and model versions (Gemini-2.0-Flash and GPT-4o
  as of the KITAB paper). We did not re-run them; no paid API was used.
- **Small sets.** ArabicOCR is 50 paragraphs; the intervals above say how much that matters.
- **Nothing was tuned on a benchmark.**
  - The calibration came from our own crops.
  - The polarity rule is generic.
  - The splitter change followed a visible failure. It was checked on the boxes, never on a score.
  - The readers are exactly the weights of exps 83, 84 and 85.
- **Exp 89's readers** were read with `train77.py infer`. Its `Reader` class is identical to train89's, and it
  takes the 28M's sizes from the checkpoint's meta.
  - v7-28M: 7–23 lines/s on 2 CPU threads, about 35 minutes for every subset.
  - Rerun everything: `bash read86.sh NAME CKPT` per reader, then `score86.py v3 v6r v5 v7s v7`.

## Files

- `dump86.py`, `prep86.py`, `read86.sh`, `score86.py`, `fig86.py`, `published86.json`.
- `out/`: `scores86.json` and `scores86.txt` (every reader × subset × measure), `calib86.json`, `pred/`, `shards/`,
  `audit/` (the 40-line look at the KITAB line set), `look/bench86_v7.png` (first version: `look/bench86.png`).
- `data/` (gitignored): `KITAB-Bench/` (clone), `kitab/` (parquet), `kitab_img/`, `pats_a01/` (ground-truth text
  only), `papers/` (the KITAB paper's HTML, Nuqta's card, the PATS page, the ISI-PPT README).
