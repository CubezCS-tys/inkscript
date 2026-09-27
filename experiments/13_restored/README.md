# 13 · The restored edition: the page reset in the book's own typeface

**Question.** The faithful PDFs cannot feel like a born-digital journal article
— by construction. D3 forbids reusing a glyph, so every occurrence carries its
own traced outline and a page costs ~500 KB. A native file
(`DuffyCN.pdf`, QuarkXPress → Distiller, the owner's reference) is 15 KB a page
*because* it reuses glyphs. Fidelity and that kind of cleanliness are the same
property with opposite signs.

So: can the third output named in [ideas.md](../../docs/ideas.md) — same page,
same layout, letters drawn from the document's own restored font (experiment
11) — be made, and does it feel native?

**Method.** `make_page.py` takes a built document's `shapes.json` (every word's
text and box), groups the words into lines, and sets each line in the restored
TTF at the place the scan has it, through MuPDF's layout engine (which shapes
Arabic). One embedded font, glyphs reused, no image.

```
python make_page.py experiments/09_pen_path/out/build 0582-004-009-012 --page 2 \
    --font experiments/11_typeface/out/Inkscript-0582-Restored.ttf
```

## Result

**It looks right.** `out/scan_vs_restored.png` — the scan beside the restored
page. Same face, same layout, paragraphs, footnotes, page number; it reads as a
typeset page rather than a traced one.

| | DuffyCN (born-digital) | restored edition | faithful vector | Azure |
|---|---|---|---|---|
| KB per page | 15 | **157** | 522 | 101 |
| images | none | **none** | none | 1 bitmap |
| fonts | 9 real subsets | 1 restored + subset fallbacks | 88 Type 3 | 1 |

**And it is broken in Chrome.** pdfium reads every word reversed — `وان` comes
back `ناو` — while MuPDF reads it correctly. A naively typeset Arabic PDF does
not survive Chrome's bidi reconstruction. This is precisely what
`text.visual()` exists for ([pdf-writing-rules.md](../../docs/pdf-writing-rules.md),
"Glyphs"), and it is why the restored edition cannot be finished with a layout
engine alone: it needs this repo's own writer, storing the text in the form
pdfium inverts, with the restored font's glyphs in place of traced outlines.
Words intact in pdfium: **23%**. The faithful build of the same page: 100%.

That is the finding worth keeping. The look is a day's work with any layout
engine; the text layer is not, and the measured Chrome rules are the part of
this project nothing else supplies.

## What it changes

The restored edition moves from an idea to a half-built output with a known
remaining piece: `pdf/type3.py`'s writer, emitting the restored font's glyph
ids with `text.visual` storage, instead of MuPDF's story engine.

## Known faults of the prototype

Footnote lines collide; the page number lands left instead of centred; lines
set wider than the printed ones (the restored face has its own metrics), so a
line may run past the original margin. Most of the 157 KB is *fallback* fonts:
the restored font has no digits or punctuation
([typeface.md](../../docs/typeface.md), known faults), so the engine embeds Noto
subsets for them. Giving the book's font its own digits would take the page
close to DuffyCN's 15 KB.

Four shapes were tried before the one that worked, and the reasons are in the
code comments: sizing each word to its own box, letting the engine shrink each
word to fit, pinning each word at the scan's x with a uniform size, and setting
whole lines into boxes that could wrap.
