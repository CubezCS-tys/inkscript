"""labocr — experiment 75's own-software OCR lab (a bounded experiment module; the Azure + Gemini pipeline is untouched).

Separate tasks, separate scores: recognition (text), layout (regions), reading order, structure, extraction.
Raw engine output is kept verbatim; `raw_text` is never overwritten; pages are one-based; boxes are top-left pixel
boxes [x0, y0, x1, y1) on a declared canonical render.  See ../README.md.
"""
SCHEMA_VERSION = "labocr/1"
PROTOCOL_VERSION = "labocr-jsonl/1"
INGEST_VERSION = "ingest/1"
