# Experiment 90: the LOCKED final test of our own Arabic line reader

**Question (lead, owner's OK of 2026-11-05: "you have my ok").** Does the reader phase's final model meet its exit
criteria (Plan m31 with m34) on material that nobody trained on, tuned on or looked at?
- The material: experiment 84's 20 locked journals, and experiment 88's 280 locked old-print documents.
- C1: ours ≥ Azure on letters and lines overall, and not clearly worse in any era.
- C2: no line type more than 2× Azure's errors. Titles count; mastheads are excluded by the owner's decision.

Both locked sets were opened once, for this claim. Nothing was trained, tuned or changed after the locked results
were seen.

**Status: done (2026-11-06).**
- Gemini **$8.73 of $25**: a 50-line pilot with standard calls, then 2,900 lines through the Batch API.
- GPU: none (everything ran on the local CPU, niced, 2–4 threads).
- The final reader is experiment 89's pick, **v7-28M** (`../89_final_reader/FINAL_READER.json`; weights
  `out/weights/v7_28m/last.pt`, sha256 ce8ea07c… checked).

## Verdict

**C1: PASS**, with every letter counted (strict).
- Overall, ours makes fewer letter errors than Azure (1.34% against 1.50%) and has fewer wrong lines (17.5% against
  22.4%).
  - Paired with Azure on the same lines: −0.16 points of letters (95% CI −0.21 to −0.10), −4.8 points of lines
    (−5.6 to −4.1).
- Ours is clearly better in three eras. In 2000+ it is level:

  | era | letters, ours − Azure (95% CI) | lines, ours − Azure (95% CI) |
  |---|---|---|
  | pre-1950 | −0.36 (−0.51 to −0.20) | −8.7 (−11.3 to −6.1) |
  | 1950–79 | −0.20 (−0.28 to −0.12) | −6.8 (−8.5 to −5.3) |
  | 1980–99 | −0.14 (−0.18 to −0.09) | −4.9 (−6.1 to −3.8) |
  | 2000+ | −0.07 (−0.20 to +0.06), level | −2.2 (−3.6 to −0.7) |

**C2: PASS** (strict). No line type is above 2× Azure. Titles are the weakest type, at 1.33×.

**Folded spelling** (hamza forms, ى/ي, ة/ه and vowel marks ignored) gives a weaker result:
- overall, ours is level with Azure on letters (−0.007, CI −0.035 to +0.024) and still has fewer wrong lines (−1.5,
  CI −2.0 to −1.0);
- **in 2000+, ours is clearly worse: +0.07 points (CI +0.02 to +0.13).** Under a folded reading of C1 this one era
  fails;
- titles reach **1.99× Azure**, just under the line. Light text on a dark ground is 1.50× (31 lines only).

So the reader passes the criteria as the owner set them (transcribe as printed, every letter counted). The one
weakness is modern 2000+ print once the spelling conventions are folded away. There, Azure is a little ahead on the
letters themselves.

## Method

The method mirrors experiment 81: build81, read81, agree81, judge81 and est81, with the scorer fix and the folded
measure.

**1. The locked sets (`build90.py`).** Documents were fetched read-only from `s3://mandumah-source-docs` with
presigned URLs and cut locally. The cut is experiment 81's:
- a 250-dpi pypdfium2 5.12.1 render;
- Azure's line polygon;
- `cut_line(test=True)` at 48 px.

Every key passes `88_truth_and_lock/locked_old.py`'s guard at run time.
- **Journals.** The eligible documents of the 20 locked journals follow experiment 84's rule (2,075 documents).
  - Up to 24 per journal were taken in random order (seed 90).
  - At most 5 pages per document, taken round-robin, until a journal holds about 1,000 lines.
  - Result: **20,562 lines, 537 pages, 411 documents** (1980–99: 8,992 lines; 2000+: 11,570).
- **Old documents.** All 280 locked documents were opened. Their 104,717 lines exceed the 8,000 cap, so pages were
  taken round-robin, one per document.
  - Result: **8,047 lines, 228 pages, 228 documents** (pre-1950: 4,258; 1950–79: 3,789).
  - While experiment 88 ran its last check, these files were kept outside the repo. They still are, in a session
    scratch folder linked from `out/src`.
- **Titles.** Experiment 89's title rule (`title89.rule_titles`, imported unchanged) was run on page 1 of every
  document in the test. No Argon labels exist for locked material.
  - It proposed 896 candidate lines. I looked at every one on contact sheets (`out/look/titles90_sheet*.png`).
  - 222 were not article titles: bylines, affiliations, dates, body text or verse, and journal logos. They are listed
    by key in `out/not_titles90.json`.
  - **674 title lines** are kept. In the Arabic frame that is 82 on test pages and 591 on the 371 page-1 pages cut
    only for their titles.
- **Frame** (Arabic letters, arabic_share ≥ 0.5, as experiment 81): 24,590 lines plus 591 title-only lines.
  - Left apart: 1,777 mostly-Latin lines (ours = Azure on 87%) and 2,237 lines with no letter (94%).
