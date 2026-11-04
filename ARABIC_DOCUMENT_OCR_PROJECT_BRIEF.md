# Arabic Document OCR Lab — Coding Agent Project Brief

Prepared for Yassine Soltani · 4 November 2026

## 1. Your assignment

Build a local-first experimental workbench for Arabic and multilingual document OCR, parsing and extraction. The immediate deliverable is working code that ingests documents, runs interchangeable engines, preserves their outputs and source locations, evaluates results, and lets a person inspect and correct mistakes.

This is a research and engineering harness. It must help us discover which components work for our collection before we commit to a production pipeline or fine-tuning strategy.

Start implementing, not merely proposing an architecture. Inspect the repository and its instructions first. Reuse compatible existing code and conventions. If this is an existing OCR project such as inkscript, integrate a clearly bounded experiment module; do not replace its production pipeline. If the repository is empty, scaffold a standalone project with the working package name `dococr_lab`. The name is provisional.

Complete Milestone 1 first, then continue through the available milestones. Make reasonable implementation decisions without asking about routine choices. Keep a short implementation log of decisions, completed work, verified commands and blockers. When GPU access or user documents are unavailable, finish and test everything that does not depend on them, provide precise commands for the remaining run, and distinguish implemented integration from real-model validation. Never fabricate successful inference, benchmark scores, GPU measurements or test documents.

Do not provision paid infrastructure, send documents to hosted inference APIs, upload a dataset, publish the repository, or begin a large training run as part of this brief. Provide launch instructions for a user-supplied local machine or rented GPU. Running small tests on an already supplied development machine is expected.

## 2. Context and intended outcome

The collection includes:

- Older printed Arabic books and articles with fading, uneven ink, unfamiliar typefaces, skew and scan artifacts.
- Difficult pages with multiple columns, spanning headings, footnotes and marginal notes.
- Modern Arabic academic documents containing inline and display equations.
- Tables with Arabic headings, merged cells, mixed numerals and Latin symbols.
- Arabic mixed with English or French, especially references and scientific terminology.
- Western-language documents that must continue to work well.

Do not assume old print means handwriting. Handwritten manuscripts, if supplied, require a separate evaluation category. Examples of Arabic script styles should be labelled only when known; do not automatically classify all difficult handwriting as Maghribi or Naskh.

The workbench must separate these tasks:

| Task | Required result |
| --- | --- |
| Recognition | Faithful text transcription |
| Layout | Locations and types of content regions |
| Reading order | Sequence and relationships of regions |
| Structural parsing | Equations, tables, headings, lists and references |
| Extraction | Requested facts with source evidence or an explicit missing/uncertain result |
| Reconstruction | Later export to searchable PDF, HTML or editable documents |

A model may perform several tasks at once. Our schema and evaluations must still expose which task failed. Good-looking Markdown is not proof of accurate or complete transcription.

Success means we can answer: which engine works on each document category; what caused its errors; whether cropping or specialist routing improves it; how much it costs per accepted page; and which failures justify annotation or fine-tuning.

## 3. First-release scope and boundaries

Required:

1. PDF and page-image ingestion with immutable source files and hashes.
2. Page rendering, native-text inspection and a versioned dataset manifest.
3. An engine adapter interface and a working PaddleOCR-VL baseline.
4. Resumable runs with raw outputs, normalised outputs, timing and error records.
5. A page-review interface with source image, overlays, candidate outputs and corrections.
6. Text recognition and completeness evaluations, followed by structural metrics.
7. A second Arabic-specialist adapter and controlled crop experiments.
8. An evidence-preserving extraction experiment after the parsing loop works.

Defer distributed scheduling, Kubernetes, multi-tenant authentication, billing, production RAG ingestion, a custom foundation model, automated RL training, perfect Word reconstruction and large-scale processing. Searchable-PDF export is a later milestone, not a prerequisite for evaluating OCR.

The default inference path is local or on a user-controlled GPU host. Model and dependency downloads are a separate setup operation. Normal inference must not require a hosted commercial API.

## 4. Proposed implementation choices

Use these defaults unless the existing repository makes another choice materially better:

| Area | Default |
| --- | --- |
| Core | Python 3.11-compatible package, Pydantic schemas, Typer CLI |
| Dependency management | `uv` with a committed lockfile for the core environment |
| API | FastAPI, sharing the same core services as the CLI |
| Review UI | React, TypeScript and Vite; reuse an existing compatible frontend if present |
| State | SQLite for jobs, runs and annotations; filesystem for source files and large artifacts |
| Rendering | PDFium through `pypdfium2`; Pillow for images |
| Native PDF text | `pypdf` inspection/extraction; record its limitations and validation status |
| Models | Isolated worker environments or containers per engine |
| Tests | Pytest and focused frontend/browser tests for the review workflow |

Resolve current compatible package versions from official documentation and lock them. Do not install all GPU frameworks into the core environment. Keep renderer, model and dataset licences in `docs/DEPENDENCIES_AND_LICENSES.md`. If an existing dependency already provides rendering, use it after checking its suitability and licence.

One GPU is the initial scheduling target. Run heavy engines sequentially by default. A worker may retain a model in memory across pages; do not reload it for every page. Use a local subprocess JSONL protocol initially, with a typed local-HTTP transport only if an engine's official server requires it. Never assemble shell commands by interpolating document names or OCR output.

Suggested module ownership:

| Location | Responsibility |
| --- | --- |
| `src/dococr_lab/schemas/` | Versioned manifests, predictions, annotations, metrics |
| `src/dococr_lab/ingest/` | PDF/image inspection and rendering |
| `src/dococr_lab/adapters/` | Engine contracts and normalisers |
| `src/dococr_lab/runs/` | Scheduling, state, resume, resource measurement |
| `src/dococr_lab/evaluation/` | Matching, metrics and reports |
| `src/dococr_lab/extraction/` | Schema-constrained extraction and evidence validation |
| `src/dococr_lab/api/` | Review API |
| `workers/` | Isolated engine entrypoints and environment definitions |
| `web/` | Review frontend |
| `configs/` | Dataset, engine and experiment YAML |
| `tests/fixtures/` | Small, clearly labelled synthetic/publicly usable fixtures |
| `docs/` | Setup, experiments, data conventions and implementation status |

Do not commit user documents, model weights, caches, tokens or bulk predictions. Configure an explicit data root and use relative paths inside manifests.

## 5. Engine priorities

The following checkpoint names come from the research snapshot, not from a successful deployment. Verify access, exact revisions, recommended preprocessing, output formats and runtime requirements during implementation. Pin resolved revisions. If anything has changed, document it rather than silently substituting a different model.

| Priority | Engine | Purpose |
| --- | --- | --- |
| P0 | `PaddlePaddle/PaddleOCR-VL-1.6` | Main multilingual parsing baseline |
| P1 | `SalahALHaismawi/Nuqta-Arabic-OCR-4B` | Arabic-specialist comparison; card lists 4.75B parameters |
| P1 | A detector plus `arabic_PP-OCRv5_mobile_rec` | Lightweight conventional recognition baseline |
| P2 | `dots-studio/dots.mocr` | Alternative multilingual page parser with region outputs |
| Optional | `datalab-to/chandra-ocr-2` | Additional multilingual structural comparator |
| Later | MinerU, DeepSeek-OCR-2, Kraken | Additional parsing or historical-script experiments |

Chandra's code and weights have different licences. Keep this integration optional and do not equate downloadable weights with unrestricted commercial deployment. Record the current terms before enabling it for a deployment.

Nuqta's model card discloses overlap with part of KITAB-Bench. Preserve this caveat in reports; public benchmark results cannot replace testing on our own held-out documents.

Do not substitute base Falcon-OCR for the separately reported Falcon-OCR-Arabic checkpoint. The earlier research did not establish a downloadable exact Arabic checkpoint. Baseer is useful research context; do not assume its published scores apply to any similarly named public checkpoint.

The baseline Paddle integration must use the official complete parsing pipeline where appropriate. Distinguish a complete pipeline from a bare recognition model. Label their stages and timing separately.

## 6. Adapter contract

Expose a typed contract equivalent to:

```python
class EngineAdapter(Protocol):
    def capabilities(self) -> EngineCapabilities: ...
    def health(self) -> EngineHealth: ...
    def load(self, config: EngineConfig) -> None: ...
    def predict(self, request: PageRequest) -> PredictionResult: ...
    def close(self) -> None: ...
```

The core process should load only the lightweight transport adapter. GPU imports and model loading belong in the isolated worker. Implement request IDs, protocol versioning, health checks, timeouts, structured errors and worker termination. Logs must go to stderr so they cannot corrupt a JSONL stdout protocol.

Capabilities must explicitly describe full-page and crop support, text/box granularity, supported output types, configurable image budgets and known limitations. Do not invent word boxes when an engine emits only block boxes. Any derived alignment must be labelled with its method.

Preserve verbatim raw responses before normalisation. A parse failure must leave useful raw evidence. Unknown model labels go through a documented mapping to canonical types; unmapped labels remain visible.

Use official decoding settings as the initial baseline. Record temperature, seed where supported, image limits and output-token limits. Do not silently force identical image dimensions or decoding configurations onto incompatible architectures.

CPU-only fixture workers are allowed to test orchestration, but name and label them as fixtures. A mock worker must never count as a validated model integration or appear in an accuracy leaderboard as a real OCR engine.

## 7. Ingestion and canonical data model

### Source and page identity

- Store each source unchanged with its SHA-256, original name, media type, page count and ingestion version.
- Derive stable document/page IDs from source identity and page index. Page numbers are **one-based** everywhere in the public API and manifests.
- Store each rendered image with its own hash, width, height, DPI, rotation and renderer revision.
- Record native-text presence, content, extraction warnings and a status such as `unverified`, `usable` or `suspect`.
- Presence of a text layer is not sufficient to skip OCR. Include scanned PDFs with garbage hidden text in tests. Mixed pages may require native-text extraction and image-region OCR.
- Support a `force_ocr` option and a source-selection policy. Keep baseline source selection explicit.

### Coordinate convention

Use top-left-origin pixel coordinates on a declared canonical page render, with boxes `[x0, y0, x1, y1]` and exclusive upper bounds. Every prediction points to that render's ID and dimensions.

Preserve the transforms from PDF coordinates to the canonical render, from render to crop, and from crop to model input. Map predictions back to the canonical frame. For dewarping, store the appropriate inverse mapping or explicitly mark geometry as unavailable; do not pretend an affine transform covers a non-linear warp. Model pixel budgets and resized dimensions must be logged.

Do not use predicted box coordinates as the only persistent annotation identity. Predictions have per-run block IDs; ground-truth annotations have separate stable IDs. Evaluation stores their matching relationships.

### Page prediction

Define validated schemas covering:

- `schema_version`, `document_id`, `page_number`, `render_id`, `run_id`, `attempt_id`.
- Status, engine metadata, raw-artifact references and measurements.
- Blocks with ID, type, geometry, text and optional language/direction spans.
- Types including paragraph, heading, list, footnote, header, footer, table, equation, figure, caption, bibliography and unknown.
- Parent-child relationships and explicit reading-order information. Validate graph edges and detect cycles.
- Tables with cell text, zero-based row/column indices, spans, optional cell boxes and header flags. Store columns in declared spatial order and preserve a separate reading-direction/order mapping; do not reverse every table merely because it contains Arabic.
- Equations with raw LaTeX or other emitted representation, equation number and crop reference. Keep display equations and inline equation spans distinguishable.
- Nullable engine confidence with its provenance and meaning. Keep independent quality flags separate from model probabilities.

Inline offsets must use a declared convention, preferably Unicode code points in the immutable raw string. Changing normalisation must not silently invalidate these offsets.

Preserve `raw_text` separately from derived `search_text`. Never overwrite the faithful transcription with normalised text, spelling corrections, generated diacritics, transliteration or translation.

### Extraction result

Every extracted field must include:

- Value, status (`observed`, `inferred`, `not_present`, `uncertain`) and schema version.
- Source document, page and block references.
- A verbatim supporting quote and offsets when available.
- Extraction model/prompt revision and validation flags.

Missing and unreadable are different states. JSON schema validity does not prove factual correctness. Initially disable inference of absent facts: prefer missing/uncertain values. Label any later inference separately.

