# Experiments

Each answers one question with a number. 01–05 are kept verbatim from before
the package existed (they import the old script layout and are not
maintained; `inkscript trace` and `inkscript alphabet` are their reproducible
forms). 06 onward run against the package. Outputs go to each experiment's
`out/` (gitignored).

| # | Question | Answer | Became |
|---|---|---|---|
| 01 | Can a page's ink be traced as outlines, and do shapes recur? | 97.4% of the ink reproduced; 310 shapes for 735 blobs | `geometry/trace.py`, `alphabet.py` |
| 02 | Does the shape alphabet saturate across pages? | Within a document yes; it resets between documents | one alphabet per document |
| 03 | Is the reset a matcher fault? | No — a different type weight is a different alphabet | — |
| 04 | If shapes are labelled once, how pure are the groups? | Strict groups 99.8% consistent, covering 36% of words | alphabet as knowledge, never as drawing (decision D3) |
| 05 | Can a page be written as a Type 3 font of its own ink? | Yes (page 1) | `pdf/type3.py` |
| [06](06_pdfjs_nominal_size/README.md) | Why does Firefox copy lines word-reversed? | pdf.js infers spaces from pen jumps relative to font size; a larger size fixes half and costs pdfium 0.1% | 8 pt stays (D6) |
| [07](07_engine_comparison/README.md) | How do we compare with Azure's PDF and ocrmypdf? | Lines in order: 98–100% vs 34–75% vs 2–16% | STATUS |
| [08](08_letter_joins/README.md) | Can letters be cut at columns? | Free alignment no better than Chrome's equal slices (90.9% vs 91.6%); only real joins are worth cutting | D7, then superseded by 09 |
| [09](09_pen_path/README.md) | Can letters be cut along the pen path, judged by the document's own alphabet? | Yes: 96.8% of words fully letter-selectable on 194 scanned documents, text unchanged | `geometry/penpath.py`; its scripts are the letter tooling |
| [10](10_atlas_reader/README.md) | Can the document's atlas read a page with no OCR text? | 41% of pieces (isolated letters 67%, joined ~20%); stored examples beat mean pictures | the "checker" idea (milestone 1) |
| [11](11_typeface/README.md) | Can a book's letters become a font you can type with, better than any one printing? | Yes, two books; and the font exposes systematic cutting errors | typeface.md; two cutter fixes |
