# inkscript

Ink as geometry, geometry as a font, the scanned page as native text.

A scanned Arabic journal page goes in. A PDF comes out in which every printed
word — and, within it, every letter — is a real glyph whose outline is its own
ink, mapped to its text:
the selection highlight sits on the letters, copy gives the words with their
vowel marks, search works, and the vector version needs no image at all.

Two halves, one meeting point — see [docs/pipeline.md](docs/pipeline.md):

- **OCR** (`inkscript.ocr`): Azure Document Intelligence for words and boxes,
  Gemini re-reading page 1 where titles and authors are, aligned into Azure's
  boxes even when the two engines read the page in a different order.
- **Geometry** (`inkscript.geometry`): every mark on the page traced as an
  outline; a shape alphabet across pages; joined words cut into letters along
  the pen path, judged by the document's own alphabet — [docs/letters.md](docs/letters.md).
- **PDF** (`inkscript.pdf`): the two combined into Type 3 fonts, written by
  rules verified against Chrome's engine — [docs/pdf-writing-rules.md](docs/pdf-writing-rules.md).

## Setup

```
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env        # add GEMINI_API_KEY
.venv/bin/pytest            # ~3 min, runs the whole pipeline on one bundled document
```

## Use

```
inkscript native --azure-dir DATA/azure --scan-dir DATA/input \
    --frontpage-dir OUT/frontpage --out OUT/native --vector --verify
```

`inkscript --help` lists the commands (`fetch` pulls documents from the corpus bucket; `check` writes a review list from the shape alphabet). `tests/fixtures/` holds one real
document (five pages) so the tests and a first run need no data setup.

## Status

Measured 2026-09-20 on 227 journals (4,440 pages): 99.99% of words copy out
intact in Chrome's engine, 99.95% of lines in reading order, and on the
scanned documents **96.8% of words have a selection box for every letter**.
The text is the OCR's reading; making it trustworthy is the next milestone.
Numbers with their dates, and what the PDFs do not do: [docs/STATUS.md](docs/STATUS.md).

## Finding your way

[CLAUDE.md](CLAUDE.md) is the entry point for people and agents alike;
[docs/README.md](docs/README.md) maps the documentation: the owner's vision,
every idea and its fate, the decisions and their evidence, how letters are
cut, the typeface, running at scale, a glossary. `experiments/` holds the
numbered experiments, each a question with its answer.

`docs/demo/ink_to_text.html` is a self-contained animation of the idea;
`docs/storyboard/` an interactive storyboard built from real outputs (it
predates letters and the typeface).
