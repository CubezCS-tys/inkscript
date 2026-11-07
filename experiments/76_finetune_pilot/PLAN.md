# Experiment 76: fine-tuning Nuqta on our own pages (the plan; nothing run yet)

**Question (owner, 2026-11-04).** "Could we fine-tune it on our own Mandumah pages using the Gemini and Azure
outputs we had?" Planned on 2026-11-04 to run after the OCR lab's document 3. No GPU was rented, no paid API was
called, and nothing was trained. Every number below was measured from files on this machine by the scripts in this
folder (read only). They are listed under *Files*.

## Summary (10 lines)

1. **What.** Teach Nuqta-Arabic-OCR-4B our pages with a small add-on (LoRA, about 0.1 GB). It keeps reading whole
   pages the way it does today, with the text exactly as printed (target (a)). Structure (target (b)) comes second.
2. **The labels we have are not what they seem.** Argon did not read the pages on its own: it edited Azure's lines
   and left 96.8% of them untouched. On the owner's 20 checked pages, 6.2% of the lines Argon left alone are still
   wrong. Azure and Argon "agreeing" therefore does not make a clean label.
3. **A truly independent second reading is clean.** Where Azure and a blind Gemini reading of the same line crop
   agree (experiment 34), the line is right **449 times out of 450** on the owner's pages. That happens on 58% of lines.
4. **Lines.** On disk: 40,612 pages and 2.15 million Azure lines with Argon output, all with the scan. At a 58% yield
   that is about 1.2 million clean lines, but only once a third reader has read those pages. Free today: **4,239 clean
   lines** (27,366 words) on 173 yardstick pages.
5. **Third reader.** We need one, run on our rented GPU: Nuqta itself (before fine-tuning), plus PaddleOCR-VL-1.6.
   A line becomes a label when 2 of the 3 independent readers agree, and every other line is left out of the
   training loss.
6. **Size of the pilot.** Step 1 trains on the 173 free pages. Step 2 adds 1,000 pages read by the third reader
   (half from before 2000), which gives about 30–40k trained lines.
7. **Cost.** About $20 expected, with a **cap of $50** all in (RTX 5090 at $0.935/h: labelling ~$10, training ~$3,
   tests ~$2, set-up and idle time ~$5). Step 1 alone costs ≤ $3.
8. **Time.** Step 1 takes about 1.5 GPU hours. Steps 2–3 take about 15 GPU hours (mostly labelling), and run
   unattended. The owner's time is only the look at the first result.
9. **The test.** It uses only journals never seen in training: the owner's 20 checked yardstick pages, the lab's
   documents 1–3, and 100 pages of journal 0097. The scorer is the lab's own, with letters and words as the headline.
10. **Success** means word errors fall by at least a fifth on the owner-checked pages, with no loss elsewhere:
    document 1 stays perfect; footnote marks, old spellings and printed vowel marks are kept; there are no new
    invented words; and no reading loops. **Stop and show the owner after step 1.**

