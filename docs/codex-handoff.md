# Codex continuation: 2026-10-17/18

Written by Codex for Claude when the owner switches back. Read this alongside
[handoff.md](handoff.md), whose main account is dated 2026-10-15. This is a
continuation record, not a replacement for the existing decisions or roadmap.
Append subsequent work here while Codex is collaborating with the owner.

## Paused direction and commit scope (2026-10-18)

After inspecting the viewer, the owner proposed a language-aware model that
can follow pen movements and asked about open-weight GPU inference. Codex
discussed comparing image-only input against image plus ordered strokes or
progressive frames, with the same model and context. Qwen3-VL-8B-Instruct
was a candidate, not an evaluated choice. No model was downloaded, no GPU
was rented and no LLM integration was implemented. The owner then parked
this direction and requested a commit of Codex's changes only; Claude is
working concurrently. Experiment 43 is not Codex's work and is excluded.
Pre-commit focused/documentation rerun: 18 passed, one failed because the
concurrent `43_rehearsal` directory did not yet have its README. No changes
were made to that work to satisfy the check.

## Latest: experiment 42 authorised and built (2026-10-17/18)

The owner subsequently said: "ok auto mode should be on can you build it out?"
This authorised implementing the diagnostic discussed below. Codex built
[experiment 42](../experiments/42_stroke_recovery/README.md), without editing
`src/`, making paid model calls, renting a GPU, committing or pushing.

Read that README for exact commands and the interpretation of results.
Code: pinned public-data download, annotation validator/word extraction,
controlled rasterisation, a component-wise adapter to the existing feel.walk,
fixed nearest-example controls, three small PyTorch CTC readers, a local
viewer and a freely drawn pointer recorder. All data/results/models are in
the experiment's ignored out/ folder (about 243 MB after both runs).

Important findings and boundaries:

- Calliar is human tracing of images by four annotators, with prescribed
  character-component order. It is NOT the original artist's pen recording.
  Its timestamps, pressure, writer/style IDs and most vowel marks are absent.
  Images here are uniform-width rasterisations of those traces, not the
  original artwork. Never present this as proving natural-motion benefit.
- 30 inconsistent drawings rejected explicitly; 7,507 word samples retained,
  official drawing splits preserved (6,027 train / 734 validation / 746 test).
  Word boundaries are oracle annotations. No primitive labels enter features.
  No exact normalised word-raster duplicate found; near duplicates not ruled out.
- 98.1% ink covered within 1 px on average by the adapted legacy traversal.
  This is geometric coverage, not recognition or stroke-order correctness.
- Fixed retrieval on the same 2,000 train / 500 test samples: exact image
  21.6%, reference 31.8%, recovered 24.0%. The 170 unseen-text test samples
  necessarily score 0% exact. No learned warping or language prior.
- The 12-epoch CTC pilot did not learn useful recognition: CER image 100%,
  reference 93.8%, recovered 88.7%. CPU 1m42s, peak 612 MiB RSS. Saved in
  out/runs/pilot. Do not rank representations from these undertrained models.
- The longer run, out/runs/extended, completed 72 total epochs per reader:
  exact image 1.8%, reference 39.2%, recovered 12.2%; CER 78.7%, 25.5%,
  61.8%. The reference reader gets 27/170 unseen-text words exactly right.
  Selection uses validation. The test set was already inspected, so scores
  are exploratory. The image baseline is weak and annotation order favours
  the reference arm. This is not an OCR ranking or proof about natural motion.
  Wall time 10m53s on three CPU threads, peak 608 MiB RSS. Active results are
  in out/results.json. The reference reader on recovered input, without
  retraining, gets 2.0% exact / 82.6% CER (includes distribution shift).
