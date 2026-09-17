# inkscript

Ink as geometry, geometry as a font, the scanned page as native text.

A scanned Arabic journal page goes in. A PDF comes out in which every printed
word is a real glyph whose outline is the word's own ink, mapped to its text:
the selection highlight sits on the letters, copy gives the words with their
vowel marks, search works, and the vector version needs no image at all.

Two halves, one meeting point — see [docs/pipeline.md](docs/pipeline.md):

- **OCR** (`inkscript.ocr`): Azure Document Intelligence for words and boxes,
  Gemini re-reading page 1 where titles and authors are, aligned into Azure's
  boxes even when the two engines read the page in a different order.
- **Geometry** (`inkscript.geometry`): every mark on the page traced as an
  outline; a shape alphabet across pages.
- **PDF** (`inkscript.pdf`): the two combined into Type 3 fonts, written by
  rules verified against Chrome's engine — [docs/pdf-writing-rules.md](docs/pdf-writing-rules.md).

## Setup

```
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env        # add GEMINI_API_KEY
.venv/bin/pytest            # ~30 s, runs the whole pipeline on one bundled document
```

## Use

```
inkscript native --azure-dir DATA/azure --scan-dir DATA/input \
    --frontpage-dir OUT/frontpage --out OUT/native --vector --verify
```

`inkscript --help` lists the five commands. `tests/fixtures/` holds one real
document (five pages) so the tests and a first run need no data setup.

## Status

30-document test set, 115 pages: 98.5% of words copy out intact in pdfium,
0 reading-order inversions. Selection is per word. Every glyph is the
printed occurrence's own outline, stored in scan pixels; the document's shape
alphabet is exported beside the PDF and never substituted into it. `experiments/` keeps the
numbered scripts that established the geometry results, verbatim.

`docs/demo/ink_to_text.html` is a self-contained animation of the idea.