**One decision for the owner first (found while measuring).** The owner's two corrections of the same page
(document 2: the yardstick gold of 2026-10-11 and the lab's rev1 of 2026-11-04) disagree in 22 places. In the
October gold, the space printed before «،» and «.» and inside « » is kept 15 times. The November correction, which
started from Nuqta's reading, has none. Training teaches whichever rule the labels follow, so the rule has to be
chosen before step 2. Until then, this spacing is scored separately and never counted in the headline.

## 1. What is on disk (measured, `inventory76.py` → `out/inventory76.jsonl`, `out/journals76.json`)

"Argon output" = an answer of experiment 43's pipeline: Azure's lines + the page images → Gemini 4 Argon, which returns
each page's blocks as Azure line ids (title, byline, paragraph, footnote, reference, table, header/footer …) plus a
list of **fixes** (a substring of an Azure line → what it says it should be). It does not return its own reading of
the page. Runs counted (each article once; 2 duplicates dropped):

| run (experiment) | articles | pages | Azure lines | lines in a labelled block | lines Argon fixed |
|---|---|---|---|---|---|
| v2_55 (41/43, the 55 with all 20 gold pages) | 55 | 399 | 17,137 | 15,395 | 957 |
| v33_300 (43, random 300) | 299 | 3,521 | 160,664 | 136,861 | 9,645 |
| v33_300b (43, second random 300) | 300 | 3,404 | 146,663 | 121,753 | 8,426 |
| j0130 (52) | 126 | 2,439 | 114,390 | 83,251 | 4,382 |
| j0165 (70) | 145 | 2,841 | 91,112 | 74,092 | 3,318 |
| j0011, j0013, j0097, j0246, j0523, j0840, j1001 (74) | 1,048 | 28,008 | 1,621,235 | 1,147,055 | 41,527 |
| **all** | **1,973** | **40,612** | **2,151,201** | **1,578,407** | **68,255** |

- **Azure JSON and the scan PDF are local for all 1,973 articles** (and for 340 more of journal 1182, read by Azure
  but never sent to Argon: experiment 74 stopped before it). The PDFs are Mandumah's page scans; a training image
  is a render of the PDF page (the lab renders with pypdfium2 5.12.1).
- **Journals and years.** 415 journal codes. Nine education journals of experiments 52, 70 and 74 make 33,339 of
  the 40,612 pages, almost all 2010–2025 (0013 دراسات نفسية 6,679 pages; 0246 6,468; 0523 5,880; 0011 2,997;
  0097 2,915; 0165 2,841; 0130 2,439; 1001 1,636; 0840 1,484). The two random 300s and the 55 add 7,273 pages
  from 406 other journals, 1920s–2020s. Pages by decade over everything: 1920s 39, 1930s 96, 1940s 97, 1950s 398,
  1960s 623, 1970s 763, 1980s 773, 1990s 835, 2000s 923, 2010s 21,286, 2020s 14,779. **Old print is scarce: about
  3,600 pages before 2000**, and the owner-checked test pages are mostly old.
- **Truth on disk.** The owner checked 20 yardstick pages (experiment 34, `status: done`), 751 lines, 1937–2006, one
  page per journal. Every one of the 202 yardstick pages (8,457 lines) also carries **a blind second reading per
  line**: gemini-3.8-flash read each line's crop without seeing Azure's text (experiment 34 `second.py`). The lab adds
  documents 1 and 2 with the owner's verdicts (`lab.sqlite`, rev1 each), and document 3 is being read now.
- **Gemini alone** (experiment 40, approach A: one page image → HTML) exists for about 45 pages. It is not used here.

## 2. How many lines are clean enough to teach? (measured, `consensus76.py`, `pagelevel76.py`)

Policies are the lab's (`experiments/75_ocr_lab/labocr/evaluation.py`): **faithful** = as printed (marks, hamza,
ى/ي, digits, punctuation and its spacing count); **no_punct** = faithful with punctuation removed (letters and words);
**folded** = the search fold (marks, alef forms, ى/ي, ة/ه, digits, punctuation folded).

**Azure vs Argon (all 40,612 pages).** Argon changed 68,255 lines, or 3.2%, so 96.8% "agree exactly" *by
construction*: Argon edits Azure's lines rather than reading the page itself. Of its 70,137 fixes:
- 58% change letters or words;
- 23% change punctuation only;
- 18% change marks or letter forms only;
- 1% change nothing visible (Unicode only).

Under the fold, about 1.9% of lines differ.

**Against the owner's truth (20 checked pages, 751 lines; the 748 Argon covers).**

| a line is taken as a label when … | lines it keeps | right, as printed | right, letters (no_punct) | right, folded |
|---|---|---|---|---|
| Azure alone | 751 | 90.4% (679) | 92.9% (698) | 95.6% (718) |
| Argon's reading (Azure + its fixes) | 748 | 91.3% (683) | 94.4% (706) | 97.5% (729) |
| Argon left Azure's line unchanged | 711 | **93.8%** (667) | 96.5% (686) | 98.7% (702) |
| **Azure = blind Gemini** (independent) | 450 / 555 / 683 | **99.8%** (449 of 450) | 99.8% (554 of 555) | 99.7% (681 of 683) |
| Argon = blind Gemini | 467 / 573 / 701 | 98.7% (461 of 467) | 99.0% | 99.1% |

