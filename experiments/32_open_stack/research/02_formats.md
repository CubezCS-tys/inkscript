# What file should a faithful digitised article be kept in?

Research note for experiment 32 (open OCR stack). Question: in what format(s)
should a scanned Arabic scholarly article be stored so that **text, equations
and tables survive exactly**, right-to-left works, and anything else can be
made from it later? Web research done 2026-10-11; sources are linked inline
and listed at the end. Things I could not confirm from a primary source are
marked *(unverified)*.

## In ten lines

1. No single file does everything. Everyone serious keeps **one file for the article** (what it says, in what order, with its maths and tables) and **one for the page** (where every word sits on the scan), plus the scan itself.
2. For the article, the journal world's answer is **JATS XML** (NISO Z39.96-2024, v1.4). PubMed Central, Portico and the Library of Congress all name it; LoC lists it as the *preferred* format for electronic serials.
3. For the page, libraries use **ALTO XML** (BnF Gallica, LoC's newspapers, Europeana) or **PAGE XML** (OCR research, ground truth); both store each word's box and confidence.
4. inkscript already writes exactly this pair (JATS 1.4 + ALTO 4.4, decision D20). **The research says keep it**, and fill the two holes it has today: equations and tables.
5. **Equations**: OCR models write **LaTeX**; browsers, PDF/UA-2 and JATS read **MathML**. Keep both side by side in JATS `<alternatives>` (LaTeX as the model read it, MathML for display, a crop of the scan as the witness). MathML has a `dir="rtl"` switch for Arabic-style maths; LaTeX has no standard for it.
6. **Tables**: store them as **XHTML-style tables inside JATS** (`rowspan`/`colspan`, header rows). That is the same tree that table accuracy (**TEDS**) is scored on, so the stored file can be graded directly. Markdown tables cannot hold merged cells, so Markdown cannot be the master.
7. Right-to-left: store cells and words in **reading order** (first cell = rightmost on the page) and say so once in the file; direction comes from `xml:lang="ar"` and Unicode, because JATS has no `dir` attribute.
8. Provenance (which model read what, its confidence, the link from each word to its box) lives in ALTO (`WC`, `ALTERNATIVE`, `Processing` steps) and in ids shared by both files.
9. Everything else is **made from the master, never edited by hand**: HTML+MathML for reading, Markdown+LaTeX for search/LLMs, the faithful PDF, a IIIF manifest for viewers, DoclingDocument JSON or TEI if someone asks.
10. Not recommended as master: Markdown (loses spans, boxes, ids), DoclingDocument/DocTags (a tool's internal format, changes with versions), hOCR (page only), PDF (a rendering, not a record).

## Recommendation

**Master (the files that are the record):**

| File | What it holds | Why this one |
|---|---|---|
| the scan (TIFF or lossless JP2, unchanged) | the evidence | every other file points back to it; libraries keep it forever ([HathiTrust/CDL](https://cdlib.org/hathitrust/submission-guidelines), [NDNP](https://loc.gov/ndnp/guidelines/archive/guidelines2021.html)) |
| `<stem>.jats.xml` — JATS 1.4 *Archiving*, MathML3 flavour (already written) | the article: front matter, sections, paragraphs in reading order, footnotes, references; **new:** every equation as `<alternatives>` (MathML + LaTeX + crop), every table as an XHTML table with spans, ids on every cell | the publishers' and archives' format for journal articles; LoC "preferred" for e-serials; PMC and Portico normalise everything into it |
| `<stem>.alto.xml` — ALTO 4.4 (already written) | the page: blocks, lines, words with boxes, confidence, alternative readings, processing history; **new:** one block per table cell and per equation, pointing at the JATS id | the libraries' format for OCR with coordinates (BnF, LoC, Europeana) |
| a small package wrapper (BagIt directory, or METS) *(new, optional)* | checksums, which file is what, versions of models and code | HathiTrust and NDNP both ship page images + OCR + checksums as one package |

**Derived (re-made by a script at any time, never edited):**

- `<stem>.html` — HTML5 with `dir="rtl"`, native MathML and real tables: what a person reads in Chrome; Chromium renders MathML Core by default since early 2023 ([W3C Math WG charter 2026](https://www.w3.org/Math/Documents/Charter2026.html)).
- `<stem>.md` — Markdown with `$…$` LaTeX and HTML tables (olmOCR's own convention): for search indexes and LLMs.
- the faithful vector PDF (inkscript's own product); later PDF/UA-2 tags with MathML ([PDF Association](https://pdfa.org/iso-14289-2-pdfua-2/)).
- IIIF Presentation 3 manifest + word-level Web Annotations (for Mirador/Universal Viewer, like Europeana and QDL).
- On request: DoclingDocument JSON (to feed tools that speak Docling), TEI P5 (for digital humanities partners), EPUB 3.

**Why not change course.** The alternatives each lose something the owner cares about: Markdown loses merged cells and every box; Docling's JSON keeps boxes and spans but is a library's internal model with no standards body and no MathML; PAGE XML is better than ALTO for tables and reading order but describes only the page; TEI can hold everything but no journal or OCR tool reads it, and OpenITI — the largest Arabic text corpus — chose *not* to use TEI because of RTL and size problems ([OpenITI, DH2019](https://dh-abstracts.library.virginia.edu/works/10038)). One honest exception: if table *cells on the page* need boxes that ALTO cannot structure, write a PAGE XML for those pages too (PAGE has `TableCellRole` with row/column index and spans, [OCR-D](https://ocr-d.de/en/gt-guidelines/pagexml/pagecontent_xsd_Complex_Type_pc_TableCellRoleType.html)); otherwise ALTO blocks linked by id are enough.

## What it looks like

How the page looks (sketch), right to left:

```
  ┌───────────────────────────────────────────────────────┐
  │   تعتمد الدراسة على عينة من ١٢٠ طالباً، وتبين أن:      │  ← paragraph (reads right→left)
  │                                                       │
  │   (٣)            س = (أ + ب) ÷ ٢                       │  ← equation, Arabic-style maths
  │                                                       │
  │        ┌──────────┬──────────┬──────────┐              │
  │        │  النسبة  │  العدد   │  الفئة   │  ← header     │  ← table; first column is the
  │        ├──────────┼──────────┼──────────┤              │    RIGHTMOST one
  │        │   ٪٦٠    │    ٧٢    │  ذكور    │              │
  │        │   ٪٤٠    │    ٤٨    │  إناث    │              │
  │        └──────────┴──────────┴──────────┘              │
  └───────────────────────────────────────────────────────┘
```

(Read from the right, the columns are الفئة | العدد | النسبة, and that is the
order they are stored in below.)

### In the JATS file (the article)

```xml
<article xml:lang="ar" article-type="research-article"
         xmlns:mml="http://www.w3.org/1998/Math/MathML"
         xmlns:xlink="http://www.w3.org/1999/xlink">
 <front>…
  <processing-meta table-model="xhtml" math-representation="mathml tex"
                   mathml-version="3.0">
   <custom-meta-group>
    <custom-meta><meta-name>cell-order</meta-name>
     <meta-value>logical: the first cell of a row is the rightmost on the page</meta-value></custom-meta>
   </custom-meta-group>
  </processing-meta>
 </front>
 <body>
  <p id="p3b07">تعتمد الدراسة على عينة من ١٢٠ طالباً، وتبين أن:</p>

  <disp-formula id="p3eq1">
   <label>(٣)</label>
   <alternatives>
    <mml:math display="block" dir="rtl">            <!-- laid out right to left -->
     <mml:mi>س</mml:mi><mml:mo>=</mml:mo>
     <mml:mrow><mml:mo>(</mml:mo><mml:mi>أ</mml:mi><mml:mo>+</mml:mo>
       <mml:mi>ب</mml:mi><mml:mo>)</mml:mo></mml:mrow>
     <mml:mo>÷</mml:mo><mml:mn>٢</mml:mn>             <!-- the printed digit, not "2" -->
    </mml:math>
    <tex-math specific-use="read-by:olmocr-2"><![CDATA[\text{س} = (\text{أ} + \text{ب}) \div ٢]]></tex-math>
    <graphic xlink:href="crops/p3eq1.png" specific-use="scan-crop"/>
   </alternatives>
  </disp-formula>

  <table-wrap id="p3t1">
   <caption><p>توزيع العينة حسب الجنس</p></caption>
   <table>
    <thead>
     <tr><th id="p3t1c00">الفئة</th><th id="p3t1c01">العدد</th><th id="p3t1c02">النسبة</th></tr>
    </thead>
    <tbody>
     <tr><th id="p3t1c10" scope="row">ذكور</th><td id="p3t1c11">٧٢</td><td id="p3t1c12">٪٦٠</td></tr>
     <tr><th id="p3t1c20" scope="row">إناث</th><td id="p3t1c21">٤٨</td><td id="p3t1c22">٪٤٠</td></tr>
    </tbody>
   </table>
   <alternatives>…optional: <graphic xlink:href="crops/p3t1.png"/></alternatives>
  </table-wrap>
 </body>
</article>
```

(A merged cell is simply `<th colspan="2">`; for a table inside a cell see
Tables below — not confirmed against the DTD.)

### In the ALTO file (the page) — the same ids, now with boxes

```xml
<TextBlock ID="p3b07" xlink:href="doc.jats.xml#p3b07" …>
 <TextLine BASEDIRECTION="rtl" …>
  <String ID="p3w0101" CONTENT="تعتمد" HPOS="1820" VPOS="412" WIDTH="96" HEIGHT="58" WC="0.98"/>
  <SP/> …
  <String ID="p3w0106" CONTENT="١٢٠" HPOS="1310" VPOS="412" WIDTH="70" HEIGHT="55" WC="0.71">
   <ALTERNATIVE PURPOSE="gemini">١٢٥</ALTERNATIVE>   <!-- the other reader disagreed -->
  </String> …
 </TextLine>
</TextBlock>
<Illustration ID="p3eq1" TYPE="formula" xlink:href="doc.jats.xml#p3eq1" HPOS="900" VPOS="520" WIDTH="700" HEIGHT="90"/>
<ComposedBlock ID="p3t1" TYPE="table" xlink:href="doc.jats.xml#p3t1" …>
 <TextBlock ID="p3t1c11" xlink:href="doc.jats.xml#p3t1c11" …>   <!-- one block per cell -->
  <TextLine BASEDIRECTION="rtl"><String CONTENT="٧٢" WC="0.95" …/></TextLine>
 </TextBlock> …
</ComposedBlock>
```

(`Illustration`/`ComposedBlock` with a free `TYPE` are how ALTO marks a
formula or a table; ALTO has no cell grid of its own, which is why the grid
lives in JATS and the boxes in ALTO, joined by id. ALTO's `Description` keeps
one `Processing` entry per model with name and version — inkscript already
does this.)

### The derived HTML (what Chrome shows)

```html
<p dir="rtl" lang="ar">تعتمد الدراسة على عينة من ١٢٠ طالباً، وتبين أن:</p>
<math display="block" dir="rtl"> …same MathML… </math>
<table dir="rtl"><thead><tr><th>الفئة</th><th>العدد</th><th>النسبة</th></tr></thead>…</table>
```

Because the JATS cells are already in reading order, `dir="rtl"` alone puts
الفئة on the right — no reordering anywhere.

---

# Details

## 1. The candidates, one by one

| Format | Owner / status | Article structure | Word boxes on scan | Maths | Tables (spans) | RTL | Verdict |
|---|---|---|---|---|---|---|---|
| **JATS 1.4** | NISO Z39.96-2024, approved 2024-10-31 ([NISO](https://niso.org/publications/z3996-2024-jats)) | yes (front/body/back, refs, footnotes) | no (by design) | MathML 2/3 + `tex-math` in `<alternatives>` | XHTML model and/or OASIS CALS, rowspan/colspan | `xml:lang`; no `dir` attribute in the 1.4 attribute list | **master (article)** |
| **ALTO 4.4** | Library of Congress | blocks/lines only | yes, word and glyph, `WC` confidence, `ALTERNATIVE` | none (Illustration) | none (ComposedBlock TYPE) | `BASEDIRECTION` | **master (page)** |
| **PAGE XML** (2019/2024 schema) | PRImA | regions, explicit `ReadingOrder` | yes, polygons, word/glyph, confidence | MathsRegion (text only) | `TableRegion` rows/columns, `TableCellRole` rowIndex/columnIndex/rowSpan/colSpan/header ([OCR-D](https://ocr-d.de/en/gt-guidelines/pagexml/pagecontent_xsd_Complex_Type_pc_TableCellRoleType.html)) | `readingDirection` | good alternative to ALTO; best for ground truth |
| **hOCR** | microformat in HTML, spec v1.2 ([kba/hocr-spec](https://github.com/kba/hocr-spec)) | weak | yes (`bbox`, `x_wconf`) | no | no | via HTML | IA and Tesseract output; not a master |
| **TEI P5** | TEI Consortium | yes, very rich | via `facsimile/zone` | `<formula notation=…>`, MathML by namespace | `table/row/cell` with `rows`/`cols`, `role` | via `xml:lang`; no native `dir` | for DH partners; not read by journal tools |
| **OpenITI mARkdown** | KITAB project | light tags for headings, pages, verse | no | no | no | native Arabic | Arabic premodern corpora; chose it *instead of* TEI ([wiki](https://wiki.digitalclassicist.org/OpenArabic_mARkdown)) |
| **DocBook 5** | OASIS | books/manuals | no | MathML by namespace | CALS and HTML | `dir` attribute | technical books; nobody archives journals in it |
| **DoclingDocument JSON** | IBM / Docling v2, pydantic model ([docs](https://docling-project.github.io/docling/concepts/docling_document/)) | body/furniture trees, reading order = tree order | yes (provenance: page + bbox) | formula as text item (LaTeX) | `TableItem` with cell grid | Unicode only | excellent *working* format; not a standard |
| **DocTags** | SmolDocling/Granite-Docling output | page-level tags | yes, 0–500 grid `<loc_…>` | LaTeX in `<formula>` | OTSL tokens (`fcel`, `ecel`, `ched`, `rhed`, …) | — | model output only |
| **Markdown + LaTeX** | olmOCR, Marker, Nougat (`.mmd`) | headings, paragraphs | no | `$…$` LaTeX | GFM pipes (no spans) or embedded HTML | — | derived output only |
| **HTML5 + MathML** | WHATWG / W3C | via semantics | possible (`data-` attrs) | native MathML (Core) | full | `dir`, `lang` | the best *reading* output; arXiv HTML is this ([arXiv blog](https://blog.arxiv.org/2023/12/21/accessibility-update-arxiv-now-offers-papers-in-html-format)) |
| **EPUB 3** | W3C | XHTML inside | no | MathML | HTML | `dir`, `page-progression-direction` | distribution only |
| **PDF/UA-2** (ISO 14289-2, on PDF 2.0) | ISO / PDF Association | tag tree | yes (it is the page) | MathML inside `Formula` or as Associated File ([BPG Math in PDF](https://pdfa.org/download-area/publications/BPG-Math-in-PDF.pdf)) | tag tables | logical order | the right target for the *PDF* output; not a source of truth |
| **IIIF Presentation 3 + Web Annotation** | IIIF Consortium / W3C | ranges only | yes, annotations with `textGranularity` ([extension](https://iiif.io/api/extension/text-granularity/)) | no | no | — | delivery to viewers; Europeana models full text this way |

## 2. Equations

**What the models write.** Every current open VLM OCR emits **LaTeX**:
olmOCR-2 is prompted for "LaTeX equations and HTML tables" in Markdown ([HF
blog](https://huggingface.co/blog/ocr-open-models), [AI2](https://allenai.org/blog/olmocr-2));
Marker fences LaTeX with `$$` in Markdown and with `<math>` in HTML ([PyPI](https://pypi.org/project/marker-pdf/));
SmolDocling's instruction set converts formulas to LaTeX ([model card](https://huggingface.co/docling-project/SmolDocling-256M-preview/blob/60e3cdca435f5a3be1ba54ed3faa90a7c05bbc86/README.md));
Nougat writes Mathpix-style `.mmd` (LaTeX in Markdown) *(from memory, not re-checked)*.

**What readers consume.** Browsers render **Presentation MathML** natively
(MathML Core, W3C Candidate Recommendation 2025-06-24, expected final Q4 2026;
Chromium enabled it by default in early 2023 — [W3C](https://www.w3.org/news/2025/w3c-invites-implementations-of-mathml-core),
[charter](https://www.w3.org/Math/Documents/Charter2026.html)). PDF/UA-2
requires MathML for accessible formulas. JATS accepts both, and the JATS4R
recommendation says: use `<tex-math>` or `<mml:math>`, images only inside
`<alternatives>`, at most one of each kind there, all logically equivalent, no
preferred one ([JATS4R math](https://jats4r.niso.org/math)). The JATS tag
library shows exactly the pattern recommended above — `<disp-formula>` →
`<alternatives>` → `<graphic>` + `<mml:math>` + `<tex-math>` ([JATS 1.4 disp-formula](https://jats.nlm.nih.gov/archiving/tag-library/1.4/element/disp-formula.html));
NLM recommends MathML 3 for new work (MathML 2 may be dropped, [JATS MathML chapter](https://jats.nlm.nih.gov/archiving/tag-library/1.4/chapter/tag-mathml.html)).
arXiv converts LaTeX → HTML5+MathML with LaTeXML and in 2026 adds MathML 4
`intent` annotations; corpus-wide 75 % converts without error ([arXiv/NIST 2026](https://arxiv.org/pdf/2605.16562)).

**Presentation vs Content MathML.** Presentation MathML says *how it looks*
(this symbol, then that, stacked so); Content MathML says *what it means*
(apply divide to …). An OCR reading of a scan knows only the look, so
Content MathML would be a guess. Keep **Presentation MathML**; the MathML 4
`intent` attribute is the light way to add meaning later, for speech.

**Arabic mathematics.** The W3C Interest Group Note *Arabic mathematical
notation* (2006-01-31, still the current version, [W3C](https://www.w3.org/TR/arabic-math/))
shows that Arabic maths may be laid out left-to-right (Moroccan style) or
right-to-left (Maghreb style, with mirrored ∑, <, ∈), uses Arabic letters as
variables and function names, three digit systems, and special forms
(factorial enclosed by a ل-like hook, stretched حد for limits). Its proposal —
a `dir` attribute on `<math>` — **is now in MathML** (MathML 3 and Core;
[MDN](https://developer.mozilla.org/en-US/docs/Web/MathML/Reference/Global_attributes/dir)).
Several of its other proposals (new `mathvariant` values, `madruwb`
enclosure, new Unicode symbols) are not in MathML Core. Consequences:

- MathML can say "this formula runs right to left" and keep `<mn>٢</mn>`
  with the printed Arabic-Indic digit. **LaTeX has no standard way to do
  either**; RTL maths in TeX depends on engine packages (XeLaTeX `bidi`,
  LuaLaTeX) and KaTeX/MathJax do not lay out Arabic maths right to left
  *(general knowledge; worth a quick test)*. So LaTeX is fine as the *model's
  witness* but MathML must be the display form.
- The faithful rule (CLAUDE.md: no glyph is substituted) applies here too:
  keep the digits and letters as printed (٢ not 2, س not x). If a Latin
  normalised form is wanted for search, put it in a derived output.
- Expect VLMs to "Westernise" Arabic maths (flip to LTR, convert digits, put
  Arabic letters in `\text{}`). That is exactly the kind of systematic error
  the crop in `<alternatives>` lets a reviewer catch.

**Converters.** LaTeX → MathML: LaTeXML (`latexmlmath` for one formula),
pandoc's `texmath` library, MathJax/Temml. MathML → LaTeX: texmath (pandoc's
JATS *reader* uses it, [pandoc source](https://hackage-content-origin.haskell.org/package/pandoc-2.15/docs/src/Text.Pandoc.Readers.JATS.html)).

**Scoring equations.** OmniDocBench uses **CDM** (render both LaTeX
formulas, match characters by position; F1 over matched boxes) instead of
string distance, because one formula has many spellings ([OmniDocBench](https://arxiv.org/pdf/2412.07626));
olmOCR-Bench renders with KaTeX and checks symbol layout ([olmOCR-Bench](https://evalscope.readthedocs.io/en/latest/benchmarks/olmocr_bench.html)).
Neither is built for RTL Arabic maths — any score on Arabic formulas will need
our own check against the crop.

## 3. Tables

**What each format can express.**

| | merged cells | header rows/cols | nested table | RTL column order | link cell → box |
|---|---|---|---|---|---|
| JATS XHTML model | `rowspan`/`colspan` | `thead`, `th`, `scope` | not inside a cell (use a second `table-wrap`) *(per JATS content model; verify against DTD)* | logical order + `xml:lang` | cell `id` → ALTO |
| JATS/OASIS CALS | `namest`/`nameend`, `morerows` | `thead`, `rowheader` | `entrytbl` | logical | `id` |
| HTML5 | yes | yes | yes | `dir="rtl"` | `id`/`data-` |
| PAGE XML | rowSpan/colSpan | `header` flag | via nested regions | `readingDirection` | it *is* the box |
| TEI | `rows`/`cols` on cell | `role="label"` | yes | — | `facs` |
| DoclingDocument | span per cell, header flags | yes | — | — | provenance bbox |
| OTSL/DocTags | `lcel`/`ucel`/`xcel` merge tokens | `ched`/`rhed` | — | — | `<loc>` |
| GFM Markdown | **no** | first row only | **no** | — | no |

JATS's `table-model` attribute declares which model a file uses (`xhtml`,
`oasis`, `both`, `none`) ([tag library](https://jats.nlm.nih.gov/archiving/tag-library/1.4/attribute/table-model.html));
the tag library notes most users prefer XHTML because it goes straight to the
web, while CALS is chosen for print tooling ([which DTD](https://jats.nlm.nih.gov/publishing/tag-library/1.3/chapter/which-dtd.html)).
Elsevier's own DTD uses CALS ([Elsevier DTD 5](https://www.elsevier.com/researcher/author/policies-and-guidelines/elsevier-xml-dtds-and-transport-schemas)).
**Choose XHTML**: the OCR models emit HTML tables, the scoring metric works on
HTML trees, and the browser output is HTML — one shape end to end.

**RTL column order.** Store cells in *reading* (logical) order, the way
Unicode stores letters: the first cell of a row is the rightmost printed one.
HTML with `dir="rtl"` then displays it correctly, and TEDS comparisons with
models' output (which also emit logical order when they get it right) are
like for like. The danger is a model that emits visual order (left column
first); a direction check per table (does the label column come first?)
belongs in the verifier.

**How table accuracy is scored.**

- **TEDS** (PubTabNet, [Zhong et al. 2019/2020](https://arxiv.org/pdf/1911.10683)): both tables as HTML trees, `1 − tree-edit-distance / size of larger tree`; cells carry text, rowspan, colspan. **TEDS-S** ignores cell text — structure only. Sensitive to equivalent markup spelt differently.
- **GriTS** ([Smock et al. 2022](https://arxiv.org/pdf/2203.12555)): compares the 2-D grids directly; GriTS-Top (spans), GriTS-Con (cell text, LCS), GriTS-Loc (cell boxes); precision/recall/F. Robust to markup variations.
- Arabic data point: on KITAB-Bench, table TEDS (HTML) was 85.8 for GPT-4o, 83.1 Gemini-2.0-Flash, 59.3 Qwen2.5-VL-7B; the paper lists table structure detection and numeral recognition among recurring failures ([KITAB-Bench, ACL Findings 2025](https://arxiv.org/pdf/2502.14949)).

Storing the master table as XHTML means TEDS/TEDS-S can be computed straight
from the JATS file against hand-made ground truth, and GriTS-Loc from the ALTO
cell boxes.

## 4. What the big holders actually store

- **PubMed Central (NLM):** converts every publisher's XML into the JATS *Archiving and Interchange* tag set, its archival format ([JATS archiving intro](https://jats.nlm.nih.gov/archiving/tag-library/1.4/chapter/set-intro.html)). For its scanned back issues (1.2 M articles, some from the 1800s) it kept **page-image PDFs plus uncorrected OCR text for search and XML abstracts** — not full JATS bodies ([PMC scanning](https://www.ncbi.nlm.nih.gov/books/NBK153388/); sources 2004–2008). Our project would be doing better than PMC did for scans.
- **Portico** (preservation for Elsevier, Springer, …): migrates ~70 publisher formats into a Portico flavour of JATS **and keeps the publisher's original XML** next to it ([Portico e-journal plan v1.3, 2023](https://www.portico.org/wp-content/uploads/2023/09/Portico_Content_Type_Action_Plan_E-Journals_1_3.pdf)). The pattern: one normalised master + the original.
- **Elsevier:** its own DTD 5 family (JA 5.6.0, CEP 1.7.0, Jan 2024), with **MathML** for formulas and **CALS** tables ([Elsevier DTDs](https://www.elsevier.com/researcher/author/policies-and-guidelines/elsevier-xml-dtds-and-transport-schemas)). Springer Nature (its "A++" DTD) and Wiley (WileyML) also keep in-house XML and deliver JATS to PMC/Crossref *(unverified: no primary documentation found)*.
- **Library of Congress:** Recommended Formats Statement — electronic serials: **JATS preferred**, with PDF/UA, PDF/A; digital text: XML with schema, EPUB 3, TEI, DocBook, PDF/UA preferred ([RFS text](https://www.loc.gov/preservation/resources/rfs/text.html)). For digitised newspapers (Chronicling America/NDNP): **TIFF/JP2 + PDF + METS/ALTO per page** ([NDNP 2020 guidelines](https://loc.gov/ndnp/guidelines/archive/guidelines2021.html)).
- **BnF (Gallica):** OCR kept as **ALTO**, because it keeps coordinates for text overlay and image/text PDFs ([BnF](https://www.bnf.fr/node/1296)).
- **HathiTrust:** per volume a package of page images (TIFF → JP2 on ingest), **one plain-text OCR file per page (required)** plus coordinate OCR (hOCR/ALTO-like XML, encouraged), metadata and MD5 checksums ([CDL guidelines](https://cdlib.org/hathitrust/submission-guidelines)).
- **Internet Archive:** derives **hOCR** (its preferred parse target), a DjVu-style XML, plain text and page-number JSON from Tesseract runs ([IA OCR docs](https://archive.org/developers/ocr.html); page could not be fetched today, summary from search).
- **Europeana:** OCR source in **ALTO**; served to viewers as **IIIF + Web Annotations** (full text modelled as annotations on the image) ([Europeana fulltext](https://github.com/europeana/fulltext/wiki)).
- **Qatar Digital Library:** publishes **IIIF Presentation manifests** and IIIF Image API for every item ([QDL](https://www.qdl.qa/en/image-options)); its transcription format is not publicly documented.
- **Bibliotheca Alexandrina (DAR):** open-source repository with METS/MODS metadata and Arabic full-text search ([DAR](https://en.wikipedia.org/wiki/Digital_Assets_Repository)); OCR storage format not documented publicly.
- **OpenITI (largest open Arabic corpus, release 2025.1.9):** plain text with **mARkdown** tags; TEI conversion postponed because of RTL, connected script and very long texts ([Zenodo](https://zenodo.org/records/17767721), [DH abstract](https://dh-abstracts.library.virginia.edu/works/10038)).

**Why they converge.** Journals → JATS because it is the shared target that
lets archives outlive publishers' own formats; libraries → ALTO/hOCR because
search-and-highlight on a page image needs word boxes; everyone → keep the
scan and checksums because a reading can always be redone, the scan cannot.

## 5. One master + derived outputs, and provenance

The pattern everywhere (Portico, PMC, NDNP, arXiv): **one normalised master,
the original evidence beside it, and every display format generated.**
For inkscript, concretely:

- **Ids are the glue.** Already: ALTO word `p3w0042` ↔ JATS block via
  `xlink:href` ↔ glyph in `shapes.json`. Extend the same to equation and cell
  ids (`p3eq1`, `p3t1c11`).
- **Which model read what.** ALTO `Description/Processing` per tool (name,
  version, date) — inkscript already writes one per reader. In JATS, mark the
  source of a LaTeX string with `specific-use` (e.g. `read-by:olmocr-2`) and
  the article-level history in `<processing-meta>`/`<custom-meta>`.
- **Confidence and disagreement.** ALTO `WC` (word confidence, 0–1), `CC`
  (per glyph), `ALTERNATIVE` (other readings) — all already in use. For
  equations and tables, confidence lives on the ALTO Illustration/ComposedBlock
  (`TAGREFS` to a trust mark), not in JATS.
- **Never edit derived files.** A correction is made in the master (or in
  inkscript's corrections record, D21) and outputs regenerated.

## 6. Tools and validation

| Job | Tool |
|---|---|
| Validate JATS | the NLM DTD/XSD/RNG (inkscript caches them, D20); `xmllint`; JATS4R validator (Schematron) |
| Validate ALTO | LoC ALTO 4.4 XSD (already done: 205/205 valid) |
| Validate PAGE | PRImA XSD; OCR-D `ocrd workspace validate` |
| JATS → HTML/PDF | NLM's JATS preview XSLT (Saxon); pandoc (`-f jats`); for HTML+MathML just copy the `mml:math` out |
| LaTeX → MathML | LaTeXML / `latexmlmath`; texmath (pandoc); Temml/MathJax |
| PAGE ↔ ALTO | `ocrd-page-to-alto` (tables and reading order still on its TODO list, [PyPI](https://pypi.org/project/ocrd-page-to-alto/)) |
| Anything ↔ Docling | docling reads JATS, writes Markdown/HTML/DocTags/JSON |
| Table scoring | TEDS reference code (PubTabNet), GriTS (`table-transformer` repo) |
| Package | BagIt (`bagit-python`) or METS |

Pandoc's JATS writer emits formulas as `tex-math`/MathML *(from memory —
check with `pandoc -t jats` before relying on it)*; its JATS reader gained
rowspan/colspan in 2023 ([changelog](https://hackage.haskell.org/package/pandoc-2.16/src/changelog.md)).

## 7. What this changes for inkscript (proposals, nothing done)

1. Keep JATS 1.4 + ALTO 4.4 as the record (D20 holds).
2. Add `<disp-formula>/<inline-formula>` with `<alternatives>` (MathML with
   `dir` as printed + the model's LaTeX + scan crop); add `table-wrap` with
   XHTML tables, spans, `th`/`scope`, ids per cell; set
   `processing-meta/@table-model="xhtml"` and `@math-representation`.
3. ALTO: an `Illustration TYPE="formula"` per equation and a
   `ComposedBlock TYPE="table"` with one `TextBlock` per cell, each pointing at
   its JATS id. (Today table cells are set aside as furniture — STATUS.md.)
4. A derived HTML+MathML page per document, `dir="rtl"`, generated from JATS.
5. Measure: TEDS/TEDS-S on a hand-made set of Arabic tables; for equations,
   a side-by-side page (crop | rendered MathML) for the owner to mark yes/no,
   since no benchmark covers RTL Arabic maths.

## Sources

- NISO JATS Z39.96-2024: https://niso.org/publications/z3996-2024-jats
- JATS 1.4 tag library — table-model: https://jats.nlm.nih.gov/archiving/tag-library/1.4/attribute/table-model.html ; disp-formula: https://jats.nlm.nih.gov/archiving/tag-library/1.4/element/disp-formula.html ; MathML chapter: https://jats.nlm.nih.gov/archiving/tag-library/1.4/chapter/tag-mathml.html ; archiving intro: https://jats.nlm.nih.gov/archiving/tag-library/1.4/chapter/set-intro.html ; which DTD: https://jats.nlm.nih.gov/publishing/tag-library/1.3/chapter/which-dtd.html
- JATS4R math: https://jats4r.niso.org/math
- W3C Arabic mathematical notation (Note, 2006-01-31): https://www.w3.org/TR/arabic-math/
- MDN MathML `dir`: https://developer.mozilla.org/en-US/docs/Web/MathML/Reference/Global_attributes/dir
- MathML Core CR: https://www.w3.org/TR/mathml-core/ ; https://www.w3.org/news/2025/w3c-invites-implementations-of-mathml-core ; Math WG charter 2026: https://www.w3.org/Math/Documents/Charter2026.html ; MathML 4 WD 2025-09-19: https://www.w3.org/TR/2025/WD-mathml4-20250919/
- arXiv HTML: https://blog.arxiv.org/2023/12/21/accessibility-update-arxiv-now-offers-papers-in-html-format ; https://arxiv.org/pdf/2605.16562
- PDF/UA-2: https://pdfa.org/iso-14289-2-pdfua-2/ ; https://pdfa.org/download-area/publications/BPG-Math-in-PDF.pdf
- Docling: https://docling-project.github.io/docling/concepts/docling_document/ ; SmolDocling card: https://huggingface.co/docling-project/SmolDocling-256M-preview/blob/60e3cdca435f5a3be1ba54ed3faa90a7c05bbc86/README.md
- olmOCR: https://allenai.org/blog/olmocr-2 ; https://huggingface.co/blog/ocr-open-models ; https://evalscope.readthedocs.io/en/latest/benchmarks/olmocr_bench.html
- Marker: https://pypi.org/project/marker-pdf/
- TEDS: https://arxiv.org/pdf/1911.10683 ; GriTS: https://arxiv.org/pdf/2203.12555 ; OmniDocBench: https://arxiv.org/pdf/2412.07626 ; KITAB-Bench: https://arxiv.org/pdf/2502.14949
- PAGE XML (OCR-D): https://ocr-d.de/en/gt-guidelines/pagexml/pagecontent_xsd_Complex_Type_pc_TableCellRoleType.html ; https://www.primaresearch.org/schema/PAGE/gts/pagecontent/2019-07-15/changelog.txt ; ocrd-page-to-alto: https://pypi.org/project/ocrd-page-to-alto/
- ALTO: https://loc.gov/standards/alto/techcenter/layout.html
- hOCR spec: https://github.com/kba/hocr-spec
- TEI figures/tables: https://tei-c.org/Vault/P5/1.0.1/doc/tei-p5-doc/en/html/ref-row.html
- OpenITI: https://wiki.digitalclassicist.org/OpenArabic_mARkdown ; https://dh-abstracts.library.virginia.edu/works/10038 ; https://zenodo.org/records/17767721
- IIIF Text Granularity: https://iiif.io/api/extension/text-granularity/
- LoC Recommended Formats (text): https://www.loc.gov/preservation/resources/rfs/text.html ; NDNP: https://loc.gov/ndnp/guidelines/archive/guidelines2021.html
- PMC scanning: https://www.ncbi.nlm.nih.gov/books/NBK153388/
- Portico: https://www.portico.org/wp-content/uploads/2023/09/Portico_Content_Type_Action_Plan_E-Journals_1_3.pdf
- Elsevier DTDs: https://www.elsevier.com/researcher/author/policies-and-guidelines/elsevier-xml-dtds-and-transport-schemas
- BnF: https://www.bnf.fr/node/1296
- HathiTrust (CDL): https://cdlib.org/hathitrust/submission-guidelines
- Internet Archive OCR: https://archive.org/developers/ocr.html
- Europeana fulltext: https://github.com/europeana/fulltext/wiki
- QDL IIIF: https://www.qdl.qa/en/image-options
- Bibliotheca Alexandrina DAR: https://en.wikipedia.org/wiki/Digital_Assets_Repository
- pandoc JATS reader: https://hackage-content-origin.haskell.org/package/pandoc-2.15/docs/src/Text.Pandoc.Readers.JATS.html
