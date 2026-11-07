# Experiment 75: the OCR lab (how much of the reading can we own?)

**Question (owner, 2026-11-04;
[ARABIC_DOCUMENT_OCR_PROJECT_BRIEF.md](../../ARABIC_DOCUMENT_OCR_PROJECT_BRIEF.md)).** How much of the reading process
can we run on software we control, compared with the big players? This is an experiment beside the Azure + Gemini
pipeline, which it does not replace. Recognition, layout, reading order, structure and extraction are scored
separately. We go one document at a time through the document types (clean modern Arabic academic → older/faded
print → two columns + footnotes → tables → Arabic maths → Arabic with English/French → Western control), and the
owner gives feedback after each.

**Status: documents 1, 2 and 3 done; waiting for the owner's feedback on document 3 (2026-11-04, night).** The owner
dropped PaddleOCR as a reader after document 3 ("drop paddle its terrible"). Its runs stay on disk and on /lab,
hidden behind "show dropped readers". From document 4 on, no Paddle text variants are run unless the owner asks.
Earlier status, documents 1 and 2: The owner checked
document 1 by eye: Nuqta "as written" was right character for character. The lead saved that as correction
`2399-003-008-002_p021:rev1` (text only), and doc 1's scores are on `/lab`. Document 2 (older print) ran on an RTX
5090 and shows disagreements only. An earlier status line follows for document 1:

**Document 1 (2026-11-04, morning):** Built:
- the lab package (`labocr/`);
- the engine workers;
- a rented-GPU session helper;
- the Desk page `/lab`, with Compare, Correct and Scores views.

Document 1 ran on PaddleOCR-VL-1.6 (three stages) and Nuqta-Arabic-OCR-4B (two modes), beside our existing Azure
output and experiment 36's PaddleOCR-VL-1.5 output for the same page.

**There are no accuracy numbers yet, by design.** The owner asked (2026-11-04) for a fresh correction instead of the
old gold pages. Scores appear on `/lab` once the owner saves a correction there. Until then the page shows only
where the readers disagree, and labels it that way.

GPU: one RTX 4060 Ti 16 GB (Vast.ai datacenter, $0.269/h). About 35 minutes for everything, **$0.157** at the time
of writing; the session is kept open for document 2 (see *GPU*).

## Document 1

**Page:** `2399-003-008-002` page 21, from مجلة المعهد العالي للدراسات النوعية (2023, Egypt). It is a clean, modern,
one-column Arabic academic page. It has:
- a running head in two parts and a numbered finding;
- bold run-in subheadings (هدف الدراسة، عينة الدراسة …) and numbers in parentheses;
- a superscript note call «1» and its footnote below a rule;
- a running foot with a dotted leader, and a boxed page number.

The PDF draws the page from 68 image pieces, with a text layer beside them whose origin is unknown. The layer is
recorded as `unverified` with that warning, and it is not used: OCR is forced.

