# 33 · An open line reader (Kraken), out of the box and fine-tuned on Mandumah

**Question.** How well does an open, CPU-only line reader (Kraken 7.1 with the OpenITI printed-Arabic model) read
Mandumah pages out of the box, compared with Azure, and how much does fine-tuning it on Mandumah's own lines improve
it? The "Kraken track" of [32's plan](../32_open_stack/research/03_build.md). Later in the night the brief grew: a
second engine (PP-OCRv6, kraken 7.1's new architecture), real-scan lines read by Azure as training data (round B),
a fine-tuned line finder, a targeted round for old prints, footnotes and vowelled lines (round C), and a first look
at a VLM (PaddleOCR-VL-0.9B).

The owner's page: `out/report.html` (line images with the truth and every reader's text, errors highlighted; bars to
scale; pages with the found lines drawn). Everything below is dated 2026-10-11/12.

## Answer, short

- **Out of the box Kraken is 3–12× worse than Azure.** Born-digital lines: 3.6% of characters wrong against Azure's
  1.0%; real scans: 24.5% of experiment 19's judged words wrong against Azure's 2.0% (body text 5.4% vs 1.1%).
- **Fine-tuning closes most of the gap on print like the training print, and part of it on real scans.** Born-digital
  lines 3.6% → **1.3–1.5%** (Azure 1.0%), scan-like copies 9.0% → **1.4–2.1%**; real-scan judged words 24.5% →
  **15.2%** (body text 5.4% → **4.3%**; Azure 1.1%), lines against Azure's reading 7.0% → **5.0%**, whole scanned
  pages 13.4% → **8.2%**. On real scans it is still **4–8× Azure**.
- **Kraken's own line finder is not the main loss**: it finds 93% of Azure's lines cleanly out of the box (see
  "The line finder").
- **A VLM off the shelf (PaddleOCR-VL-0.9B) reads single lines about as well as fine-tuned Kraken but invents and
  skips on whole pages** (44% of its page words are not in Azure's reading; one page ran to the 4,096-token cap).
- **Training on a rented GPU is ~110× faster than this laptop's CPU** (an epoch of 27k lines: 95 s against ≈ 3 h).

## Method

**Line truth from born-digital PDFs** (`lines.py`, `build_data.py`, `doc_quality.py`). Mandumah's born-digital PDFs
carry their own text, so every line comes with its exact reading. It is not read from MuPDF's lines: those mix the
producer's runs (`يراعي2».` for `يراعي».2`) and ligature glyphs extract with their letters reversed (`سالمة` for
`سلامة`, `املحترف` for `المحترف`). `lines.py` rebuilds each line from the glyphs: marks join the letter they sit on,
zero-width glyphs are ligature parts, glyph groups go right to left by position, and runs of Latin and digits are
turned back (a small inverse of the bidi rules). Two variants per document (ligature letters as stored or reversed;
brackets as stored or mirrored) are chosen by agreement with Azure: Azure only decides which of two deterministic
decodings a document's fonts need, never a line's text. Documents whose text layer is broken (junk symbols, fonts
that map ل to م, digit glyphs carrying the wrong codes: `6944، ص 613` printed as `1988، ص 147`) are dropped by
document-level agreement with Azure (median line CER ≤ 2%, 60% of lines within 2%, 80% of numbers agree); this keeps
107 of 165 Arabic born-digital documents and biases the test a little towards documents Azure reads well. Test lines
more than 30% away from **both** Azure and out-of-the-box Kraken are marked suspect and left out for every reader (72
of 4,161).

Documents: experiment 19's 80 Arabic born-digital documents plus 400 drawn here (one per journal, Arabic, printed
2005 or later, catalogue years). **Split by journal**: train 67 documents / 67 journals / 13,421 lines, dev 10 / 10 /
895, test 30 / 25 / 4,161 (2000s 40 lines, 2010s 2,604, 2020s 1,517). Up to 8 pages a document in train, 4 in
test. Each line is rendered at 300 dpi and also degraded to a scan-like copy (`degrade.py`: skew, lost resolution,
blur, ink spread or thinning, paper tint, uneven light, noise, specks, JPEG).

