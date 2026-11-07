# Experiment 84: a locked final test, and teaching the reader display faces and white-on-dark text

**Question (lead, owner's approval 2026-11-05).**

**A.** Every fix so far has been measured on experiment 81's held-out test (26 journals of `split76.json`). Fixing
whatever that test shows slowly wears it out. So: lock a final test that nobody looks at until the final claim.

**B.** Experiment 81 found that on 2000+ print essentially all of v3's excess letter errors against Azure come from
journal 0097's running header «المجلة العربية للتربية». It is set in a decorative calligraphic display face, often
white on a dark band, and on all other modern lines v3 beats Azure (0.48% against 0.50% letters). Can generic
training teach the reader display faces and light-on-dark text, without ever showing it 0097? The training adds:
- real lines inverted or banded on the fly;
- synthetic lines in free display faces.

Added by the lead: the owner's convention is "transcribe AS PRINTED", but Azure writes printed «» as (( )), so the
readers never write «». Teach both marks faithfully with synthetic lines, and report «» precision and recall apart from
the headline.

**Caps:** GPU $12, no Gemini.

**Status (2026-11-05): done.** One RTX 5090 (Vast instance 59318387, Czechia, $0.99/h), 20:34–22:38 UTC: **GPU $2.05
of $12**. The host was destroyed with `gs84.py stop`, and none of this experiment's instances are left (the one still
listed is experiment 85's). No Gemini.

**Verdict.**
- Plain display titles and the dates on dark bands are now read.
- Journal 0097's stacked calligraphic logotype is still not read. Its header letters improve only from 21.0% to 19.3%
  wrong (Azure 8.1%). No free font draws stacked thuluth like it.
- Overall the new reader is level with v3 on the held-out lines (0.84% against 0.85%; Azure 0.88%) and on the owner's
  pages (0.71% against 0.69%, within noise).
- **Guillemets now come out as printed:** 55 of the 58 printed marks on the owner's pages (v3: none). Stray
  parentheses fall from 116 to 35.

## Part A: the locked final test

`LOCKED_TEST.json` holds 20 journal codes with names, countries, fields, eras, year spans and the selection rule. Its
note says: *locked: no training, no tuning, no peeking; opened once for the final claim with the owner's OK*.
`select84.py` made it (no network, no page opened).

**The guard: `locked.py`.** Every later selector, trainer, text source and test builder imports it:
- `locked_codes()` returns the 20 codes;
- `is_locked(stem)` tests one stem or code;
- `assert_not_locked(stems)` raises if any stem, line key or code belongs to a locked journal.

This experiment already calls the guard in:
- `presign84.py`: no locked document is ever cut;
- `text84.py`: no locked journal's names or titles are rendered.

The traced faces of experiment 78 were checked too (14 faces, none locked).

**Rule.** A journal qualifies when all of these hold:
- the catalogue (`marc.db`, read only) has at least 8 eligible documents for it: Arabic, the article-like types of
  experiments 80/83, 2–40 printed pages, PDF and Azure JSON both in the main bucket (so a test can later be cut from
  S3 exactly as experiment 83 cut its lines);
- its code is in none of the following. 3,801 codes are excluded, so 617 journals remain eligible.
  - the 27 codes of `split76.json`. These cover experiment 81's test and lab documents 1–3 (journals 2399, 0018,
    0877);
  - experiment 77's training, dev and old80 manifests, and its `select77.json`;
  - experiment 83's `plan83` (its training pool);
  - experiment 80's plan, manifest and ids;
  - experiment 76's inventory;
  - every document stem in a file name anywhere under /home/appuser (AI-Search not walked; 6,846 stems);
  - every stem named in a text, JSON or code file of the repo. Left out of this scan: catalogue enumerations
    (experiment 44's bucket listing, candidate lists, experiment 16's id list, experiment 43's catalogue draw,
    experiment 53's Word-file list) and files of 30 MB or more (Gemini batch files, whose documents are on disk by
    name). This scan found 16,682 stems.

**Choice (seed 84).** The strata go by the journal's median year: 1980–1999 (9) and 2000+ (11). Inside a stratum,
journals are taken round-robin over their field of study, so subjects spread.

