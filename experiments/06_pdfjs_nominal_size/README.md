# 06 — Firefox (pdf.js) and the nominal font size

pdf.js infers word spaces from the pen's jumps relative to the font size
(`SPACE_IN_FLOW_MIN_FACTOR` 0.102, `SPACE_IN_FLOW_MAX_FACTOR` 0.6 in
`evaluator.js`): a jump under 0.102 × size adds no space, one over 0.6 × size
starts a new text item, and items come out in stream order, so a
right-to-left line broken into items copies out with its halves swapped.
pdfium (Chrome) does not depend on the nominal size at all.

Run (needs `npm i pdfjs-dist@4` next to `words.mjs`):

    python size_experiment.py <scratch-dir> "doc1+doc2" 8 16 24 -8

Negative sizes select `SIZE_MODE = "gap"` (per-line size from the widest
word gap). Measured on three test-set documents, pdfium 7947:

| nominal size | pdfium words intact | pdf.js words intact | pdf.js lines same as Chrome / reversed |
|---|---|---|---|
| 8 pt (current) | 100.0% | 95.1% | 2% / 27% |
| 16 pt | 99.9% | 94.0% | 48% / 0% |
| 24 pt | 99.9% | 92.6% | 48% / 0% |
| per-line from widest gap, min 8 | 99.9% | 94.1% | 33% / 0% |
| per-line from widest gap, min 16 | 99.9% | 93.8% | 49% / 0% |

(final writer, 2026-09-18 morning; the single-column fixture alone reaches
86% of lines at 24 pt.) The other half: pdf.js merges word gaps under
0.102 × size (`أدخلهاعلى`), and a word written as pieces (right to left in
the stream, as pdfium wants) moves the pen backwards by more than
0.2 × size, which starts a new item — so piece-heavy documents break up.
Decision: keep 8 pt. Every larger size costs pdfium 0.1% of words, and
pdf.js loses words faster than it gains line order. A Firefox-specific
build would need its own piece order; not worth it while Chrome is the
target.
`items.mjs` prints pdf.js's text items with positions for one page.