**Real scans** (`scan_sample.py`): the lines of experiment 19's 2,962 judged words, cropped from the 139 scanned
documents (1930s–2020s). Two measures: (1) the judged word, located in each reader's line by aligning that line to
Azure's, against the truth on the ink (Azure's word where the blind judge said right, the judge's reading where it
said wrong) under the judge's rule (letters and hamza count; vowels, kashida, punctuation and ى/ي do not); 2,894
words; (2) the whole line against Azure's line, **silver** (Azure's errors count against Kraken).

**Whole pages** (`fullpage.py`): each reader finds its own lines (kraken's default `blla` line finder); scored
against the PDF's lines (born-digital test pages) or Azure's lines (scans, silver), missed and invented lines
included.

**Normalisations** (`textnorm.py`): *faithful* keeps vowels, hamza forms, ى/ي, ة/ه and punctuation (NFKC, no
tatweel, one kind of digit, Persian ی/ک/ھ printed like Arabic letters folded to them); *search* also drops vowels and
punctuation and folds hamza seats, ى→ي, ة→ه. Rates are pooled over characters or words; 95% intervals bootstrap the
documents (1,000 draws).

**Readers.**

| tag | what | trained on | where, how long |
|---|---|---|---|
| base | OpenITI printed-Arabic model (zenodo 7050296, VGSL, 4.1 M parameters) | — | — |
| pp0 | PP-OCRv6 small multilingual base (zenodo 21788405) | — | — |
| cpuq | base, fine-tuned a quarter epoch | born-digital train (clean + scan-like, 27k images) | this CPU, 1 h; the run was stopped by the memory watchdog when a page job ran beside it |
| ftA | base, fine-tuned, kraken augmentation, early stop on dev (best epoch 16 of 20) | same | RTX 5090, 35 min (95 s an epoch) |
| ppA | pp0, fine-tuned 14 epochs (cosine) | same | RTX 5090, 60 min (4 min an epoch, batch 8) |
| ftB | ftA continued, 5 epochs | + 22,238 real scan lines read by Azure (every word ≥ 0.9 confidence; 269 documents, 160 printed before 2000; no journal of experiment 19) | RTX 5090, 45 min beside ppB |
| ppB | ppA continued, 3 epochs | same | same |
| ftC | ftA continued (round C) | see "Round C" | see "Round C" |

Line images are given to every model with a level baseline at 70% of the crop's height and the crop as boundary:
the OpenITI model was trained on baselines and read the same crops 40% worse as plain boxes (silver CER 10.4% vs
6.3% on 300 scan lines). Code: `krk.py`.

## Results

### Lines (characters wrong, faithful; [95% interval over documents])

| reader | born-digital clean | search-folded | scan-like copies | real-scan judged words wrong | … printed before 2000 | … body text | scan lines vs Azure (silver) | scan pages vs Azure (silver) |
|---|---|---|---|---|---|---|---|---|
| Kraken out of the box | 3.6% [2.6–5.0] | 2.5% | 9.0% [7.8–10.6] | 24.5% [22.3–26.6] | 22.1% | 5.4% | 7.0% [5.9–8.5] | 13.4% [10.4–16.9] |
| PP-OCRv6 out of the box | 3.1% [2.4–3.9] | 2.6% | 4.8% | 20.3% | 20.6% | 7.8% | 6.5% | – |
| Kraken, ¼ epoch on CPU | 3.0% | 2.3% | 5.9% | 23.9% | 22.9% | 5.7% | 6.8% | – |
| Kraken round A | 1.5% [1.0–2.2] | 1.2% | 2.2% [1.6–2.9] | 16.8% | 18.2% | 4.5% | 5.5% | 8.6% |
| PP-OCRv6 round A | 1.3% [1.0–1.8] | 1.0% | 1.5% [1.1–1.9] | 17.6% | 20.4% | 6.2% | 5.9% | – |
| **Kraken round B** | 1.5% [1.0–2.2] | 1.2% | 2.1% [1.5–2.8] | **15.2%** [13.6–16.9] | **16.0%** | **4.3%** | **5.0%** [4.1–6.3] | **8.2%** [6.8–9.8] |
| **PP-OCRv6 round B** | **1.3%** [1.0–1.8] | **1.0%** | **1.4%** [1.1–1.9] | 15.5% [13.9–17.2] | 18.1% | 4.3% | 5.0% [4.1–6.1] | 8.6% [7.2–10.2] |
| Azure | **1.0%** [0.8–1.2] | 0.6% | (never saw them) | **2.0%** [1.4–2.5] | 2.5% | 1.1% | (reference) | (reference) |

Words wrong on born-digital lines (faithful): out of the box 13.3%, round B 5.1% (Kraken) / 4.7% (PP-OCRv6), Azure
4.8%. Weighted like experiment 19 (each document counts with all its words), real-scan words wrong are 13.0% → 6.7%
(Kraken B) / 5.7% (PP-OCRv6 B) against Azure's 1.5%.

**By kind, born-digital** (clean, faithful; before → round B Kraken / PP-OCRv6, Azure): body 3.1% → 1.4 / 1.1, Azure
0.9; footnotes 3.9 → 1.7 / 1.8, Azure 1.5; headings 3.9 → 1.4 / 1.0, Azure 0.9; numbers 31.1 → 17.4 / 31.5, Azure 4.6
(digit order inside right-to-left lines); Latin 60.8 → 2.7 / 1.9 (the OpenITI model has no Latin letters until
fine-tuning adds them); vowelled (13 lines) 10.3 → 5.0 / 6.9, Azure 19.0.

**By kind, real scans** (judged words wrong; out of the box → Kraken B / PP-OCRv6 B, Azure): body 5.4 → 4.3 / 4.3,
1.1; first-page body 10.1 → 6.1 / 5.1, 0.0; footnotes 17.3 → 10.2 / 12.0, 1.4; vowelled 13.6 → 11.4 / 17.3, 3.1;
running heads 22.8 → 17.4 / 15.0, 1.2; headings 58.7 → 49.0 / 47.1, 2.9; first-page titles 31.5 → 21.8 / 16.4, 0.5;
numbers 32.7 → 21.8 / 30.7, 2.5; Latin 98.0 → 37.6 / 25.9, 9.1. The two engines differ: Kraken (VGSL) is better on
old print, vowelled lines, footnotes and numbers; PP-OCRv6 on modern print, titles, running heads and Latin.

### Whole pages

Born-digital test pages, each reader finding its own lines: out of the box 10.9% of characters wrong, round A 3.6%,
Azure 2.2% (scan-like copies: 13.0% → 4.2%). Scanned pages against Azure's lines (silver): 13.4% → 8.2% (Kraken B),
8.6% (PP-OCRv6 B); pre-2000 9.1%, 2000 on 7.2%. On the lines both found, Kraken B differs from Azure in 7.8% of
characters against 5.0% on Azure-cut line crops: the page loses about 3 points to how lines are found and cut, and
about 5.6% of Azure's lines get no Kraken line at all.

### The line finder

SEG_RESULTS

### Round C (old prints, footnotes, vowelled)

ROUND_C

### A first look at a VLM (PaddleOCR-VL-0.9B)

On 60 real-scan lines (7 per stratum) and 7 of 10 scanned pages from the line finder's test set, scored only (no
prompt or setting tuned on them). The model card's own transformers recipe, prompt `OCR:`, greedy, bf16. Lines: the
judged word wrong 26.7% (Kraken B 25.0%, PP-OCRv6 B 25.0%, Azure 1.7% on the same 60), 29.0% of characters
different from Azure (Kraken B 9.8%, PP-OCRv6 B 9.2%). Pages (word bags against Azure's page): it left out 30% of
Azure's words and 44% of its words are not in Azure's reading (Kraken B 11% / 11%, PP-OCRv6 B 18% / 18%); no
4-word loops, but one page ran to the 4,096-token cap and filled it with fully vowelled words that are not on the
page, and 3 pages did not finish inside the 25-minute cap (35–500 s a page). Running it took three tries: the
current model code fails under transformers 4.55 (the card's version) and under 5.0/5.19; revision `7faba727`
(2025-12-11) with transformers 4.57.1 runs.

## What it means

- An open line reader trained on our own pages gets **close to Azure on clean print like the training print**
  (1.3–1.5% against 1.0% of characters) and **robust to scan-like damage** (1.4–2.1%), but on **real scans it is
  still 4–8× Azure** (body text 4.3% of judged words wrong against 1.1%; all strata 15% against 2%). Born-digital
  lines alone teach modern typefaces; real-scan lines read by Azure (round B) help, most on old print (pre-2000
  18.2% → 16.0%) and footnotes (13.4% → 10.2%).
- It is **not yet a replacement for Azure**. It is already a useful **second reader**: its errors are local and
  visible, and it gives every line's position.
- **What would close the gap**, in order of evidence: many more real-scan lines (round B used 22k; Azure-read silver
  lines are free, and every journal outside the yardstick could give some), old typefaces specifically, and the
  owner's gold pages to measure on. A rented GPU makes each round minutes, not days, **if the data can be got to it**:
  tonight this machine's upload ran at 0.02–0.17 MB/s to every rented host (1.1 MB/s to Cloudflare), which blocked
  round C on the GPU.

## Limits

- Born-digital lines are easier than old scans, and the born-digital test is 2000s–2020s print only.
- The document filter that keeps trustworthy text layers uses agreement with Azure (whole documents only), which
  favours documents Azure reads well; Azure's 1.0% may be flattering.
- Real-scan line and page measures are silver (Azure's own errors count against Kraken); only the judged words
  (2,894, experiment 19's judge, 2% misses on one-mark changes) are against the ink.
- Round B's silver lines came from 32 journals that experiment 34 later held out for its yardstick (the rule arrived
  after the run): **ftB and ppB must not be scored on the yardstick**; rounds A and C and the line finder never saw
  a held-out journal (one born-digital training journal, 1 of 67, is also on the list).
- Numbers lines are scored with digits folded to one kind, and their order inside right-to-left lines is the PDF's
  reconstruction; treat the numbers row with care.
- The VLM test is a smoke test (60 lines, 7 pages), not a bake-off.

## Compute and spend

CPU (this machine, 16 cores, ≤ 8 GB for this experiment, watchdog `watchdog.sh`): fine-tuning reads 2.7 lines a
second whatever the thread count above 6 (an epoch of 27k images ≈ 3 h), peak 6.3 GB; inference 7–10 lines a second
with 2 workers; kraken's page finder 5–15 s a page. GPU (Vast.ai RTX 5090, datacenter, verified): the same epoch in
95 s (VGSL, batch 32) or 4 min (PP-OCRv6, batch 8). **GPU spend: SPEND** (credit $23.02 → CREDIT); every instance,
including the failures (three uploads too slow, one host stuck loading its image, the VLM's library mismatches), is
in `out/gpu_spend.jsonl` and the report. No paid API.

## Reproduce

```
python3 -m venv out/env && out/env/bin/pip install torch==2.14.1+cpu torchvision --index-url https://download.pytorch.org/whl/cpu
out/env/bin/pip install --no-deps kraken==7.1.1 && out/env/bin/pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
PYTHONPATH=../../src .venv/bin/python sample_docs.py 400 && inkscript fetch --id-file out/cand_ids.txt --out out/docs
PYTHONPATH=../../src .venv/bin/python meta.py
out/env/bin/python build_data.py --workers 3 && out/env/bin/python krk.py <model> out/lists/test_clean.txt out/preds/test_clean_base.jsonl
out/env/bin/python doc_quality.py && out/env/bin/python make_train.py      # then ketos compile (train.sh's header)
out/env/bin/python scan_sample.py && out/env/bin/python fullpage.py <model> <tag> [--scan] [--segmodel M]
out/env/bin/python silver_data.py && out/env/bin/python synth.py && out/env/bin/python pack_C.py
out/env/bin/python seg_data.py && out/env/bin/python segeval.py <tag> [model]
out/env/bin/python evaluate.py base pp0 cpuq ftA ppA ftB ppB ... && out/env/bin/python make_report.py
GPU: gpu_offers.sh; DPH=<$/h> gpu_run.sh <offer> gpu_job*.sh <files>; gpu_status.sh <host> <port>
```

Models (out/models, out/gpu): `arabic_best.mlmodel` (sha256 673064a5…), `ppocrv6_small.safetensors` (3108259…),
`ftA.safetensors`, `ppA.safetensors`, `ftB.safetensors`, `ppB.safetensors`. Versions: kraken 7.1.1, torch 2.14.1+cpu
here and 2.9.0+cu128 on the GPU, lightning 2.6.1.

## What it changed

STATUS (open reader measured), ideas.md (the three-layer idea's first measurement; silver real-scan lines as the way
forward), experiments/README. Nothing in `src/`.
