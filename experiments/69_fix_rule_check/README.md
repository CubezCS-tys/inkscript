# Experiment 69 — does prompt v3.6's fix rule earn its place?

**Question (owner, 2026-11-02).** Prompt v3.6 carries the lead's bullet from experiment 66: *"a fix is ONLY for a word
where the IMAGE plainly shows other letters than Azure's text … a printer's misprint is a "sic" flag … Never turn
letters into the word you expect. When unsure, do not fix."* Experiment 65's first check (13 pages) saw it stop 4 of
4 bad fixes but lose 4 real fixes on the faded 1080-002-010-015 p8. Before gate 2: on a wider check, does the bullet
avoid bad fixes and overwritten misprints without losing good fixes (faded prints above all), and what does it add on
top of experiment 66's code guard? Keep, drop or reword. Cap $4 of Gemini.

**Status.** Done 2026-11-02. **$3.156** of Gemini (Argon, Batch, four runs; experiment 43's log
$100.942 → $104.098; `out/baseline_spend.json`). No reworded variant was run (below). Nothing outside this folder was
written: answers in `out/<tag>/raw`, the variants registered at run time (`prompts69.py`), `prompt43.py` untouched.
Log: [progress.md](progress.md).

## Answer

**The bullet does nothing measurable.** Argon makes the same fixes with it and without it; the differences between the
two prompts are the differences between two runs of the same prompt.

- **Run to run.** On the 30 pages run twice with each prompt, the fixes of v3.6 and of v3.6 without the bullet overlap
  as much (Jaccard 0.53–0.57) as v3.6 with itself (0.544) or the no-bullet prompt with itself (0.541). Fix counts:
  660 with the bullet, 643 without (74 page-runs each).
- **Experiment 66's judged fixes** (every one was made by the saved run, so a re-run already avoids many of them):

  | judged fix (both runs pooled) | v3.6 | v3.6 without the bullet | v3.6 + guard | without + guard |
  |---|---|---|---|---|
  | bad (B, print right) made again | 9 / 23 | 11 / 23 | 7 / 23 | 8 / 23 |
  | printed misprint overwritten (M) again | 16 / 25 | 14 / 25 | 8 / 25 | 8 / 25 |
  | **B + M made again** | **25 / 48 (52%, [38, 66])** | **25 / 48 (52%)** | **15 / 48 (31%, [20, 45])** | **16 / 48 (33%)** |
  | good fix (G) still made | 26 / 31 | 27 / 31 | 25 / 31 | 26 / 31 |

  Paired by fix: the bullet alone avoided 5 that the other prompt made, the other prompt avoided 4 that v3.6 made.
- **Every word the runs changed differently** (158 decidable units judged on the scans over both runs, 19 not decidable; net = words that
  match the print with the bullet minus without; 95% interval by resampling pages):

  | kind of word | units (pages) | the bullet, no guard | the bullet, with the guard | the guard, with the bullet | the guard, without |
  |---|---|---|---|---|---|
  | letter shapes (dots, a letter swapped / added / dropped, digits) | 79 (27) | +7 (−7, +22) | +7 (−6, +21) | **+16 (+2, +33)** | **+16 (+3, +31)** |
  | … on poor prints | 30 (11) | +1 (−7, +9) | −1 (−8, +5) | +3 (−2, +9) | +5 (0, +10) |
  | … on clean prints | 49 (16) | +6 (−5, +18) | +8 (−2, +20) | +13 (0, +28) | +11 (−1, +26) |
  | hamza / alif maqsura / ta marbuta | 39 (17) | +12 (−7, +40) | +12 | 0 | 0 |
  | punctuation | 33 (9) | −3 (−11, +5) | −3 | 0 | 0 |
  | vowel marks | 7 (4) | −5 (−10, +1) | −5 | 0 | 0 |

  Run by run the letter-shape net was +7 and 0; the hamza net 0 and +12 — and that +12 is one page (0549-001-008-019)
  where the no-bullet run wrote hamzas the print lacks, the mirror of run 1, where the no-bullet run stripped a page's
  hamzas (0549-013-150-014). Whole pages flip their hamza policy from run to run; it is not the bullet.