- **Argon** exists for none of the locked documents (0 of them are among experiment 41's Argon labels).
- **Nuqta** was not run. It was optional, and no GPU was rented.

**2. Mastheads (`masthead90.py`).** The rule was fixed before any reader's reading was looked at, and uses Azure's
JSON and geometry only.
- A masthead is a line in the top 12% or bottom 10% of the page whose folded letters (fuzzy ratio ≥ 70) recur in that
  band:
  - on at least 40% of its issue's pages (and at least 3); or
  - on at least 25% of its journal's pages (and at least 5).
- **548 Arabic frame lines** are mastheads: journal names, issue lines, and running heads with the article's or
  author's name.
- A few footnote lines in old print were caught too, for example «- دراسة».

**3. Readers (`read90.py`).** All read on the CPU with experiment 81's `image_reader` / `image_logprobs`, greedy CTC.

| name | what |
|---|---|
| azure | Azure's line text (its JSON from S3) |
| final | **v7-28M**, experiment 89's pick |
| v3 | experiment 83 |
| v6r | experiment 85 |
| v7 | experiment 89's runner-up; a reference only, read after the sample was drawn and never shown to the judge |

The CPU path was checked before the locked lines were read:
- v3 on 500 of experiment 81's crops: 497 identical to experiment 81's CPU reads;
- v7-28M on 200 of them: 194 identical to experiment 89's GPU reads (fp16).

**4. Agreement and the judge (`agree90.py`, `judge90.py`).**
- **Comparison form.** The strict form is experiment 85's `sform`: punctuation removed, vowel marks kept as marks.
- **Agree stratum:** azure, final, v3 and v6r are all equal. That is **80.5%** of the frame:
  - pre-1950: 67.2%;
  - 1950–79: 79.4%;
  - 1980–99: 83.3%;
  - 2000+: 84.2%.
- **Final = Azure** on 84.0% of lines: journals 87.2%, old print 76.7%.
- **Strata** are stratum × era × group, where group is masthead / title / title_x / other. Titles and mastheads were
  judged in numbers this way.
- **Sample** (seed 90):
  - every title dispute (233) and every masthead dispute (132);
  - about 534 "other" disputes per era;
  - 400 agreed lines.
  - Total: 2,900 lines (`out/judge/frame.json`).
  - The 50 pilot lines were drawn before the sample, from a v3 + v6r map, and are never part of it.
- **The judge** is judge81's, unchanged: gemini-3.8-flash, thinking low, two turns of one conversation (blind
  reading first, then the lettered candidates), run through the Batch API as experiment 85 does.
  - Pilot: $0.0059 a line with standard calls; the Batch rate was about half that.
- **Not answered:** 144 lines, 5.0% of the sample, were refused by the API (`block_reason OTHER`) at every try. They
  are mostly 1950–79 and pre-1950 disputes (60 and 35). They are left out of their strata, as unreadable lines are.
  - This is the one gap in the judging. If those lines differ (for example, religious text), the 1950–79 estimate
    carries an unknown bias.

**5. Estimates (`est90.py`).** est81's stratified estimator and its paired page bootstrap, imported unchanged (1,000
draws).
- Measured strict and folded, with mastheads in and out.
- Titles: the title and title_x strata together.
- Line types: domain estimates, mastheads out.
- The verdict is computed in code from `out/est90.json`.

## Results

**Judge spend and consistency.**
- Spend: $8.73 (50 pilot lines, then 2,900 lines in batch; 2,680 judged with a verdict).
- Verdicts on disputed lines: 1,703 match a candidate, 596 none right, 19 unreadable.
- The blind reading equals the final answer on 70% of disputes and 90% of agreed lines (strict); folded, 85% and 96%.
- Agreed lines the judge calls wrong:

  | era | strict | folded |
  |---|---|---|
  | pre-1950 | 20% | 7% |
  | 1950–79 | 7% | 3% |
  | 1980–99 | 10% | 5% |
  | 2000+ | 5% | 4% |

