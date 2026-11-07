# Experiment 78: synthetic printed lines for our own line reader

**Question (owner, 2026-11-04).** Experiment 77 trains a line reader from scratch on real line crops labelled by
Azure. Can lines we *render ourselves* (free fonts, typefaces traced from our own old scans, real paper, scan damage)
teach the same reader? Three arms with the same model and settings: **synthetic only**, **synthetic then real**
(pretrain on synthetic, fine-tune on experiment 77's real lines), and experiment 77's **real only** as the reference.
Tested on held-out real pages only. Cap: $20 GPU on Vast, no paid API.

**Status (2026-11-05): done.** GPU $6.14 of the $20 cap (one RTX 5090 at $0.96/h, 384 minutes including ~50 idle
minutes at the end before the keeper destroyed it; `vastai show instances` empty afterwards). No paid API.

**Verdict.** Synthetic lines alone teach our reader to read 98% of the letters of old held-out pages (1.74% wrong
with v2, vs 0.75% from real lines). Pretraining on them does not improve a reader that already has 520k real lines,
but with 10% of the real lines it cuts word errors by 40%. **What it changed:** synthetic lines are a tool for the
scarce cases (old print, rare journals, new scripts or layouts), not a replacement for real labels; and kashida must
be rendered (it was the synthetic reader's biggest error). **Next step:** use v2 synthetic as pretraining for the
old-print reader (experiment 77's v2b with exp 80's old lines), and for the small-data arms (a new journal, Latin
or tables) measure how many real lines synthetic pretraining saves (a 1%, 3%, 10%, 30% curve, ~$1).

## Result

Seven readers, one model (experiment 77's v1 CRNN, 8.3 M parameters), scored by experiment 77's harness on its
held-out test crops. **Letters** = CER with punctuation removed (marks, hamza, ى/ي and digits count); **words** =
order-free word error; both in %. "+p" = with punctuation counted (shown apart: the spacing rule is still the owner's
open question). Real-only is experiment 77's v1 (520k Azure-labelled real lines, 16 epochs).

| reader | owner's 20 pages: letters | words | letters+p | lab docs 1-2: letters | words | doc 3 vs Argon: letters | words |
|---|---|---|---|---|---|---|---|
| Azure (for reference) | 0.60 | 1.42 | 0.84 | 0.23 | 1.32 | 0.07 | 0.36 |
| **real only** (exp 77 v1) | **0.75** | **1.92** | 1.17 | 0.20 | 1.50 | 0.31 | 1.73 |
| **synthetic only**, v1 (600k lines) | 2.75 | 10.86 | 3.38 | 1.47 | 7.12 | 1.36 | 6.57 |
| synthetic only, v2 (600k, old print, kashida) | 1.74 | 6.27 | 2.51 | 1.37 | 6.29 | 1.40 | 6.85 |
| **synthetic v1, then real** | **0.72** | **1.93** | 1.12 | 0.16 | 1.31 | 0.31 | 1.73 |
| synthetic v2, then real | 0.78 | 1.99 | 1.17 | 0.20 | 1.60 | 0.21 | 1.28 |
| 10% of the real lines only (55k) | 1.33 | 4.58 | 1.75 | 0.65 | 3.57 | 0.70 | 3.91 |
| **synthetic v1, then 10% real** | **0.96** | **2.75** | 1.40 | 0.36 | 2.35 | 0.31 | 1.64 |

Whole lines right on the owner's 20 pages (no punctuation): real only 89.3%, synthetic-then-real 90.4%, synthetic
v1 52.0%, v2 68.6%, 10% real 76.1%, synthetic-then-10%-real 84.4%. Experiment 77's real dev lines (Azure labels):
real only 1.01% CER, synthetic-then-real 1.03%, v2-then-real 1.01%; synthetic-only v1 3.4%, v2 2.9%.
Picture: `out/look/results78.png`; confusions with crops: `out/look/confusions_*.png`.

**What it shows.**
1. **The gap.** Trained on rendered lines alone, the reader gets 2.75% of letters wrong on the owner's old pages
   (v1), **1.74% with v2**, against 0.75% for the same reader on 520k real lines: 2.3 times the real reader's
   letter errors and 3.3 times its word errors. Without a single real label, it reads 98% of the letters.
2. **Version 2 closed a third of the gap**, from one finding: the v1 reader's most common error (195 times on 20
   pages) was an inserted س wherever old print stretches a join with a kashida, which no font draws by itself. v2
   draws kashida in 30% of lines (label without it), adds old-print text, paper and traced typefaces; on the owner's
   (mostly old) pages letters fell 37% and words 42%. On the modern lab document 1 and on document 3 it changed little.
3. **With all the real lines, synthetic pretraining does not beat real only**: 0.72 vs 0.75 letters, 1.93 vs 1.92
   words on the owner's pages, 0.16 vs 0.20 on documents 1-2 (7 vs 8 words), equal on document 3; v2-then-real is
   0.78 / 1.99 (document 3 better, 0.21 vs 0.31). These differences are a few words out of ~6,000 and within noise.
   It does converge faster: after one real epoch the pretrained reader's dev CER is 1.27%, which real-only reached
   only after six.
4. **With little real data, it clearly does.** On 10% of the real lines, pretraining on synthetic cuts letter errors
   on the owner's pages from 1.33% to 0.96% (-28%), words from 4.58% to 2.75% (-40%), documents 1-2 from 0.65% to
   0.36%, document 3 from 0.70% to 0.31% (= the full real reader). Synthetic lines are worth most where real labels
   are scarce: rare journals, old print, new layouts.
5. **What is left is mostly not reading.** The fine-tuned readers' top confusions on the owner's pages are spaces
   (42 missing, 28 extra), «» read as (( )) (Azure's convention, learned from the real labels; the owner's gold
   itself writes (( )) in some lines), a space before ( ) and أ/ا. The synthetic-only readers' «» are the printed
   ones, and the owner's truth counts them wrong where it writes (( )): part of the synthetic "gap" is label
   convention, not sight.


## Method

**Same reader, same test, same scorer as experiment 77.**
- `train78.py` is experiment 77's `train77.py` (the version of its v1 run: CNN + 2-layer BiLSTM + CTC, 8.3 M
  parameters, height 48, 16 epochs, lr 1e-3, OneCycle, the same augmentation), plus `--init` (start from a
  checkpoint; the charset is kept and new real characters appended), `--realdev` (log the real dev CER of a synthetic
  run; never used to pick a checkpoint) and a guard that stops OneCycleLR from being stepped past its end.
- `common78.py` is experiment 77's `common77.py` (crop geometry, labels, right-to-left target) plus a reader of
  experiment 80's page list.
- `eval78.py` is experiment 77's `eval77.py`, reading its test pages (`experiments/77_scratch_reader/out/test`, read
  only): the owner's 20 checked yardstick pages, lab documents 1-2 (owner rev1) and document 3 (Argon only, not a
  truth). Letters = CER without punctuation in the truth's line order; words = order-free word error (the lab's
  `bag`, `experiments/75_ocr_lab/labocr/evaluation.py`); punctuation and the space before it are shown apart.