- **Faded prints: no loss.** On the 11 poor-print pages with letter differences the bullet nets +1 (−7, +9). On
  experiment 65's faded 1080-002-010-015 p8 the no-bullet prompt also failed to make 3 of the 4 "lost" fixes
  («الاسيوى»، «نرضته»، «يمنع») and both made «للعبودية»: that loss was the one-page window and run variation, not the
  bullet. Only «حال»→«مال» (one of the bullet's own examples) differed, as experiment 65 saw.
- **The guard is what works.** With or without the bullet, experiment 66's guard turns ≈ 10 of 25 bad fixes /
  overwritten misprints back into the print and costs 1 good fix in 31 (here: يسكن→يكن on the faded 1080 p8 and
  سبيقان→سيقان, both Azure-sure misreadings); on letter shapes it nets +16 (+2, +33) on these pages (chosen rich in
  bad fixes, so the size is not the corpus rate; experiment 66 has that). The bullet adds nothing on top (+7 (−6, +21)).

**Recommendation: drop the bullet** (gate 2 can run v3.6 = v3.5b + P1–P3), and keep experiment 66's guard in the
pipeline. It is harmless — it did not cost good fixes, faded pages included — but it does not change what Argon does,
so it is an untested-in-effect instruction in every request. **No rewording was tested:** "unless the print is faded or
broken" would loosen a rule that is already not followed, and the faded-page loss it was meant to cure is not the
bullet's. What remains (≈ half of the judged bad fixes / overwritten misprints survive the guard, mostly words Azure was
unsure of and Gemini's "written as printed" non-words) needs the ink, as experiment 66 concluded: a dot / letter check
on the word crop or a second reader, not prompt wording.

## Method

- **Pages** (`select69.py` → `out/pages69.json`): the 299 pages that hold experiment 66's judged fixes (270 sample +
  40 refusal checks; almost one judged fix per page). Stratified choice of 44, one per journal first: 12 with a bad fix
  (B), 12 with an overwritten printed misprint (M), 10 with a good fix on a poor print, 10 with a good fix on a clean
  print. "Poor print" from Azure's words on the page: ≥ 12% below 0.80 confidence or median < 0.95 (18 of the 44).
  36 journals, 1920s–2020s; the saved answers are all Argon (v3.3 40, v3.5b 2, v2 2).
- **Variants** (`prompts69.py`): `v3.6` = `prompt43.PROMPT_V36`; `v3.6-nofix` = the same text with the bullet removed
  (the diff is exactly those five lines); `v3.6-faded` (a rewording, written, not run). Registered in
  `prompt43.PROMPTS` at run time.
- **Runs** (`run69.py`: run43's request builder, Batch, cap and spend log; answers in `out/<tag>/raw`): one page per
  request, as experiment 65's check (Image 1 = the article's first page and page 1's lines for context, metadata
  asked). Both prompts get identical requests, so the comparison isolates the bullet; it is not the original 10-page
  chunk context (that would have cost ≈ 8× the cap). Output limit 6,000 tokens (one table page, 0496 p15, needed 16,000
  and was re-asked). Run 1: `v36` / `nofix` on 44 pages ($0.939 + $0.036 + $0.953). Run 2, a replicate after run 1
  showed that most differences were noise: `v36r` / `nofixr` on 30 of them (every B and M page but 0496, 4 + 4 good
  pages; $0.604 + $0.624).
- **Units** (`units69.py`): each page's Azure lines corrected by each condition's fixes the way the masters apply them
  (first occurrence of `from` → `to`), compared with Azure word by word; a unit = a stretch of Azure's words some
  condition changes (stretches of all conditions merged). Conditions: the saved answer, each run, each run after
  `d30guard43.decide` (the guard as now in rules43). Persian look-alikes folded (the letter fix writes them by code).
- **Judging** (`sheets69.py`, `zoom69.py`, `lab69.py` → `out/labels69.tsv`): every unit where the conditions differ
  and experiment 66 had not judged the word, on the scan (the word at up to 10×, contrast-stretched, beside its line):
  the printed text, `AZ` / `AZM` (Azure's text is the print — a right word / a printed misprint), `U` not decidable
  (halftone hamzas, fine verse vowels, clipped fragments). Experiment 66's labels give the truth on its judged words
  (G → the saved fix's text; B / M → Azure's). 164 judged here, 18 of them U.
- **Scoring** (`score69.py`, `judged69.py`, `pool69.py`): a condition is right when its text equals the print (spaces
  ignored, ٫ = . as a decimal point; on letter-shape units vowel marks ignored). Kinds by what differs: letter shapes,
  hamza / ya / ta marbuta (d30guard43.ORTH), vowel marks, punctuation. Intervals: Wilson for rates, page bootstrap
  (4,000) for nets.

## Limits

One judge (this agent) on the scans; hamza on halftone prints and verse vowels were left `U` rather than guessed. Two
runs per prompt; one-page windows, not the original chunks. The pages are rich in bad fixes by design, so the guard's
net here overstates its corpus effect (experiment 66 measured that: ≈ 16% of bad fixes refused, 0.5% of good ones).
The decision does not depend on these: the bullet's run-to-run signature is indistinguishable from none at all.

## Files

- `common69.py`, `select69.py`, `prompts69.py`, `run69.py`, `units69.py`, `sheets69.py`, `zoom69.py`, `lab69.py`,
  `score69.py`, `judged69.py`, `pool69.py`.
- `out/` (gitignored): `pages69.json`, `candidates.json`, `replicate_stems.json`, `baseline_spend.json`;
  `v36/`, `nofix/`, `v36r/`, `nofixr/` (raw answers, batch state, requests); `units.jsonl` / `units_r.jsonl`,
  `fixes69.jsonl` / `fixes69_r.jsonl` (every fix with the guard's decision); `labels69.tsv`; `sheets/`, `sheets_r/`;
  `score_units*.json`, `score_rows_units*.json`, `judged.json`, `judged_r.json`, `pooled.json`; `run_*.log`.
