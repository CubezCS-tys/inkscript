# Why this exists

The owner's own words, kept verbatim because they have steered every design
choice (spelling as typed).

**The idea (2026-09-17).** "my type of OCR that I'm trying to achieve is
different from the conventional way of just text extraction into a standard
filetype, I'm trying to achieve perfect digitisation … all the letters are
permanent objects and a liquid is going around them and creating an outline
and somehow I want each letter or word stored as a number so that I can
recreate the font and then have the text as my own geometry numbers which
could be a better medium for LLMs to try and help digitise the document."

**The dream, in one sentence (2026-09-17).** "I want to be able to take an
image PDF such as 0582-004-009-012 and be able to select and copy text as if
it was a native English text PDF."

**The constraint (2026-09-17).** "our goal is to keep absolute accuracy
towards the document."

**The output that matters (2026-09-20).** "I'd still want the vector PDFs to
be the output because that's the PDF feel I want, to have the original font
be the text."

**On restoration (2026-09-20).** "maybe we should also be enhancing the font
to make up for the broken pieces in the scans."

## What those became

| In their words | In the repo |
|---|---|
| liquid going round the letters, an outline | every mark traced as a polygon (`geometry/trace.py`), 97% of the ink reproduced |
| each letter or word stored as a number; recreate the font | the document's shape alphabet (`geometry/alphabet.py`, `<stem>.shapes.json`), and the typeface export (`experiments/11_typeface`) |
| select and copy as if native | Type 3 glyphs of the ink itself, written by rules measured against Chrome (`pdf/type3.py`, `docs/pdf-writing-rules.md`) |
| absolute accuracy | every occurrence drawn with its own outline; nothing substituted in the faithful PDF |
| feel the strokes written on your back | letters cut along the pen path (`geometry/penpath.py`) |
| a database of the letters' strokes | the document's own letter atlas; matching against stored examples (`experiments/10_atlas_reader`) |
| make up for the broken pieces | restored glyphs voted from many printings (`experiments/11_typeface`); a restored edition is an open idea |

The corpus is Mandumah's scanned Arabic journals (`s3://mandumah-source-docs/<id>/`),
each already read by Azure Document Intelligence. Page 1 (title, author) is
re-read by Gemini, because that is where Azure fails most and where it matters
most.
