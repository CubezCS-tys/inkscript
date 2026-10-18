# Handoff: where we are (as of 2026-10-15)

**Continuation, 2026-10-17:** Codex is working with the owner while Claude is
unavailable. Read [codex-handoff.md](codex-handoff.md) for the review, reopened
tracing discussion, current scope and subsequent work before resuming.

I am the Claude session that worked with the owner on the laptop up to 2026-10-13 (section 0 brought up to
2026-10-15). I'm writing this for the next
session, on the owner's Ubuntu ssh server, which will have none of my memory. My private notes (the "memory" files) don't
travel with git, so everything in them that matters is written out here. Read this first, then `CLAUDE.md` and the
docs it lists. Where this file and an older doc disagree, this file is newer.

## 0. Since 2026-10-13 (read this first)

Three experiments and one decision landed on 2026-10-14/15. The headline: **Gemini reading structure on top of
Azure's words works**, and the owner now has two roads to choose between (end of this section).

- **Exp 39, layout model round 2** (commit `2fe141a`; section 4 has the steps that were run).
  - Overall flat: **87.7% → 87.8%** of the 44 test pages' lines named like the Pro referee.
  - Gained: equations **0% → 78%**, lists 54% → 68%.
  - Broke: footnotes **95% → 67%**, verse **96% → 61%**. The new training pages were 63% table lines, which drowned
    the rest. With dots.mocr for tables and equations: 90.5% (round 1 92.1%).
  - **Round 1 stays the best model.** GPU $1.94 (2.3 h, RTX 5090). Report, same URL:
    https://claude.ai/artifact/MYoVS8BUMfS3xkEJ2BAxeA.
  - Decision **parked**: rebalance the training mix and train round 3, or move on to the order specialist.
- **Exp 40, Gemini 4 (gemini-4-argon) alone as the document reader** (`545183b`, `experiments/40_gemini4_vlm`).
  - Five approaches, **$13.34**. Report: https://claude.ai/artifact/54SBuWQZQQosVQqyqEpE31.
  - Structure far ahead of everything else: **96.8%** of block types right, Azure 74%, our layout model 84%.
  - Its text is about Azure's level but **not faithful**: it fixes misprints and adds hamzas. So it reads the
    structure, not the words.
- **D30** (`fbeec99`, `docs/decisions.md`): the digital text is the print as printed.
  1. Printed text kept; suspected misprints carry a flagged correction (`span.sic`), never replace it.
  2. Azure's misreadings (text that differs from the ink) are fixed.
  3. Old and Quranic spelling untouched.
  - The owner agreed to all three.
- **Exp 41, Azure's words + Gemini's structure** (`1fb3ced`, `experiments/41_azure_structure`).
  - Gemini sees the page and Azure's lines and answers with **line ids only** (type and order per line), so it
    can't rewrite words. 55 articles, 399 pages, Argon vs Flash, **$10.72**. Report:
    https://claude.ai/artifact/AiqhFTZTvMF2or8W9Bi4mp (`out/report.html`).
  - The format holds: no chunk failed. A quarter of the 17,137 lines were dropped as noise, some wrongly (below).
  - Words wrong on 34 truth pages: **Argon 1.55%**, Flash 1.77%, Azure alone 1.80%. The models agree on 94.7% of
    types and 99.5% of order.
  - Choice: **Argon for the edition, Flash for training labels.**
  - Prompt gaps to fix in any next run: list vs body, endnotes, and "a line with words is never noise".
  - Cost per million documents: **Argon about $120k batch, Flash about $46k batch**. Gemini prices double on
    Dec 1 / Jan 1, so these go up.
  - **In progress:** a reader for the 55 articles, `experiments/41_azure_structure/reader.py` (uncommitted) →
    `out/reader/`.
- **Mistral OCR 4.1 annotations** (`1112ceb`, `experiments/32_open_stack/research/05_mistral_annotations.md`): not a
  line labeller; a candidate for the pictures specialist.
- **Chandra 2: skipped.** 68% on Arabic on its own benchmark, and its licence forbids competing with Datalab.

**Open decisions for the owner:**
1. Hand-check 5 articles from exp 41 (`experiments/41_azure_structure/out/handcheck/`).
2. Then: pay Gemini to process the archive, or use Flash labels to train our own specialists.
3. Round 3 of the layout model or move to order (above, parked).