Three things follow:
- An unchanged Argon line is wrong 1 time in 16, so Azure + Argon alone is **not** a clean label.
- Two independent readers that agree are wrong about 1 time in 500.
- Argon agreeing with Gemini is *less* clean than Azure agreeing with Gemini. The two Gemini models share habits,
  so their agreement is not independent.

The one wrong line among the 450 agreed ones is telling. The page prints a misprint, «الحدوود», and both readers
silently corrected it to «الحدود». Readers fix misprints, and decision D30 says we print what is printed.

Caveat: the owner corrected these pages starting from Azure's draft. That flatters Azure, and so flatters every row
built on Azure.

**Yield of independent agreement (202 yardstick pages, 8,457 lines, Azure vs blind Gemini).**

| | as printed | letters (no_punct) | folded |
|---|---|---|---|
| lines that agree | **58.0%** | 74.2% | 87.1% |
| by decade, as printed | pre-1960 47%, 1960s 51%, 1970s 50%, 1980s 52%, 1990s 66%, 2000s 63%, 2010s 62%, 2020s 69% | | |
| by kind, as printed | text 56%, table cell 68%, footnote 45%, running head/foot 66%, heading 62%, equation 27% | | |
| whole pages where *every* line agrees | **0 of 202** | 6 | 17 |
| gold regions where every line agrees | 1,670 of 3,611 (but these hold only 28% of the lines) | 2,385 | 2,803 |
| median share of a page's lines that agree | 56% | 74% | 90% |

So:
- **Whole pages cannot be "clean pages".** No page agrees on every line.
- **Region crops waste most of the agreement**: only 28% of lines sit in fully agreed regions.
- **The recipe is the whole page with a loss mask.** The image is the whole page, the target is the whole page's
  text, and the training loss counts only the tokens of agreed lines. This is the same input as Nuqta reads today
  (2.4 MP whole page), and it keeps every agreed line.

**Is a third reader needed?** Yes. The only blind second reading on disk covers the 202 yardstick pages. For the
40,612 Argon pages there is Azure and an *edit* of Azure, nothing independent.
- **Nuqta (before fine-tuning) as a reader, on document 2 against the October gold:**
  - as printed: 8 of 27 lines match the truth, because it drops the printed spaces before «،» and «.»;
  - letters (no_punct): 22 of 27;
  - where its reading contains Azure's line: 8 of 8 right as printed, 21 of 21 by letters, 22 of 22 folded.
- **There is a catch in using Nuqta alone.** Lines where Azure and Nuqta agree are lines Nuqta already reads right.
  They keep it on our pages and guard against forgetting, but they teach it nothing new. The lessons are the lines
  where Nuqta is wrong and two *other* readers agree. So the third reader is a pair:
  - **Nuqta base**, about 20 s a page with the lab's speed fix;
  - **PaddleOCR-VL-1.6**, about 16 s a page; it is weaker (5–6% of characters from Azure), but independent of both.

  A line becomes a label when 2 of the 3 independent readings agree (Azure, Nuqta, Paddle). Argon's fix stands in
  for Azure where Argon changed the line. The label is marked a *lesson* when Nuqta is the one that disagrees, and
  *reinforcement* when Nuqta agrees. Every other line is masked out of the loss, or listed for adjudication.
- **GPU cost of the third reader:** (20 s + 16 s) × $0.935/h = **$0.0094 a page**.
  - 1,000 pages: 10 h, **$9.35**; Nuqta alone would be 5.6 h, $5.20.
  - The card reports ~1.8 s a page with batched vLLM serving. If step 2 shows vLLM gives the same text as the
    lab's runs, labelling falls to well under $2. The plan budgets the measured 20 s, not the card's figure.

