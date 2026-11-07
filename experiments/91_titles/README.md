# Experiment 91: catalogue titles for our line reader

**Question (owner's approval 2026-11-06).** Can the catalogue teach the final reader (v7-28M) to read article titles?
Display-face article titles are its weakest line type:
- held-out titles: 3.82% letters wrong against Azure's 2.36% (folded, 2.9×);
- locked titles: 7.55% against 5.70% (folded, 1.99×).

Titles are rare in training, about 1–2 lines per article. Mandumah's catalogue (marc.db) holds every article's title
as text, and page 1 of the article shows it in print. Matching the two gives labelled title lines across the archive,
with no Gemini cost.

**Caps:** GPU $6, Gemini $3 (the Gemini cap is only for judging test title lines that no judge has seen).

**Status: done (2026-11-06).**
- **GPU: $1.87 of $6.** One RTX 5090 (Vast 59422047, 61-CPU quota) ran the re-cut, the title pull, the render,
  training and the reads back to back. It was destroyed after the last fetch (`gs91.py stop`; no instance left).
- **Gemini: $1.35 of $3.** 131 test title lines whose new reading no judge had seen were judged with standard calls:
  25 held-out and 106 locked.
- **S3 egress, at the lead's cap:**
  - the new-document pull measured 11.4 GB: JSON first, the PDF only after a confident match;
  - the exp 83 re-cut is exp 89's recipe, about 38 GB;
  - the title lines of the 10,251 training documents cost no extra download.

## Verdict

**The new reader `t91` is kept**, by the rule fixed before scoring ([RULE91.json](RULE91.json)). It is written in
[READER.json](READER.json). For article titles it supersedes `../89_final_reader/FINAL_READER.json`. It passed the
no-regression rule as well, so it can replace v7-28M everywhere if the lead agrees.

- **Titles get clearly better.**
  - On the held-out title test (exp 89's 250 judged lines), the final reader made 3.94% letters wrong; t91 makes
    3.58%. The paired difference is −0.36 points (95% CI −0.67 to −0.13).
  - 1950–99 calligraphy goes from 14.5% to 13.1% (−1.39, CI −2.62 to −0.23).
  - With spellings folded, the gap to Azure narrows from 2.9× to 2.3× (1.66% against Azure's 0.72%).
- **Locked titles, a second read.** These are exp 90's 674 lines; nothing was tuned on them, and they were scored
  only once the reader was fixed.
  - Every letter counted: 7.07% → 6.27% (−0.81, CI −1.05 to −0.59). Azure makes 5.38%, so the ratio goes from 1.31×
    to 1.17×.
  - Folded: 3.53% → 2.76% (−0.76, CI −0.99 to −0.57). Against Azure's 1.77%, the ratio goes from **1.99× to 1.56×**.
- **Nothing regressed on exp 81's held-out lines** (18,138, two-phase estimates, every letter counted):
  - all lines 0.789 → 0.771 (−0.020, CI −0.037 to −0.007);
  - 1950–99 0.798 → 0.788 (−0.013, CI −0.038 to +0.003);
  - 2000+ 0.833 → 0.781 (−0.052, CI −0.078 to −0.026), almost all of it journal 0097's display header;
  - **pre-1950 0.535 → 0.551 (+0.018, CI −0.008 to +0.053)**: within noise, so the rule passes, but its point
    estimate is the only one that is worse;
  - with the header left out: −0.009 overall (CI −0.024 to +0.004);
  - folded: −0.031 overall (CI −0.049 to −0.017).
- **The owner's 20 pages are level:** letters 0.67 against 0.68, words 1.61 against 1.59, «» 59/59 on rev2 for both.
- The titles are still the weakest line type. The title gap to Azure is about a quarter smaller, not closed.

## Title lines from the catalogue

| | documents | confident match | title lines kept |
|---|---|---|---|
| pre-1950 | 3,209 | 2,490 (77.6%) | 2,953 |
| 1950–99 | 9,146 | 7,627 (83.4%) | 11,917 |
| 2000+ | 6,985 | 6,529 (93.5%) | 10,445 |
| **all** | **19,340** | **16,646 (86.1%)** | **25,315** (24,519 train + 796 title dev), 3,827 journals |

- The documents come from two sources:
  - **10,251 already in the training mix** (plan83 7,763, exp 77 1,916, exp 80 572): 89.7% matched;
  - **9,089 new training-pool documents**: 82.0% matched. All 2,089 eligible pre-1950 documents were taken, plus
    6,000 from 1950–99 and 1,000 from 2000+, smallest first and round-robin across journals.
- 15,003 of the kept lines are display size, at least 1.2× the page's body text.
- **How often the catalogue and Azure differ.** In the confident runs, 2,188 of 27,173 Arabic title lines (8.1%)
  differ from the catalogue in folded form:
  - 1,879 by a word or two (Azure misread, or the cataloguer tidied);
  - 309 with words the catalogue lacks.
- **Where they differ, the current reader decides:**
  - 381 lines (20%) took the catalogue word, spelled as the reader read it, because the reader agrees with the
    catalogue;
  - 690 were dropped because the reader sides with Azure. Azure and the reader learned from the same labels, so
    their agreement is not proof;
  - 800 were dropped because all three differ.
- **Spacing-only differences** count as agreement, with Azure's spacing kept (و علم / وعلم). A footnote mark that the
  catalogue lacks is kept as printed.
- **Looked at before training (`out/host/prov/eyecheck91.json`).** I checked 100 random kept crops against their
  labels:
  - letters right on 100 of 100;
  - printed vowel marks missing on 8 (shadda, tanwin, sukun), which is Azure's habit and the same as in the
    training mix;
  - punctuation off on 2;
  - all 5 catalogue-corrected lines in the look-sample are right.
- 30 more crops from new pre-2000 documents: 28 fully right. One has an ornament box written "0", and one has a hamza
  where the print has a bare alif.

## Scores (letters wrong %, punctuation ignored)

**Titles** (`score91.py titles`, `score91.py locked`). The truth includes this experiment's 131 judged lines, so
Azure's and l28's figures move slightly from exp 89 and 90.

| set | Azure | final (v7-28M) | **t91** | t91 − final (95% CI) |
|---|---|---|---|---|
| held-out titles, strict | 2.46 | 3.94 | **3.58** | −0.36 (−0.67, −0.13) |
| held-out, 1950–99 (59) | 7.59 | 14.47 | **13.08** | −1.39 (−2.62, −0.23) |
| held-out, 2000+ (186) | 1.52 | 2.00 | **1.85** | −0.15 (−0.32, +0.01) |
| held-out, without 0097 (76) | 6.16 | 11.67 | **10.51** | −1.16 (−2.17, −0.28) |
| held-out titles, folded | 0.72 | 2.08 | **1.66** | −0.42 (−0.71, −0.18) |
| locked titles, strict (second read) | 5.38 | 7.07 | **6.27** | −0.81 (−1.05, −0.59) |
| locked titles, folded (second read) | 1.77 | 3.53 | **2.76** | −0.76 (−0.99, −0.57) |

- Lines wrong on held-out titles: Azure 24.4%, final 32.4%, t91 29.6%.
- Locked titles: 29.1, 30.7 and 29.6.
- Title dev (796 lines of training-pool documents, labels as above): CER 1.28% → 1.08%.

**Exp 81's held-out lines** (`score91.py heldout`: est84 / est81 two-phase, paired page bootstrap; l28 reproduces
exp 89's figures exactly):

| measure | final | **t91** | t91 − final, all (CI) | pre-1950 | 1950–99 | 2000+ |
|---|---|---|---|---|---|---|
| strict | 0.789 | **0.771** | −0.020 (−0.037, −0.007) | +0.018 (−0.008, +0.053) | −0.013 (−0.038, +0.003) | −0.052 (−0.078, −0.026) |
| strict, no 0097 header | 0.699 | 0.692 | −0.009 (−0.024, +0.004) | +0.018 | −0.013 | −0.003 |
| folded | 0.521 | **0.490** | −0.031 (−0.049, −0.017) | +0.016 | −0.017 (−0.042, −0.001) | −0.088 |
| folded, no header | 0.482 | 0.470 | −0.012 (−0.028, 0.000) | +0.016 | −0.017 | −0.004 |

- Coverage (the new reading was a candidate the judge saw): t91 92.9%, l28 92.8%.

**The owner's 20 pages** (`score91.py owner`; letters / words / letters with punctuation, original truth and rev2):
- final: 0.68 / 1.59 / 1.05 / 0.97;
- t91: 0.67 / 1.61 / 1.03 / 0.97;
- Azure: 0.60 / 1.42 / 0.84 / 1.01.

Picture: `out/look/fig91.png` (looked at).

## Method

1. **Candidates (`select91.py`).** Exp 83's plan83, exp 77's train documents, exp 80's pull, plus new documents
   from exp 83's eligible pool (`candidates83.jsonl`), with the catalogue's 245 $a / $b as title and subtitle.
   - Never used: split76's held-out journals, exp 84's locked journals, exp 88's locked documents
     (`locked_old.assert_not_locked` on every id), or exp 77's dev documents.
   - The new set is capped by estimated egress.
2. **Match rule (`match91.py`).** It was fixed on 900 local training documents and a contact sheet before any host
   run.
   - Every run of 1–6 consecutive Azure lines on page 1 is compared, folded, with the title (or the title plus
     subtitle).
   - A match is confident when:
     - the similarity is at least 0.85;
     - at least 85% of the title is covered;
     - the run starts in the top 60% of the page (exp 89's rule);
     - the run's median line is at least 0.9× the body text.
   - Each line in a confident run then gets a verdict:
     - agree: every word matched;
     - differ: at most a third of its words, and no more than 2, replaced by close words;
     - extra: it has words the catalogue lacks;
     - small or short.
   - Only agree and differ lines are cut.
3. **On the host:**
   - `cut91.py` is `cut83.py` plus a title hook: page 1 of each re-cut document goes through the matcher with the
     files already fetched;
   - `title91.py cut` handles the new documents;
   - v7-28M reads every title crop, and `title91.py labels` applies the label rule;
   - documents with md5 % 100 < 3 form the title dev set `tdev91`, which is never trained on;
   - a provisional label pass ran on the first 15k lines, and I looked at it while the new documents were being
     pulled. Training waited for `go91`.
4. **Training (`train91.py`, `host91.sh`).** `train89.py` plus `--title_share` and several dev splits.
   - Fine-tuned from v7-28M on exp 89's full mix, plus 24,278 title lines repeated ×7 (5.8% of the 2,909,733 items in
     an epoch).
   - The ordinary training copies of the same lines were relabelled (`overrides91.jsonl`; v6r's judged labels win).
   - 2 epochs at one-cycle 2e-4 with a 10% warm-up and exp 84's polarity augmentation; 25 minutes an epoch.
   - The checkpoint is the last epoch.
   - The guard checked 3,402,089 training and label keys and found none forbidden.
5. **Tests.**
   - On the host GPU: exp 81's 22,778 crops, exp 89's title crops and the owner's pages.
   - The locked titles were read on the local CPU only (`read91locked.py`, which asserts every key is locked). l28 was
     read the same way, so the pair is like for like.
   - `judge91.py` uses exp 90's judge imported unchanged (judge81's prompts, gemini-3.8-flash, blind reading first,
     then the shuffled unnamed candidates). It judged every test title line where t91's or l28's reading was neither a
     shown candidate nor the truth.
   - The locked estimate is est81's stratified estimator over exp 90's title strata. Agreed lines where a new reading
     differs moved to census strata, and every one of those was judged.

## What it changed

- **A new reader for titles:** `out/weights/t91/last.pt` (READER.json). It supersedes FINAL_READER.json for article
  titles. It is also no worse than v7-28M on body text by the pre-set rule, and slightly better overall.
- **The catalogue is a free, archive-wide source of title labels.** It gives 1.3 confident title lines per document,
  86% of documents match, and no judge is needed.
  - Azure disagrees with the catalogue on 8% of title lines. When the reader breaks the tie, about a fifth of those
    become corrected labels.
- Locked titles folded drop from 1.99× Azure to 1.56×, and strict from 1.31× to 1.17×. Display titles remain the
  weakest line type.
- **Caveats:**
  - pre-1950 body text: +0.018 points, not significant, but the only era whose point estimate is worse;
  - the title labels inherit Azure's dropped vowel marks;
  - more title data, from older and calligraphic journals, is the obvious next step.
- Nothing in `src/` changed.

## Files

- Code:
  - `select91.py`, `presign91host.py`, `forbid91.py`, `bundle91.sh`, `gs91.py` (the GPU session);
  - `match91.py`, `title91.py`, `cut91.py`, `train91.py`, `host91.sh`;
  - `look91.py` (contact sheets), `read91locked.py`, `judge91.py`, `score91.py`, `fig91.py`.
- `RULE91.json` (the keep rule, written before scoring) and `READER.json`.
- `out/` (gitignored, private):
  - `data/docs91.jsonl`;
  - `host/` (title manifests, labels, stats, predictions, logs, `run_t91/`);
  - `host/prov/` (the provisional labels, sheets and eye check);
  - `weights/t91/last.pt`;
  - `heldout/est91_*.json`, `owner91.json`, `score91_titles.json`, `score91_locked.json`;
  - `judge/` (sample, answers, spend);
  - `locked/` (CPU reads of the locked titles);
  - `look/fig91.png`;
  - `gpu/` (session, spend; the URL lists were mode 600 and are expired).