- Raw local recordings retain x/y, event timestamp, pressure, tilt, device
  type, optional writer ID/style and transcription status. No automatic
  train/test assignment. Mouse is never labelled pen. The internal JSON
  record is an experimental interface, not adoption of a new file standard.
  Records are saved before optional inference; errors retain the raw data.
  Saved sequence predictions name their model run. The viewer's reader
  selector switches between retrieval and sequence outputs on the same sample.
- Viewer: http://127.0.0.1:8842. Default loopback. For a remote browser,
  forward the port intentionally. Model inference is optional; geometric
  inspection/recording works without PyTorch. Baseline outputs are not
  certified readings, particularly on natural input.

Validation includes focused tests and Playwright desktop/mobile screenshots,
changing canvas-pixel checks, playback, navigation, empty states, pointer
channels, undo and preservation of writing after a rejected save. Browser
test recordings are intercepted, not stored in the research data. Screenshots
and JSON check results are in out/checks. See final verification below and
the experiment README for the completed test count.

Future Claude: the owner should first see the instrument and its limits.
Do not turn the reference/recovery retrieval difference into a claim about
natural calligraphy. Next useful evidence is genuinely captured Arabic
writing with checked text and writer-disjoint evaluation, or better controlled
sequence-reader training; neither is automatically approved as a paid run.

## Owner's current direction

The owner first requested a read-only assessment of the project from its
beginnings through Gemini 4 Argon, taking a researcher's and AI-data user's
perspective. They then asked for a high-level conversation about feeling stuck.
They are now revisiting their original picture: recognise a word by feeling
the pen moving, as if someone wrote it on your back.

Their motivation includes Arabic's cultural, artistic and religious importance,
and dissatisfaction with its treatment in digital documents. Preserve that
motivation without treating it as evidence that a recognition method works.
They are considering whether calligraphy and modern print need different
representations, and whether a new file format is needed. These are questions,
not decisions to replace JATS, ALTO, Unicode or the current pipeline.

The owner explicitly asked Codex to take on coding as needed while Claude is
unavailable, follow the repository's established working style, and leave a
record of everything done for the returning Claude session. This does not by
itself approve a paid model run, GPU rental, or a new experiment's scope.
Continue thinking with them before committing to an implementation.

## Initial read-only work (through 2026-10-17)

- Read CLAUDE.md, the vision, handoff, status, decisions, relevant ideas and
  pipeline documentation; traced git history to the first 2026-09-17 commit.
- Reviewed experiments 40 and 41: prompts, line-ID assembly, correction
  handling, master writing, master-backed layout reading, scoring and exports.
- Inspected saved scores, JATS/ALTO-derived JSON, correction sheets and page
  images, including poetry, tables, equations and layout overlaps. This was a
  sample inspection, not an independent audit of all 399 pages.
- Recomputed aggregate experiment-41 word comparisons from saved scores:
  Azure 1.801%, Argon 1.547%, Flash 1.770%; confirmed 20 done gold pages and
  14 born-digital truth pages. No recogniser or scorer was rerun.
- Revisited experiments 10, 16 and 17, including feel.py, model_lib.py,
  bench.py and the trained-reader notes. Checked primary references below.
- Added this note and entry-point links, and recorded the revived question in
  ideas.md. No application code, model, data or existing output was changed.

For the initial review: zero paid model calls and zero GPU rental. No training,
corpus rebuild, new recognition experiment, commit or push was performed then.

## Assessment already shared with the owner

The system has useful reading and discovery outputs with source evidence.
That is different from certifying a corpus as an exact transcription or gold
training data. The strongest choices are line-ID anchoring, separate print and
search text, D30, and deriving views from JATS + ALTO masters.

Outstanding qualifications discussed:

- Some automatic reader fixes alter the print: the saved review labels 34 of
  40 Argon fixes right, 4 wrong and 2 unsure. Exact substring validation is
  not an independent check of the printed ink.
- The word-multiset comparison is not a complete document-fidelity measure.
  Model agreement is not independent truth; table-cell relationships, maths,
  order and punctuation need their own evidence.