## 3. Target: (a) transcription first, (b) structure second

**Recommendation: (a), the text exactly as printed.** The reasons:
1. **It can be measured today.** The owner's truth (20 yardstick pages, documents 1–3) is text. The layout truth is
   unfinished: document 1's rev1 is text only, and Nuqta gives no boxes at all.
2. **It is a small change for the model.** It is the same prompt, the same page and the same kind of answer, only
   on our pages. Teaching (b) means a new output format (fields), which is a larger shift and makes forgetting more
   likely.
3. **Structure already works in production.** It costs $0.008–0.016 a page through Azure + Argon, with block types
   right 96.8% (experiment 40). But Argon's labels are a teacher's labels, not truth: the owner has checked 183
   blocks of one article. Recognition is where Nuqta beats the teachers (document 1: Azure 20 characters wrong,
   Nuqta 0). Where the student can win is where the pilot should go first.
4. **Argon still earns its place in (a).** Its blocks give each page's reading order and say which lines are running
   heads, footnotes and table cells. That is how the target text of a page is put in order (Nuqta reads in reading
   order), and how the results are broken down by kind.

(b) is the next pilot. It would use Nuqta's Markdown mode, with Argon's line labels written as light tags (title,
author, affiliation, abstract, footnote, reference). It needs a structure truth first: the owner's corrected regions
on /lab.

## 4. Split: by journal, never by page (`out/split76.json`)

- **Test journals (never trained on), 26 codes:**
  - the 20 journals of the owner's checked yardstick pages;
  - the lab's documents: 2399 (document 1), 0018 (document 2), 0877 (document 3);
  - **0097** المجلة العربية للتربية, a whole modern education journal (2015–2024), as the large held-out set;
  - 4 codes that share a printed name with one of these (0081, 0084, 0108, 2071: «مجلة كلية التربية» and
    «دراسات تربوية» are printed by several codes; experiment 74 found the same journal under two names).

  Together these hold 144 articles, 3,376 pages and 126,453 Azure lines, none of which may be trained on.
- **Training pool:** 1,829 articles, 389 journals, 37,236 pages, 2,024,748 Azure lines. In addition there are 173
  yardstick pages (7,289 lines, 136 journals) outside the test journals; 9 yardstick pages fall in test journals and
  are dropped.
