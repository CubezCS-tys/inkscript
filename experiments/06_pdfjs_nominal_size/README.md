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
| 8 pt (current) | 99.9% | 95.2% | 1% / 28% |
| 16 pt | 99.8% | 92.6% | 48% / 0% |
| 24 pt | 99.8% | 92.6% | 49% / 0% |
| per-line from gap | 99.8% | 92.7% | 44% / 0% |

The other half of the lines differ from Chrome's for reasons not yet
separated (pdf.js merges tight word gaps, joins lines differently). Not
adopted: Chrome is the target and the words-intact figure drops in pdf.js.
`items.mjs` prints pdf.js's text items with positions for one page.
