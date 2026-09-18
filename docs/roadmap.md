# Roadmap

Written 2026-09-18 after the first corpus-scale test. Ordered by what each
step buys for the goal: a faithful, natively selectable digital copy of
every page, with the accuracy of the text improving over the OCR it started
from.

## Where it stands

- Scans in the corpus are Azure's searchable PDFs; born-digital journals
  exist too and are left alone. Both handled.
- 30-document test set and 47 corpus documents (1,007 pages) build end to
  end. Numbers in `docs/pdf-writing-rules.md`.
- Chrome's engine is the verification target; MuPDF and poppler are
  measured but disagree with it on vowelled text.
- (2026-09-18, night) Chrome's line reconstruction is now known from
  pdfium's source and emulated (`text.chrome_reads`); the stored text is
  its exact inverse, and `--verify` reports words intact, **lines in
  order**, in-column inversions and pages that lost their image.
  pypdfium2 is pinned to the build that reads like Chrome (see
  `docs/pdf-writing-rules.md`, "History"). Two writer defects that the
  old checks could not see were found and fixed the same night: pages
  inheriting `/Resources` lost their image (98 of 224 night documents);
  scanner content ending in an unbalanced `cm` mirrored every word.

## Next, in order

1. **Corpus sample at real scale.** 500–1,000 documents drawn evenly
   across journals, built and checked unattended; read the per-page
   report for anything under 97% or with inversions. Every failure mode
   so far was found this way, not by reasoning. Cost: ~$0.005 per document
   for Gemini page 1.
2. **Make the review list useful.** `inkscript check` finds contradictions
   and lists numbers; turn that into crops (the word's ink, the two
   readings) that a person can judge in seconds, and a way to write the
   corrected text back into the PDF's ToUnicode without rebuilding.
3. **Second reading for numbers and contradictions only.** Send just those
   crops to Gemini (a few per page) and accept a correction only when the
   two readings agree. Cheap, and it targets the errors that matter.
4. **Letter-level selection inside a connected run.** The remaining
   selection limit. Needs join detection along the baseline, its own
   verification design (a wrong cut is a wrong answer, not a fallback),
   and pdfium's per-glyph behaviour kept in mind: only unvowelled words
   can carry it.
5. **Other viewers.** Firefox (pdf.js) measured (`experiments/06`): words
   come back intact (95%) but lines copy out word-reversed at the 8 pt
   nominal size, because pdf.js splits a line into items at any pen jump
   over 0.6 × size and keeps items in stream order; a 16–24 pt nominal
   size fixes about half the lines with no effect on Chrome. Decide
   whether to adopt it after the other half is understood. Apple Preview
   untested.
6. **The typeface.** Export the document alphabet as an installable font
   (OpenType via fontTools) once letter-level pieces exist; until then the
   SVG specimen is the honest form.

## Standing rules

- Every glyph is the printed occurrence's own outline, stored in scan
  pixels. No substitution, no simplification.
- No rule about the text layer is adopted on reasoning alone; each is
  measured against pdfium, MuPDF and poppler and recorded in
  `docs/pdf-writing-rules.md` with the number that justified it.
- The word stays one glyph whenever splitting would require a guess.