- Real-only numbers are experiment 77's own predictions (`out/pred/test_v1.jsonl` there), scored here.

**Text** (`text78.py`, `out/text/`). 1.5 M lines drawn from 221,328 Azure lines of 680 articles of training-pool
journals (every pre-2000 article of experiment 77's pool and as many modern ones; experiment 76's 27 held-out journal
codes are asserted out, so no owner page and no lab document can leak). Rare things weighted up (marks ×4, لل, ى,
hamza forms, digits, brackets, Latin); 20% cut to 1-6-word snippets, 20% two lines joined; 15% random strings
(random letters and words, Arabic-Indic and Latin digits, punctuation, footnote marks «(1)» «١» and note calls drawn
as ¹²³ but labelled as plain digits as the owner's truth writes them, page numbers, dates, references, Latin words,
brackets and quotes). Old spelling (final ي→ى, إلى→الى, hamza dropped on initial alef) in 35% of lines from
pre-2000 articles and 15% of the rest; printed marks in 6%. Version 2 adds `text80.jsonl.gz`: 400k lines from
experiment 80's old-print pull (580 documents, 1924-1999, 158,579 Azure lines), 40% of v2's lines.

**Fonts** (`out/fonts/`; every licence recorded below). Shaping by Pillow 13.0.0 with raqm 0.11 (HarfBuzz 14.5,
FriBiDi 1.0): checked by eye on `out/look/shaping_check.png` (joins, lam-alef, لله, bidi of numbers and Latin), and
the rented host was checked to render byte-identical sheets. Lines without an Arabic letter are laid out left to right.