## 8. Dataset and annotation workflow

Implement a versioned JSONL manifest plus a YAML dataset configuration. Each entry records document/page IDs, source category, languages where known, provenance, usage permissions, split, render reference and optional annotation references. Do not require every page to have gold labels.

The intended pilot is:

- Thirty diagnostic pages: five each from older print; difficult Arabic layouts; Arabic mathematics; tables; Arabic mixed with English/French; Western-language control material.
- Then approximately 180 checked pages: 60 development and 120 held out.
- Add handwriting as a separate category if supplied.

These are sampling targets, not files already available. Ship small labelled synthetic fixtures for installation/testing. Include actual mixed Arabic/Latin text, combining marks, numbers, two columns, footnotes, equations and tables. Validate that fonts support Arabic shaping. Synthetic fixtures test software correctness, not real-world OCR quality.

Group splits by book/source document, and by source family where needed. Provide a leakage check that rejects the same document in multiple splits. Lock a test manifest hash and ground-truth version before comparing final configurations. Annotation edits create a new version and invalidate only affected metric caches.

Add optional importers for KITAB-Bench and Misraj-DocOCR. Do not download public datasets during a normal unit-test run. Keep original dataset splits and licences; explicitly record any derived evaluation split. Store benchmark release and evaluator versions. Do not silently substitute reviewed annotations for original annotations while retaining the same benchmark label.

## 9. Runs, reproducibility and failure handling

Persist resolved configuration at run creation, including source and label manifest hashes, code commit plus dirty-state indicator, engine revision, worker environment, prompt hash, preprocessing settings, precision, image/output budgets, device and framework versions.

Run identity must incorporate all settings that affect outputs. Prediction caches must not depend on mutable annotation text; evaluation caches must include prediction and annotation versions. Re-evaluating corrected labels should not rerun expensive inference.

Store a page-level state machine: `pending`, `running`, `succeeded`, `failed`, `cancelled`. Keep attempts separately. On restart, reconcile stale running leases. Write large artifacts atomically and persist status only after artifacts are durable. Resume skips only results with matching identities and valid completed artifacts.

Record failures such as unreadable PDF, render error, worker crash, timeout, OOM, generation truncation, invalid output and missing required output. An empty successful result on a page containing text must remain distinguishable from a blank page and from an engine failure.

Retry budgets must be bounded and configured. If a retry changes resolution, precision, batch size or model, record it as a different attempt/configuration. Do not hide adaptive retry policies inside a fixed-configuration baseline. Reports must distinguish first-pass accuracy from the final retry policy.

Measure rendering, model load, inference, normalisation and total wall time separately. Report warm/cold status, batch size, concurrency, output length, peak memory measurement method, retry count and throughput. Serial inference is the first supported execution mode. Unsupported measurements must be null with a reason, not zero.

Accept GPU price as a user configuration value with currency and date. Compute observed cost from measured runtime and rate; do not hardcode researched rental prices. Calculate cost per accepted page only when an explicit acceptance policy exists, and return unavailable if no page qualifies. Record human review time separately.

## 10. Evaluation requirements

Implement transparent, deterministic metrics before LLM judging. Human-checked references are the primary truth for the pilot. Always report labelled/unlabelled counts, failures, metric coverage and exclusions.

| Area | Implementation |
| --- | --- |
| Recognition | Raw CER/WER under a documented Unicode convention; separate configurable normalised scores; insertion/deletion/substitution counts |
| Recognition without order confounding | Text scores on matched blocks or manually supplied crops, separate from full-page ordered text |
| Completeness | Missing/extra blocks and lines where those labels exist; output repetition and truncation flags |
| Layout | Type-aware region matching at declared IoU thresholds, precision/recall, and unmatched region counts |
| Reading order | Pairwise order accuracy on matched comparable blocks, with pair coverage and missing-block rates |
| Tables | A pinned TEDS implementation plus cell text/structure checks; clearly state matching rules and unsupported cases |
| Equations | Initial normalised LaTeX exact match with known limitations; add a pinned rendered/structural metric such as CDM later |
| Extraction | Per-field precision/recall and exact match where appropriate; false filling of absent fields; evidence validity |
| Operations | Latency distribution, throughput, memory, failure/retry rate and configured cost |

