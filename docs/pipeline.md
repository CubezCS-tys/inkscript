# The two halves

```
 scan.pdf ─┬─► OCR (Azure words+boxes; Gemini re-reads page 1) ──► what each word SAYS
           │                                                            │
           └─► GEOMETRY (binarise → ink blobs → outline polygons) ──► what each mark IS and WHERE
                                                                        │
                                   pdf/  (blobs → word boxes → Type 3 glyphs → text runs)
                                                                        ▼
                                        <stem>.pdf  scan + selectable ink glyphs
                                        <stem>_vector.pdf  the glyphs alone
```

| part | package | reads | writes |
|---|---|---|---|
| OCR | `inkscript.ocr` | Azure JSON, scans, Gemini | page-1 text per box, searchable PDF (older path) |
| Geometry | `inkscript.geometry` | scans | outline polygons, shape alphabet, blob→word layout |
| Meeting point | `inkscript.pdf` | both | ink-glyph PDFs |
| Checks | `inkscript.verify` | PDFs | pdfium/MuPDF/poppler numbers |
| Review | `inkscript.viewer` | outputs | static HTML bundles |

## Typical run

```
inkscript frontpage --azure-dir DATA/azure --scan-dir DATA/input --out OUT/frontpage --verify
inkscript native    --azure-dir DATA/azure --scan-dir DATA/input --frontpage-dir OUT/frontpage --out OUT/native --vector --verify
inkscript compare   --frontpage-dir OUT/frontpage --azure-dir DATA/azure --out OUT/review --zip
inkscript trace     --pdf DATA/input/<stem>.pdf --page 1 --out OUT/trace
inkscript alphabet  DATA/input/*.pdf --pages 5 --out OUT/alphabet.json
```

`DATA/azure/<stem>/<stem>.json` + `<stem>.pdf` are Azure prebuilt-read outputs;
`DATA/input/<stem>.pdf` the image-only scans. Data never lives in the repo.

## What the geometry does not do yet

- Share one glyph per repeated shape across a document (the alphabet
  saturates within a document; different type weights are different
  alphabets). Today each page carries its own outlines — hence file size.
- Letter-level glyphs (Arabic joins letters; a blob is a sub-word).
- Read on its own: labels come from the OCR half. See
  `experiments/04_label_once_purity.py` for the measurement that frames it:
  strict shape groups are 99.8% consistent, but two-thirds of a page's
  words are shapes that appear once.