**Display faces.** The catalogue cannot show which journals use display faces. In the 2000+ stratum, two slots went
first to arts and design fields, the only hint it gives.

| era | journals |
|---|---|
| 1980–1999 | 0174 اللغة والأدب · 0352 الواحة · 0583 الناشر العربي · 0637 الإيمان · 0874 مجلة المال والصناعة · 1047 مجلة الموسم · 1166 مجلة الأمن · 1297 مجلة دراسات سينمائية · 1366 مجلة كلية الآداب والعلوم الإنسانية |
| 2000+ | 0187 مجلة دراسات المعلومات · 1273 مجلة دفاتر جغرافية · 1486 مجلة المعرفة التربوية · 2023 المجلة السعودية للعلوم النفسية · 2131 مجلة الشهاب · 2151 مجلة جامعة البعث (الاقتصادية) · 2255 مجلة العلوم الاجتماعية · 2351 المجلة السعودية للفن والتصميم · 2469 مجلة جامعة دمشق للدراسات التاريخية · 2522 مجلة الفن والتصميم · 2611 مجلة السياق |

**No old print can be locked at journal level.** Of the 363 journals with any document before 1980 in the main bucket,
all but two are already in experiments 77/80/83's training pools or on disk:
- 0871 has 1970 documents;
- 1204 has 1978–79 documents.

Neither has enough eligible documents. So the locked test covers 1980 onward only. For old print, the options are
these, for the owner to choose:
- a document-level lock inside training journals (weaker: the journal's typeface is seen);
- reserving part of experiment 81's held-out pre-1950 journals from now on.

## Part B: method

**Rule: never journal 0097 or its header.**
- 0097 is held out (`split76.json`), and `text84.py` also drops it by name.
- Three training-pool journals have names containing 0097's header phrase: 0066, 0552 and 1801 (for example
  «المجلة العربية للتربية الخاصة»). Every synthetic line containing «العربية للتربية» is left out, whatever journal it
  comes from: 271 of 400,000.

**1. Real-line polarity augmentation (`train84.py`).** On the fly, a share of the real training lines is changed:
- 6% are inverted: white or light text (185–255) on a dark, grainy, uneven ground (0–90);
- 4% get a dark band behind part of the line, with the text light inside it;
- the synthetic lines carry their own polarity and skip this step.
- Picture: `out/look/aug84_real.png`.

**2. Synthetic display lines (`text84.py`, `render84.py`).**

*Text* comes from the catalogue's own names and titles of experiment 83's 3,529 training-pool journals:
- running headers (40%): the journal's name with an issue and a date, in the orders and separators printed headers use,
  with Latin or Arabic-Indic digits and Gregorian or Syriac month names;
- journal names alone (15%);
- article titles (35%);
- section headings (10%).

*Faces* are 50 display faces, chosen by eye from a specimen of 75 (`out/look/specimen_all.png`). Their licences are
recorded in `out/fonts/LICENCES84.json`.

| face(s) | licence | source |
|---|---|---|
| Aref Ruqaa (Regular, Bold), Alkalami, Amiri Quran, Badeen Display, Blaka, Changa, El Messiri, Gulzar, Jomhuria, Katibeh, Lalezar, Lemonada, Mada, Marhey, Mirza Bold, Noto Nastaliq Urdu, Qahiri, Rakkas, Reem Kufi, Reem Kufi Fun, Vibes, Zain (Bold, Black) | SIL OFL 1.1 (each `OFL.txt` and `METADATA.pb` kept) | github.com/google/fonts |
| Arabeyes: Tholoth, Mashq (Regular, Bold), Nagham, Granada, Ostorah, Ouhod Bold, Rasheeq Bold, Shado, Cortoba, Hor, AlHor, Japan, Kayrawan, Metal, Hani, AlBattar | GPL-2 with the font exception | Debian `fonts-arabeyes` |
| KACST: Title, Decorative, Poster, Art, Farsi, Pen, Letter, Screen, Digital | GPL-2 | Debian `fonts-kacst` (Latin digits there are boxes, so these faces get Arabic-only text) |

- No free thuluth or diwani with stacked letters like 0097's logotype was found. Tholoth, Ruqaa, nastaliq and the
  Kufi and poster faces are the nearest.