- The generic edition parser flattens reader-fix and sic annotations; the
  Markdown/JSON do not carry the individual decisions retained in the XML.
- Some latest layout pages have heading overlaps; PDF extraction still has
  losses and ordering limitations. Schema validity does not establish these.
- Important qualification to the report's noise finding: on
  0656-016-001-011 p4 (printed p37), the requested article, "حضارة الاسلام",
  resumes below a separator with a continuation marker referring to printed
  p33. The upper political passage appears to belong to another article.
  Excluding it from this article may be correct; calling it noise conflates
  out-of-article text with OCR debris. This is Codex's visual interpretation,
  not an owner-verified correction. Do not blindly require every printed
  word on a source page to enter the article. The ALTO retains excluded text.

## The reopened tracing question

Respect experiment 17 and D19: the tested feeler did not beat Azure on the
sampled disagreements. Do not describe the earlier work as only crude
matching: experiment 16 also trained CTC readers, reaching 79.0% agreement
on held-out pieces, later 82.6% with a 1.5M-parameter reader and more books
(reported in its README; not newly reproduced). These are piece agreement
with Azure, not independently established accuracy on calligraphy.

What remains open is a different distinction:

- Captured pen input has an observed sequence and stroke boundaries, with
  timing and optional pressure/tilt channels. A scan contains the final ink;
  several writing motions can explain it, and printed type may have no
  original handwritten trajectory to recover.
- feel.py walk() follows the skeleton trunk and traverses branches out and
  back. This is a constructed traversal, not measured writing order.
- The trained model's raw() pools branch walks into extrema and counts along
  trunk positions, alongside dots and geometric features (18 channels).
  It does not receive the full original time-ordered pen recording.
- Thus the result constrains that representation and recogniser; it does not
  settle whether a better stroke representation could help. Conversely,
  recovering strokes adds no new observed evidence to a scan, and stylus
  recognition does not guarantee recognition of arbitrary calligraphy.

A diagnostic initially discussed with the owner: compare actual captured strokes with
paths recovered from rasterisations of the same writing, using controlled
recognition comparisons and a matched image baseline. This would distinguish
information lost in path extraction from recogniser weakness. The owner later
approved implementation (experiment 42, above). Human retracing must be identified
as a human interpretation, not the historical writer's true stroke sequence.

Possible direction, still a hypothesis: keep the source image and evaluate
several plausible stroke explanations together with candidate readings,
rather than committing to one skeleton walk before recognition. Script rules
can constrain alternatives. Re-rendering can check geometry, but two different
readings may explain the same ink; visual agreement alone cannot prove text.

## References checked

- [Experiment 16](../experiments/16_feel/README.md) and
  [experiment 17](../experiments/17_judge/README.md).
- [Unicode Arabic rendering](https://unicode.org/versions/Unicode17.0.0/core-spec/chapter-9/):
  characters, contextual joining and ligatures are distinct from their glyphs.
- [W3C InkML](https://www.w3.org/TR/InkML/): existing storage for pen traces,
  contact states and optional dynamic channels; annotations can link meaning.
  This is not a proposal to replace the current masters with InkML.
- [TRACE, 2021](https://arxiv.org/abs/2105.11559): learned line-level recovery
  of trajectories from offline handwriting is an existing research direction.
  It does not establish performance on this archive or Arabic calligraphy.

## Verification

Experiment 42, 2026-10-18: full repository suite **118 passed** (5m45s).
Latest focused tests plus documentation checks **19 passed**; Playwright
**16/16 checks passed**, including desktop/mobile overflow, moving canvas
pixels and pointer recording. Browser test samples were intercepted, and
server write tests used pytest's temporary directory. No synthetic test
records were added to the research data. `git diff --check` passed.

Initial documentation-only review:

Documentation link checks: `.venv/bin/pytest -q tests/test_docs.py` passed,
3 tests. `git diff --check` also passed. No behavioral test run was needed
for this documentation-only continuation.
