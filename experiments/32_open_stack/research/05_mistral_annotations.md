# Mistral OCR and its annotations: could they serve our specialists?

Research only, done 2026-10-14. Nothing was spent and no API was called. Sources are Mistral's own docs (fetched as
markdown from docs.mistral.ai on 2026-10-14), its Python SDK's schema docs on GitHub, its legal pages, and a few
independent sources. Each one is marked **official**, **independent** or **anecdote**.

## Summary (six lines)

1. **(a) Line-level labeller: no, not as it stands.** Mistral labels its *own* paragraph blocks, 13 types, and does not accept our line boxes. Its types have no footnote, verse or furniture-as-such (it has header/footer/aside_text). Scored the way we scored dots.mocr (each Azure line takes the type of the block it falls in), it would be a third opinion, not a Flash replacement.
2. **The labelling feature is not "annotation" anyway.** The block types come free with plain OCR (`include_blocks=True`, $4 per 1,000 pages). "bbox annotation" runs only on the *images* it crops. "document annotation" fills one JSON form for the whole document, from Mistral's own markdown, so it never sees our lines.
3. **(b) Pictures specialist: plausible, the best fit of the three.** It returns each figure's box and crop, then runs a vision model on each crop with our JSON schema (kind, caption, description), for $5 per 1,000 pages. We do not know if it finds grey halftone photos on old scans.
4. **(c) Whole-document specialist: plausible but blind.** `document_annotation_format` plus a prompt returns title, authors, abstract and keywords as JSON. But the model (mistral-small) reads only Mistral's *own* Arabic markdown plus at most 8 image crops, not the page images and not Azure's text. Arabic quality is unmeasured, and there is a reported right-to-left column-order bug.
5. **Arabic evidence is thin.** Mistral lists Arabic as supported but publishes no Arabic number. The one independent number is for the 2025 model (CER 0.21 on 200 traditional-print pages). Nothing independent exists for OCR 4/4.1 on Arabic. Outputs are ours to train on (only image outputs are restricted). ZDR covers `/v1/ocr` but not batch or files. EU by default.
6. **Cheap test: the 44 test pages through `mistral-ocr-4-1` with blocks, bbox annotation and a document schema, ≈ $0.25.** Plus ~40 first pages for the whole-document test, ≈ $0.25 more. Optionally Mistral Medium 3.5 *chat* given page + Azure lines, ≈ $1–2 (see "The honest route to line labels"). **Total under $3.** Score it with `experiments/39_ink_geometry/score_yolo.py`'s dots.mocr mapping.

## 1. The current model and what the API returns