- About the same as experiment 81 (11.6% strict, 3.6% folded).
- The heaviest-weighted of these lines are judge mistakes, not reader mistakes. For example, on 2522-…_p004 the judge
  dropped «المستوي الأول (», which costs 29 letters to every reader.
- They raise every reader's absolute error equally. That is why the per-reader intervals are wide (overall 0.8–2.1%)
  and why the 2000+ level is high (journals 2522 and 2469). The paired differences are not affected, since all
  readers read those lines the same.
- **The comparison is what the numbers support. The absolute levels are inflated by the judge.**

**Letters wrong %, mastheads OUT** (the verdict's view). 95% intervals are in `out/est90.json`.

| | strict, all | pre-1950 | 1950–79 | 1980–99 | 2000+ | lines wrong, strict | folded, all | folded 2000+ |
|---|---|---|---|---|---|---|---|---|
| Azure | 1.50 | 1.82 | 0.89 | 1.18 | 1.85 | 22.4 | 0.96 | 1.53 |
| **final (v7-28M)** | **1.34** | **1.46** | **0.70** | **1.05** | **1.78** | **17.5** | **0.95** | 1.60 |
| v6r | 1.37 | 1.45 | 0.73 | 1.05 | 1.85 | 18.3 | 0.99 | 1.69 |
| v3 | 1.38 | 1.48 | 0.74 | 1.05 | 1.86 | 18.5 | 1.00 | 1.70 |
| v7 (reference) | 1.36 | 1.50 | 0.71 | 1.06 | 1.80 | 17.7 | 0.97 | 1.65 |

- **Mastheads IN** changes nothing: final 1.34 against Azure 1.50; paired −0.15 (CI −0.21 to −0.09).
- **Mastheads alone** (544 lines, 163 judged): Azure 1.37%, final 1.53%, v3 2.14%.
- **Final against v3:** −0.042 (CI −0.060 to −0.021). Against v6r: −0.029 (CI −0.047 to −0.009). It also leads in
  lines (−1.0 and −0.8 points).
- **v7's coverage:** its reading was a shown candidate or the truth on 83% of judged lines (folded 87%), so its row
  is biased against it.
- **By set** (strict, mastheads out):
  - journals: Azure 1.53, final 1.42 (lines 17.3 vs 13.8);
  - old print: Azure 1.43, final 1.14 (lines 33.9 vs 26.1).

**Titles** (674 lines, 296 judged):

| | strict letters | strict lines | folded letters | folded lines |
|---|---|---|---|---|
| Azure | 5.70 | 29.5 | 1.81 | 15.5 |
| final | 7.55 (1.33×) | 30.0 | 3.60 (1.99×) | 19.9 |
| v3 | 8.36 | 34.0 | 4.20 | 25.7 |

- Paired, final − Azure: +1.85 letters strict (CI +1.29 to +2.46), +1.79 folded.
- Old-print titles are the hardest:
  - Azure 12.1%, final 16.2% strict;
  - folded, 5.1 against 9.2.

**Line types** (C2; strict, mastheads out; ratio = final ÷ Azure, letters):

| type | lines (judged) | final | Azure | ratio | folded ratio |
|---|---|---|---|---|---|
| display titles | 672 (296) | 7.55 | 5.70 | **1.33** | 1.99 |
| light text on dark | 31 (8) | 11.97 | 8.85 | 1.35 | 1.50 |
| tilted > 3° | 277 (54) | 8.84 | 7.37 | 1.20 | 1.26 |
| with digits | 4,065 (450) | 1.14 | 1.40 | 0.81 | 1.08 |
| with Latin letters | 583 (98) | 1.17 | 2.36 | 0.50 | 1.36 |
| plain | 19,259 (1,682) | 1.35 | 1.50 | 0.90 | 0.96 |

- The dark and tilted types rest on few judged lines (8 and 54), and some of their cells borrow their stratum's lines
  (4 each). Their intervals are wide (dark: final 7.4–18.8, Azure 6.3–12.5).

Picture: `out/look/verdict90.png` (looked at; sent to the owner).

## What it changed

- **The reader phase's exit criteria are met on the locked test**, as the owner defined them (every letter counted,
  mastheads to layout):
  - C1 PASS, with ours ahead in every era but 2000+, where it is level;
  - C2 PASS, worst type titles at 1.33×.
- **Caveats to keep with the claim:**
  - with spellings folded, ours is level overall and slightly behind on 2000+ print (+0.07 points);
  - titles are 1.99× Azure folded;
  - 5% of the sample was refused by the judge's API;
  - the judge errs on agreed lines, so absolute levels are inflated. Compare readers with the paired differences.
- **The final reader beats its predecessors on unseen material too.** v7-28M is ahead of v6r and v3, with clear
  paired intervals.
- **Next, by the Plan:** layout (mastheads, titles' context) and the writer (experiment 87). Display titles in old
  print are the reader's weakest remaining line type.
- The locked sets are now spent for this claim. Any later reader needs a new locked set.
- Nothing changed in `src/`.

## Files

- `build90.py`: document lists and presigned URLs, the fetch, page selection, cutting, merge (`out/lines90.jsonl`,
  `out/crops48/`, `out/src/`).
- `title90.py`: titles by experiment 89's rule, contact sheets, the looked-at drops (`out/title90.json`,
  `out/not_titles90.json`).
- `masthead90.py`: the repeated-band masthead rule (`out/masthead90.json`).
- `read90.py`: a reader on every locked crop (`out/read/image_<name>.jsonl`).
- `agree90.py`: readings, the agreement map, the sample, the pilot (`out/readings90.jsonl`, `out/agree90.json`,
  `out/judge/`).
- `judge90.py`: judge crops and the blind-first judge, pilot and Batch (`out/judge/answers.jsonl`, `spend.jsonl`).
- `est90.py`: estimates and the verdict (`out/est90.json`, `out/est90.log`).
- `fig90.py`: the picture (`out/look/verdict90.png`).

Everything in `out/` is private (scans, crops, texts, URL lists with mode 600, which expire) and gitignored.
Line crops went to Gemini for judging and nowhere else.