**Who read it** (`configs/doc1_e0.yaml`; each engine's documented native settings, E0):

| reader | what ran | time on the page | peak GPU memory | cost of the page |
|---|---|---|---|---|
| **Ours: Azure Read** (existing, exp 28) | prebuilt-read 2024-11-30, lines + paragraphs | (not timed per page) | hosted | already paid |
| PaddleOCR-VL-1.6, **full pipeline** | official `PaddleOCRVL(pipeline_version="v1.6")`, defaults, native Paddle backend | **20.0 s** | 11.4 GB | $0.0015 |
| PaddleOCR-VL-1.6, recogniser alone | `use_layout_detection=False`, `prompt_label="ocr"`, whole page | 16.6 s | 10.8 GB | $0.0012 |
| PP-DocLayoutV3, layout stage alone | `LayoutDetection("PP-DocLayoutV3")` | 1.0 s | 0.6 GB | $0.0001 |
| **Nuqta-Arabic-OCR-4B**, as written | the card's prompt, greedy, bf16, 8,192-token cap, card `prepare()` → 1303×1840 input | **79.0 s** (453 tokens out) | 9.8 GB (torch 9.5 GB) | $0.0059 |
| Nuqta-Arabic-OCR-4B, Markdown mode | the card's Markdown prompt | 81.5 s | 9.8 GB | $0.0061 |
| PaddleOCR-VL-1.5 full pipeline (exp 36, imported) | same page, 2026-10-12, RTX 5090 | (batched, not comparable) | — | — |

Cost of a page = inference seconds × the rental rate. It leaves out set-up, downloads and model load: about 5 s a
run here, because the weights stay on the host's disk. **No Argon output exists for this article on this machine**,
so "ours" for document 1 is Azure alone. The Argon importer is ready for document 2.

**Where the readers disagree** (no truth here; the Compare tab on `/lab` marks every word).
- **Nuqta and Azure** differ in 12 of 228 words: 1.4% of characters as printed, 0.2% folded for search.
- **PaddleOCR-VL-1.6** is 5.7% from Azure and 5.8% from Nuqta.
- **PaddleOCR-VL-1.5** is 5.0% from Azure.

By eye on the scan (an observation, not a score), the disagreements fall into these patterns:
- **Nuqta (as written)** keeps the printed details. The note call is «التخصص.1» and the footnote marker «1الرجبي».
  It also keeps the unspaced «وعباس(2008)», «على(37)» and «القاهرة،2007.», ى in «القريوتى», all nine leader dots,
  and the running foot as one line in the right order. Its Markdown mode adds `**bold**` around the run-in heads and
  drops one leader dot.
- **Azure (ours)** reads the note call as «.!» and the footnote marker as «"». It puts spaces before parentheses
  that the page does not print. It cuts the running foot into three pieces in the wrong order
  («(البحث العلمي في مجال الإعاقة العقلية. | .) صابر الشرقاوي، علياء الوهيبي | ......»).
- **PaddleOCR-VL-1.6 (full pipeline)** misreads letters:
  - «دراسة القريوتى» becomes «(دراسته القرويتي»;
  - «النتائج / نتائج» becomes «النتاج / نتاج» three times;
  - ة becomes ه in «بسلطنه» and «فقره»;
  - «مستجيبا» becomes «مستجبيا».

  It also:
  - writes the note call as «¹» (U+00B9) and drops the footnote's marker;
  - moves a parenthesis («الوظيفية (وتوجد»);
  - spaces «بالرضا الوظيفي», which the page prints joined;
  - reads the running foot as «(البحث العلمي في مجال الاعاقة العقلية) (صابر», losing the dots and the hamza.

  Its layout is good on this page: running heads, body paragraphs, footer and page number are each a region. But
  the footnote is labelled plain `text`, not `footnote`, and its reading order starts with the left-hand half of the
  running head.
- **The recogniser alone** (no layout) is worse again: «دالة» → «الدالة», «التربوي» → «التربية» twice, the year
  moved, «القروتى».
- **PaddleOCR-VL-1.5** (exp 36) errs like 1.6 (النتاج, فقره, مستجبيا) and adds «علياع».
- **The layout stage alone** finds 7 regions where the full pipeline shows 12 (the pipeline merges and splits
  regions after detection).

**Failures, shown and kept.** The first PaddleOCR-VL-1.6 attempt hung for 645 s: one CPU core at 100%, GPU idle. It
was stopped by its PID and recorded as a failed attempt (`protocol_error`; the run's note explains). The cause was on
our side. The worker had redirected only Python's `sys.stdout`, so output from the engine's C++ code could still
reach the protocol pipe. The worker base now points the process's own fd 1 at the log, and the same page then ran in
20 s. The failure stays visible on `/lab`.

## Document 2: older print (2026-11-04, RTX 5090)

**Page:** `0018-010-003-002` page 3, from مجلة التربية الحديثة (1937), one column of old Naskh type. The page has:
- ى for final ي (فى، التى، الذى، شىء، القارىء);
- «الى» without hamza;
- the old لل ligature (اللذة);
- kashida stretches (طفولتـه، المدرســة، يعيــد);
- a space printed before «،» and «.», and inside « »;
- «ألاّ» with a shadda;
- a running head and an Arabic-Indic page number «١٩٦».

The PDF carries a page-sized image with a third-party text layer over it; that layer is marked `suspect` and not
used. **Ours** here = Azure Read **and** Azure + Gemini Argon (experiment 41's run, our masters).

| reader | time on the page | peak GPU memory | cost of the page |
|---|---|---|---|
| Ours: Azure Read / Azure + Argon | existing | hosted | already paid |
| PaddleOCR-VL-1.6, full pipeline | 16.2 s | 11.4 GB | $0.0042 |
| PaddleOCR-VL-1.6, recogniser alone | 15.2 s | 11.2 GB | $0.0040 |
| PP-DocLayoutV3, layout stage alone | 1.0 s | 1.0 GB | $0.0003 |
| Nuqta, as written (card settings) | 82.7 s (486 tokens) | 10.3 GB | $0.021 |
| Nuqta, Markdown mode | 79.6 s | 10.3 GB | $0.021 |
| Nuqta, as written, **speed fix** (same text) | **20.8 s** | 10.3 GB | $0.0054 |
| Nuqta, as written, fast kernels (same text) | 78.6 s | 10.2 GB | $0.020 |

**Disagreement with our Argon text** (characters as printed / folded): Nuqta 1.5% / 0.3%; Azure alone 0.5% / 0.1%;
Paddle 1.5 3.6% / 1.4%; Paddle 1.6 4.3% / 2.1%; Paddle 1.6 recogniser alone 7.4% / 4.6%.

**By eye on the scan** (observations, not scores):
- **Nuqta (as written)** keeps the old spelling as printed: ى in فى / التى / شىء / القارىء, «الى» without hamza,
  and «ألاّ» with its shadda. It also keeps the head «١٩٦ مجلة التربية الحديثة», and splits «يشعر انه» as printed.
  Its slips:
  - «ببذل» → «يبذل» (one dot pair);
  - «لديها» → «لديهما»;
  - the لل ligature «اللذة» → «المذة»;
  - it drops the printed space before «،» / «.» and inside « » (about 20 places), and closes «أ كان» → «أكان».
  - Markdown mode is the same but modernises «شىء» → «شيء».
- **Ours.**
  - Azure reads «أصلها» as «أصلبا» and the quotation marks as «((تلب))» / «(«كلب))».
  - Argon fixes all three, but keeps Azure's «يشعرانه», where the page prints «يشعر انه».
- **PaddleOCR-VL-1.6** modernises the old spelling: every فى / التى / الذى / شىء / يدرى becomes ي, and «ألاّ» loses
  its shadda.
  - It reads the page number «١٩٦» as «194» (wrong digit, and Latin digits).
  - It reads the running head as «محله الترية»; elsewhere it reads «لنرى» → «لذري», «لأنه / بأنه» → «لأنها / بأنها»,
    «ويجمعها» → «ويعمعها», «وانما» → «والما», «فالوالد» → «خالوالد», «ودعابة» → «ودعاية», «جداً» → «جدأ»,
    «ويوتر» → «ويتر», «اللذة» → «المذة», and «التعليم» → «التعاميم».
  - It reads the Arabic comma «،» as the digit «٤» twice.
  - Layout: running head, page number and five paragraphs, each a region in reading order. That is one more region
    than Argon's six: Argon groups the head with the page number.
- **The recogniser alone** is worse still: «التربية» → «الترىعة», «يدرى» → «يدرس», «يميز» → «يعزز», «في الأمر» →
  «في مساهل», «اللذة» → «اللَّمَّات» (invented vowel marks).
- **PaddleOCR-VL-1.5** (exp 36) has the same family of errors (لذري, غالوالد, «اللذة» → «الآية»).

## Document 3: two columns + footnotes (2026-11-04, RTX 5090, GPU destroyed afterwards)

**Page:** `0877-007-027-003` page 4, from الأمن العام (1964). It was chosen because it has two body columns over a
block of eight footnotes with real text (court rulings, quotations), and both Azure and Argon outputs are on disk.

**What ran:**
- Paddle 1.6, all three variants;
- Nuqta "as written" and Markdown with the speed fix, plus one card-default "as written" reference (identical text);
- a **combination**: Nuqta reading each of Paddle 1.6's 16 regions as a crop (12 px margin), in Paddle's order
  (`combo.py`);
- a **derived ordering**: the same combination with a plain right-to-left column rule (`rtl_order.py`, code only,
  no inference).

| reader | time on the page | peak GPU memory | cost of the page |
|---|---|---|---|
| Nuqta as written, speed fix | 41.9 s (1,012 tokens) | 10.3 GB | $0.011 |
| Nuqta Markdown, speed fix | 51.8 s (1,271 tokens) | 10.3 GB | $0.013 |
| Nuqta as written, card default (reference) | 104.4 s | 10.3 GB | $0.027 |
| Paddle 1.6 full pipeline | 27.2 s | 8.9 GB | $0.007 |
| Paddle 1.6 recogniser alone | 26.0 s | 11.2 GB | $0.007 |
| PP-DocLayoutV3 alone | 1.0 s | 0.9 GB | $0.0003 |
| Combination (16 crops) | 69.8 s | 9.8 GB | $0.018 |

**Disagreement with our Argon text** (characters as printed / folded): Azure 0.1 / 0.1; Nuqta Markdown 3.9 / 0.5;
combination + RTL rule 11.3 / 8.7; Nuqta as written 25.3 / 23.4 (a missing column); combination in Paddle's order
41.7 / 39.2; Paddle 1.5 40.4; Paddle 1.6 47.4 (order and losses).

**Reading order and footnotes, by eye on the scan** (the page: a right column, a left column, then the footnotes
across the page, then the page number «- ٢٢ -»):
- **Ours (Argon):** right column first, then the left column, then eight separate blocks typed `footnote`, then the
  page number. **Right.** Its boxes join the end of the right column and the start of the left into one
  "continued" paragraph.
- **Nuqta, as written** (card default and speed fix, identical): right column first, then **straight to the
  footnotes. The whole left column (four paragraphs, about 100 words) is missing.** No boxes.
- **Nuqta, Markdown mode:** right column, left column, then the footnotes. **The right order and nothing missing.**
  The footnotes are plain lines (no footnote marking), and there are no boxes.
- **PaddleOCR-VL-1.6 (and 1.5):**
  - **left column first**, then the right column: backwards for Arabic;
  - **the top region of the right column comes back empty**, so its lines are lost;
  - every footnote region is labelled plain `text`, never `footnote`, though they come after the body;
  - one footnote line is not inside any region;
  - the page number is found, but read as «YY».
- **PP-DocLayoutV3 alone** finds only 12 regions, and two of them cover the footnotes.
- **Combination** (Paddle's regions, Nuqta's text per crop):
  - **all the text is there**: the empty Paddle region is read («ووضعت قواعدها … على مقتضاها» (١)), and the left
    column is kept;
  - it **inherits Paddle's wrong column order** and footnotes labelled as text;
  - it loses the first line of footnote 8 (outside Paddle's regions), and invents «مجموعة المحاكم الفصلى» in one
    footnote.
- **Combination + right-to-left column rule:** right column, left column, footnotes, page number. **The right order,
  with all the text Paddle's regions cover.** The footnotes are still untyped.

**Word errors, by eye.** The page prints the old spelling: فى، التى، الذى، يجرى with ى.
- Nuqta (both modes, and its crops) **modernises it to ي** throughout this page, unlike on document 2.
- Nuqta's full-page readings swap the date in footnote 1 («١٣ مارس» → «٣١ مارس»); its crop reading has it right.
- Markdown slips: «سلطة» → «ساطة», «الخاضعة» → «الخاصة», «إطلاقات» → «إطارات», «حجيتها» → «حجيها»,
  «محرروها» → «محرووها».
- Paddle 1.6:
  - writes Persian digits and wrong years in the footnotes («۱۳مارس ۱۹۹۹»);
  - turns «مجموعة أحكام النقض» into «مجموعاً آهنگات المقاضیس»;
  - reads «للمحكمة» as «للمبحكة» / «للمسحكية»;
  - reads ٢٢ as YY.

**Was Paddle's LAYOUT useful? (for the owner's decision).** Partly. Its region boxes are good:
- each column paragraph is a clean region;
- the footnote zone is separated from the body and placed after it.

But the layout's own reading order is wrong for Arabic columns, it never labels footnotes, and it misses a footnote
line. The **combination** shows the useful part: Nuqta's text inside Paddle's boxes recovers everything Nuqta
alone dropped (the left column) and everything Paddle alone lost (the empty region). With a **one-rule
right-to-left column fix** in code, the order becomes right. Ours (Azure + Argon) is still the only reader here with
correct footnote typing. **Nuqta's Markdown mode alone** got the order and completeness right on this page, without
boxes.

## Text measured apart from reading order (owner, 2026-11-04)

The owner tests text and regions separately. Regions are a later, separate track and are not built yet.

**Disagreement and scores now lead with an order-free measure.** Two texts are taken as bags of words, and the
measure is 1 − F1 of the word multisets (experiment 40/41's measure), with punctuation ignored.
- It is shown as printed, and again folded for search.
- After a correction, Scores also shows "≈ N words" (unmatched words on both sides, halved).
- **Missing words still count:** a word one text has and the other lacks is a difference in any order. Nuqta "as
  written" on doc 3 stays 12.3% from Argon because of its missing column.

The order-sensitive figures appear apart, in grey, as the **reading order effect**: characters that differ in each
reader's own order, and line pairs in the correction's order. On doc 3 the combination and the combination with the
column rule are 10.4% from Argon in any order, but 41.7% and 11.3% in their own orders.

On doc 3, Compare's right-hand reading defaults to Nuqta Markdown (speed fix), the complete one; "as written" stays
selectable with a visible note that it drops the left column. The notes live in `out/data/reader_notes.json`.

**Doc 1–2 against the owner's corrections** (words that differ in any order, punctuation ignored):
- doc 1: Azure ≈ 2 words, Nuqta 0, Paddle 1.6 ≈ 12;
- doc 2: Azure ≈ 6, Azure + Argon ≈ 4, Nuqta ≈ 3, Nuqta Markdown ≈ 4, Paddle 1.6 ≈ 36.

## Speed on the two cards (doc 1, the same page)

| engine / setting | RTX 4060 Ti 16 GB ($0.269/h) | RTX 5090 32 GB ($0.935/h) | text |
|---|---|---|---|
| Nuqta as written, card settings | 79.0 s, 9.8 GB | 76.5 s, 10.3 GB | identical on both cards |
| Nuqta as written + fast kernels (`nuqta-ocr[fast]`: flash-linear-attention 0.6.0, causal-conv1d 1.7.0) | — | 104.0 s (Triton's first compile; doc 2: 78.6 s) | identical |
| **Nuqta as written + speed fix** | — | **19.9 s**, 10.3 GB (doc 2: 20.8 s) | **identical** |
| PaddleOCR-VL-1.6 full pipeline | 20.0 s, 11.4 GB | 16.0 s, 11.8 GB | one word differs (القرويتي on the 4060 Ti, القريوتي on the 5090) |

**Why the bigger card did not help, and the fix.** A profile on the 5090 found the time in one place. Of Nuqta's
~60 s before the first word, **59.6 s went into a single `torch.conv3d`**: the vision tower's patch embedding, in
PyTorch 2.9 with bf16. Turning cuDNN off did not help (60 s), and neither did the fast linear-attention kernels.
Decoding itself runs at 25 ms a token. The patch embedding is a convolution whose kernel equals its stride, applied
one patch at a time, so it is exactly a matrix product. Computing it as one (`F.linear`, the same weights;
`conv3d_as_linear` in `workers/nuqta_worker.py`, setting `patch_embed_as_linear`) brings a page to **~20 s, 4×
faster, with text identical to the card-default run on both documents.** The card-default run stays the reference
on /lab. The speed fix is its own labelled variant, so a reader never mistakes it for the official settings. Paddle's
native backend is ~16–20 s a page on either card; its official vLLM server (not used here) is the documented way to
make it faster. The new **Speed by card** table on /lab shows every run's time, memory, cost and a text fingerprint.

## The /lab page (Desk, `desk/lab.py`, `web/pages/lab.tsx`)

Screenshots, all looked at: `out/shots/`.
- `01_compare`–`04_compare_full`: the real lab, read only.
- `05_correct_start`, `06_scores_before_correction`: the real lab.
- `07`–`11`: a browser check on a **test copy** with a test actor. That check started a correction, selected an
  Arabic line (logical order kept, its box lit on the scan), edited it, saved revision 1, saw the scores, reloaded,
  and found the edit still there. The result is in `out/shots/check_test.json`; it was **not** written into the real
  lab (`annotations` = 0 rows).

- **Compare**:
  - the scan, with each engine's regions as overlays you can switch on and off, numbered in its reading order and
    labelled with their kind;
  - two readings side by side, with the words where they disagree marked (hover a word for the other reading);
  - a table of how much every pair of readers disagrees (as printed, and folded for search);
  - a card per engine (time, GPU memory, cost, what it gives, flags such as *cut off*, *loops*, *benchmark caveat*);
  - a banner for every failed attempt.
- **Correct** (brief §11):
  - the owner picks which reading's text to start from, and whose regions;
  - each line is edited in a right-to-left box, with the other engines' reading of that line under it where it
    differs (one click adopts it);
  - lines can be split, added, deleted, reordered (↑ ↓) and marked unreadable with a reason;
  - regions can be retyped, reordered, marked unreadable, deleted, or drawn with a drag on the scan.
  - **Save** writes a new revision (who, when, which candidate it started from, an optional note, "page checked").
    It goes in the lab's SQLite (`annotations`, append-only), never touches predictions, and re-scores.
- **Scores**, against the latest revision:
  - recognition: CER and WER as printed, plus every named normalisation policy in the details;
  - lines missing;
  - regions found at IoU ≥ 0.5 and how many have the right kind;
  - reading order (pairs of lines in your order);
  - per-engine details: the word diff against your text, letter changes, flags.

  The engine the correction started from is marked *flattered*. A failed page counts as 100% wrong in totals.

Dev servers, as run: API `127.0.0.1:8155` (`python -m desk.cli serve --port 8155`) and web `127.0.0.1:8154`
(`NEXT_DIST_DIR=.next-lab DESK_API_ORIGIN=http://127.0.0.1:8155 npx next dev -p 8154`). The live :8004/:8005 were
not touched; deploying is the lead's job (`desk/lab.py` is registered at the end of `desk/api.py`; one menu line in
`Layout.tsx`, Quality → OCR lab).

## Method and design (brief §4–§10, as built)

- **`labocr/schemas.py`** (Pydantic, `labocr/1`). It covers sources, renders, manifest entries, the engine contract
  messages, blocks (type, verbatim `raw_label`, box or none, `raw_text`, order, cells, LaTeX), predictions, timings
  with null reasons, and truth pages.
  - Pages are one-based; boxes are `[x0,y0,x1,y1)` px, top-left, on the named render.
  - Reading-order graphs are validated: parents exist, no cycles, unique orders.
- **`labocr/ingest.py`**:
  - immutable source copy (SHA-256, read-only);
  - pypdfium2 **5.12.1** renders with their own hash, DPI, and the PDF→pixel transform;
  - native-text inspection (`unverified` / `suspect` / `absent`, with warnings);
  - JSONL manifest with a hash, a leakage check, and path-safety guards.
- **Adapters** (brief §6):
  - `adapters/transport.py`: `EngineAdapter` over a JSONL subprocess (`labocr-jsonl/1`). Request ids, the protocol
    version checked on each reply, a timeout per op, and termination by PID. The argv is a list, never a shell string.
    A remote worker is just an `ssh … python worker.py` argv, with the image inside the request.
  - `adapters/worker_base.py` (standard library only) runs on the GPU host. Logs go to stderr, fd 1 is redirected,
    and errors come back structured (oom / other).
  - `adapters/normalise.py`: raw → blocks, run core-side and re-runnable (`labocr renormalise RUN`). It holds an
    explicit label map; unknown labels stay visible as `unknown` + `raw_label`. Boxes are never invented: Nuqta has
    none, and the recogniser-alone's whole-page box is not counted as a region.
- **Workers** (`workers/`):
  - `paddle_vl_worker.py`: variants `pipeline` / `bare_ocr` / `layout_stage`, so each stage is timed and labelled
    on its own.
  - `nuqta_worker.py`: the card's code, prompts and `prepare`; it records truncation (no EOS at the cap), output
    tokens, input pixels and the image grid.
  - `fixture_worker.py`: CPU, labelled `is_fixture`. A fixture can never serve a real run, and the reverse is also
    refused.
- **`labocr/runs.py`**: SQLite (`runs`, `pages`, `attempts`).
  - The run identity is a hash of the manifest, renders, engine, variant, settings, revision and worker argv.
  - Page states are pending / running / succeeded / failed. Stale leases are reconciled on restart.
  - The raw reply is written atomically before it is validated; a page is marked done only after the files are on
    disk; resume skips only valid finished pages.
  - Retries are bounded and use the same configuration; a worker that cannot load fails every page with a recorded
    `load_error`.
  - Framework versions are checked on resume. Imported runs (existing outputs) are labelled as imported.
- **`labocr/evaluation.py`**:
  - Primary policy `raw`: only whitespace is collapsed. Hamza, ى/ي, ة/ه, digits, diacritics and bidi controls all
    count.
  - Named policies `faithful` (exp 34), `markup_stripped`, `no_punct`, `folded` (exp 34's search fold).
  - CER and WER with substitution / deletion / insertion counts, unclamped; an empty reference gives null; failed
    pages stay in the denominator. Also the order-free word measure (exp 40/41).
  - Completeness: truth lines located with rapidfuzz, missing lines, a loop flag, truncation.
  - Layout: one-to-one IoU matching at 0.5 and 0.75, class agreement on body / furniture / footnote, and a
    line-coverage view.
  - Reading order: pairwise accuracy by text position for every engine, and by block order for engines with boxes,
    with pair coverage.
- **`labocr/annotations.py`**: append-only revisions (pydantic + sqlite only, so the Desk process can import it).
  `to_truth()` turns a revision into the scorer's truth page.
- **`labocr/report.py`**:
  - `compare` builds the page bundle `/lab` reads (engines, texts, boxes, candidates, other engines' readings per
    line, disagreements, failures, cost).
  - `evaluate` scores against the latest revision, cached on revision + prediction files. A new correction
    re-scores without inference.
- **CLI**: `python -m labocr doctor | ingest | render | run | status | renormalise | evaluate | compare` (argparse;
  Typer is not installed in the repo venv).
- **Tests**: `experiments/75_ocr_lab/tests/test_lab.py`, 27 tests, all synthetic, run in 3 s. They cover:
  - schemas, and the Unicode round trip through the pipe (mixed Arabic/Latin, marks, Arabic-Indic digits, bidi
    marks);
  - protocol failure and timeout;
  - resume after a worker crash (finished pages kept, a retry attempt recorded) and stale-lease reconciliation;
  - fixture refusal, and a configuration change giving a new run;
  - leakage and path traversal;
  - label mapping and table cells (spatial order kept, not reversed for Arabic);
  - raw vs folded policies, a missing footnote staying visible, reversed order detected, CER > 100%, an empty
    reference giving null, a failed page staying in the denominator;
  - the loop flag;
  - append-only revisions, bad-input rejection, and unreadable lines left out.

## Setup actually run

```
# core (repo venv): one new light dependency
.venv/bin/pip install rapidfuzz==3.14.6
cd experiments/75_ocr_lab
../../.venv/bin/python -m pytest -q tests                        # 27 passed
../../.venv/bin/python doc1.py                                   # ingest + render page 21, import Azure and exp 36
python3 gpu_session.py offers                                    # datacenter, verified, rel >= 99.5 %, >= 300 Mbps
python3 gpu_session.py start 57913313                            # RTX 4060 Ti 16 GB, $0.269/h; link test 7.9 / 7.9 MB/s;
                                                                 # uploads workers, starts workers/setup_gpu.sh
W=$(python3 gpu_session.py worker nuqta)
../../.venv/bin/python -m labocr run --dataset doc1 --engine nuqta --variant as_written \
    --revision 6a8cdd625f7360203bfce10ef48a41c4a5c1ad3c --settings '{"max_new_tokens": 8192}' --worker-json "$W" --embed-image
#   … and --variant markdown;
W=$(python3 gpu_session.py worker paddle_vl)
#   --engine paddle_vl --variant pipeline | bare_ocr (--settings '{"pipeline_version": "v1.6"}') | layout_stage ('{}')
../../.venv/bin/python -m labocr compare --dataset doc1 --page 2399-003-008-002_p021   # the /lab bundle
```

Set-up on the host took about 9 minutes, most of it the 1.9 GB paddlepaddle-gpu wheel from the Paddle mirror. The
weights came down in 114 s (Nuqta), 19 s and 4 s, each sha256 checked against Hugging Face. The engines, revisions
and licences are in [DEPENDENCIES_AND_LICENSES.md](DEPENDENCIES_AND_LICENSES.md).

## GPU

**Choice.** Offers passing every rule on 2026-11-04 were few:
- RTX 4060 Ti 16 GB at $0.27 and $0.40;
- two mining cards (CMP 170HX), avoided;
- H100/H200 at $4.3+.

The RTX 4090 offer had reliability 0.9949, below the rule. Nuqta's card says it "serves comfortably on a 16 GB GPU
in bf16" and Paddle's VL model is 0.9B, so the cheapest card that fits was taken. Measured peak: Nuqta 9.8 GB,
Paddle 11.4 GB of 16. **The owner decided (2026-11-04) that later sessions use a bigger, faster card.**
`gpu_session.py` now defaults to `LAB_GPU_MIN_GB=32`: prefer an RTX 5090, or a 48 GB+ card (L40S / RTX 6000 Ada /
A6000 / A100) when it passes the same rules at a sensible price. Chandra (~18 GB in bf16) would not fit on 16 GB,
and Nuqta's 79 s a page on this card is slow (about 5.7 tokens/s on its linear-attention layers with the
transformers fallback kernels).

**Session rules** (`gpu_session.py`):
- One instance lives for a working session, not a single document. It is destroyed (`vastai destroy instance ID -y`,
  then checked that none is left):
  - when the owner or lead ends it (`python3 gpu_session.py stop`);
  - after 90 minutes without inference;
  - before the $10 cap would be passed.
- A keeper process (exact PID in `out/gpu_session.json`) logs every minute to `out/gpu_spend.jsonl` and applies the
  idle and cap rules. `budget MINUTES` warns before a run that would pass the cap. Every run touches the activity
  timestamp.

**Spend.** Instance 59139473 started 17:40 UTC. Document 1 (setup, 5 engine runs, the hang and its retry) was
finished at about 35 minutes, **$0.157**. Vast credit before: $15.60.

## Honest limits

- One page. Nothing here is a ranking.
- Every remark about errors above is by eye; the scores wait for the owner's correction.
- Any correction starts from one engine's text and regions, and that engine is then flattered (the Scores view says
  so). Starting from Nuqta's text flatters Nuqta; Azure's flatters ours.
- Layout is scored on body / furniture / footnote classes and IoU. Paddle splits paragraphs differently from any
  one truth.
- Nuqta gives no boxes, so its layout is "not available", never zero.
- Timings come from a 16 GB consumer card with the native (unaccelerated) backends. Paddle's vLLM server and
  Nuqta's vLLM serving would be faster.
- Experiment 36's v1.5 output was made from a JPEG of the same page at the same size (boxes in the same frame), not
  from this exact PNG.

## GPU, session 2

**Session 2** (document 2 + speed runs): RTX 5090 32 GB, Vast offer 45508888 (Alberta, datacenter, reliability
0.9975, $0.935/h, link 5.6 / 5.5 MB/s), instance 59148382 from 19:01 UTC. **$0.53 at 34 minutes**, with all document-2
runs, the doc-1 re-runs and the speed diagnosis done. Left open as instructed; the keeper destroys it after 90 idle
minutes. Session 1 ended at **$0.287** (the lead stopped it). Filters fixed for this card:
- Vast reports a 5090 as 31.8 GB, so the floor is `LAB_GPU_MIN_GB=31`;
- the `cuda_vers` filter dropped every 5090, so it is now `cuda_max_good>=12.8`;
- Blackwell needs Paddle's cu129 wheel, so `setup_gpu.sh` picks the wheel by compute capability;
- `/opt/nuqta_fast` (fast kernels) was built by hand on this host: pip `flash-linear-attention==0.6.0`, plus the
  prebuilt causal-conv1d 1.7.0 wheel `cu12torch2.9cxx11abiTRUE-cp311` (the runtime image has no nvcc).

## GPU, session 3 (document 3)

- **The first rental failed the link test.** RTX 5090 in Czechia (instance 59156010): the 20 MB upload never
  finished. My own 900 s scp timeout hid that for 10 minutes. The instance was destroyed, **$0.167**.
  - The link test now aborts after 45 s (the 0.5 MB/s floor).
  - Machines that fail it are remembered (`out/gpu_bad_machines.json`) and skipped.
  - `start` also takes a card name (`start RTX_5090`), because Vast changes offer ids between searches.
- **The second rental worked.** RTX 5090 in Alberta (instance 59157010, $0.935/h, link 1.7 / 5.6 MB/s): every run,
  then **destroyed** as the owner asked, **$0.263** (16.9 min).
- **GPU total so far: $1.366** ($0.287 + $0.649 + $0.167 + $0.263).

## Pending

- The owner's feedback on document 3, and the layout decision (see "Was Paddle's LAYOUT useful?").
- Document 4 (tables) only after that, with no Paddle text variants.
- The lead's deploy of `/lab` to :8004/:8005, with the document switcher, the speed table and the "not corrected"
  regions cell.
- Document 3 (two columns + footnotes) only after that.

## Document 2: what was run

Older print: **`0018-010-003-002` page 3** (مجلة التربية الحديثة, 1937, one column). Azure **and** Argon outputs
exist on disk (experiment 41), so "ours" will be complete. The alternative is `0197-002-001-003` p3 (1967, also
with Argon).

```
cd experiments/75_ocr_lab
../../.venv/bin/python doc1.py --dataset doc2 --stem 0018-010-003-002 --page 3 --category older_print
python3 gpu_session.py status            # the session may still be open (90-min idle timer); else:
python3 gpu_session.py offers            # now >= 32 GB: RTX 5090 or a 48 GB card
python3 gpu_session.py budget 30 && python3 gpu_session.py start <offer>
W=$(python3 gpu_session.py worker paddle_vl)
for v in pipeline bare_ocr; do ../../.venv/bin/python -m labocr run --dataset doc2 --engine paddle_vl --variant $v \
  --revision c5630abae1d940eafe0697512a0325494b02ab42 --settings '{"pipeline_version": "v1.6"}' --worker-json "$W" --embed-image; done
../../.venv/bin/python -m labocr run --dataset doc2 --engine paddle_vl --variant layout_stage \
  --revision 241f8bdfc77a7c7bee915a5057aaee58c235a8d3 --settings '{}' --worker-json "$W" --embed-image
W=$(python3 gpu_session.py worker nuqta)
for v in as_written markdown; do ../../.venv/bin/python -m labocr run --dataset doc2 --engine nuqta --variant $v \
  --revision 6a8cdd625f7360203bfce10ef48a41c4a5c1ad3c --settings '{"max_new_tokens": 8192}' --worker-json "$W" --embed-image; done
../../.venv/bin/python -m labocr compare --dataset doc2 --page 0018-010-003-002_p003
```

On a new host, `start` builds everything again (about 10 minutes). The /lab document picker shows doc2 once its
bundle exists.

## Files

- `labocr/`: the package.
- `workers/`: the engine workers and `setup_gpu.sh`.
- `doc1.py`: set-up for one document.
- `gpu_session.py`: the GPU session helper.
- `configs/doc1_e0.yaml`.
- `tests/`.
- `shots75.py`: screenshots and the browser check.
- `labtest_app.py`: dev only; the Desk API on a test copy with a test actor.
- `DEPENDENCIES_AND_LICENSES.md`, `STATUS.md`, `progress.md`.
- Desk: `../49_correction_desk/desk/lab.py`, `web/pages/lab.tsx`, `web/components/lab/*`.
- Outputs (gitignored) in `out/`:
  - `data/`: sources, renders, `lab.sqlite`, `runs/<run>/raw|pred`, `bundles/`, `scores/`;
  - `shots/`;
  - `cards/`: model cards at the pinned revisions;
  - `gpu_spend.jsonl`, `gpu_session*.json`, `dev/` (server logs).