- Excluded after looking: ae_Haramain (ornament glyphs) and the KACST faces' Latin digits.
- The fonts are used only to render training images on the rented host. They are not redistributed.

*How a line is drawn* (`render84.py`, on top of experiment 78's helpers):
- size: an alef 14–40 px high;
- 40% of header lines are mixed: the journal's name in the display face, the rest in a plain bold face, as headers
  are printed;
- polarity: 38% light text on a dark band covering the line, 14% a band behind part of the line, 10% a grey band,
  38% ordinary dark on paper. Bands have grain, gradients and soft edges;
- scanner damage, an Azure-like polygon, then experiment 77's cut (`common78.cut_line`).

*Quote lines* make up 40% of the synthetic lines (lead's addition):
- they are ordinary body lines (experiment 78's text, faces, paper and damage, `render78.render_one` unchanged);
- a span of 1–5 words is set in «…» (60%) or printed ((…)) (40%);
- the label is exactly what was rendered.

Pictures: `out/look/syn84_sheet.png`.

**3. Fine-tuning (`train84.py`, `host84.sh`).**
- The start is experiment 83's v3 (`../83_reader_scale/out/weights/v3/best.pt`). Its 463-class charset is kept.
- The data is v3's own training set, re-cut on the host from S3 with presigned URLs (`presign84.py`, `cut83.py`
  unchanged, as experiment 83): 2.47M lines, with v3's 444k held-aside lines dropped (`labels_v3.jsonl` from
  `held_v3`).
- Settings: 3 epochs, AdamW, one-cycle at 3e-4 with 10% warm-up. Every epoch is kept. The model used is the last
  epoch.

There are two arms:
- **v5a**: real lines plus the polarity augmentation only;
- **v5**: real lines, the augmentation, and 300k synthetic lines (180k display faces, 120k quote lines). Real lines
  whose Azure label contains (( or )) are dropped: Azure writes printed «» that way, so those labels cannot teach
  the mark. They are dropped, never rewritten.

**4. Scoring.**
- (a) `../83_reader_scale/eval83.py` with `--out` here: the owner's 20 pages, lab documents 1–2 and document 3.
  `quotes84.py` measures «» and (( )) precision and recall on the owner's 20 pages.
- (b) `read84.py` reads experiment 81's 22,783 crops on the local CPU. `est84.py` scores them with experiment 81's
  existing judged truths (est81's estimator imported unchanged) and reports coverage: the share of judged lines whose
  new reading is a candidate the judge saw.
- (c) `est84.py` also gives diag81's 2000+ buckets (0097's header against other lines, dark ground against light
  ground) and the pre-1950 and 1950–99 eras.

## Results

**Control, no GPU: v3 with a test-time polarity flip** (`read84.py --flip`).
- The flip inverts every 48-px window whose mean column-median grey is under 110. The threshold is diag81's, fixed
  before looking.
- It changes 1,057 of 22,783 crops.

On experiment 81's judged lines (letters wrong, %):

| | 2000+ all | 0097 header | dark ground | other 2000+ | pre-1950 | 1950–99 |
|---|---|---|---|---|---|---|
| Azure | 0.704 | 8.08 | 17.7 | 0.504 | 0.737 | 0.943 |
| v3 | 1.014 | 21.0 | 47.8 | 0.472 | 0.562 | 0.829 |
| v3 + flip | 0.979 | 19.4 | 39.2 | 0.478 | 0.562 | 0.833 |

Flipping the polarity alone recovers little. The display face itself, not only the dark ground, is what the reader
has never seen.

**Baseline «» and (( )) on the owner's 20 pages** (`quotes84.py`):

| reader | «» precision | «» recall | (( )) precision | (( )) recall |
|---|---|---|---|---|
| Azure | 7/7 | 7/30 | 28/51 | 28/28 |
| v3 | – (writes none) | 0/30 | 28/59 | 28/28 |

**The data on the host.**
- The host re-cut exactly experiment 83's lines: 513,533 + 8,198 + 231,012 + 2,165,425, with 0 document errors, in
  7 minutes on 40 workers. Its cgroup v1 quota was 46 CPUs, and the scripts now read it.
- It rendered 300,000 + 4,000 synthetic lines in 1 minute.
- v5's training set:
  - 2,692,234 lines;
  - 61,882 real lines dropped for (( or )) in their Azure label;
  - 11,485 synthetic lines dropped for characters outside v3's charset.
- Each epoch took about 18 minutes.

**Dev, last epoch** (Azure-labelled real dev / synthetic dev):

| | real dev CER | synthetic dev CER |
|---|---|---|
| v3 | 1.002% | 10.3% |
| v5a | 0.990% | 8.5% |
| v5 | 1.046% | 1.5% |

v5's higher real-dev CER is expected: the dev labels are Azure's, which write printed «» as (( )).

**Synthetic dev by kind** (`out/vsyn84.json`, letters wrong with punctuation):

| | dark band | partial band | grey band | display on paper | «» / (( )) body lines |
|---|---|---|---|---|---|
| v3 | 15.5 | 14.6 | 11.2 | 9.9 | 6.5 |
| v5a (augmentation only) | 10.4 | 11.3 | 10.3 | 9.9 | 6.2 |
| v5 | 1.4 | 2.5 | 1.4 | 1.2 | 1.8 |

**(a) The owner's 20 pages, lab documents and document 3** (`out/results84.json`; letters / words wrong, punctuation
excluded):