CER/WER may exceed 100% because of insertions. Do not clamp them or call `100 - CER` a universal accuracy score. Define empty-reference behaviour explicitly. Keep both micro and macro aggregation and per-category results. Use document-level bootstrap intervals when the sample supports them; report sample sizes and seeds.

Primary transcription evaluation must not collapse hamza forms, `ى/ي`, `ة/ه`, digits or diacritics. Provide separately named optional policies for search-oriented normalisation. Preserve raw bytes and expose every policy in reports. Do not strip bidirectional controls without recording the policy.

A missing table/equation or failed page cannot vanish from the denominator and improve a model's score. Report conditional recognition scores and end-to-end coverage together. If a metric is unavailable, mark it unavailable rather than manufacturing a proxy score under that metric's name.

Generate machine-readable JSON and an HTML comparison report with per-category tables, sample counts, worst pages, links to source crops, configurations and failure reasons. Export CSV summaries. Avoid a single overall ranking until explicit task weights are configured.

## 11. Review interface

Build a functional research UI with three connected views:

1. **Dataset:** documents/pages, categories, split, annotation status and filters.
2. **Runs:** engine/configuration, progress, failures, measured resources and comparison selection.
3. **Page review:** source image with zoom and selectable overlays; two or more candidate outputs; editable ground truth; differences and quality flags.

Required interactions:

- Clicking a block highlights its source location and opens the original crop.
- Toggle region types, reading-order labels and raw/normalised text.
- Edit transcription, block type and reading-order relationships; add/move missing region boxes when needed for crop experiments.
- Save corrections as a new annotation revision. Never edit model predictions in place.
- Mark a region unreadable or a page reviewed, recording who/when and an optional reason.
- Queue a selected crop for recognition with a selected supported engine.
- Navigate directly from a failed metric to the relevant source/prediction.
- Show failed pages and unsupported features explicitly.

Arabic display must preserve logical Unicode text. Use direction-aware containers and bidi isolation for mixed spans; keep LaTeX, code and identifiers in suitable LTR containers. Do not reverse strings to achieve an RTL appearance. Test selection, copy/paste and table column labels, not only screenshots.

Treat document text, HTML tables and model-generated content as untrusted display content. Escape/sanitise it; do not execute generated scripts or raw HTML. Render mathematical content with restricted settings. Serve files through a data-root allowlist; avoid arbitrary filesystem reads and path traversal. Bind to localhost by default and document SSH tunnelling for a rented host.

## 12. Experiment configurations

Provide reusable YAML configurations for these experiments, with only implemented features selectable:

| ID | Experiment | Purpose |
| --- | --- | --- |
| E0 | Each engine's documented native pipeline | Establish out-of-box behaviour |
| E1 | Same suitable reader on manually corrected crops | Estimate recognition performance with layout errors removed |
| E2 | Same reader on automatic crops | Measure automatic layout/segmentation cost |
| E3 | Arabic specialist for text; parser for tables/equations | Evaluate routing benefits and overhead |
| E4 | Original vs individual preprocessing changes | Identify useful image transformations |
| E5 | Image-only vs image plus OCR transcript | Test whether correction helps or misleads |
| E6 | Predicted text vs verified text into the same extractor | Separate OCR errors from extraction errors |
| E7 | Precision/batching experiments after accuracy is established | Measure cost/quality tradeoffs |

Start with E0, E1 and E2. E3 onward are later milestones, not reasons to delay the first runnable pipeline.

Use 200/300 DPI as initial render comparisons; 400 DPI is an optional tiny-text experiment. Record effective input dimensions, because processor downsampling can erase the difference. Retain the untouched image and test deskew, contrast adjustment, denoising and binarisation independently. Avoid claiming that visually cleaner images necessarily improve Arabic recognition.

Crop experiments need padding and enough context for Arabic dots, diacritics and paragraph interpretation. Preserve crop transforms and reading order. Keep whole-page parsing as a comparator: cropping can lose context or omit material.

