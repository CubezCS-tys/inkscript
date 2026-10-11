# 04 · From a scanned newspaper page to a native, re-flowable document

*Research note, 2026-10-11. Web research only: nothing downloaded, installed, trained or paid for. Numbers are
the sources' own, and most are self-reported by the people who built the system. Claims I could not confirm
from a primary source are marked **(unverified)**. Notes 01–03 (models, formats for journals, building our own
reader) are not repeated here; this note covers what changes when the page is a newspaper and the goal is a
re-flowed, re-typeset document.*

## In ten lines

1. A newspaper page is not one text. It is a **mosaic of articles**, headlines, bylines, captions, ads and
   notices. Some articles snake round others, and some continue on another page ("تابع ص ٥"). Reading it means
   cutting the mosaic into pieces and putting each article's pieces back in order.
2. The world's newspaper archives do this in **three steps**: find the blocks on the page, decide which blocks
   belong to which article, then order the blocks inside each article (and the articles on the page).
3. The best published systems get blocks right about 9 times in 10 and articles right about 8 times in 10.
   **BnF/Teklia (Jul 2026)**: article separation F1 80%. **Boston Public Library/Harvard (Aug 2026)**: reading
   order 81%. **American Stories**: headline-to-article F1 97%, but it does not join articles split over
   columns or pages. Continued articles across pages are still largely unsolved.
4. General document VLMs (dots.ocr, PaddleOCR-VL, Qwen3-VL) read newspaper *text* well, but they have **no idea
   of an "article"**. Their labels are Title, Text, Picture, Caption, and so on. Article grouping is a separate
   step that we must build, as every serious project has.
5. **No public Arabic newspaper layout dataset with article labels exists** that I could find. The big Arabic
   newspaper archives (Al-Ahram on East View, AUB's Lebanese dailies, NLI's Jrayed, NC State's Arab-American
   press) offer page images plus imperfect page OCR, sometimes article clipping, and no open structured data.
   An Arabic article-level newspaper archive would be a first.
6. Storage: libraries hold a newspaper issue as **METS + ALTO**. METS lists the issue's articles and points each
   one at its blocks in the ALTO page files. ALTO 4.3+ adds explicit reading order and a right-to-left base
   direction. This is the newspaper twin of the journals' JATS + ALTO choice.