| | owner's 20 pages | lab docs 1–2 | doc 3 vs Argon | lines exact (20 pages) |
|---|---|---|---|---|
| Azure | 0.60 / 1.42 | 0.23 / 1.32 | 0.07 / 0.36 | 93.0% |
| v3 | 0.69 / 1.61 | 0.16 / 1.31 | 0.17 / 1.09 | 91.4% |
| v5a | 0.70 / 1.69 | 0.16 / 1.31 | 0.17 / 1.09 | 90.8% |
| v5 | 0.71 / 1.70 | 0.16 / 1.31 | 0.14 / 0.82 | 90.6% |

- Both fine-tuned readers make 102 word errors on the owner's 20 pages against v3's 97, whether or not the
  synthetic lines were added. So it comes from the extra epochs, not from the display lines, and it is within the
  noise of 745 lines.

**«» and (( )) on the owner's 20 pages** (`quotes84.py`, `out/quotes84*.json`):
- **Against the owner's truth as written:**
  - v5's «» recall is 28/30 and its precision 28/57;
  - its (( )) recall falls to 1/28.
- **Against the print:** I looked at every line with a mark (`out/look/quotes_yard.png`, 28 lines), and every mark on
  them is printed «». The owner's truth writes 28 of them as (( )), inherited from Azure's draft. Counted with those
  as «» (the 9 more lines with only a closing mark are assumed the same):

| | «» written | right | precision | recall (of 58) | stray ( ) |
|---|---|---|---|---|---|
| Azure | 7 | 7 | 100% | 12% | 105 |
| v3 | 0 | 0 | – | 0% | 116 |
| v5a | 0 | 0 | – | 0% | 115 |
| v5 | 57 | 55 | 96.5% | 94.8% | 35 |