| family | licence | weight in the mix |
|---|---|---|
| Amiri (Regular, Bold) | OFL 1.1 | 10 + 4 |
| Scheherazade New (Regular, Bold) | OFL 1.1 | 7 + 3 |
| Noto Naskh Arabic (variable 400-700) | OFL 1.1 | 10 |
| Lateef (Regular, Bold), Markazi Text, Harmattan, Mirza | OFL 1.1 | 4+2, 5, 3, 4 |
| Noto Sans Arabic, IBM Plex Sans Arabic, Vazirmatn, Cairo, Tajawal, Almarai, Readex Pro, El Messiri | OFL 1.1 | 5, 4, 3, 2, 2, 2, 1, 1 |
| Noto Kufi Arabic, Reem Kufi, Kufam, Aref Ruqaa, Alkalami | OFL 1.1 | 1, 0.5, 0.5, 0.7, 0.3 |
| Latin-only lines: Tinos (Regular, Bold, Italic), Noto Serif (3), Noto Sans (2), Source Serif 4, Crimson Pro, Courier Prime | OFL 1.1 (google/fonts METADATA; Noto from the system's fonts-noto) | 6, 2, 1.5; 2, 1, 0.5; 2, 1; 2; 1; 0.7 |
| **typefaces traced from our own scans** (experiment 11's `make_font.py`) | ours, private (never leave this machine and the destroyed host) | 12% of lines (v1), 20% (v2) |

Traced typefaces: 14 traced from training-pool articles of 1927-1958 (v1: 0737 1937, 0924 1928, 0775 1958, 0300
1957, 0484 1958, 0756 1951 from experiment 77's pool; v2 adds 0924 1936, 0739 1938, 0917 1927, 0775 1949, 0749 1951,
0873 1940, 0763 1936, 0690 1948 from experiment 80). Every one was looked at as a specimen (`specimen78.py`, every
letter in four forms beside Amiri, `out/look/specimen_*.png`). **None is clean**: each has 4-8 wrong glyphs (an
isolated ه or ة with a stray alef, ء drawn as و or ر, إ/أ without hamza, ئ without body, ي without dots). Three were
dropped (0484, 0756, 0690: too many); the others are used only for text that avoids their wrong forms
(`out/fonts/traced/exclude.json`, characters and isolated forms, with what was seen), which limits them to about
6-10% of texts, mostly short. As experiment 11 found, a wrong glyph is a systematic wrong cut; here it would have
been a systematic wrong label.

**Damage and paper** (`render78.py`). Ink spread or erosion, broken strokes, faded and uneven ink, blur; real paper
cut from blank areas of training-pool scans (`bg78.py`: 806 patches from 500 pages, v2 adds 869 from 600 old pages of
experiment 80) or plain paper; show-through from mirrored real text patches (328 + 379); curl, a residual skew,
noise, specks, bilevel thresholding (25%), low resolution, scanner JPEG; neighbouring lines above and below (real
crops show their dots and descenders). Then an Azure-like polygon and experiment 77's own `cut_line` (pad 0.22 /
0.35, height 48, JPEG q80). Calibrated on experiment 77's crops with `stats78.py`: darkest row 28 of 48 (real 28),
ink bottom 39 (real 38), 12.0 pixels a character (real 11.6), darkest ink p3 37 (real 21).
Version 2 (after the confusions of v1, below): stretched joins (tatweel/kashida) in 30% of Arabic lines, the label
without them; old text and old paper from experiment 80; the 11 reviewed traced typefaces at 20%.

**Look before generating** (`look78.py`). Four rounds of contact sheets, 50 synthetic beside 50 real crops, and a
blind mixed sheet with a key (`out/look/cmp_v1..v4*.png`, `cmp_v2data*.png`). Round 1: text too small and too high,
ink too light, grey paper too often, Latin lines shaped right to left. Round 4: in the blind sheet most rows cannot
be told apart; what still gives synthetic away is random-letter strings and a few rare fonts.

**Scale.** v1: 600,000 training lines (+6,000 dev), rendered on the rented host's CPUs (the container had 7.7 cores,
~600 lines/s), stopped at 2 full shards per worker so that the GPU would not sit idle past ops/vast_guard.sh's 30
minutes. v2: 600,000 more lines (+6,000 dev), from the v2 recipe. Nothing was rendered at scale on this machine.

## Prior art (indicative only)

Mostafa et al. 2021 ("OCFormer") and Mostafa et al. 2022 ("An End-to-End OCR Framework for Robust
Arabic-Handwriting Recognition using a Novel Transformers-based Model and an Innovative 270 Million-Words Multi-Font
Corpus of Classical Arabic with Diacritics", [arXiv 2208.11484](https://arxiv.org/abs/2208.11484)) trained on a
synthetic corpus of 30.5 M single-line images (270 M words, 1.6 B characters) rendered in 12 Arabic fonts "that
closely resembled archaic fonts used in historical printings" (the fonts are not named in the paper), plus KHATT
handwriting. Their degradation is generic augmentation (cropping, padding, flipping, zooming, rotation, shearing,
brightness, random-angle rotation and line stretching) on "noisy" renders; real paper or show-through is not
described. They trained on 100,000 of the images and report CER 4.46% (2022, BEiT encoder + Transformer decoder;
OCFormer 2021: CER 7.27% with all fonts and diacritics, and 0.32% in its controlled setting as the IJCV 2026 review
reports it; the 2021 paper itself was not found openly) **on held-out lines of
the same synthetic corpus**, with CER as character edit distance over the reference length. Their test is synthetic;
ours is real held-out print scored against the owner's corrections, so the numbers are not comparable: our
synthetic-only reader's 2.75% letters on real old pages (punctuation removed) is a harder test than theirs.
Shugaba et al. (IJCV 2026), the review that pointed to them, is in `experiments/79_signal_reader/data/`.

## Files

- `text78.py`, `bg78.py`, `render78.py`, `look78.py`, `stats78.py`, `specimen78.py`, `trace_fonts.sh`
  (+ `trace_list.txt`, `trace_list2.txt`): data.
- `train78.py`, `gs78.py` (experiment 77's `gs77.py` pointed here), `setup_gpu78.sh`: GPU.
- `eval78.py`, `sheet78.py`: scores, `out/results78.json`, `out/confusions78.json`, `out/look/results78.png`,
  `out/look/confusions_*.png`.
- `out/` (not in git, private): fonts, text, paper, the synthetic dev shards, predictions, weights
  (`out/weights/*/best.pt`), logs, `out/gpu/gpu_spend.jsonl` (every minute of rental).