**Money now:** the Gemini credit **ran out on 2026-10-15**. Don't spend any without the owner. **0 Vast instances.**

## 1. The owner, and how to work with them

**How they think**
- They think in **physical pictures**: liquid flowing round letters, strokes felt on your back, "the map", "rivers of
  paper". Those pictures have been the right design more than once. Describe choices by what the result looks like,
  not by data structures.
- They **understand visually**. Deliver every result as a page with real examples (scan beside output, before and
  after, the ink itself), with the headline numbers on it. Publish it as an Artifact and give the link. Keep the chat
  summary short. Tables support the page; they never replace it.
- They want to **stop and think at turning points**. Don't fill the pause with experiments. Since 2026-10-12 they've
  been thinking abstractly about how to "attack" a document. In their words: "I dont want to finalise on a plan until
  i can feel it in my mind". Answer their questions and run only the tests they ask for. Don't turn their thinking into
  a plan or roadmap until they say it feels right.

**How work gets done (2026-10-13)**
- **Agents do the hands-on work; the owner and I orchestrate.** Their words: "from now on let agents do the work please
  you and me are high level orchestartors". They run several projects in parallel and want this conversation kept
  for decisions.
  - Hand execution (scripts, runs, GPU rentals, scoring, reports) to background agents, each with a self-contained
    brief: caps, rules, files, and what to report back.
  - I check results, publish reports and talk with the owner.