- What remains is mixed marks: v5 sometimes writes «…)» or («…». That is the real labels' (( )) habit, still in
  the lines it kept.
- **For the owner:** the 20-page truth itself writes printed «» as (( )) in about half the cases, so that truth needs
  the «» fix before it can score marks.

**(b) Experiment 81's held-out lines** (`out/est84.json`). All 22,783 lines were re-read; the estimate uses exp 81's
judged truths (2,767 lines).

| | letters wrong (95% CI) | lines wrong | pre-1950 | 1950–99 | 2000+ |
|---|---|---|---|---|---|
| Azure | 0.875 (0.73–1.06) | 23.3% | 0.737 | 0.943 | 0.704 |
| v3 | 0.854 (0.70–1.05) | 19.5% | 0.562 | 0.829 | 1.014 |
| v3 + flip | 0.849 | 19.5% | 0.562 | 0.833 | 0.979 |
| v5a | 0.839 (0.68–1.03) | 19.4% | 0.589 | 0.824 | 0.955 |
| v5 | 0.839 (0.68–1.04) | 19.5% | 0.548 | 0.816 | 0.988 |

- Paired with v3, v5 is −0.015 points overall (95% CI −0.036 to +0.004). By era it is −0.013 pre-1950, −0.012
  1950–99 and −0.026 2000+; every interval includes 0.
- v5a: −0.059 on 2000+ (interval −0.09 to −0.03, the only clear move), and +0.027 pre-1950 (interval −0.004 to
  +0.061).
- **Coverage.** The share of judged lines whose new reading is a candidate the judge saw: v5 92.2%, v5a 93.4%. By era
  for v5: pre-1950 95.5%, 1950–99 95.1%, **2000+ 82.4%**. The rest are still scored against the judged truth, but
  the judge never saw that reading.
- On the whole frame, v5 reads 94.8% of lines exactly as v3 does.
- No new Gemini was used. A judge pass on the about 220 uncovered judged lines would cost about $1.20 if the lead
  wants it.

**(c) The 2000+ diagnosis** (diag81's weights; letters wrong %):

| | 0097 header (62 judged) | dark ground (27) | other 2000+ (585) | light ground (620) |
|---|---|---|---|---|
| Azure | 8.08 | 17.7 | 0.504 | 0.627 |
| v3 | 21.0 | 47.8 | 0.472 | 0.801 |
| v3 + flip | 19.4 | 39.2 | 0.478 | 0.805 |
| v5a | 18.8 | 43.3 | 0.471 | 0.763 |
| v5 | 19.3 | 38.7 | 0.493 | 0.817 |

- On the header lines v5 now reads the date on the band, but turns the logotype into other words (الجلة التركنة
  اللربية …).
- Journal 0498's dark-band title «المال والتجارة» (not a header) is read exactly by v5 on 1 of its 5 judged lines,
  against 0 by v3. Two more are one letter off, ح for ج.
- Pre-1950 and 1950–99 did not get worse with v5. v5a's pre-1950 is +0.03, within noise.

Picture: `out/look/result84.png`. Real lines with the judge's truth, v3 and v5, the owner's «» lines, and the numbers.
The version sent by Telegram has the headers only.

## What it changed

- **A locked final test now exists**, with its guard (`locked.py`). Every later selector and trainer must call
  `assert_not_locked`. It has no print before 1980, because no untouched old journal is left.
- **«» is learnable from synthetic lines alone**, without rewriting any Azure label. v5 is the first of our readers
  to write printed guillemets. The owner's 20-page truth needs the same fix before marks can be scored on it.
- **Generic display-face training does not solve 0097.** Its stacked calligraphic logotype has no free look-alike.
  The remaining options are not generic and not this experiment's to choose:
  - accept Azure's reading for running headers;
  - recognise a repeated header once per journal (it is the same image on every page);
  - trace that one face from the scans as experiment 11 traced old faces. This one would mean training on held-out
    0097.
- **v5 or v3?** They are level on the headline. v5 adds «» and better dark-band and display reading, and costs
  nothing measurable elsewhere. The weights are `out/weights/v5/last.pt` (exp 77's checkpoint format, 463 classes).
- **Next:**
  - fix the owner's 20-page truth's «» (about 28 marks), then re-score;
  - if wanted, judge the 2000+ lines v5 reads differently (about $1);
  - a «»-consistent real label set, from v5's own reading where it and Azure agree up to the mark.

## Files

- `select84.py`, `LOCKED_TEST.json`, `locked.py`: the locked test and its guard.
- `text84.py`, `render84.py`: the synthetic display and quote lines (`out/text/display84.jsonl.gz`, `out/fonts/`).
- `train84.py`: train83 plus `--init`, `--invert`, `--band`, `--drop_re`, `--dev2`, `--warm` and the cgroup thread
  count.
- `host84.sh`, `setup_gpu84.sh`, `gs84.py`, `presign84.py`, `bundle84.sh`: the host side. `gs84.py` is gs83 with a
  $12 cap; follow with bracket patterns only.
- `read84.py`, `est84.py`, `quotes84.py`, `vsyn84.py`: the scoring. `fig84.py`: the picture (`out/look/result84.png`).
- `out/` (gitignored, private): fonts, text, the bundle, URL lists (mode 600, they expire), data lists, reads,
  pictures.