7. For the *re-flowed text* of each article, the journal pipeline can be reused: one **JATS file per article**
   (`article-type="news"`, `"obituary"`, `"announcement"`…), with every word's id shared with ALTO. NewsML/NITF
   (the news industry's XML) and TEI were looked at and are not the right master; reasons are below.
8. Re-typesetting: **LuaLaTeX** (HarfBuzz shaping, babel's kashida justification) gives the best open Arabic
   print today. **HTML + CSS** (Paged.js or Vivliostyle for PDF; EPUB 3 for e-readers) is the easiest and shares
   one stylesheet with the web, but browsers still justify Arabic only by widening spaces. Kashida is a Chromium
   prototype behind a flag (Aug 2026). **Typst** is not ready for Arabic: there is no Arabic justification and
   direction must be set by hand.
9. For AI and search: publish **one JSONL/Parquet record per article** (original text, search-folded text,
   title, byline, date, pages, box links, OCR confidence, licence), plus Markdown. Index two forms of the text:
   exact, and "folded" (diacritics, tatweel and hamza variants removed, digits unified).
10. What readers expect, from the best archives (Trove, Papers Past, impresso, Veridian sites): **the article
    clipped out of the scan beside its clean text**, a stable link and a "cite this" box. Our extra, which nobody
    else has, would be that each re-flowed word can light up its own ink on the scan.

## A newspaper page, from scan to re-flowed article (picture)

```
 1. THE SCAN (what the camera saw)                 2. UNDERSTOOD (blocks → articles → order)
 ┌───────────────────────────────────────────┐    ┌───────────────────────────────────────────┐
 │  ═════════ الأهـــرام ═══ ١٢ مايو ١٩٣٦ ════ │    │ [masthead]  ← furniture, not an article     │
 │ ┌───────────────────────────┐ ┌──────────┐ │    │ ┌───────────────────────────┐ ┌──────────┐ │
 │ │ مفاوضات المعاهدة تبدأ غداً  │ │  ║ صورة ║ │ │    │ │ A·headline (spans 3 cols) │ │ B·photo  │ │
 │ ├────────┬────────┬─────────┤ │ ╚══════╝ │ │    │ ├────────┬────────┬─────────┤ │ B·caption│ │
 │ │ ......│ ...... │ لندن -   │ │ الوفد في │ │    │ │ A·3    │ A·2    │ A·1     │ ├──────────┤ │
 │ │ ......│ ...... │ ......   │ ├──────────┤ │    │ │        │        │ byline  │ │ C·1      │ │
 │ │ ......│ ...... │ ......   │ │ أخبار    │ │    │ │        │        │         │ │ C·2      │ │
 │ │ (تابع │        │          │ │ محلية    │ │    │ │ A→p.5  │        │         │ │          │ │
 │ │ ص ٥)  │        │          │ │ ......   │ │    │ └────────┴────────┴─────────┘ └──────────┘ │
 │ ├───────┴────────┴──────────┴─┴──────────┤ │    │ ┌─────────────────────────────────────────┐ │
 │ │  ★ إعلان: صابون نابلسي ★ ....        │ │    │ │ D·advertisement                          │ │
 │ └────────────────────────────────────────┘ │    │ └─────────────────────────────────────────┘ │
 └───────────────────────────────────────────┘    └───────────────────────────────────────────┘
   columns read RIGHT → LEFT; A starts in the        each block knows: its article (A, B, C, D),
   rightmost column under its headline, snakes       its role (headline, byline, body, caption, ad),
   left, and jumps to page 5                         its place in the article's order (1, 2, 3, →p.5)

 3. RE-FLOWED (one article, a native document)       4. STILL TIED TO THE INK
 ┌──────────────────────────────┐                     each word in 3 carries the id of its box in
 │        مفاوضات المعاهدة تبدأ غداً│  ← one heading     the ALTO page file:
 │                  لندن – مراسلنا│  ← byline           tap «المعاهدة» on the phone → the scan opens
 │ ــــــــــــــــــــــــــــــــ │                     at page 1, column 1, line 1, word 2, outlined.
 │ بدأت اليوم في لندن المحادثات   │  ← column 1 text
 │ التمهيدية ... (column 2 text)  │  ← column 2 text   the "(تابع ص ٥)" note is gone from the text;
 │ ... (column 3) ... (page 5     │  ← p.5 piece       it became a join between two pieces.
 │ continuation) ...              │     joined in
 │  ─ الأهرام، ١٢ مايو ١٩٣٦، ص ١، ٥ │  ← citation line   the same article prints on A4, reads on a
 └──────────────────────────────┘                     phone (EPUB/HTML), and goes into a dataset.
```

## Recommendation

**One issue = one package.** It is the newspaper twin of the journal choice (JATS + ALTO, D20), with METS added
because a newspaper issue holds many articles that cross pages.

| File | Role | Standard | Why |
|---|---|---|---|
| page scans (unchanged) | the evidence | TIFF / JP2 | everything points back to them |
| `p001.alto.xml` … one per page | **where** every block, line and word is, its confidence, and the page's reading order | ALTO 4.4 (`BASEDIRECTION="rtl"`, `ReadingOrder`, `IDNEXT` between an article's blocks) | what LoC, Europeana, Papers Past and Veridian read; already written by inkscript for journals |
| `issue.mets.xml` | **what** the issue contains: the articles, each one's parts (headline, byline, body, caption) and their order, pointing at ALTO block ids on one or several pages | METS with a physical `structMap` (pages) and a logical one (`ARTICLE` › `HEADING`/`BODY`/…), as in the "article-level METS/ALTO" used by Veridian and Europeana Newspapers | the only widely deployed way to store "this article = these blocks on pages 1 and 5" |
| `a0007.jats.xml` … one per article | the **re-flowed text** of each article: title, byline, paragraphs in reading order, tables, footnotes; `article-type` = news, editorial, obituary, announcement, letter…; every word or paragraph id shared with ALTO | JATS 1.4 Archiving (as for journals) | same downstream code as the journals (HTML, EPUB, PDF, Markdown); JATS has a suggested `article-type="news"` |
| issue-level metadata | newspaper title, place, date, issue number, language, licence | MODS inside METS (and the MARC record, as experiment 29 does for journals) | library standard |

**Derived, never edited by hand:**

- **Web and phone**: one HTML page per article (`dir="rtl"`, `lang="ar"`, schema.org `NewsArticle`, Google
  Scholar `citation_*` meta tags), with the scan clip beside it; IIIF Presentation 3 manifest + Web Annotations
  for the word boxes.
- **E-reader**: one reflowable EPUB 3 per issue (a contents list of articles, `page-progression-direction="rtl"`).
- **Print**: a re-typeset PDF per article and per issue, via **LuaLaTeX + babel** (best Arabic justification),
  or via **Paged.js/Vivliostyle** from the same HTML when speed of building matters more than kashida.
- **AI and search**: JSONL/Parquet with one record per article, plus Markdown; a Croissant/Hugging Face dataset
  card with licence and provenance.
- The **faithful PDF** of the page (inkscript's own product) stays as the page-level view.

**Tools to build the understanding step** (all open; to be measured on Mandumah pages, nothing measured yet):

1. Blocks: a YOLO-family layout detector fine-tuned on hand-marked Arabic newspaper pages (every 2025–26
   newspaper project that works uses one: American Stories, BnF/Teklia, BPL/Harvard, Urdu newspapers). The
   classes are newspaper ones (headline, sub-headline, byline, body, caption, photo, ad, table, masthead,
   page number, separator). The VLM layout labels are not enough.
2. Text: the readers from note 01 (Kraken for lines and boxes plus a VLM second reading) run **on each block**,
   never on the whole page.
3. Articles and order: rules first (headline over the columns below it, separators, the right-to-left column
   order), as American Stories and BPL do. Then a small learned or LLM pairwise judge for the ambiguous pages
   (the Armenian-newspaper method, Jul 2026). The judge only *proposes* orders; a person confirms them while the
   gold set is being built.
4. Jumps ("تابع ص ٥", "البقية في الصفحة …", "تتمة"): find the jump phrases and page numbers in the text, then
   match the cut-off piece to a "continued from" piece on the named page by headline words and text similarity.
   No open tool does this today.

**Why not the alternatives as master:** NewsML-G2/NITF/ninjs are delivery formats for today's wire copy, with no
boxes, no pages and no scan. TEI could hold it all, and OpenArabicPE uses it for Arabic periodicals, but no OCR
tool or newspaper viewer reads it, and note 02 already set it aside for journals. Keep TEI as an export for
digital-humanities partners. EPUB and HTML are renderings, not records. impresso's JSON is a good *working*
format to imitate (see §2.4) but is a project schema, not a standard.

---

# Details

## 1. Cutting a newspaper page into articles: what has been done

### 1.1 The large English and European projects

| Project (date) | What it does | Numbers (their own) | Lesson for us |
|---|---|---|---|
| **American Stories** (Dell et al., Harvard, Aug 2023; [arXiv 2308.12477](https://arxiv.org/abs/2308.12477), [code](https://github.com/dell-research-harvard/americanstories), [data, CC BY 4.0](https://huggingface.co/datasets/dell-research-harvard/AmericanStories)) | YOLOv8 layout (articles, headlines, captions, bylines, images, ads, tables, mastheads, headers, page numbers), a legibility classifier, its own OCR (EffOCR), then **rules** that tie headlines and bylines to the article box below | ~20M Chronicling America scans; layout mAP50:95 0.91 for article boxes, 0.84 for headlines; headline-to-article F1 97.0 on 10 full pages; OCR CER 1.8–8.9% by decade | Simple geometry rules go a long way. But they **do not join** an article split across boxes or pages (3.8% of articles span several boxes, 0.2% several pages), and they say so. Output fields: `headline, byline, article, newspaper_name, date, page, edition`. |
| **Newswire** (Dell et al., NeurIPS 2024; [arXiv 2406.09490](https://arxiv.org/abs/2406.09490)) | the same pipeline on ~138M article texts, then de-duplication of reprinted wire stories | 2.7M unique newswire articles 1878–1977, georeferenced and entity-linked | Once articles exist, the research value multiplies (topics, entities, reprints). |
| **Chronicling Germany** (Bonn, 2024–25; [arXiv 2401.16845](https://arxiv.org/html/2401.16845v4)) | 801 hand-annotated German pages (1617–1933) in PAGE XML: caption, table, paragraph, heading, header, vertical and horizontal separators, image, inverted text | paragraph F1 0.97, table 0.90, heading 0.67, caption 0.63; reading order generated automatically and "poor for advertisement pages" | Headings and captions are the hard classes. **Separators** (column rules) are labelled as their own class, because they decide reading order. |
| **NewsEye** (EU H2020, 2018–22; [NAS dataset paper](https://l3i.univ-larochelle.fr/app/uploads/sites/12/2024/08/girdhar2023NAS.pdf)) | article separation on German, Finnish and French papers, annotated in Transkribus in PAGE XML; a benchmark and new metrics | — | The first multilingual article-separation benchmark. Transkribus now sells this as a service ([page](https://www.transkribus.org/newspaper-digitization)): articles, headlines, ads and captions exported as ALTO/PAGE. No Arabic is mentioned. |
| **Europeana Newspapers** (2012–15; [CORDIS](https://cordis.europa.eu/project/id/297380), [IFLA 2013](https://cf-www.ifla.org/wp-content/uploads/2019/05/assets/newspapers/Singapore_2013_papers/day_1_10_2013_ifla_satellite_neudecker_clemens_wilms_lotte_europeana_newspapers_-_a_gateway_to_european_newspapers_online.pdf)) | OCR by Innsbruck; layout/article recognition ("OLR") by CCS docWorks, written as METS/ALTO | target ~10M pages refined (final count **unverified**) | The origin of "article-level METS/ALTO" as a library delivery format. |
| **BnF / Teklia / LITIS "Tiramisu"** (16 Jul 2026; [arXiv 2607.15082](https://arxiv.org/html/2607.15082)) | two ways compared: a **pipeline** (YOLO26 blocks + LayoutReader order + separator detection + an article-grouping algorithm) and **one end-to-end model** (sections → articles → blocks) | article separation F1@0.5: pipeline **80.4%**, end-to-end 70.7%, commercial Arcanum 59.4%; block reading order BLEU 87.2 vs 73.3; pipeline 1.7 s/page on CPU against 57 s for the end-to-end model | The newest public result. **The pipeline wins** on accuracy and speed. BnF plans to deploy it on Gallica's newspapers by the end of 2026. Open data: [Teklia/Newspapers-finlam-La-Liberte](https://huggingface.co/datasets/Teklia/Newspapers-finlam-La-Liberte) (~8,800 pages; licence not stated). |
| **Boston Public Library + Harvard IDI** (19 Aug 2026; [arXiv 2608.18972](https://arxiv.org/abs/2608.18972)) | YOLO26x crops, **two readers** (Tesseract 5 and the dots.mocr VLM), type and language classifiers, reading order by column clustering (HDBSCAN) + rules, entities, embeddings | 1.47M scans (1795–1930) → 83M crops, 16.3B tokens; crop P/R 0.93/0.91; reading order 81% micro, 72% macro; ~1,650 GPU-hours ≈ $25k, against an estimated $250k–800k for frontier APIs | The closest published thing to what the owner wants, at archive scale. It uses the same "two readers" idea as note 01. Reading order is the weakest step. ([summary](https://blog.pebblous.ai/blog/bpl-newspaper-pipeline-16b-tokens/en/)) |
| **impresso** (EPFL/Lausanne/Zurich/Luxembourg; funded to Feb 2027; [schemas](https://github.com/impresso/impresso-schemas)) | 200 years of Swiss/Luxembourg/French papers as **content items** (article, ad, image, table, death notice, weather…) with reading order, linked to IIIF regions; web app + Datalab API | — | Its data model is a good picture of an "understood" issue; see §2.4. |
| **NCSE v2** (Bourne, Feb 2025; [arXiv 2502.14901](https://arxiv.org/abs/2502.14901)) | 84k pages of 19th-c. English serials re-read with Pixtral-12B | median CER 1% (5× lower than the next model) | A VLM as the reader of crops works on old print, once the page is cut up. |

### 1.2 Right-to-left and Arabic-script newspapers

- **No open Arabic newspaper dataset with article-level labels was found.** The nearest are an Ain Shams
  study (text/non-text on 40 Arabic newspaper scans, F 0.91; [PDF](https://research.asu.edu.eg/bitstream/12345678/19761/1/J5558.pdf)),
  a Szeged thesis with ground-truthed Arabic magazine and newspaper pages ([booklet](https://doktori.bibl.u-szeged.hu/id/eprint/10445/8/thesis%20booklet%202.pdf)),
  Humans-in-the-Loop's CC0 Arabic documents set with a newspaper class (page and line outlines only;
  [link](https://humansintheloop.org/resources/datasets/arabic-documents-ocr-dataset/)), the BCE/BE-Arabic
  *book* layout sets ([BU](https://cs-people.bu.edu/wdqin/BCEAW/bceaw.html)), and the 2003 "Arabic Newspaper Page
  Segmentation" paper (Hadjar & Ingold, ICDAR, from memory: **unverified**;
  [ResearchGate](https://www.researchgate.net/publication/220860287_Arabic_Newspaper_Page_Segmentation)).
  KITAB-Bench's nine domains do not include newspapers ([arXiv 2502.14949](https://arxiv.org/pdf/2502.14949)).
- **Urdu newspapers** (Arif & Farid, May 2025; [arXiv 2505.13943](https://arxiv.org/html/2505.13943v1)), the
  closest right-to-left case: YOLOv11x cuts the page into **articles first** (mAP50 0.975, trained on 26,830
  articles), a second YOLOv11x cuts each article into columns, SwinIR up-scales, then an LLM reads. Gemini-2.5-Pro
  WER 0.13; open Llama-4 models 0.31–0.35. They do not say how column order is decided.
- **Armenian newspapers** (Vidal-Gorène et al., 1 Jul 2026; [arXiv 2607.00596](https://arxiv.org/html/2607.00596v1)):
  66 annotated pages. Ordering by geometry alone is poor (Kendall τ distance 0.42). Semantic blocks + local sort
  gets 0.17, and adding **pairwise LLM judgements between blocks** gets 0.10. Asked to order the page by itself,
  an LLM is terrible (0.79): it regroups by topic. Across pages the error rises to 0.26. The authors present
  this as a way to *propose* orders for human checking.
- **Older Arabic/Urdu layout work**: Bukhari, Shafait & Breuel, ICDAR 2011, multi-column Arabic/Urdu layout and
  reading order ([PDF](https://www-live.dfki.de/fileadmin/user_upload/import/5454_Bukhari-Arabic-Layout-Analysis-ICDAR11.pdf)).

**What is specific to Arabic papers (from the domain, not a source):** columns run right to left. A main
headline (مانشيت) spans several columns, and its article starts in the *rightmost* column beneath it. Articles
are often L-shaped or wrap round a photo. Jump lines say «التتمة ص ٧», «البقية على الصفحة ...», «تابع ص ٥», with
Arabic-Indic or Western digits. A Latin-language column (French in Egyptian and Lebanese papers) can sit on the
same page and read left to right. Kashida-stretched headlines fool word segmentation.

### 1.3 How the general document VLMs do on newspapers

- **dots.ocr / dots.mocr** label blocks as Caption, Footnote, Formula, List-item, Page-footer, Page-header,
  Picture, Section-header, Table, Text, Title, "sorted according to human reading order" by the prompt
  ([prompt script](https://huggingface.co/datasets/uv-scripts/ocr/blob/refs%2Fpr%2F7/dots-ocr-1.5.py)).
  **No article, byline or advertisement class.** It is a strong *reader of blocks*. BPL uses dots.mocr exactly
  that way, on crops.
- **PaddleOCR-VL** has the best newspaper score in a block-level OmniDocBench test (normalised edit distance
  0.035, against 0.056 for Qwen2.5-VL-72B and MinerU2.5; [PaddleOCR-VL paper](https://arxiv.org/pdf/2510.14528)).
  Those are mostly Chinese and English modern newspapers.
- **Qwen3-VL-8B**, fine-tuned on 19th-century Swedish newspapers, beat ABBYY FineReader by 68.5% on CER (1.93%;
  [Chalmers thesis](https://odr.chalmers.se/items/7ca2200d-24b8-4de4-a2c9-9a75e095a017)).
- Known failures on old newspapers ([Beyene & Dancy, Mar 2026](https://arxiv.org/html/2603.25761v1)): **column
  collapse** (Tesseract reads across columns), token loops (Surya), and **invented entities** (olmOCR 2).
- No published test of any VLM on Arabic newspaper layout was found. Note 01's Arabic results apply to the text
  inside a block. Nothing tells us how they handle a whole Arabic newspaper page.

### 1.4 Tools that exist for the work (and their Arabic state)

| Tool | Newspaper features | Arabic / RTL |
|---|---|---|
| **Kraken 7 / eScriptorium** (open) | trainable layout (regions + lines), trainable reading order (**unverified** for v7 details), ALTO/PAGE/TEI export; region types are user-defined | RTL and BiDi supported ([Wikipedia summary](https://en.wikipedia.org/wiki/EScriptorium)); OpenITI print models (note 01) |
| **Transkribus** (commercial, free tier) | article/headline/ad tagging, ALTO/PAGE export ([page](https://www.transkribus.org/newspaper-digitization)) | not advertised for Arabic newspapers |
| **YOLO11/YOLO26, DocLayout-YOLO** (AGPL for Ultralytics; check) | the block detector everyone fine-tunes | language-blind; needs our labelled pages |
| **LayoutReader** (reading-order model) | used by BnF/Teklia | trained on LTR English; would need RTL retraining (**unverified**) |
| **Teklia evaluation framework** ([gitlab](https://gitlab.teklia.com)) | article-separation and reading-order metrics | language-blind |
| **Veridian / Olive** (commercial viewers) | article-level METS/ALTO display, clipping, OCR correction | NLI's Arabic **Jrayed** collection runs on Veridian ([NLI](https://nli.org.il/en/discover/newspapers/arabic-press)) |

## 2. Where an understood issue lives: formats

### 2.1 METS + ALTO with articles (the library answer)

- **ALTO** holds the page. Since **4.3** it has `BASEDIRECTION` on lines and blocks and an explicit
  `ReadingOrder` (`OrderedGroup`/`UnorderedGroup`/`ElementRef`). Blocks carry `IDNEXT`, a pointer to "the next
  block in reading order". 4.4 is current and adds page-level `LANG` ([LoC ALTO](https://www.loc.gov/standards/alto/)).
  ALTO alone has no "article".
- **METS** holds the issue. A *physical* `structMap` lists the pages. A *logical* `structMap` lists the articles,
  and each article `div` points at ALTO blocks with `<area FILEID="ALTO00001" BEGIN="P1_TB00006"/>`. Veridian
  calls this "article-level METS/ALTO" ([Veridian](https://veridiansoftware.com/knowledge-base/metsalto)). A
  worked example ([Samvera wiki](https://github.com/samvera-labs/newspaper_works/wiki/Article-segmentation-in-METS-ALTO)):

  ```xml
  <div TYPE="ARTICLE" DMDID="MODS_ART7">
    <div TYPE="HEADING"><div TYPE="TITLE">
      <fptr><area BETYPE="IDREF" FILEID="ALTO_P1" BEGIN="P1_TB06"/></fptr></div></div>
    <div TYPE="BODY"><div TYPE="BODY_CONTENT">
      <div TYPE="PARAGRAPH" ORDER="1"><fptr><area FILEID="ALTO_P1" BEGIN="P1_TB07"/></fptr></div>
      <div TYPE="PARAGRAPH" ORDER="2"><fptr><area FILEID="ALTO_P1" BEGIN="P1_TB09"/></fptr></div>
      <div TYPE="PARAGRAPH" ORDER="3"><fptr><area FILEID="ALTO_P5" BEGIN="P5_TB02"/></fptr></div>  <!-- تابع ص ٥ -->
    </div></div>
  </div>
  ```

  The last paragraph is the "continued on page 5" piece, joined by a pointer into page 5's ALTO. That is how a
  jump is stored.
- The profile is not one single standard. NDNP (Chronicling America) ships **page-level** METS only
  ([NDNP 2021](https://loc.gov/ndnp/guidelines/archive/guidelines2021.html)). Europeana Newspapers ("ENMAP"), the
  Czech national profile (which adds reading order of article segments,
  [Moravian Library](https://journals.phil.muni.cz/proinflow/article/view/2013-2-2)), Sweden's KB and Belgium's
  meemoo ([newspaper SIP](https://developer.meemoo.be/docs/diginstroom/sip/1.1/profiles/newspaper.html)) each have
  their own profile. I could not retrieve the ENMAP document itself (**unverified** details). Choose one and write
  it down. The Samvera/Veridian `TYPE` vocabulary is the most widely read.
- **Cost reference**: vendors charge $0.80+ per page for article-segmented METS/ALTO, 2–5× unsegmented, because
  of human checking ([Veridian, Dec 2024](https://veridiansoftware.com/knowledge-base/newspaper-article-segmentation-pros-cons)).

### 2.2 JATS for newspaper articles?

JATS is built for journal articles, and an archive of journals is exactly what JATS describes. For a newspaper,
JATS can carry **one article** well. The suggested `article-type` values include `news`, `editorial`, `letter`,
`obituary`, `announcement` and `calendar`. Newspaper title, date, issue and page(s) go into `journal-meta` and
`article-meta` (`<fpage>1</fpage><page-range>1, 5</page-range>`). JATS has no *issue* container and no notion
of a page mosaic. That is why METS sits above it. The gain is that every downstream tool written for the
journals (HTML, EPUB, LuaLaTeX, Markdown, the viewer from experiment 29) works on newspaper articles unchanged.
pandoc reads JATS as input (from memory, **unverified** for its current coverage of tables/MathML).

### 2.3 Formats considered and set aside as the master

| Format | What it is | Why not the master |
|---|---|---|
| **NewsML-G2 2.34 / NITF / ninjs 3.0** ([IPTC](https://iptc.org/standards/ninjs/), [NewsML-G2 README](https://iptc.org/std/NewsML-G2/2.34/README.md)) | how news agencies send today's stories | no page, no box, no scan; made for delivery, not for archives. A `ninjs` JSON export per article would be cheap if a news partner asks. |
| **TEI P5** | the humanities' all-purpose text XML | [OpenArabicPE](https://github.com/openarabicpe) encodes early Arabic periodicals in TEI (6 editions, ~630 issues, >7M words; page breaks linked to facsimiles, later via IIIF; [DHQ](https://dhq-static.digitalhumanities.org/pdf/000593.pdf)), so it *can* be done. But no OCR tool or viewer reads it, and the TEI newspapers special-interest group is listed as dormant ([TEI SIGs](https://tei-c.org/Activities/SIG/)). Keep it as an export. |
| **EPUB 3** (3.3 is a W3C Recommendation, 2023) | an e-book: XHTML + CSS in a zip | a rendering. Reflowable EPUB is the phone/e-reader product; fixed-layout EPUB would just be the page again. `page-progression-direction="rtl"` sets the page-turn direction, but readers may ignore it; test on real devices ([W3C EPUB WG, 2021](https://www.w3.org/publishing/groups/epub-wg/Meetings/Minutes/2021-07-08-epub)). |
| **HTML** | the web page | a rendering; it carries schema.org `NewsArticle` and citation meta tags. |
| **PAGE XML** | OCR research format | good for training data (Chronicling Germany and NewsEye use it). Write it for the gold set if the labelling tool prefers it; convert to ALTO for the archive. |

### 2.4 A picture of an "understood issue": impresso's model

impresso's canonical JSON ([schemas](https://github.com/impresso/impresso-schemas)) is the clearest small
model, worth copying for the *working* data between steps:

- **issue**: `id` (e.g. `GDL-1900-01-02-a`), `pp` (its pages), `i` = list of **content items**, each with `tp`
  (article, ad, image, table, death_notice, weather, …), `t` (title), `lg` (language), `pp` (pages it spans),
  `ro` (reading order in the issue).
- **page**: `iiif_img_base_uri`, and `r` = regions, each with a box `c` = [x, y, w, h], paragraphs `p`, and
  **`pOf`**: the id of the content item the region belongs to.

So "which article does this block belong to" is one field on the block, and "in what order" is one number per
article. METS/ALTO says the same thing in library XML.

## 3. Re-typesetting: a new print PDF and an EPUB in good Arabic typography

### 3.1 Engines

| Engine | Arabic shaping | Justification | RTL columns, footnotes | Verdict |
|---|---|---|---|---|
| **LuaLaTeX** (LuaHBTeX + luaotfload HarfBuzz mode, **babel** Arabic) | HarfBuzz | babel's `justification=kashida` / `elongated` for Arabic (improved in babel 3.61, Jun 2021; [CTAN ann.](https://lists.dante.de/pipermail/ctan-ann/2021-June/015441.html)); [texnegar](https://ctan.org/pkg/texnegar) for kashida too; research-grade variable-font justification with DigitalKhatt ([TUGboat 2021](https://TUG.org/TUGboat/tb42-3/tb132anane-variable.pdf)) | mature (babel's RTL column/layout options **unverified** in detail) | **best open print quality today**; slower to build, harder to style |
| **ConTeXt (LMTX)** | its own OpenType engine | strong Arabic tradition (Hamid/Hagen) — **unverified** for current kashida state | mature | excellent but a small community; second choice |
| **HTML + CSS → PDF**: Paged.js (Chromium), Vivliostyle (Chromium), WeasyPrint (own engine on Pango/HarfBuzz) | HarfBuzz (all) | **spaces only**: browsers do not do kashida ([W3C Arabic gap analysis, Mar 2026](https://www.w3.org/TR/2026/DNOTE-alreq-gap-20260330), gap #225 "Basic", open). Chromium **Intent to Prototype** for `text-justify: kashida` + `text-kashida-space`, behind flags, 4 Aug 2026, no ship milestone ([blink-dev](https://groups.google.com/a/chromium.org/g/blink-dev/c/WtV5cKOvhhc)) | CSS Paged Media handles running heads and footnotes; WeasyPrint RTL quality **unverified** (only a bidi border fix found) | **easiest**, and one stylesheet serves web, EPUB and print; set Arabic ragged or space-justified until kashida ships |
| **Typst** | Rust HarfBuzz port | Arabic justification issue [#195](https://github.com/typst/typst/issues/195) **open**; maintainer, Jun 2025: "not high on the priority list"; only a community WASM kashida plugin | direction is set by hand per paragraph ([auto-bidi](https://typst.app/universe/package/auto-bidi)); an [araby-book](https://typst.app/universe/package/araby-book) template exists | **not yet** for Arabic newspapers |
| **pandoc** | via its LaTeX or HTML output | inherits the engine's | `dir: rtl`, `lang: ar` metadata | glue: JATS → HTML / EPUB 3 / LaTeX |

**Kashida help that is new**: Khaled Hosny's **Raqim kashida** library (Rust, 20 Aug 2026;
[Alif Type](https://aliftype.com/blog/introducing-raqim-kashida/english)) finds *where* a kashida may go, with
Naskh, Nastaliq and Syriac rule sets inspired by TeX's hyphenation patterns. It leaves the stretching itself to
the engine. It is the piece every engine above lacks. LibreOffice's kashida code comes from the same author.

### 3.2 Fonts (all SIL Open Font Licence)

- **Amiri** (Hosny & Kosch): classical Naskh for books, v1.003 (Nov 2024) ([Wikipedia](https://en.wikipedia.org/wiki/Amiri_(typeface))).
  Beautiful, but it sets wide for narrow columns.
- **Markazi Text** (Izadpanah, Reading/Google, 2018): moderate contrast, made "for print and screen", variable
  weight ([Google Fonts](https://fonts.google.com/specimen/Markazi+Text/about)). A good **newspaper body** candidate.
- **Noto Naskh Arabic** (Google): plain, wide coverage, a safe default for screens.
- **Noto Kufi Arabic, IBM Plex Sans Arabic**, and similar: headlines and captions (sans).
- **Scheherazade New** (SIL): very wide coverage (Quranic marks, rare letters); useful as a fallback.
- Whatever the face, a re-typeset old newspaper is a **new edition**, and should say so. The faithful PDF (and,
  later, the archive's own reconstructed typeface from experiment 11) is what keeps the original look.

### 3.3 Keeping each re-flowed word tied to its box

- In the master: every word (or at least every line) in JATS carries the ALTO id (`<named-content
  content-type="alto" xlink:href="p001.alto.xml#P1_TB07_L3_W2">` or a shared `id`). That is the same mechanism
  note 02 proposed for journals.
- In HTML/EPUB: `<span data-alto="P1_TB07_L3_W2">`. A click opens the scan region through IIIF:
  `…/iiif/p001/x,y,w,h/full/0/default.jpg`. The **IIIF Content State** spec gives a standard link for "this region
  of this page".
- In the re-typeset PDF: link annotations from each paragraph to the scan region. The ALTO/METS/JATS can be
  attached *inside* the PDF as associated files (PDF/A-3 / PDF 2.0 `AF`, as e-invoices do), so the PDF carries
  its own evidence (idea; not tried).

## 4. Making it searchable and AI-trainable

### 4.1 What large text datasets publish per document

- **American Stories**: per article `article_id, newspaper_name, edition, date, page, headline, byline,
  article`; CC BY 4.0; split by year ([card](https://huggingface.co/datasets/dell-research-harvard/AmericanStories)).
- **Institutional Books 1.0** (Harvard IDI, Jun 2025; [arXiv 2506.08300](https://arxiv.org/pdf/2506.08300)):
  242B tokens from 983k public-domain volumes; per volume the original OCR *and* a cleaned version, the
  catalogue language *and* a detected language, and an OCR quality score.
- **Common Corpus** (PleIAs): each document carries its licence or public-domain status, so users can filter by
  licence ([card](https://huggingface.co/datasets/PleIAs/common_corpus)).
- **HathiTrust Extracted Features 2.0**: page-level token counts for 17M volumes, CC BY 4.0; a model for
  sharing *features* of in-copyright text without the text itself ([HTRC](https://htrc.atlassian.net/wiki/spaces/COM/pages/43295914/Extracted+Features+v.2.0)).
- **Croissant 1.1** (MLCommons): JSON-LD dataset card with provenance and usage-policy fields; read by Hugging
  Face, Kaggle and OpenML ([ODI](https://theodi.org/news-and-events/blog/croissant-11/)).

**Proposed record per article** (JSONL/Parquet, one file per year):
`id, newspaper, place, date, issue, pages, section, article_type, headline, byline, text_original
(exact Unicode, diacritics kept), text_search (folded), lang, ocr_reader(s), mean_confidence, flagged_words,
iiif_regions, jats_url, scan_url, licence, rights_holder, attribution`. And a Markdown file per article, with a
YAML header holding the same metadata and `#` for the headline. Licence: Mandumah's archive is licensed
content. Which articles may go into an open dataset is a rights question for the owner, not a format question.
Croissant and Common Corpus show how to record the answer per article.

### 4.2 Arabic normalisation for search

Keep two forms of every text:

- **exact**: as printed and read (harakat, tatweel, original digits), for display, citation and phrase search;
- **folded**: for matching. Remove harakat and tatweel. Fold أ إ آ ٱ → ا, ى → ي, ة → ه (as Lucene's
  `ArabicNormalizer` does: [docs](https://lucene.apache.org/core/9_0_0/analysis/common/org/apache/lucene/analysis/ar/ArabicNormalizer.html)).
  Fold Persian ی ک → ي ك and Arabic-Indic and Persian digits → one set. Drop ZWNJ/ZWJ. Optionally add light
  stemming (prefixes و، ف، ب، ال) as a *third* field, never in place of the second.
- Search engines: OpenSearch/Elasticsearch `arabic` analyzer (Lucene) or SQLite FTS5 with our own folding.
  CAMeL Tools has the same folds in Python.
- Archives warn users that Arabic OCR search misses spellings: Al-Ahram's archive (WashU guide) and NLI's Jrayed
  ("play with the spelling") both do. Folding plus showing the scan clip of every hit is the remedy.

## 5. What the best archives show users

| Site | What the reader gets | Notes |
|---|---|---|
| **Trove** (Australia) | per-article page: corrected text beside the article highlighted on the scan; crowd OCR correction; citation and stable article URL (from memory, **unverified**: the site blocked automated checks; [example](https://trove.nla.gov.au/newspaper/article/13587501)) | the reference design |
| **Papers Past** (NZ, Veridian) | article-level access added in a 2005–06 project; text + image (2008 review); open METS/ALTO data without images ([open data](https://catalogue.data.govt.nz/group/about/papers-past)) | shows article segmentation at national scale |
| **Veridian sites** (incl. NLI's Arabic **Jrayed**) | article highlight and **clip** from the page, OCR correction ([Veridian](https://veridiansoftware.com/knowledge-base/newspaper-article-segmentation-pros-cons)) | whether Jrayed is article-segmented: **unverified** |
| **impresso** | content items with facsimile, entities, topics, text reuse, OCR quality ([Historical Methods 2024](https://orbilu.uni.lu/handle/10993/61815)) | the research-interface model |
| **Chronicling America** (relaunched 4 Aug 2025 on loc.gov; [migration](https://loc.gov/ndnp/migration)) | page-level OCR text beside the page; reprocessing early OCR with Tesseract ([LoC blog, Apr 2025](https://blogs.loc.gov/headlinesandheroes/2025/04/ocr-reprocessing/)) | no articles; American Stories was built because of that |
| **Al-Ahram Digital Archive** (East View; 1875–) | page PDFs, full-text search on OCR, OCR correction ([MENALIB](https://www.menalib.de/english/digital-resources/licensed-databases/al-ahram/), [East View guide](https://eastview.com/al-ahram_userguide)) | Arabic OCR warned as unreliable for older (microfilm) issues; licensed |
| **AUB Lebanese Newspapers** (Annahar, Assafir, Al-Hayat, L'Orient-Le Jour) | page images ([AUB](https://libraries.aub.edu.lb/digital-collections/collection/lebanese-newspapers)) | campus access |
| **Khayrallah Center** (Arab-American press 1894–1960) | Tesseract-based Arabic OCR mapped back onto PDFs; 75–93% accuracy in beta, later "98%" ([NC State](https://chass.ncsu.edu/news/2021/11/22/transforming-research-in-arabic-based-languages/)) | page search only |

**What none of them offers, and inkscript can**: a re-flowed article in which each word, tapped, outlines its
own ink on the scan. The faithful PDF (words *are* their ink) and the re-flowed article are two views of the
same ids.

## 6. A staged way in (proposal; nothing done)

1. **Ten pages by hand.** Choose ten Mandumah newspaper pages of different decades. Mark blocks, articles,
   order and jumps by hand (eScriptorium, or a small marking page). Write the METS/ALTO + JATS for them by hand
   or by script. Build the HTML/EPUB/LuaLaTeX outputs. The owner then *sees* the whole chain before any model
   is trained.
2. **Gold set**: about 150–300 pages with article labels and order. That is the size BnF and Chronicling Germany
   trained on per class. It gives Arabic newspapers their first public layout benchmark.
3. **Block detector** fine-tune (YOLO family, CPU-trainable at small sizes, **unverified** time); rules for
   headline → article and right-to-left column order; measure with the Teklia metrics (article F1, reading-order
   BLEU / Kendall τ).
4. **Jump joiner** for «تابع ص …». Measure it as the share of continued articles correctly re-joined.
5. **Readers per block** from note 01; flag disagreements.
6. Report what the user experiences: share of articles that come out **whole and in order**, not boxes found.

## Open questions for the owner

- Which papers and decades come first? The Mandumah newspapers, or journals laid out like newspapers?
- Should the re-typeset edition look *like the original paper* (columns, same hierarchy) or like a **clean
  article page** (one column, research-paper style)? The formats above allow both; the second is far simpler.
- Which articles may go into an open AI dataset (rights)?