- **Specialists are attacked one at a time** (the owner's choice on 2026-10-13: "for now lets leave it sequential").
  Layout is first. Don't start another specialist until they ask.
- **Initiative is welcome inside an approved cap.** When an agent turned "a few minutes of GPU" into a bigger
  comparison, they said "i like that type of proactivity". Say what changed and why when reporting. The caps
  themselves always need their approval.
- **Agents save every item to disk as they go**, and skip items already saved. On 2026-10-12 a session-limit stop
  lost nine reviewers' finished work, and the owner objected: "the review cant start over otherwise im just losing
  credits for no reason". Their Claude plan is a real, limited cost.
  - Keep units small.
  - Before resuming, check what was saved.
  - Warn the owner before heavy multi-agent runs.

**Money**
- **Report spend at every step.** The Gemini credit is shared with their other projects. On 2026-10-13: "if we need
  more gemini I will add more I just wanted to be ontop of things". Keep a cap for each experiment, and ask before
  going past it.
  - Gemini: about $20 per experiment is acceptable ("no 20 is good"). Every Gemini agent gets a hard cap, a cost
    estimate before each batch and a running spend log.
  - Prefer a cheaper model when calibration shows it's about as accurate.
- **GPU rental is cheap.** "GPU renting is cheap man": a two-hour training run cost $1.70. The real cost is Gemini
  labels and the owner's Claude usage.

**Other standing rules**
- **Edition font.** They looked at the editions on 2026-10-12, said "I hate that font" (Markazi Text in the PDFs,
  Noto Naskh on the web and in the e-book), and picked **Scheherazade New** (SIL, OFL) from a 16-font sheet
  (`experiments/35_edition/out/fontsheet/index.html`).
  - The switch is still to do: `src/inkscript/edition` (`fonts.py`, `html.py`), regular and bold, in every edition.
  - Unanswered: headings in Scheherazade bold, or a contrasting font?
  - Check its Latin coverage, and record the change as a decision.
- **Deletions:** propose them, never do them.
- **Disk:** on the laptop the WSL disk lives on Windows C:, 96 GB free on 2026-10-13. Pause big runs below 50 GB free.
  `~/.cache/pip` (14 GB) and `~/.cache/huggingface` (11 GB) could be cleared there. On the server, just watch `df -h`.

## 2. The big picture

- **A year of chasing perfect OCR.** The owner has worked since September 2025 to get perfect OCR of Arabic journal
  scans for Mandumah. The project began as *ink-as-text* (experiments 1–31): each printed word or letter becomes a
  Type 3 glyph traced from its own ink, which selects and searches in Chrome. That vision **is not dropped**; never
  call it abandoned.
- **On 2026-10-12, after exp 38, they said they don't see "the light at the end of the tunnel".** That started the
  abstract "attack" thinking in section 3.
- **The reframe (2026-10-11/12).**
  - Their words: "Azure is what we have to be dependent on for now because we've already got all the text"; "more
    than a million documents that are sitting in S3" (`s3://mandumah-source-docs/<id>/<id>.{pdf,json}`).
  - The goal is to become "our own sort of document parser": rebuild each document natively, respecting columns,
    images, tables and equations, out to JATS/XML, PDF and editions. The output is for reading online, printing and
    AI training.
  - On 2026-10-12 evening: "from now we should assume that azure is the gold truth as it just simplifes life instead
    of getting into its 1% errors". **Text is settled. All effort goes to structure.** Don't propose text-correction
    work (LLM correction, diffusion fill-in) unless they reopen it.
- **Exp 38 → D29** (`docs/decisions.md`).
  - Our own parser keeps Azure's words and takes layout, order, tables, formulas and pictures from dots.mocr.
  - A blind Gemini Pro judge preferred the new layout page on 18 of 33 hard pages (old 4, tie 11); a Claude reviewer
    preferred it on 28 of 44 (old 3).
  - No Azure word was lost.
  - Model correction of the text stays off.

## 3. The attack on a document: specialists

The owner's picture is a team of specialists, each doing **one job** and handing off. They connect through **the map**
(the page's ink) and **the master copy** (the one rebuilt document). The owner on training them: "remember to not step
on the toes of other specialists… we just need to connect and train all these experts". Each specialist is
deterministic, a model, an agent, or a mix. Measure first, use a model where recognition is needed, and consult an
agent (Gemini) only on hard or disputed cases.

| # | Specialist | Job | Kind | Status (2026-10-13) |
|---|---|---|---|---|
| 1 | Reader | the words | Azure (prebuilt-read: words, lines, paragraphs; no roles, tables or figures) | done: treated as truth |
| 2 | Map | every island of ink, traced | deterministic | built (exp 39) |
| 3 | Layout | what each line/region is | model (+ rivers for edges) | round 1 is the best model; round 2 done 2026-10-14, not better (section 0) |
| 4 | Order | which block is read after which | model + rules | not started (Azure's order today) |
| 5 | Style | bold, size, centring, indents | deterministic + model | not started |
| 6 | Tables | rows, columns, merged cells; Azure's words into cells | model | not started (layout hands off "table") |
| 7 | Equations | maths as LaTeX/MathML | model | not started (layout hands off "equation") |
| 8 | Pictures | cut out figures, link captions | map + model | not started |
| 9 | Whole document | running headers, the book's heading style, footnotes and tables across pages | deterministic + agent | not started |
| 10 | Writer | writes the master copy once | deterministic | exists in exp 38 form |
| 11 | Auditor | checks against the map: unclaimed ink, ink claimed twice, disagreements; sends only those spots to Gemini or a person | deterministic | idea; I suggested running it alongside, the owner chose sequential |

The order they lean on each other (not a plan): layout first, because it hands work to tables, equations and
pictures. Order and style need layout's blocks. Whole document needs all of them. Writer and auditor connect
everything. The auditor would also give a timeline that doesn't depend on Gemini ("ink left unclaimed: X% → Y%").
The offered test "count unclaimed islands on the 44 pilot pages" was **not approved**.

### What exp 39 measured (all in `experiments/39_ink_geometry/`, README has the detail)

- **The map** (`geometry/trace.py`, report `out/report.html`).
  - How: Otsu threshold, rules lifted out, each connected component traced as a polygon with holes
    (`approxPolyDP` 0.6 px).
  - Redrawn from the shapes alone, a page matches **95.0–97.5%** of the ink.
  - It didn't help *read* text (the letter atlas never beat Azure). Its value is as a model-free survey that every
    other specialist pins to.
- **Rivers of paper** (`rivers.py`, `out/rivers.html`; the owner liked it).
  - How: ink smeared sideways; tall thin paper channels are gutters; gaps wider than 1.7× the page's median line gap
    are block breaks; long rules are walls.
  - Finds: columns on every two-column page; equations, tables and references set apart; a table's column gaps and a
    verse's halves.
  - Misses: single-column headings and footnotes, bullets and grey photos.
  - The owner on regions: "both". A whole-page model names the blocks; the rivers and the map give exact edges.
- **The other senses** (`senses.py`, `out/senses.html`): labels each Azure line from ink measurements and text
  patterns, with no model. The measurements: letter size, stroke thickness, line pitch, indents, a short rule above
  the footnotes, footnote numbers matching markers in the body, dash bullets, the verse gap, top-row furniture.
  - On the two pages it was tuned on, every line was right. The owner: "literally perfect on those two pages". I
    warned it was tuned there.
  - Untuned on the 44 pilot pages (Gemini Pro referee, $0.52): **47%** overall, 72% on plain single-column text.
  - It breaks on: columns (verse false alarms), tables (footnote cascade), numbered lists, bottom furniture, varied
    headings. Report: `out/layout_score.html`.
- **dots.mocr** (a VLM with a few billion parameters, exp 36), its block types on the same lines: **80.5%** vs the
  rules' 34.6%.
  - By kind of page: plain 89%, tables 92%, equations 88%, columns 70%, decorative 22%.
  - Weak on lists (19%), verse (0%, no such label) and headings (57%).
  - The owner then: "use model on everything if we can find a good small and cheap one".

### The layout model, round 1 (2026-10-13)

- **Labels.** 2,700 pages from 228 documents (`train_pages.py`; at most 40 per document; none from the 44 pilot
  pages' documents). Gemini 3.8 Flash labelled every Azure line, about $0.0045 a page; it agrees with Pro on 92.7% of
  lines.
  - Eleven labels: furniture, heading, body, list, verse, footnote, references, caption, table, equation, other.
  - "references" was added because Flash and Pro mostly disagreed on reference lists.
- **Model.** DocLayout-YOLO (YOLOv10 fork, DocStructBench weights, about 20M parameters, about a hundredth of
  dots.mocr), fine-tuned to detect each line box with its label at 1280 px (`make_yolo.py`, `gpu/`).
  - Split by document: train 2,508 pages, val 185 (22 documents), test = the 44 pilot pages labelled by Gemini 3.1
    Pro (`out/score_test`).
- **Run.** One RTX 5090 on Vast, 2.0 h, **$1.70**. Training stopped itself at epoch 52 and kept epoch 32 (val mAP50
  ≈ 0.69). The library's final step crashed (see section 6); predictions ran on the laptop CPU from the saved weights
  (`predict_local.py`, 1.5 s a page, 1 GB peak). Weights: `out/gpu/out/run/weights/best.pt`.
- **Score on the 44 test pages** (2,075 lines, `score_yolo.py`): **model 87.7%**, dots.mocr 84.4%, rules 39.5%.
  - By kind of page: plain text 95%, decorative 95%, columns 86%, tables 86%, equations 74%.
  - By label: body 96%, verse 96%, footnote 95%, table 89%, furniture 87%, references 78%, heading 64%, list 54%,
    **equation 0%** (only 77 equation lines in training).
  - On labels dots.mocr can say at all, **dots is still better**: 91.7% vs 88.0%, mostly tables and equations.
  - The model wins overall through verse, reference lists and lists.
  - **The model's label, but dots.mocr's wherever it says table or equation: 92.1%.** That's the "connect the
    specialists" idea on a small scale.
- **Report:** https://claude.ai/artifact/MYoVS8BUMfS3xkEJ2BAxeA (`out/layout_model.html`, `report_yolo.py`).
- **What I told the owner about distillation.** A small student copies a big teacher on one narrow job. Four catches:
  1. It copies the teacher's consistent mistakes; only random slips wash out. The ceiling is Gemini's own
     consistency: Flash and Pro agree on only about 93% of lines.
  2. It can only learn from what it sees. It sees pixels only, no words and no other pages. Lists and headings need
     words (أولاً، (١)، الفصل) and the whole book.
  3. Variety beats volume.
  4. "Perfect" needs a rulebook: is quoted dialogue body or verse?
  - My guess for round 2: 93–95% against Pro, beating dots on every label.
- **Next ideas after round 2** (from the same talk, not approved):
  - **Give the model the words.** A small second step using Azure's text plus the senses' measurements, for lists
    and headings.
  - **Whole-book consistency.** Headings look the same throughout one book.
  - **Stretch the Gemini money.** dots.mocr on a rented GPU pre-labels pages, and Gemini judges only where dots and
    our model disagree.

## 4. Round 2: what was run (done 2026-10-14; results in section 0)

Kept for the record; all steps below were done and committed in `2fe141a`.


Goal: steps 1 and 2 of the plan the owner approved. **Step 1:** equation and table pages. **Step 2:** the pages the
round-1 model is least sure of. **Caps:** Gemini total for exp 39 **$19** (round 1 spent $11.92, so up to about $7
more); GPU **$3** this round.

Done:
- **`more_pages.py`.** 150 new documents (30 each) from journals 1541, 0527, 0700, 1016 and 2483. These carry
  equations, and **none of them has a page in the 44-page test set**, so a jump in the equation score is honest.
  - Only Azure's JSON was fetched first: 5,211 pages, 294 with ≥2 maths lines, 600 with ≥2 table-row lines.
  - Outputs: `out/more/kinds.json` and `out/more/azure/`.
  - Why new documents: the yardstick pool was used up (only 315 unused pages left, one with maths).
- **`round2.py candidates` and `draft`.** 1,752 candidate pages from 221 documents (the maths and table pages, 600
  others, and the pool's leftovers), drafted into `out/round2/pages/`.
- **`predict_local.py round2`.** The round-1 model over every candidate. **Complete: `out/round2/pred.json` has all
  1,752 pages** (checked at the time of writing).

Then (done 2026-10-14):
1. `../../.venv/bin/python round2.py select`: all maths pages, then the least sure, N=1450 → `out/round2/chosen.json`.
   Look at a few chosen pages first.
2. `../../.venv/bin/python round2.py label`: Flash labels → `out/round2/labels/`. `round2.py` sets the cap to $19.
   Don't raise it without the owner.
3. `ROUND2=1 ../../.venv/bin/python make_yolo.py` → `out/train/yolo2/` (round-1 val documents stay val, plus 10% of
   the new documents). Check that the equation count rises well above 77.
4. GPU training into `out/gpu2/`, same hyperparameters as round 1, starting from the DocStructBench weights (not
   round 1's best.pt), so the two rounds compare cleanly.
5. Predict val and test, run `score_yolo.py` (→ `out/score_yolo2.json`), and rebuild `report_yolo.py` as round 1 vs
   round 2 side by side. Say the equation score on the 8 equation test pages explicitly.
6. Update the README and the `experiments/README.md` row, commit, push, and republish the report at the same URL.

The round-2 agent's script changes (committed with round 2):
- Modified: `gpu/gpu_end.sh`, `gpu/gpu_run.sh`, `gpu/gpu_wait.sh`, `gpu/train.sh`, `make_yolo.py`,
  `predict_local.py`, `report_yolo.py`, `score_yolo.py`.
- New, from me: `more_pages.py` and `round2.py`.
- The GPU scripts were adapted for round 2 (`GOUT` env for the output folder, the fuse patch, `save_period`). Some
  `make_yolo.py` and `predict_local.py` edits are mine (ROUND2 / round2 modes).

Round 2 was resumed by one background agent with the steps above, the caps, the GPU rules (section 6) and "report back:
round 1 vs round 2 by page kind and label, the model+dots number, spend, GPU hours, 0 instances, commit hash; be
honest if round 2 is not better".

## 5. Spend so far

- **2026-10-14/15:** exp 39 round 2 GPU **$1.94**; exp 40 Gemini **$13.34**; exp 41 Gemini **$10.72**. The Gemini
  credit ran out on 2026-10-15.

- **Exp 39 Gemini: $11.92** (round-1 labels, the test referee, small scoring runs).
  - Logged in `experiments/39_ink_geometry/out/gemini_spend.jsonl`.
  - Enforced by `experiments/38_parser/common.py:gemini()`, which refuses any call whose worst case would cross
    `common.CAP` and caches answers in `out/gemini_cache.jsonl`.
  - `score_layout.py` points `SPEND`/`CACHE` at exp 39's `out/` and sets CAP 15; `round2.py` raises it to 19.
- **Exp 39 GPU: $1.70** (instance 55640758, 1.99 h at $0.852/h), logged in `out/gpu/gpu_spend.jsonl`.
- **Earlier:** exp 33 spent $2.64 of a $10 GPU cap; Vast credit was about $20 after that, so check the balance.
  Exp 38 spent $3.08 Gemini.

## 6. Vast.ai GPU rental

- **CLI.** On the laptop it lives in its own venv: `~/.local/venvs/vast/bin/vastai`. It isn't on PATH, and the
  scripts call it by that path. On the server: `python3 -m venv ~/.local/venvs/vast &&
  ~/.local/venvs/vast/bin/pip install vastai`.
- **Key.** It lives in `~/.config/vastai/` (mode 600). **The owner types it** (`vastai set api-key …`). Never print,
  cat or read it, and never ask for it in chat.
- **SSH key for the machines:** on the laptop, `~/.ssh/id_ed25519_vast`. On the server, make a new one and add it to
  the Vast account (`vastai create ssh-key`), or copy it if the owner prefers.
- **Scripts.**
  - `experiments/39_ink_geometry/gpu/`:
    - `gpu_offers.sh`: filters offers (CUDA ≥12.8, disk ≥60 GB).
    - `gpu_run.sh`: rents, link test, setup, upload of a packed tar, starts training.
    - `setup.sh` and `train.sh`.
    - `gpu_wait.sh`: waits for `train.done`/`train.failed`, fetches, then destroys.
    - `gpu_end.sh`: destroys and logs cost.
  - Exp 36 (`experiments/36_vlm_bakeoff/gpu/`) has the same pattern for dots.mocr.
  - Some of these scripts hard-code `/home/yassine/inkscript` (section 7).
- **Guard.** `ops/vast_guard.sh` destroys any instance older than 6 h (`MAX_MIN`, raised from 3.5 h by the owner) or
  with its GPU idle 30 min. It checks nvidia-smi over ssh, because Vast's `gpu_util` lags. Log:
  `~/.config/vastai/guard.log`.
  - Start it with `(setsid nohup bash ops/vast_guard.sh >/dev/null 2>&1 </dev/null &)` in its own call, then verify.
  - Restart it after every reboot.
- **Rules (strict):**
  - Datacenter / secure-cloud machines only, because Mandumah pages go on them.
  - RTX 5090 (about $0.85/h), or a 4090 if none passes; reliability ≥99.5%; inet up and down ≥300 Mb/s.
  - Right after renting, test about 20 MB of upload. Destroy if it's under 0.5 MB/s. The laptop's own upload is only
    about 1.1 MB/s, so a server with better upload should help.
  - Estimate cost first, log spend, and keep to the cap for each experiment.
  - Destroy (not stop) with **`vastai destroy instance ID -y`**. Without `-y` it waits for a confirmation and,
    unattended, aborts.
  - Confirm **`vastai show instances` = 0** at the end of every job and in every report.
- **Traps learned:**
  - **`pkill -f PATTERN` kills itself** when the calling shell's command line contains the pattern. This happened
    locally (exit 144) and over ssh (`ssh host "pkill -f 'gpu/train.sh'"` killed the remote shell). Check with `ps`
    in a separate call; use exact patterns.
  - **doclayout_yolo** fuses Conv+BN before predict and final validation, then crashes in its dilated block
    (`'Conv' object has no attribute 'bn'`). Patch first: `import doclayout_yolo.nn.tasks as T;
    T.BaseModel.fuse = lambda self, verbose=True: self`.
  - Pass `save_period=-1`. Round 1 saved every 10 epochs and fetched a 1.2 GB `result.tgz`.
  - Setup on the image needed: `pip install doclayout-yolo huggingface_hub`, a forced reinstall of
    `opencv-python-headless`, `apt-get install libxcb1 libgl1 libglib2.0-0`, `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1`,
    a patched `check_amp`, and batch 8 with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` (batch 16 ran out of
    memory at 1280 px).

## 7. Moving to the server (updated)

`docs/moving-to-a-server.md` still holds for the core pipeline. It doesn't cover experiments 33–39, Vast or the
agents. Notes:
- **`~/Desktop/OCR_gem_json/…`**, referred to in `docs/operations.md` and `moving-to-a-server.md`, **no longer exists
  on this laptop**. Today's data lives under each experiment's `out/` and on S3.
- **Git holds** code, docs, tests and the bundled fixture. It doesn't hold `experiments/*/out/`, `.env`, `.venv/` or
  keys.

**Sizes measured 2026-10-13** (what the layout work reads):

| Folder | Size | Why it's needed |
|---|---|---|
| `experiments/34_yardstick/out` | 589 MB | gold pages + images (`gold/`), `pool.json`, the `extra/` documents (435 MB) |
| `experiments/19_azure_map/out/docs` | part of 1.1 GB | real files behind `experiments/28_scale/out/azure` (those are **symlinks**; copy both, or use `rsync -L`) |
| `experiments/28_scale/out/azure` | 454 MB followed | the pool's other 127 documents |
| `experiments/36_vlm_bakeoff/out` | 291 MB | dots.mocr's outputs (`raw/dots_mocr/`), Kraken |
| `experiments/38_parser/out` | 178 MB | `pages.json` (the 44 pilot pages), parser outputs |
| `experiments/39_ink_geometry/out` | 8.9 GB in all | skip `out/venv` (1.6 GB, rebuild it) and `out/gpu/result.tgz` (1.1 GB); keep `train/` (2.8 GB), `round2/` (1.1 GB), `more/` (1.2 GB), `score_test/`, `gpu/out/run/weights/best.pt`, the reports |
| `experiments/29_catalogue/out`, `35_edition/out` | 789 MB, 522 MB | the masters and old editions exp 38 reads |

**Hard-coded paths** that break if the server's home isn't `/home/yassine/inkscript`:
- `experiments/38_parser/common.py` (`MAIN`), which exp 39 imports for every Gemini call and page reader.
- `experiments/34_yardstick/*.py` (`OUT`, `MAIN`).
- `experiments/39_ink_geometry/gpu/gpu_run.sh`, `gpu_end.sh` and `gpu_wait.sh`.
- The absolute paths inside `experiments/34_yardstick/out/pool.json` (`azure`, `scan`) and inside
  `39_ink_geometry/out/train/plan.json` and `out/round2/candidates.json`.

The simplest fix: put the checkout at the same path on the server (or a symlink `/home/yassine/inkscript → the
clone`). Otherwise rewrite those paths with sed after copying.

**Steps**
```
# on the server
git clone git@github.com:CubezCS-tys/inkscript.git && cd inkscript
bash ops/setup_nosudo.sh                     # main .venv (+ awscli); then .venv/bin/pytest -q (~3 min)
# the owner types the keys: GEMINI_API_KEY in .env; `.venv/bin/aws configure` with a read-only key for the bucket;
#   the Vast key and ssh key (section 6)
# from the laptop (resumable; repeat until it finishes)
rsync -avh --partial experiments/34_yardstick/out/ SERVER:inkscript/experiments/34_yardstick/out/
rsync -avh --partial experiments/19_azure_map/out/docs/ SERVER:inkscript/experiments/19_azure_map/out/docs/
rsync -avh --partial --links experiments/28_scale/out/azure/ SERVER:inkscript/experiments/28_scale/out/azure/
rsync -avh --partial experiments/{36_vlm_bakeoff,38_parser,29_catalogue,35_edition}/out ...   # one per folder
rsync -avh --partial --exclude venv --exclude gpu/result.tgz \
      experiments/39_ink_geometry/out/ SERVER:inkscript/experiments/39_ink_geometry/out/
# exp 39's CPU venv for the layout model
python3 -m venv experiments/39_ink_geometry/out/venv
experiments/39_ink_geometry/out/venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
experiments/39_ink_geometry/out/venv/bin/pip install doclayout-yolo huggingface_hub opencv-python-headless
# run Claude Code inside tmux so it survives disconnects
tmux new -s inkscript    # later: tmux attach -t inkscript
```
Optionally copy my notes: `~/.claude/projects/-home-yassine-inkscript/memory/` (the folder name follows the checkout
path). This file already carries their content.

**After any reboot** (laptop or server): restart `ops/vast_guard.sh`. If needed, also restart the gold-page server
(`inkscript view --gold experiments/34_yardstick/out/gold --host 0.0.0.0`) and the viewer, then check they respond.

## 8. Open items waiting on the owner

- **Proposed deletions** (not done):
  - `experiments/39_ink_geometry/out/gpu/result.tgz` (1.1 GB, already unpacked beside it).
  - The every-10-epoch checkpoints in `out/gpu/out/run/weights/` (only `best.pt` matters).
- **Edition font switch** to Scheherazade New (section 1), plus the heading-font question.
- **Exp 37 (edition review) is paused** for the owner's evening session: 20 of 205 documents reviewed, 64 issues.
- **Exp 41 hand-check, then archive-by-Gemini vs Flash labels for our own specialists** (section 0).
- **Layout round 3 (rebalanced) vs moving to order** (section 0, parked).
- **Gemini credit is empty** (2026-10-15): nothing that calls Gemini until the owner tops it up.
- **The auditor test** (count unclaimed islands on the 44 pages): offered, not approved.
- **The server move itself** (this document).