- **Model.** OCR 4.1, API names `mistral-ocr-4-1` / `mistral-ocr-4` / `mistral-ocr-latest`, released 2026-07-16, GA ([model card, official](https://docs.mistral.ai/models/ocr-4-1)). OCR 4.0 (`mistral-ocr-4-0`, 2026-06-23) was deprecated 2026-09-29 and retired 2026-09-30 ([card, official](https://docs.mistral.ai/models/ocr-4-0)). Launch post: [mistral.ai/news/ocr-4](https://mistral.ai/news/ocr-4) (2026-06-23). Nothing newer was found as of 2026-10-14.
- **Endpoint `/v1/ocr`, per page** ([OCR processor doc, official](https://docs.mistral.ai/studio/document-processing/basic_ocr); [SDK schema, official](https://github.com/mistralai/client-python/blob/main/docs/models/ocrpageobject.md)). Each page has:
  - `markdown`: headings as `#`, tables inline or as placeholders, equations as `$…$` LaTeX;
  - `images[]`: id, box, optional base64 crop, optional `image_annotation`;
  - `tables[]`: markdown or HTML (`table_format`), with per-word confidence if asked;
  - `hyperlinks`;
  - `header` / `footer` (`extract_header`/`extract_footer` remove them from the markdown);
  - `dimensions` (dpi, w, h);
  - `confidence_scores`: page, block or word level. Word level gives `{text, confidence, start_index}` into the markdown, **with no word boxes**;
  - `blocks[]` when `include_blocks=True` (OCR 4+).
- **Blocks** are "paragraph-level bounding boxes … in reading order". Each block has a type, a box (`top_left_x/y`, `bottom_right_x/y` in page pixels) and `content` (text/markdown/html), plus optional type and content confidence. The types are:
  - `text`, `title`, `list`, `table`, `image`, `equation`, `caption`, `code`, `references`, `aside_text`, `header`, `footer`, `signature`.

  `title` carries no level (the markdown's `#` count does). There is **no footnote, verse, page number or line level.** The smallest box is a paragraph.
- **Reading order**: blocks come in reading order (official claim). But an independent tool author reports that on two-column **Arabic** pages Mistral OCR emits the left column first, with no parameter to change it. He fixed it locally ([PR #9, EngDawood/mcp-mistral-ocr, 2026-09-17, anecdote](https://github.com/EngDawood/mcp-mistral-ocr/pull/9)), so `mistral-ocr-latest` was 4.1 at that date. Treat this as a likely fault to check, not a fact.
- **Tables**: HTML or markdown. **Equations**: LaTeX (inline in markdown and as `equation` blocks).
- **Annotations** ([Annotations doc, official](https://docs.mistral.ai/studio/document-processing/annotations)):
  - `bbox_annotation_format` (JSON schema only): "we call a Vision capable LLM for all bboxes individually". In the schema this lands only in `images[].image_annotation`. Text blocks have **no annotation field** ([SDK block schemas](https://github.com/mistralai/client-python/blob/main/docs/models/ocrtextblock.md)). So **it cannot classify text blocks; it runs on figure/chart crops only.**
  - `document_annotation_format` + optional `document_annotation_prompt`: "We run OCR and send the output text in Markdown, along with the first eight extracted image bounding boxes, to a vision-capable LMM". It returns one JSON object for the whole document. The launch post names the annotation model as `mistral-small-2603` ([news](https://mistral.ai/news/ocr-4)). FAQ: "each annotation accepts a maximum of 8 image bounding boxes". The doc's examples restrict to 8 pages; a hard page cap for document annotation is not stated.

## 2. Our own image plus our own line boxes?

**No.** The request takes a document or image plus `pages`, `image_limit`, `image_min_size`, the two annotation formats, a prompt, `table_format`, header/footer flags, `include_blocks` and confidence granularity ([OCRRequest](https://github.com/mistralai/client-python/blob/main/docs/models/ocrrequest.md)). No field accepts regions or boxes. Annotations work only on Mistral's own detected image regions or on the whole document.

There are two ways around it:

- **Overlay.** Assign each Azure line to the Mistral block that covers it (the same >30% overlap rule `score_yolo.py` used for dots.mocr) and map the types. This gives line labels with coordinates, but only Mistral's 13 types, and footnotes or verse will come out as `text`/`aside_text`/`footer`.
- **The honest route to line labels: Mistral's chat models, not OCR.** Send the page image plus numbered Azure lines to a vision model (Mistral Small 4 `mistral-small-2603` $0.15/$0.60 per M tokens, Medium 3.5 $1.5/$7.5, [pricing, official](https://docs.mistral.ai/inference/pricing)) with a JSON schema. That is the Gemini Flash job done by a different vendor: comparable and cheap, but it has nothing to do with the OCR annotation feature.

## 3. Pricing (official, 2026-10-14)

| What | Price per 1,000 pages | Source |
|---|---|---|
| OCR (`mistral-ocr-4-1`), includes blocks and confidence | **$4** | [pricing](https://docs.mistral.ai/inference/pricing), [card](https://docs.mistral.ai/models/ocr-4-1) |
| Annotated pages (any annotation format) | **$5** | same |
| OCR via Batch API (50% off) | **$2** | [news/ocr-4](https://mistral.ai/news/ocr-4); [batch doc](https://docs.mistral.ai/studio/batch-processing) says batch is 50% off and supports `/v1/ocr` with annotations |
| Annotated pages via batch | probably $2.50, **not stated anywhere** | — |
| EU/US regional endpoint | ×1.1, and **batch and files are not available there** | [regional inference](https://docs.mistral.ai/inference/regional-inference) |

At archive scale (1M documents, say ~15M pages) that is $30k batch OCR, or ~$37–75k with annotations. Gemini Flash line labels are ~$5 per 1,000 pages, about the same as annotated pages.

Older third-party prices ($1 per 1,000 pages OCR, $3 annotations, [the-decoder](https://the-decoder.com/mistrals-document-ai-extracts-text-from-documents-and-notes-with-high-accuracy/)) are from the 2025 models and are out of date.

## 4. Arabic

- **Self-reported.** Arabic is in Mistral's OCR language list "with strong expected performance" ([languages, official](https://docs.mistral.ai/resources/languages)). The OCR 4 post claims 170 languages and an internal "Crawl Multilingual" score of .98, with a Middle-Eastern group shown only in a chart and no Arabic figure; all competitor numbers are Mistral's own reproductions, called "directional" ([news](https://mistral.ai/news/ocr-4)). The 2025 launch table had 11 languages, none of them Arabic ([mistral-ocr, 2025-03-06](https://mistral.ai/news/mistral-ocr/)).
- **Independent (old model only).** The QARI-OCR paper, 2025-06-02, tested on 200 scanned traditional-print Arabic pages. It found Mistral OCR (API, the 2025 model) at CER 0.210, WER 0.440, BLEU 0.570, against QARI v0.2 at 0.061/0.160 and Tesseract 0.436 ([arXiv 2506.02295, Table 3](https://arxiv.org/html/2506.02295)). The authors are a competitor model's authors.
  - Mistral does not appear on KITAB-Bench or Misraj-DocOCR. Those are where Azure's Arabic numbers come from: KITAB CER 0.52, Misraj WER 0.44 (see `03_build.md`).
- **Independent, OCR 4.** On English (olmOCR-Bench) Mistral claimed state of the art but ranked #3 on the public board (already in `01_models.md`). **No independent Arabic result for OCR 4 or 4.1 was found.**
- **Annotations on Arabic/RTL**: no evidence at all, official or independent.
- **Anecdotes**:
  - "close to 99%" on Arabic PDFs ([SubtitleEdit issue #9900](https://github.com/SubtitleEdit/subtitleedit/issues/9900));
  - one blog's two Arabic PDFs: one empty, one good ([sonusahani.com](https://sonusahani.com/blogs/mistral-ocr));
  - the RTL column-order report above.

## 5. Terms, retention, region

- **Training our own models on outputs: allowed.** Commercial Terms, effective 2026-09-25 ([legal.mistral.ai](https://legal.mistral.ai/terms/commercial-terms-of-service)):
  - §3.1: the customer owns the Outputs.
  - §3.3: the only output restriction is "Customer may not use image Outputs to develop or train any image generation product that competes with a Mistral AI Product".
  - §2.2(d)–(e): Outputs may not be used to reverse-engineer Mistral's products or weights.
  - Text and JSON outputs used to train a layout model are not restricted.
- **Mistral's training on our data.** §4.2: not used except under listed exceptions (opt-in/opt-out settings, feedback). Labs and preview models are an exception, and opt-out does not apply to them (§4.3).
- **Retention.**
  - Default: API inputs and outputs kept 30 days for abuse monitoring (privacy policy as quoted by [Open Terms Archive](https://opentermsarchive.org/en/memos/mistral-ai-retains-api-prompts-and-outputs-for-30-days/), secondary).
  - **Zero data retention** covers `/v1/ocr` but **not** batch files or `/v1/files`. It is paid plans only, on request, and "may approve or deny" ([ZDR, official](https://docs.mistral.ai/admin/monitor-comply/zero-data-retention)). So the cheap batch route cannot be zero-retention.
  - Uploaded files are kept 30 days unless deleted ([known limitations](https://docs.mistral.ai/resources/known-limitations)).
- **Region.** "The Mistral API is served from EU data centers by default" ([known limitations](https://docs.mistral.ai/resources/known-limitations)). The newer regional-inference page says the global endpoint makes no location commitment, and the EU/US endpoints cost +10% and have no batch ([regional](https://docs.mistral.ai/inference/regional-inference)). These two pages disagree a little. Self-hosting is a single container for enterprise customers, price on request ([news](https://mistral.ai/news/ocr-4)).

## 6. Limits and inputs

- **Inputs**:
  - `document_url` (a public URL; PDF, DOCX, PPTX…);
  - `image_url` (URL or base64 data URI; PNG, JPEG, AVIF…);
  - base64 PDF;
  - an uploaded file id.

  Formats for OCR: PDF, PNG, JPG, JPEG, TIFF, BMP, GIF, WEBP ([basic OCR](https://docs.mistral.ai/studio/document-processing/basic_ocr), [known limitations](https://docs.mistral.ai/resources/known-limitations)).
- **Size.** The Annotations FAQ says files "must not exceed 50 MB … no longer than 1,000 pages". The known-limitations page says file uploads may be up to 512 MB. The 50 MB / 1,000-page OCR limit is the safe reading.
- **Batch**: up to 100,000 requests and 512 MB per batch file, results kept 24 h, does not count against real-time rate limits.
- **Rate limits**: per organization and tier, requests/second and tokens/minute; the numbers are shown only in the admin console. **No public number for OCR.**

## What the cheap test would look like (not run, needs the owner's OK and a Mistral key)

Pages are the 44 test pages of experiment 39 (Gemini 3.1 Pro referee labels, 2,075 lines). For each page, send the page image (JPEG, base64) once to `/v1/ocr`, `mistral-ocr-4-1`, with:

- `include_blocks=True`, `confidence_scores_granularity="block"`, `table_format="html"`;
- `bbox_annotation_format`: a JSON schema for {kind: photo/drawing/chart/map/table-image/ornament/logo, has_text, caption_ar, description_ar};
- `document_annotation_format`: {title, subtitle, authors[], affiliations[], abstract_ar, abstract_en, keywords[], journal, volume, issue, year, pages} (filled only where the page holds them).

Score it three ways:

1. **Line labels.** Map Mistral types to ours:

   | Mistral type | Our label |
   |---|---|
   | text | body |
   | title | heading |
   | list | list |
   | references | references |
   | caption | caption |
   | table | table |
   | equation | equation |
   | header, footer | furniture |
   | aside_text | footnote? furniture? (decide by looking) |
   | image, code, signature | other |

   Drop it into `score_yolo.py` beside dots.mocr (84.4%), the round-1 model (87.7%) and model+dots (92.1%). Also note its block reading order on the two-column pages, and whether its markdown text is worth a side glance against Azure.
2. **Pictures.** Look by eye at its image crops and annotations on the pages with figures, and count missed or invented pictures.
3. **Whole document.** Run a further ~40 first pages, one per yardstick document (experiment 34). Compare the document JSON with the yardstick's front-matter, or with what Gemini gives on Azure text.

Cost:

| Item | Cost |
|---|---|
| 44 + ~40 pages at $5 per 1,000 annotated pages | ≈ **$0.45** |
| Optional chat-model line labeller on the 44 pages (Medium 3.5, page image + Azure lines, ~5–10k tokens in and ~3k out a page) | ≈ $1–2 |
| **Cap** | **$3** |

No GPU is needed. Use the synchronous endpoint, not batch, so that ZDR could apply and results come back at once.

## Could not confirm

- The batch price for *annotated* pages (only OCR batch, $2, is stated).
- Whether document annotation has a hard page cap. The FAQ names only "8 image bounding boxes", and the examples use 8 pages.
- Whether document annotation sees page images at all, beyond the 8 image crops. The docs say markdown plus crops.
- OCR rate limits (console only).
- Whether the RTL two-column ordering bug (2026-09-17 report) still exists in 4.1.
- Any Arabic accuracy number for OCR 4/4.1, and any test of annotations on Arabic.
- Whether `api.eu.mistral.ai` serves `mistral-ocr-4-1`.
