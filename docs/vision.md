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

## A second branch: the open reading stack (2026-10-11)

The ink-as-text vision above is **still alive**. The owner added a second
branch in the same direction, document digitisation, and is keeping both until
it is clearer which way to take the first. In their words:

**The shift (2026-10-11).** "I no longer want to rely on azure or stuff like
that and want to move a bit more open source, and sort of build the whole
stack myself and get the most accurate OCR and output at the same time … not
have the perfect font or whatever but is to keep the accuracy of text
equations, tables as accurate as possible and having this in some sort of
file format."

**The goal (2026-10-11).** "say there is this old newspaper from the Arab world
… I basically want to take it and recognise every letter and every word and
rework the formatting if need be … once the document is understood it can
re-adjust where things go but still have a native format at the end."

**Who it is for.** "literally everyone, when you see an english paper of
research it can be read online, printed, trained etc so it needs to have that
same functionality." The print edition stays "as close to the original as
possible", tested with a model as a judge.

Agreed in the same conversation:
- Every word keeps a box on the scan, so it can be proven.
- Vowel marks are recorded exactly as printed; search ignores them.
- Equations and tables are rare in the archive but a priority.
- "Most accurate" must hold on public Arabic benchmarks and on a hand-checked
  Mandumah set.
- All papers and decades are in scope ("throw everything at it").

How it is being built: [experiments/32_open_stack](../experiments/32_open_stack/README.md)
(research and plan). An open line reader (Kraken, fine-tuned on Mandumah's own
pages) is the main text engine and gives every line's position. A VLM is the
specialist for tables, equations and layout, and a second reading. The
project's checks (Quran, judge, trust marks) referee between them. The master
files stay JATS + ALTO, and every edition is derived from them.

### Reframed: Azure's text, our own document parser (2026-10-12)

After experiments 33 and 36, the owner kept Azure's text and moved the work to what is built on top of it:

> "Azure is what we have to be dependent on for now because we've already got all the text from all the OCR that we've done. I've OCR'd, I think, more than a million documents that are sitting in S3."

> "Now what I want to get is the ability to recreate the documents using vision language models or LLMs ... and just to be able to understand and correct at the same time what the document's actually trying to say. We become an augmenter, our own sort of document parser. ... We respect the layout. We respect the images. We respect the equations."

Why it matters to them:

> "lets contiue builkding the best product for academics in the middle east who have been treated as second calss when it comes to their digital documnts and whole internt experince"

The stack (experiment 38):
1. dots.mocr finds the layout.
2. Azure's words go into it.
3. Tables, equations and images are rebuilt.
4. Correction happens only where the scan supports it, with every change logged.
5. Kraken flags missing text.
6. JATS + ALTO masters, and every edition built from them.

The ink-as-text vision stays alive beside it.
