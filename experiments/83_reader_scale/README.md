# Experiment 83: more training lines for our own reader, with consensus labels

**Question (lead, 2026-11-05).** Experiment 77's from-scratch line reader (v1: 8.3M parameters, ~520k Azure-labelled
lines) gets 0.75% of letters wrong on the owner's 20 held-out pages, against Azure's 0.60%. Does it get closer to
Azure, or past it, with six to eight times more lines, when a new line is only trained on where v1 and Azure read it
the same way (consensus)? The owner's goal: "our reader at the limit of the very best before moving on". Cap: **$15
GPU**, no Gemini.

**Status: done (2026-11-05).** v3 and v4 trained and scored; the host is destroyed. **GPU $6.14 of $15** (one RTX
5090, $1.12/h, 5.5 h). No Gemini.

## Summary

- **Data:** 7,763 new documents from 3,529 journals → **2.17M new lines** (1.27M pre-2000), cut on the rented host
  straight from S3 with 8-hour presigned URLs (nothing large uploaded, no credentials on the host).
- **Consensus:** v1 and Azure read **81.5%** of the 2.4M new lines (with experiment 80's pull) identically
  (**78.1% pre-2000**, from 68% in the 1930s to 84% in the 1990s; **87.1% from 2000 on**). Those 1.95M lines
  plus experiment 77's 0.51M became v3's training set; 444k disagreeing lines are held aside for later rounds.
- **v3** (8.4M parameters, 8 epochs): on the owner's 20 held-out pages **0.69% letters / 1.61% words wrong**,
  against v1's 0.75 / 1.92 and Azure's 0.60 / 1.42. On lab documents 1–2 it is **below Azure** (0.16 against 0.23
  letters). Against Argon on document 3 it halves v1's disagreement (0.17 against 0.31).
- **v4** (one self-training round: +101k held lines that v3 now reads as Azure does) **is level with v3**: 0.69 /
  1.60 on the 20 pages. Lab docs 1–2 are 0.23, worse than v3 by two letter errors in document 1. Document 3 against
  Argon is 0.14. The round adds nothing measurable on these small tests.
- **For experiment 81:** `out/weights/v3/best.pt` (the pick) and `out/weights/v4/best.pt`.

## Method

**Documents (`select83.py`, no network, the catalogue read only).**
- Candidates: catalogue (`marc.db`, read only, as experiment 80) language `ara`, the article-like types of
  experiment 80, 1900–2025, 2–40 printed pages, both `<id>.pdf` and `<id>.json` in the main bucket (experiment 44's
  listing). 690,808 documents.
- Excluded: the **27** held-out journal codes of `76_finetune_pilot/out/split76.json` (the brief says 26: 26 have
  articles on disk, the 27th is lab document 1's journal; all 27 are out), and every document already on this machine
  (6,303 `<id>.pdf|json` names under /home/appuser, AI-Search not walked, plus experiment 76's inventory and
  experiment 80's pull).
- Choice: **7,763 documents from 3,529 journals**. 3,363 are pre-2000 (1,139 journals; a quota per decade, heavier
  before 1970, as far as the catalogue allows: the 1920s have only 2 journals left, the 1930s 11, the 1940s 20) and
  4,400 from 2000 on (a quota per 5-year span). Inside each decade or span journals are taken round-robin in random
  order (seed 83), at most 60 documents a journal a decade before 2000 and 8 a span after.
- Pages: modern pages carry ~60 Azure lines and old ones ~42 (experiment 77's page list), so whole modern documents
  would give ~5M lines. The host cuts **at most 6 pages of a modern document and 20 of an old one** (random, seed =
  the document id): 64,024 pages. 27.5 GB of PDFs and JSON, fetched by the host itself.

**Getting the data to the host without the slow upload (`presign83.py`, `cut83.py`).**
- This machine signs time-limited GET URLs (≤ 12 h, one object each, a local computation; system `python3` with
  boto3). Only the URL lists go to the host; no credentials leave here, and nothing is written to S3.
- The host fetches each document, cuts its lines with experiment 77's `common77.py` (unchanged: 250 dpi pypdfium2
  5.12.1 render, Azure's polygon, upright, padded, 48 px, grey JPEG q80, `clean_label`; lines tilted over 8°, tiny
  or too wide are left out as in `build77.py`), and deletes the PDF and JSON.
- **Experiment 77's own training and dev pages, and experiment 80's pull, are re-cut on the host from S3 the same
  way**, so the 5 GB of existing shards are not uploaded either. Checked here on three experiment-77 articles: the
  same 690 keys, the same labels, and the crops are pixel-identical to experiment 77's shards (mean absolute
  difference 0.0).
- Uploaded from here: v1's weights (33 MB), experiment 77's test crops (6 MB), the URL lists.

**Consensus labels (`consensus83.py`).** v1 reads every new line (the new documents and experiment 80's pull, which v1
never trained on). A line becomes a training label when v1's reading and Azure's are **identical under the scorer's
`no_punct` form** (faithful text, punctuation removed; marks, hamza, ى/ي, digits and the word spaces count). The
label kept is Azure's own, with its punctuation. All other lines are **held aside**: not trained on in this round, and
saved (`held_v3.jsonl`) as the material for later rounds. Experiment 77's 513k training lines keep their Azure labels
as before.
- Preview, here, on experiment 80's pull with experiment 77's existing v1 reads: **77.1% of 231,012 lines agree**
  (68.1% in the 1920s, rising to 85.1% in the 1990s; 80.0% if spaces were ignored). See Results for the full set.

**v3.** Experiment 77's `train77.py`, unchanged, on experiment 77's 513,533 lines (Azure labels, as v1) + the
1,952,172 consensus lines. **8.4M parameters** (the 8M size: experiment 77's sweep ended 2M 1.106%, 8M 1.015%, 28M
1.064% dev CER at 0.5M lines, so bigger did not help there). Same recipe (AdamW 1e-3 one-cycle, fp16, width
buckets, light augmentation, 16 data workers), but **8 epochs instead of 16**: 4.8x the lines, so 2.4x v1's
training samples. A checkpoint every epoch in `/work/run_v3`.
- The charset grew from 261 to 463 classes (characters seen at least 5 times).
- **A crash at the very last step.** The width-bucket sampler can give an epoch one batch more than `len()` said;
  the one-cycle schedule then refused step 127,305 of 127,304, before epoch 8 was evaluated and saved. **v3 is the
  epoch-7 checkpoint** (dev CER 1.002%), taken at a learning rate already near its floor. `train83.py` is
  `train77.py` with 50 steps of slack per epoch in the schedule (the only change), used for v4. Experiment 77's
  trainer has the same bug.

**v4 (self-training, `host83.sh relabel`).** v3 reads the 444,265 held-aside lines again; where v3 now reads a line as
Azure does, the line joins the training set; the rest stay held. Same data otherwise, `train83.py`, 8 epochs.

**Scoring (`eval83.py`).** Experiment 78's `eval78.py` (itself 77's `eval77.py`) pointed at this folder. It
reproduces v1's numbers (0.75% letters, 1.92% words on the 20 pages). Headline: letters and words with punctuation
and spacing excluded (`no_punct`); punctuation shown apart.

## Results

**Data (cut on the host in ~25 minutes, 40 workers, 0 document errors).**
- Re-cut from S3: experiment 77's 513,533 training and 8,198 dev lines and experiment 80's 231,012 lines, the
  same counts as experiment 77's own shards.
- New: **2,165,425 lines from 7,763 documents, 64,338 pages, 3,529 journals** (1,273,737 lines pre-2000 from 3,363
  documents and 1,139 journals; 891,688 modern from 4,400 documents and 2,725 journals). Left out as in build77:
  38,421 lines tilted over 8°, 512 tiny, 6 too wide. 118 of the documents are mostly Latin script (46k lines).

**Agreement of v1 and Azure on the new lines** (experiment 80's pull counted with the pre-2000 ones; 2,396,437 lines):

| | lines | agree (trained on) | agree, spaces ignored |
|---|---|---|---|
| 1920s | 67,687 | 69.2% | 73.4% |
| 1930s | 143,109 | 68.1% | 73.2% |
| 1940s | 160,962 | 73.3% | 76.7% |
| 1950s | 183,388 | 77.5% | 80.1% |
| 1960s | 220,063 | 78.9% | 80.8% |
| 1970s | 227,102 | 79.7% | 81.7% |
| 1980s | 230,972 | 81.5% | 83.8% |
| 1990s | 271,466 | 84.2% | 86.6% |
| 2000s | 271,054 | 86.7% | 89.0% |
| 2010s | 401,934 | 87.1% | 89.8% |
| 2020s | 218,700 | 87.5% | 90.2% |
| **pre-2000** | 1,504,749 | **78.1%** | 80.9% |
| **2000 on** | 891,688 | **87.1%** | 89.6% |
| **all** | 2,396,437 | **81.5%** (1,952,172 lines) | 84.1% |

The 444,265 held-aside lines (`out/held/held_v3.jsonl.gz`: key, era, year, journal, Azure, v1, v1's confidence)
are mostly near misses: 62% differ by one character, 18% by two; 14% differ only in spaces. The commonest single
differences are a space (missing or extra) and the hamza on alif (أ/ا 28k and ا/أ 10k, إ/ا 16k lines): the place
where Azure and v1 disagree most, and where neither is known to be right.

**v3 vs v1 vs Azure on the held-out truths** (`out/results83.json`; letters and words wrong, punctuation and
spacing excluded):

| | owner's 20 pages: letters | words | lab docs 1–2: letters | words | doc 3 vs Argon: letters | words |
|---|---|---|---|---|---|---|
| Azure | 0.60 | 1.42 | 0.23 | 1.32 | 0.07 | 0.36 |
| Argon | 0.52 | 1.05 | 0.18 | 1.48 | – | – |
| v1 (exp 77) | 0.75 | 1.92 | 0.20 | 1.50 | 0.31 | 1.73 |
| **v3** | **0.69** | **1.61** | **0.16** | **1.31** | **0.17** | **1.09** |

- On the owner's 20 pages v3 makes 8% fewer letter errors and 16% fewer word errors than v1 (about 97 wrong words
  against 116; Azure 86). Lines read exactly right: 91.4% against v1's 89.3% (Azure 93.0%).
- On lab documents 1–2 v3 is now below Azure in letters (0.16 against 0.23) and level in words.
- With punctuation counted, v3 is also better: 1.08% letters against v1's 1.17% (Azure 0.84%).
- By decade on the 20 pages the gain is in the 1980s (0.91 → 0.71) and before 1960 (0.29 → 0.22); the 1960s page
  (2.0% for every reader) and the 1970s are unchanged. These are few pages, so this is only a hint.
- v1 run on the host gives exactly experiment 77's v1 numbers (the re-cut test crops and the GPU agree).
- «» vs (( )), not counted: the owner's truth on the 20 pages has 30 «» marks and 28 (( )); Azure writes 7 «» and
  51 (( )); v1 and v3 never write «» (0 and 58 / 59 (( ))).

**v3 relabels the held-aside lines:** on 101,091 of the 444,265 (22.7%; 23.0% pre-2000, 22.0% modern) v3 now reads
as Azure does (`out/host/agree_v4held.json`). These join the training set for v4 (2,567k lines).

**v4** (`train83.py`, 2,566,735 lines, 8 epochs, dev CER 0.991% against v3's 1.002%; v4 also kept its 8th epoch):

| | owner's 20 pages: letters | words | lab docs 1–2: letters | words | doc 3 vs Argon: letters | words |
|---|---|---|---|---|---|---|
| v3 | 0.69 | 1.61 | 0.16 | 1.31 | 0.17 | 1.09 |
| v4 | 0.69 | 1.60 | 0.23 | 1.41 | 0.14 | 0.73 |

On the 20 pages v4 reads 83.3% of lines exactly against v3's 82.2% (punctuation counted). The documents are short
(lab document 1 has about 1,000 letters), so v3 and v4 cannot be separated here. Experiment 81's large held-out
test is the place to separate them.

**Spend.** One RTX 5090 (Vast instance 59267804, Czechia, $1.12/h), 13:14–18:42 UTC: **$6.14**.
- cutting: 25 min;
- v1 reads and consensus: 20 min;
- v3: 2.2 h;
- relabel: 15 min;
- v4: 2.3 h.

Destroyed with `gs83.py stop`; a check found none of our instances left.

## What to scale next

1. **The disputes, not more of the same.** Consensus keeps the lines v1 already reads right, so each new line
   teaches less. The 444k held lines are where the errors are. Most are a single character, mainly hamza on alif
   and word spaces. Experiment 77's Gemini judging found Azure right on only 26% of judged disputes. A cheap
   arbiter per class could turn many held lines into labels: a hamza rule checked against the owner's truth, or
   Gemini Flash on a stratified sample.
2. **A bigger model at this size.** At 0.5M lines 28M parameters did not help (experiment 77). At 2.5M lines it
   might: about 3x slower, roughly $7 for 8 epochs.
3. **Not another self-training round of this kind.** v4 is level with v3.
4. Experiment 81's large held-out set should confirm the v1 → v3 gain by era. The 20 pages are only 745 lines.

**For experiment 81:** v3's weights are `experiments/83_reader_scale/out/weights/v3/best.pt` (experiment 77's
checkpoint format; load with `train77.py infer --ckpt`, 8.43M parameters, 463 classes).

## Files

- `select83.py`: the documents (`out/data/plan83.jsonl`, `plan83_summary.json`, `candidates83.jsonl`, `ondisk83.txt`).
- `presign83.py`: the URL lists (`out/data/urls_*.jsonl`, mode 600, expire).
- `cut83.py`, `consensus83.py`, `host83.sh`, `setup_gpu83.sh`, `stub83/`: the host side. `train83.py`: experiment
  77's trainer with the schedule's slack (v4).
- `gs83.py`: the GPU session (experiment 79's `gs79.py`, pointed here; $15 cap).
- `eval83.py`: the scores. `fig83.py`: the owner's picture (`out/look/v3_scored.png`, rendered with experiment 77's
  `shot77.py`).
- `out/` (gitignored, private): `data/` (plan, URL lists), `gpu/`, `mirror/`, `host/` (agreement, documents),
  `held/`, `pred/`, `weights/v3` (and `v4`), `results83*.json`, `look/`.