Route uncertain regions using measurable signals: detected text without corresponding output, truncation, repeated text, invalid structures and reader disagreement. Flags are not calibrated probabilities. Keep threshold tuning on development data and evaluate false acceptance on held-out pages. Two readers agreeing does not prove correctness.

## 13. Extraction experiment

After parsing/evaluation works, implement a small academic-metadata schema: title, authors, affiliations, publication year, abstract and references. Keep this schema configurable; no invoice-specific assumptions.

Use a supplied local text/VLM endpoint through an explicit adapter, or another already installed local model. The extractor should not decide its own cloud provider or download a huge general model automatically.

Require field evidence and null/uncertain handling. Distinguish publication year from years mentioned in the body and paper authors from cited authors. Treat document instructions as source content, not agent commands. Validate JSON and check supporting quotes against source blocks. A quote appearing in a block is necessary evidence for an observed field but does not alone establish that the field interpretation is correct.

Compare the same extractor/prompt on predicted content and human-verified content. Preserve all evidence links through the comparison. Do not fine-tune OCR to fix an extraction failure that also occurs with correct input.

## 14. Intended CLI and setup experience

Implement a consistent CLI along these lines. These are requested application commands, not claims about existing third-party APIs:

```bash
dococr doctor
dococr ingest ./documents --dataset pilot --data-root ./data
dococr dataset validate pilot
dococr render --dataset pilot --dpi 300
dococr run --dataset pilot --engine paddle_vl --config configs/baseline.yaml
dococr run --resume RUN_ID
dococr evaluate --run RUN_ID --annotations gold-v1
dococr compare --runs RUN_A RUN_B --output ./reports/comparison.html
dococr serve --host 127.0.0.1 --port 8000
```

Document core installation, each worker's pinned setup, model download/cache locations, frontend startup, a CPU fixture walkthrough, one verified real-model walkthrough when hardware permits, and the rented-GPU workflow. `doctor` should inspect prerequisites without downloading model weights or making paid calls.

Document how to stop workers and copy/persist results before ending a rental. Start with one 48GB GPU as an experiment configuration, not a guaranteed model minimum. If less memory is available, use measured batch/image adjustments and record them. For OOMs, give an actionable diagnosis; never silently switch precision and report the result as the original configuration.

## 15. Milestones and acceptance criteria

### Milestone 1 — one working end-to-end path

- Core package, schemas, manifest and SQLite run state exist.
- A PDF and image can be ingested/rendered with stable IDs and source hashes.
- Fixture worker exercises successful and failed page processing on CPU.
- Paddle worker implements actual inference through documented APIs, with raw output retention.
- CLI launches, resumes and reports a run.
- Minimal review UI shows source image and prediction and can save a correction.
- CER/WER against available gold labels and a run report work.
- Setup documentation states exactly which paths were actually executed.

If no GPU is available, complete the actual adapter and setup configuration, test transport/normalisation against labelled fixtures, and mark real inference and performance verification as pending. Do not block core work or call mocked inference real validation.

### Milestone 2 — meaningful model comparison

- Nuqta and conventional Arabic recognition adapters work where prerequisites are available.
- Side-by-side review, annotation revisions and evaluation-cache invalidation work.
- Grouped splits and leakage checks work.
- Reports include errors, failures, coverage, per-category scores and measured resources.
- Optional dots.mocr integration can be added without changing core schemas.

### Milestone 3 — diagnose layout and recognition

- Manual and automatic crop datasets, coordinate mapping and E1/E2 comparisons work.
- Add layout/reading-order evaluation and table/equation metrics as supported.
- Implement a simple E3 routing policy only after baseline results are available.
- Independent coverage/repetition/truncation flags appear in review and reports.

### Milestone 4 — extraction and training-data export

- Academic metadata extraction with evidence and missing/uncertain states works.
- E6 identifies extraction failures with verified versus predicted input.
- Export reviewed line/region/page examples with original crops, raw labels, split and provenance.
- Add an optional Kraken-compatible line/PAGE/ALTO export where appropriate.
- Propose fine-tuning experiments based on observed failure categories; training is separate work.

## 16. Meaningful verification

Cover the behaviours that could invalidate results:

1. Mixed Arabic/Latin Unicode round-trips without reversal, lost marks or unintended normalisation.
2. Crop/model/page transforms recover expected boxes after rotation/resizing.
3. Resume after a worker crash preserves finished pages and records a retry attempt.
4. Configuration changes invalidate predictions; annotation changes invalidate evaluations without rerunning inference.
5. Same-document split leakage is detected.
6. Empty, failed and truncated results cannot silently disappear from evaluation.
7. A synthetic two-column page has explicit expected reading order; missing footnotes are visible.
8. A missing table, a merged cell and a numeric sign error exercise structural checks.
9. Review edits survive reload and preserve the original prediction.
10. Extracted observed fields without valid source references are flagged.
11. Malicious filenames and model-generated HTML cannot escape the data root or execute code in the review UI.

Use small manually checked fixtures for deterministic unit tests. Real GPU smoke tests are opt-in and separate from default CI. Include a browser check of selecting an Arabic block, inspecting a crop, editing text, saving and reopening it. Record results rather than merely listing commands that ought to work.

Do not impose a fabricated minimum OCR accuracy. Early acceptance criteria are about faithful measurement and correct software behaviour. The first labelled benchmark establishes the empirical quality baseline.

## 17. Agent handoff at each milestone

Provide the implemented changes, exact runnable commands, tests actually executed, real inference performed or pending, current limitations and the next concrete experiment. Link the report and representative failures when real documents have been evaluated. Keep a short `docs/STATUS.md` so another agent can continue without reconstructing the conversation.

A useful first deliverable is a small system we can run on thirty pages and inspect carefully. Prioritise that working loop over speculative infrastructure.

## 18. Research and implementation references

These sources informed the brief. Recheck upstream setup guidance when implementing; retain exact revisions in experiment records. Published results below are not results on our collection.

- [PaddleOCR-VL-1.6 model card](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6) — checkpoint, pipeline and licence.
- [PaddleOCR-VL-1.6 paper](https://arxiv.org/abs/2606.03264) — model/data adaptation approach.
- [PP-DocLayoutV3](https://huggingface.co/PaddlePaddle/PP-DocLayoutV3) — region segmentation and reading order.
- [Paddle text-recognition documentation](https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html) — conventional Arabic recognition checkpoint.
- [Nuqta-Arabic-OCR-4B](https://huggingface.co/SalahALHaismawi/Nuqta-Arabic-OCR-4B) — Arabic model, settings and benchmark-overlap disclosure.
- [Nuqta repository](https://github.com/SalahAlHaismawi/nuqta-ocr) — inference wrapper and evaluation references.
- [dots.mocr](https://huggingface.co/dots-studio/dots.mocr) — multilingual parser with region output.
- [Chandra repository](https://github.com/datalab-to/chandra) — optional comparator; inspect weight terms separately from code terms.
- [MinerU2.5 paper](https://arxiv.org/abs/2509.22186) — global layout followed by native-resolution crop recognition.
- [DeepSeek-OCR 2 paper](https://arxiv.org/abs/2601.20552) — visual-token ordering architecture.
- [When Do VLMs Help Arabic Manuscript OCR?](https://arxiv.org/abs/2608.22366) — conditional benefits and harms of OCR-prior correction.
- [Baseer paper](https://arxiv.org/abs/2509.18174) — Arabic adaptation, synthetic data and reference-label issues.
- [Visual Merit or Linguistic Crutch?](https://arxiv.org/abs/2601.03714) — linguistic-prior stress testing of the original DeepSeek-OCR, not OCR 2.
- [KITAB-Bench](https://github.com/mbzuai-oryx/KITAB-Bench) — Arabic task-specific benchmark and evaluators.
- [Misraj-DocOCR](https://huggingface.co/datasets/Misraj/Misraj-DocOCR) — Arabic document benchmark.
- [OmniDocBench](https://github.com/opendatalab/OmniDocBench) — structural evaluation; pin evaluator and dataset versions.
- [Kraken documentation](https://kraken.re/main/index.html) and [training guide](https://kraken.re/main/user_guide/training_recognition.html) — historical/non-Latin recognition and adaptation.
- [Docling document model](https://docling-project.github.io/docling/concepts/docling_document/) — reference for hierarchy, geometry and provenance; an optional interchange format.