- **Leakage checks:**
  - in code, before every run: no test journal code or name, no test article stem, and no test page image hash in
    the training manifest (the lab's `ingest` already hashes renders);
  - one article never spans the splits;
  - the 0013 / 0840 pair (both «دراسات نفسية») stays together, in training.

| split | pages | clean lines (labels) | what it measures |
|---|---|---|---|
| train, step 1 | 173 yardstick pages | **4,239** (Azure = blind Gemini, as printed); 27,366 words | first before/after |
| train, step 2 | +1,000 pool pages: 500 before 2000 (random sets), 500 from the eight modern journals (≤ 3 pages an article) | ~30–40k expected (≈ 53 lines a page × ~60%; measured once read) | the pilot |
| test, owner truth | 20 yardstick pages + documents 1–3 (doc 2 is also a yardstick page) = 22 pages, ~800 lines | the owner's text | the headline |
| test, held-out journal | 100 pages of 0097 | lines where Azure = Paddle (no Nuqta in the label) | a larger check, no truth |

## 5. Training recipe (first pass)

- **The model gets an adapter: LoRA, not a full fine-tune.**
  - A full fine-tune of 4.75B parameters needs ~76 GB for weights, gradients and Adam: several GPUs and a full
    10 GB copy of the weights.
  - LoRA trains about 0.5–1% of the weights. The result is a ~0.1 GB file that is easy to keep private, easy to
    compare (base vs base + adapter on the same host), and easy to throw away.
  - The vision tower (0.33B) and its merger stay frozen, as they effectively were in the card's recipe (vision
    learning rate 1e-6, a tenth of the decoder's).
- **Framework.** It is the lab's stack on the host (torch 2.9.0 + cu12.8 image, transformers 5.8.1, the version
  in Nuqta's config), plus `peft` for LoRA and a plain training loop or the `transformers` Trainer with our own
  collator. The fast kernels (`flash-linear-attention` 0.6.0, `causal-conv1d` 1.7.0, built on session 2's host)
  are needed for the 24 linear-attention layers' backward pass. **The lab's speed fix (`conv3d_as_linear`) is also
  needed in training**, since the patch embedding took 59.6 s a page as a conv3d. A training step must use the
  same weights path as inference.
- **Input and target.**
  - Input: whole pages, exactly the card's `prepare()`: page-shaped images resized to 2.4 MP, which gives about
    2,340 vision tokens a page. The card's own prompt is used ("as written"), with thinking off.
  - Target: the page's lines in Argon's reading order, one per line (Nuqta's output style), so a page is about
    500–1,000 tokens.
  - **Loss mask:** only the tokens of label lines count. Disputed lines stay in the target text (Azure's
    reading, so the page reads naturally) but carry no loss.
  - Lines Argon marks as noise and show-through are dropped from the target.
- **Rehearsal against forgetting.** 20% of training pages use Nuqta base's *own* full reading as the target
  (self-distillation). This keeps its general behaviour (tashkeel only where printed, tables, no loops) without any
  public data.
- **Hyperparameters, pass 1:**
  - LoRA rank 16, alpha 32, dropout 0.05, on the decoder's attention, linear-attention projections and MLP
    (q/k/v/o, in/out projections, gate/up/down);
  - learning rate 1e-4, cosine, 3% warm-up; 2 epochs;
  - effective batch 8 (batch 1 × 8 accumulation); bf16; gradient checkpointing;
  - target cap 2,048 tokens (longer pages are skipped and counted);
  - loss computed only at target positions (the vocabulary is 248k, so full-sequence logits alone would take
    ~4 GB);
  - fixed seed.

  Step 1 also tries learning rate 5e-5. Two short runs, not a sweep.
- **GPU.** One RTX 5090 32 GB (the lab's card: Vast datacenter, reliability ≥ 99.5%, $0.935/h), under the lab's
  `gpu_session.py` rules: datacenter only, the keeper process, an idle timeout and a spend cap. A 48 GB card is the
  fallback if memory runs out.
- **Peak memory expected (to be measured in step 1 before anything larger runs):**
  - GPU, about **18–24 GB**:
    - bf16 weights 9.5 GB;
    - LoRA weights and Adam well under 1 GB;
    - checkpointed activations for a ~3.5k-token sequence, a few GB;
    - recompute peaks and logits at target positions, a few GB.

    If it passes 30 GB: batch stays 1, the target cap drops to 1,536, and the input image is **not** shrunk,
    since that would change the reading.
  - **This machine**: data preparation reads one Azure JSON at a time and renders pages with pypdfium2, so under
    2 GB. It is checked with `/usr/bin/time -v` on the first 50 pages, and experiment 9's watchdog runs during
    preparation (62 GB RAM, 27 GB free on 2026-11-04).
- **Speed (to be measured; estimate only).** A step costs about 3× a forward pass of a ~3.5k-token page. The guess
  is 3–6 s a page on the 5090 with the fast kernels, so 2 epochs of 1,200 pages is about 2–4 h. Step 1 measures it
  on 20 pages and stops if it is over 10 s.

## 6. Cost and cap

| item | GPU hours (5090) | $ |
|---|---|---|
| Step 1: set-up (~10 min), base reading of the 22 test pages (7 min), 2 short trainings on 173 pages (~2 × 25 min), after-reading (2 × 7 min) | ~1.5 | ~1.40 |
| Step 2: Nuqta + Paddle on 1,000 training pages (36 s a page) and on 100 test pages of 0097 | ~11 | ~10.30 |
| Step 3: training on ~1,200 pages, 2 epochs; after-reading of 122 test pages | ~3.5 | ~3.30 |
| set-up again, downloads (~10 GB weights), idle until the keeper stops it, one rerun | ~5 | ~4.70 |
| **expected** | **~21** | **~$20** |
| **cap (all in, including any Nuqta labelling)** | | **$50**; stop and report at $40 |

- Step 1 has its own cap of **$3**. The lab's `gpu_session.py budget` warns before any run that would pass a cap.
- Nothing is paid outside Vast: no Gemini, no Claude API, no Azure. The labels use only Azure and Gemini output
  already on disk (experiment 34's blind lines, experiment 43's Argon).

## 7. How it is judged

- **The same pages, read twice on the same host**, by Nuqta base and by Nuqta + adapter. The settings are those of
  the lab's `as_written` + speed fix: greedy, 8,192-token cap, card `prepare()`. Both readings are imported into the
  lab (`labocr`), as new labelled variants, by the lab's lead, and scored by `labocr/evaluation.py` against the
  owner's revisions.
- **Headline: letters and words.**
  - CER and WER under `no_punct`, which is as printed with punctuation removed;
  - also `folded` (search).
- **Shown separately:**
  - `raw` / `faithful`, where punctuation and its spacing count;
  - the spacing differences counted by type (space before «،» «.», inside « », before «(»).

  These wait for the owner's spacing rule (see the summary).
- **Success (all must hold on the owner-truth pages):**
  1. Words wrong (no_punct WER) fall by **≥ 20% relative** over the 22 pages, and no single page gets worse by
     more than 1 word.
  2. **Document 1 stays at 0 characters wrong** as printed (it is perfect today).
  3. **Footnote marks:** every note call and footnote marker the base reads (document 1's «1», document 3's
     columns, the yardstick footnote lines) is still read, as the same character.
  4. **Old spelling as printed:** on the pre-1960 pages (0018 1937, 0513 1951) the count of ى for final ي
     (فى، التى، الذى، شىء), «الى» without hamza and «ألاّ» with its shadda is not lower than the base's.
     Training labels from modern pages must not modernise old ones.
  5. **No invented words:** words that are neither in the truth nor in any reader's output (Azure, base,
     Paddle) do not increase. Plausible-but-wrong words (document 2's «لديهما» for «لديها») are listed one by one.
  6. **Tashkeel:** invented marks (marks the truth lacks) are not more than the base's.
  7. No new loops, truncations or empty pages (the lab's flags).
- **Held-out journal (0097, 100 pages, no truth):**
  - agreement with the lines where Azure = Paddle rises;
  - on lines where Azure, Paddle and Nuqta base all agreed, the adapter keeps **≥ 99.5%** (the forgetting check).
- **Not a success:** a better score on training-like pages only, or a gain that comes only from spacing.

## 8. Risks and how each is handled

| risk | what it would look like | guard |
|---|---|---|
| **Learning the teachers' habits** | Azure's «(( ))» for « », Azure's space before «(», Gemini's modernised فى→في, readers silently correcting misprints («الحدوود») | labels only where 2 independent readers agree (99.8% right on the owner's pages); the agreed-but-wrong cases are listed; old-spelling and misprint checks in the success test; spacing kept out of the headline until the owner sets the rule |
| **Forgetting general skills** | worse tables, more invented tashkeel, loops, worse on non-journal pages | LoRA (base weights untouched), 2 epochs, 20% self-distillation pages, the 99.5% forgetting check on 0097, document 1 must stay perfect; the adapter can always be switched off |
| **Inventing plausible words** (it is a language model) | a real Arabic word that is not on the page | greedy decoding as now; the invented-word count; every new word substitution listed beside the scan crop for the lead to look at (not routine owner checks) |
| **Train/test leakage** | the same journal, article or page on both sides; one journal printed under two names | split by journal code *and* printed name; hashes of every render checked; the test list is fixed in `out/split76.json` before any training |
| **Bad labels at scale** | the 1-in-500 agreed-but-wrong line, many times over | masked loss; per-kind yields reported (footnotes agree only 45%, so they are under-taught); a sample of lesson lines shown as crops to the lead |
| **Private data** | scans, labels or weights leaving our machines | see below |

**Private-data rules (the owner's, unchanged):**
- **Where the data lives.** Scans, renders and labels stay on this machine and on one rented Vast host
  (datacenter, verified). The host is **destroyed** after each session (`gpu_session.py stop`, then a check that no
  instance is left).
- **How it moves.** The training set goes up over ssh as one archive and dies with the host.
- **The fine-tuned weights are never pushed** to Hugging Face, GitHub or anywhere else:
  - the host gets no Hugging Face token (the base model is public);
  - after the download, `HF_HUB_OFFLINE=1` is set;
  - nothing calls `push_to_hub`;
  - the adapter comes back by scp to `experiments/76_finetune_pilot/out/adapters/` (gitignored, like every `out/`).
- **Nothing goes on a public link.** Results are shown on the Desk's /lab page (localhost) and in this folder.
- The lab manifests already mark these pages "private Mandumah page: local or rented-GPU processing only".

## 9. Steps, small to large

0. **Done (2026-11-04, $0):** inventory, consensus measurements and split (this file; `out/`).
1. **Free first pass (≤ $3, ~1.5 GPU h).**
   - Build the 173-page training set from the yardstick drafts: 4,239 label lines, the rest masked. Use Argon's
     order where the article is in v2_55, otherwise the yardstick's own `order`.
   - Measure peak memory on this machine while building it.
   - On one 5090: base reading of the 22 owner-truth test pages; then two short LoRA trainings (learning rate
     1e-4 and 5e-5), measuring s/page and peak GPU memory; then the after-reading of the 22 pages.
   - Bring the adapters back and destroy the host.
   - The lab's lead imports the readings into /lab, as variants `as_written_ft76s1_*`.
   - **STOP: show the owner the before/after on /lab**, with the word diffs beside the scan and the separate
     spacing count. Also ask for the spacing rule. Nothing larger runs without the owner's yes.
2. **Third reader (≤ $12).**
   - Render 1,000 training-pool pages (stratified as in section 4) and the 100 test pages of 0097.
   - Run Nuqta base and Paddle 1.6 over them. First try vLLM for Nuqta on 20 pages, and keep it only if its text
     is identical to the lab's runs.
   - Build the 2-of-3 labels, then report lessons vs reinforcement lines and the yield per kind and decade.
3. **The pilot training (≤ $6).**
   - Train on ~1,200 pages with the step-1 settings, or with the better of the two learning rates.
   - After-reading of the 22 + 100 test pages; score.
   - **Show the owner again.**
4. Only then: decide between a larger run, target (b), or stopping. Write the result in this folder's README,
   `docs/STATUS.md`, `docs/ideas.md` and `docs/decisions.md` (CLAUDE.md's self-documenting rule).

## Files

- `inventory76.py` → `out/inventory76.jsonl` (one line per article: set, journal, year, pages, Azure lines,
  labelled lines, fixed lines, whether the Azure JSON and PDF are local) and `out/journals76.json`.
- `consensus76.py` → `out/consensus76.json`:
  - A: Azure vs blind Gemini on 202 yardstick pages;
  - B: against the owner's 20 pages, including Argon (v2_55's answers applied to Azure's lines);
  - C: what Argon's 70,137 fixes touch.
- `pagelevel76.py` → `out/pagelevel76.json`: whole-page and region agreement.
- `out/split76.json`: the 26 test journal codes.
- Inputs, read only: experiments 34 (yardstick gold and blind lines), 41/43/52/70/74 (Argon answers, samples,
  fetched PDFs and Azure JSON), 75 (Nuqta and Azure predictions for documents 1–2, the lab's two revisions in
  `lab.sqlite`, opened read only). Nothing under `/home/appuser/data` was needed.
