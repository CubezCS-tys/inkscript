# Experiment 99 — LiteParse options, fixed BEFORE the exam run (2026-11-24, 04:20 Riyadh)

Chosen from LiteParse's docs and from 5 dev articles outside the exam (`DEV_STEMS.json`: 0013-028-004-001,
0097-040-002-003, 0246-016-001-006, 0840-000-015-002, 1001-012-002-003; page 1 and the middle page of each, 10 pages).
Nothing below was looked at on an exam article before the exam run.

LiteParse 2.21.1 (pip `liteparse`, Python API `LiteParse(...)`, same options as the `lit` CLI), in its own venv
`out/venv`; run by `scripts/run_lit.py` through `scripts/litrun.sh` (sandbox env, strace, /usr/bin/time).

| Mode | Input | Options |
|---|---|---|
| `text` | the S3 PDF (all 60 local) | `ocr_enabled=False, extract_blocks=True, emit_word_boxes=True, num_workers=4, target_pages=<exam pages>`; ocria-nano package installed, so its LayoutNet table model runs (the docs: it runs whenever the package is present, also with OCR off) |
| `text_apache` | the S3 PDF | the same, with `LITEPARSE_MODEL_DIR` pointed at an empty folder: pure Apache-2.0 LiteParse, rule-based tables only |
| `tess` | the 300-dpi page JPEG (no text layer exists in an image) | `ocr_backend="tesseract", ocr_language="ara+eng", dpi=150` (default), tessdata_best `ara` + `eng` in `out/tessdata` |
| `nano` | the 300-dpi page JPEG | `ocr_backend="ocria-nano", dpi=250` (default); `ocr_language` is ignored by this backend |

Why (dev pages, word F1 of LiteParse's words against Azure's words on the same page, order-free; Azure is ~1% wrong,
enough to rank options; `out/dev/options_summary.json`):

| Candidate | Word F1 vs Azure (10 dev pages) | s / page |
|---|---|---|
| Tesseract ara, 150 dpi (default) | 0.861 | 5.5 |
| Tesseract ara, 200 dpi | 0.858 | 4.8 |
| Tesseract ara, 300 dpi | 0.846 | 5.5 |
| Tesseract ara+eng, 300 dpi | 0.845 | 9.2 |
| **Tesseract ara+eng, 150 dpi** | **0.872** | 8.3 |
| **ocria-nano, 250 dpi (default)** | **0.683** | 2.1 |
| ocria-nano, 200 dpi | 0.682 | 2.0 |
| ocria-nano, 300 dpi | 0.670 | 2.2 |

`ara+eng` costs time but rescues the English pages (one dev page 0.72 -> 0.94); the default DPIs were best.
Not used: `--ocr-server-url` (never), `keep_clipped_text`, `preserve_very_small_text` (no reason found on dev),
`extract_text_metadata`.  Telemetry: LiteParse documents none; `ORT_DISABLE_TELEMETRY=1` set for ONNX Runtime.
