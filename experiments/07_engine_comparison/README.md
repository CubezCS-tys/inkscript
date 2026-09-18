# 07 — The same pages, three text layers, one reader

Three scanned test-set documents; each PDF read with pdfium (Chrome's engine,
build 7947). The reference is the words and lines our layer placed: Azure's
reading on pages 2+, Gemini's on page 1, lines by ink position. "Words
intact": a reference word comes back whole. "Lines in order": a reference
line's Arabic words come back contiguous, in reading order, inside one line.

    ocrmypdf -l ara --force-ocr input.pdf out.pdf      (Tesseract 5, `ara`)
    python compare_engines.py <scratch> 0582-004-009-012 0655-015-003-009 0690-012-001,012-028

| document | layer | words intact | lines in order |
|---|---|---|---|
| 0582-004-009-012 | inkscript | 1246/1246 (100.0%) | 113/113 (100.0%) |
| | Azure searchable PDF | 1232/1246 (98.9%) | 58/113 (51.3%) |
| | ocrmypdf | 1058/1246 (84.9%) | 12/113 (10.6%) |
| 0655-015-003-009 | inkscript | 1530/1530 (100.0%) | 137/137 (100.0%) |
| | Azure searchable PDF | 1494/1530 (97.6%) | 103/137 (75.2%) |
| | ocrmypdf | 1241/1530 (81.1%) | 20/137 (14.6%) |
| 0690-012-001,012-028 | inkscript | 1483/1485 (99.9%) | 121/123 (98.4%) |
| | Azure searchable PDF | 1422/1485 (95.8%) | 42/123 (34.1%) |
| | ocrmypdf | 920/1485 (62.0%) | 2/123 (1.6%) |

Read it carefully:

- For Azure's own PDF the comparison is fair on words (its layer holds the
  same words as ours on pages 2+): the gap is how Chrome reads the layer
  (one word per positioned `Tj`, no bidi-aware storage), and it shows most
  in line order.
- For ocrmypdf the words column mixes two things — Tesseract reads the
  page differently from Azure, and its layer is structured differently —
  so it is not a claim about Tesseract's recognition. The lines column is
  still telling: one word per positioned run, in visual order, and Chrome
  cannot rebuild the line.
- Selection behaviour (what a drag selects, whether a word's ink is its
  own glyph) is not measured here; that is the part no other layer has.
