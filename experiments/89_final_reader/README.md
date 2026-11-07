# Experiment 89: the reader phase's final model

**Question (lead, owner's approval 2026-11-05: "work through the night ... done and tested thoroughly").**
1. Does combining the winners of experiments 83–85 give a better reader (v7)? The winners are:
   - v3's consensus lines;
   - v6r's settled labels;
   - v5's display faces, white-on-dark lines and «».
2. How do the readers do on display-face **article titles**? The owner ruled that titles count toward the finish line;
   mastheads and running headers go to layout.
3. Does the same recipe at **28M parameters** clearly beat the 8M v7?
4. Which reader is final? Experiments 90 (the locked test) and 86 (public benchmarks) read the answer from
   [FINAL_READER.json](FINAL_READER.json).

**Caps:** GPU $15, Gemini $5.

**Status: done (2026-11-06).**
- **GPU: $4.10 of $15.** One RTX 5090 (Vast 59344074, 46-CPU quota) ran cut, render, v7 and 28M back to back. The
  idle keeper destroyed it after the last stage, and every result was mirrored first.
- **Gemini: $1.27 of $5.** Title judging: a Batch round of 244 lines, then a standard round of 66 lines.

## Verdict

- **Final reader: v7-28M** (`out/weights/v7_28m/last.pt`). It is the best of our readers on every measure here.
- **It passed the pre-agreed 28M rule** on experiment 81's held-out lines:
  - against v7, letters −0.027 points (95% CI −0.048 to −0.002, so the interval excludes 0);
  - no era is worse: pre-1950 −0.013, 1950–99 −0.005, 2000+ −0.098 (the only clear gain).
  - With 0097's running header left out, its gain over v7 is within noise: −0.012 (CI −0.029 to +0.010).
  - Its other gains are clear: the owner's pages 0.68 against 0.71, titles 3.8% against 4.4% (CI excludes 0), and
    every printed «» right (59 of 59).
- **Against Azure on the held-out journals** (the running header left out, as the owner's rule puts it in layout):
  - every letter counted, 28M is better in every era. All: 0.699% against 0.831%. Pre-1950 −0.20, 1950–99 −0.15,
    2000+ −0.07; every interval excludes 0.
  - Spellings folded, it is level: 0.482% against 0.497% (CI −0.037 to +0.009). It is better before 1950.
- **Titles are our weak line type.**
  - On 250 judged article-title lines, 28M has 3.8% letters wrong against Azure's 2.4% (1.6×).
  - 1950–99 is the worst era: 14.8% against 7.8% (1.9×). These are calligraphic, vocalised, inverted and
    textured display titles.
  - Spellings folded, the gap is 2.9×: 2.1% against 0.7%.
  - On 2000+ titles (mostly journal 0097's article titles), 28M is close: 1.8% against 1.4%.

## Scores (letters wrong %, punctuation ignored)

**(b) Experiment 81's held-out lines.**
- 18,138 Arabic lines of 26 journals, of 22,783 read.
- Truth is the judge's truth, scored with est81's estimator (via est84):
  - two-phase estimates for v5, v6r, v7 and 28M;
  - the stratified estimate for Azure, Argon and v3.
- Argon is only on the pages Argon read (6,789 lines).
- "No header" leaves out journal 0097's 71 running-header lines (est81's own rule).

| reader | all | pre-1950 | 1950–99 | 2000+ | lines wrong | all, no header | 2000+, no header | folded | folded, no header | coverage |
|---|---|---|---|---|---|---|---|---|---|---|
| Azure | 0.875 | 0.737 | 0.943 | 0.704 | 23.3 | 0.831 | 0.505 | 0.500 | 0.497 | – |
| Argon (its pages) | 0.745 | 0.777 | 0.761 | 0.661 | 19.1 | 0.743 | 0.646 | 0.435 | 0.433 | – |
| v3 | 0.852 | 0.564 | 0.826 | 1.014 | 19.4 | 0.729 | 0.473 | 0.576 | 0.505 | 100 |
| v5 | 0.837 | 0.549 | 0.816 | 0.981 | 19.3 | 0.724 | 0.486 | 0.559 | 0.505 | 92.2 |
| v6r | 0.844 | 0.551 | 0.808 | 1.035 | 18.8 | 0.717 | 0.476 | 0.575 | 0.500 | 93.5 |
| v7 | 0.816 | 0.548 | 0.804 | 0.929 | 18.9 | 0.712 | 0.470 | 0.546 | 0.498 | 92.0 |
| **v7-28M** | **0.789** | **0.535** | **0.798** | **0.833** | **18.7** | **0.699** | **0.436** | **0.521** | **0.482** | 92.8 |

Paired differences (95% page-bootstrap CI):

| pair | all | pre-1950 | 1950–99 | 2000+ |
|---|---|---|---|---|
| v7 − v6r | −0.028 (−0.051, −0.010) | −0.002 | −0.006 | −0.104 (−0.159, −0.059) |
| 28M − v7 | −0.027 (−0.048, −0.002) | −0.013 (−0.046, +0.016) | −0.005 (−0.028, +0.024) | −0.098 (−0.144, −0.064) |
| 28M − v7, no header | −0.012 (−0.029, +0.010) | −0.013 | −0.005 | −0.035 (−0.061, −0.015) |
| 28M − Azure | −0.087 (−0.123, −0.052) | −0.204 | −0.146 | +0.129 (+0.062, +0.198) |
| 28M − Azure, no header | −0.132 (−0.166, −0.100) | −0.204 (−0.295, −0.119) | −0.146 (−0.187, −0.102) | −0.068 (−0.115, −0.022) |
| 28M − Azure, folded, no header | −0.014 (−0.037, +0.009) | −0.108 (−0.187, −0.033) | −0.012 (−0.040, +0.019) | +0.003 (−0.033, +0.035) |

- **Coverage** means the judged lines whose new reading is a candidate the judge saw:
  - 28M 92.8% (2000+ 83.0%; with no header 94.8% and 91.3%);
  - v7 92.0%.
  - The uncovered readings are still scored against the judged truth. Most of them are 0097's header.
- **The 2000+ buckets (diag81):**

  | bucket | Azure | v3 | v7 | 28M |
  |---|---|---|---|---|
  | 0097 header | 8.1 | 21.0 | 17.9 | 15.5 |
  | dark ground | 17.7 | 47.8 | 34.4 | 30.6 |
  | other 2000+ | 0.504 | 0.472 | 0.471 | 0.436 |

**(a) The owner's 20 pages** (`score89.py owner`: eval83's page scorer through score88; letters / words; letters
with punctuation under the original truth and under rev2):

| reader | letters | words | letters + punct. (original) | letters + punct. (rev2) |
|---|---|---|---|---|
| Azure | 0.60 | 1.42 | 0.84 | 1.01 |
| Argon | 0.52 | 1.05 | 0.77 | 0.90 |
| v3 | 0.69 | 1.61 | 1.08 | 1.23 |
| v5 | 0.71 | 1.70 | 1.10 | 1.03 |
| v6r | 0.70 | 1.66 | 1.09 | 1.24 |
| v7 | 0.71 | 1.79 | 1.08 | 1.06 |
| **v7-28M** | **0.68** | **1.59** | 1.05 | **0.97** |

- rev2 changes only punctuation, so letters and words are the same under both truths.
- On these 745 lines Azure is still ahead, as in experiments 84 and 85. This truth was drafted from Azure (experiment
  85 showed its hamza follows Azure).

**(d) «» on the owner's 20 pages** (rev2: 59 printed marks; matched / written and matched / in truth):

| reader | «» precision | «» recall | stray (( )) written |
|---|---|---|---|
| Azure | 7/7 | 7/59 | 51 |
| Argon | 14/14 | 14/59 | 45 |
| v3 | – | 0/59 | 59 |
| v5 | 56/57 | 56/59 | 3 |
| v6r | 1/1 | 1/59 | 58 |
| v7 | 48/49 | 48/59 | 8 |
| **v7-28M** | **59/59** | **59/59** | **0** |

- Under the original truth (30 «» and 28 (( ))), 28M scores «» 30/59 and 30/30, and (( )) 0/28. The original truth
  wrote printed «» as (( )).
- v7 starts from v6r, which writes (( )). Three epochs did not fully unlearn that habit. 28M, trained from scratch,
  never learned it.

**(c) The title test** (`score89.py titles`; 250 lines with a truth; % letters / words / lines wrong; letters 95% CI
by document bootstrap):

| reader | letters | (CI) | words | lines wrong | 1950–99 (59) | 2000+ (186) | without 0097 (76) | folded |
|---|---|---|---|---|---|---|---|---|
| Azure | **2.36** | 1.4–3.5 | 15.4 | 24.0 | 7.8 | 1.4 | 6.3 | **0.73** |
| Argon (33 lines) | 5.27 | 1.5–10.4 | 27.2 | 30.3 | 6.1 | 4.7 | 5.3 | 1.82 |
| v3 | 5.32 | 3.9–7.2 | 27.0 | 48.8 | 17.1 | 3.1 | 13.8 | 3.37 |
| v5 | 4.49 | 3.0–6.4 | 22.4 | 38.4 | 16.4 | 2.2 | 13.5 | 2.73 |
| v6r | 5.08 | 3.6–6.8 | 25.7 | 44.4 | 16.6 | 2.9 | 13.2 | 3.22 |
| v7 | 4.41 | 2.9–6.1 | 22.1 | 36.8 | 16.5 | 2.1 | 13.3 | 2.64 |
| **v7-28M** | 3.82 | 2.5–5.4 | 20.3 | 32.4 | 14.8 | 1.8 | 11.9 | 2.09 |

- Paired (letters): 28M − v7 −0.59 (CI −0.98 to −0.27); 28M − Azure +1.46 (+0.77 to +2.43); v7 − v6r −0.67 (−1.05
  to −0.26).
- Pre-1950 has only 5 title lines (Azure 0.9, 28M 1.8).
- Where the gap is, looking at the worst lines:
  - stacked or calligraphic titles (0408, 0260, 0382);
  - white text on a dark textured band (0447, 0498);
  - fully vocalised titles, where the judge writes every mark: 28M drops some, and Azure some too.
- On 0097's 174 printed sans titles, 28M reads 1.7% against Azure's 1.3%.

## Method

**1. Data and training (`train89.py`, `host89.sh`, `gs89.py`, `presign89host.py`, `forbid89.py`, `bundle89.sh`).**
- `train89.py` is experiment 84's `train84.py` with three additions:
  - with `--init`, the architecture comes from the checkpoint's meta (as `train85.py` does);
  - `--charset_from`: train from scratch at any size with a reference charset;
  - `--forbid`: the guard.
- **The guard.** `forbid89.py` builds `forbidden89.json`:
  - the 27 held-out journals of split76;
  - experiment 84's 20 locked journals;
  - experiment 88's 280 locked old-print documents (`LOCKED_OLD_DOCS.json`);
  - 47 journal codes and 280 documents in all.

  It checks v6r's label file and the four URL lists with `locked_old.assert_not_locked`. On the host, `train89.py`
  refuses to start if any training key or label key belongs to one of them. Result: 3,354,235 keys checked, none
  forbidden. The host waited for experiment 88's list before training.
- **Data.**
  - Experiment 83's lines were re-cut on the host from 12-hour presigned URLs (`cut83.py` unchanged; 513,533 +
    231,012 + 2,165,425 training lines, 8,198 dev, 0 document errors), in 12 minutes.
  - Experiment 84's 300k synthetic lines and 4k synthetic dev lines (`render84.py` unchanged) took 1 minute.
- **Labels: v6r's** (`85_disputes/out/labels/labels_v6r.jsonl`): 8,012 judged lines and 42,280 bare-alif rule lines
  are relabelled, and 393,973 other held disputes are dropped.
- **Drop rule.** Real lines whose Azure label has (( or )) are dropped, as for v5 (64,373 lines).
- **Training set:** 2,739,957 lines.
- **Augmentation:** experiment 84's on-the-fly polarity on real lines (6% inverted, 4% dark band).
- **v7** (8.4M):
  - fine-tuned from v6r, 3 epochs at one-cycle 3e-4 with 10% warm-up (the 84/85 recipe);
  - 12.6 minutes an epoch;
  - checkpoint: the last epoch;
  - dev CER 1.034% on Azure-labelled real dev (v6r 0.982%; Azure's (( )) for «» costs here, as for v5), 1.40% on
    synthetic dev.
- **v7-28M** (28.5M parameters):
  - experiment 77's l28m size: CNN channels ×1.5, 640 features, a 768-wide BiLSTM;
  - fine-tuning across sizes is not possible, so it was trained from scratch with v6r's 463-class charset;
  - the same data and augmentation, 8 epochs at one-cycle 1e-3 with 5% warm-up (v3's own from-scratch recipe);
  - 22 minutes an epoch (1,700–2,000 lines/s);
  - checkpoint: the last epoch;
  - dev CER 1.011%, synthetic dev 0.73%.
- The torch threads followed the cgroup quota (46 CPUs: 8 torch threads, 16 loaders, 40 cutters).

**2. Title test (`title89.py`, `judge89.py`).**
- **Documents:** experiment 81's frame, the 144 held-out articles on disk; page 1 of each.
- **Which lines are titles:**
  - where experiment 41's Argon labels exist (22 documents), its "title" lines;
  - elsewhere, a fixed position-and-size rule on page 1 (the first group of lines at least 1.2× the page's median line
    height, before a byline or body text). Running headers and mastheads are skipped: lines in the top 8% that are
    smaller than body text, text that recurs on pages 2–3, and the journal's own name.
  - On the Argon documents the rule agreed with Argon on 68% of lines, so every chosen line was looked at.
- **Looking:** contact sheets `out/look/titles89_sheet00–06.png`. 18 of 274 lines are not titles (bylines,
  affiliations, body leads, section headings, a logo) and are listed with reasons in `out/titles/not_titles.json`.
  256 lines remain, from 118 documents. 177 are journal 0097's: it is 84 of the 144 articles.
- **Crops:** as experiment 81: 48 px from a 250-dpi render for the readers, 96 px from 300 dpi for the judge.
- **Readers:**
  - v3, v5 and v6r were read on the local CPU;
  - v7 and 28M on the host GPU;
  - Azure and Argon are their own texts.
- **Judge:** `judge85.py` imported, with judge81's prompts verbatim (gemini-3.8-flash, blind reading first, then the
  shuffled unnamed candidates). Its held-out guard is replaced by the locked-only guard, because these lines are a
  held-out test by design.
  - Round a: Batch API, 244 lines, candidates Azure, Argon, v3, v5, v6r.
  - Round b: standard calls, the 66 lines where a v7 or 28M reading had not been shown, every reader's reading
    shown; 60 were answered.
  - Experiment 81's answers were reused for 12 lines.
- **Truth:** the latest answer for the line (est81's truth rule). Coverage of v7 and 28M is 99.6%. Six lines have no
  truth (unparsable or unreadable).

**3. Scoring (`score89.py`).**
- `heldout`: est84 imported unchanged and run four ways (strict or folded × with or without 0097's running header).
  The header rule is est81's own (`EST81_EXCL_HDR`): the header lines leave both frame and sample. It adds the paired
  differences 28M − v7 and v7 − v6r with est81's `paired`.
- `owner`: score88's functions, written here, never in experiment 88's folder.
- `titles`: as above.
- `final89.py` writes FINAL_READER.json; `fig89.py` draws the owner's picture, `out/look/final89.png` (Telegram, looked
  at first).

## Against the exit criteria (Plan page)

1. **On the locked test, ours ≥ Azure overall and in every era:** not measured here. That is experiment 90's job.
   - On the held-out proxy, every letter counted and the running header left out (it goes to layout), 28M is ahead of
     Azure overall and in every era, each interval excluding 0.
   - Spellings folded, it is level overall and in 1950–99 and 2000+, and better before 1950.
   - With the header counted, 2000+ is still behind (+0.13).
2. **No line type more than 2× Azure (titles count, mastheads excluded):**
   - titles pass every letter counted: 1.6× (1950–99 1.9×, within the noise of 59 lines);
   - titles fail with spellings folded: 2.9×;
   - dark-ground lines (27 judged, mostly the header) are 1.7×.
   - So titles are the line type nearest the bar.
3. **Two rounds in a row with < 5% relative gain:** this was already met before this experiment (84 about 2%, 85 about
   1%). Experiment 89 itself gave 6.5% (v6r 0.844 → 28M 0.789), mostly from size on 2000+ display and dark lines.

## What it changed

- **The reader phase has its final model:** v7-28M, in FINAL_READER.json. Experiments 90 and 86 read it.
- Combining the winners works: v7 beats v6r by 0.028 points (CI excludes 0), all of it on 2000+.
- **At 2.7M lines, size helps**, unlike at 0.5M lines (experiment 77). The gain shows on display, dark and
  «» lines more than on plain body text.
- Display-face titles are now measured. They are the weakest line type: about 1.6× Azure, and 1.9× on 1950–99
  calligraphy. That is where the next reader work would go: titles from these faces in the synthetic set, and
  title crops with Azure's agreement as labels.
- Nothing in `src/` changed.

## Files

- Code:
  - training: `train89.py`, `host89.sh`, `setup_gpu89.sh`, `gs89.py`, `bundle89.sh`, `presign89host.py`,
    `forbid89.py`;
  - titles and judging: `title89.py`, `judge89.py`;
  - scoring and output: `score89.py`, `final89.py`, `fig89.py`.
- `serve_reader.py`, `serve_reader.sh`: the final reader as a local service for the Desk's **Try our reader** page
  (see "The reader as a service" below).
- `FINAL_READER.json`: the pick, its weights, recipe and every score above.
- `out/` (gitignored, private):
  - `weights/v7_28m/last.pt` (the final reader), `weights/v7/last.pt`;
  - `host/` (logs, predictions, runs);
  - `mirror/59344074/` (every checkpoint, epochs 0–7 of 28M; the URL copies in it are mode 600 and expired after
    12 h);
  - `heldout/` (est89_*.json/txt);
  - `owner89.json`;
  - `titles/` (selection, crops, `not_titles.json`, scores);
  - `judge/a`, `judge/b` (answers, spend);
  - `look/` (`final89.png`, title sheets);
  - `gpu/` (session, spend).

## The reader as a service (2026-11-06)

The Desk's **Try our reader** page (`/try-reader`, Quality menu) lets the owner drop, pick or paste an image of a line
of Arabic print and see what v7-28M reads. The page posts the image to the Desk API
(`POST /desk/api/try-reader`, `desk/try_reader.py`, Desk sign-in needed), which forwards it to this service:

    ./serve_reader.sh            # start or restart: 127.0.0.1:8171, nice 19, ionice idle, 2 CPU threads
    ./serve_reader.sh stop
    curl -s http://127.0.0.1:8171/health
    curl -s --data-binary @line.png http://127.0.0.1:8171/read

- **The model** is loaded once at start (`FINAL_READER.json`'s weights, `train89.Reader`), on the CPU venv of
  experiment 81 (torch 2.15 CPU, the one experiment 90 read with). Memory is about 0.5 GB.
- **Preprocessing** is experiment 86's, for line images that have no Azure polygon (`prep86.polarity`,
  `ink_box`, `cut_from_box` with `out/calib86.json`, then `common77.cut_line(test=True)` at 48 px). The network
  input is exactly `train89`'s (`LineSet` flip, `collate`). Light-on-dark images are inverted, and the answer says so
  (`inverted`).
- **Several lines** are split by our simple horizontal-profile splitter. It is `prep86.split_lines` with three
  changes, because that splitter was only ever run on whole pages:
  - The pitch for cutting touching lines is the median distance between band starts inside the image. It is not the
    autocorrelation peak, which on a one-line image sat at the smallest lag and cut one line into 6–11 slivers.
  - A band that touches the top or bottom edge and is under 60% of the tallest band is dropped. Such a band is
    usually a cut-off sliver of the next line.
  - Bands of 1–5 px are dropped (halftone stripes). If no band survives, the whole ink box is read.
  On 400 held-out one-line judge crops (experiment 81), 398 stay one line. The other 2 are fragments.
- **Reading:**
  - `text` is the greedy CTC reading, as every score of experiment 89 used.
  - `chars` gives each letter with the highest probability it got in its frames, in logical order.
  - `alternatives` holds up to 3 other readings from a CTC prefix beam of width 8.
  - `lines` gives each line's ink box, its 48-px crop (a PNG data URL), its text, letters and alternatives.
  - `ms` is the time taken.
- **Limits:** 5 MB, 40 megapixels and 12,000 px a side are checked from the PNG or JPEG header before decoding. A
  page may have at most 60 lines. Each refusal comes back as a plain sentence (HTTP 413 or 422).
- **Nothing is kept.** Images are decoded in memory and dropped with the request. The service has no access log, and
  `out/serve_reader.log` holds only start-up lines.
- **Speed** on this box's CPU (2 threads, nice 19, shared with other work), measured 2026-11-06:
  - a line 600–1,100 px wide (48 px high) takes 0.2–0.5 s;
  - a 5-line paragraph crop takes 1.4–1.7 s, about 0.3 s a line;
  - beam search adds 0.01–0.1 s a line.
