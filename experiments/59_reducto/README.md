# Experiment 59 — Reducto (hosted document-parsing API): a fair trial on hand-checked Mandumah pages

> **Privacy first (read before any further use).** The free account the key belongs to is on Reducto's *Standard*
> tier. On this tier:
> * **No zero data retention.** Reducto's ZDR (API data purged within 24 h) and its "never used for training"
>   promise are for **Growth tier and above** only (docs.reducto.ai/security/policies, enterprise-readiness:
>   ZDR "—" for Standard; "Enterprise tier data is never used for training").
> * **No deletion.** `DELETE /job/{id}` and `DELETE /upload/{id}` both answered **500 INTERNAL_ERROR** on this
>   account (tried on our own synthetic page before any Mandumah page was sent, and logged); the docs say job deletion is
>   "only available to Growth and Enterprise". A parse of the "deleted" upload still worked.
> * **Licence to use the content.** The Terms of Use (reducto.ai/terms, effective 17 Apr 2026), which govern the
>   Standard tier "even if your usage is free", make uploaded content "non-confidential and non-proprietary" and grant
>   Reducto a licence "to use, analyze, aggregate, reproduce, modify … to provide the Services to you, **to develop and
>   improve the Services, to develop new offerings or features, and for our other business purposes**". No opt-out.
> * What we could set: `settings.persist_results: false` on every call (the default; job results "generally expire
>   after 12 hours", uploads "after 24 hours"). Nothing else is offered on this tier.
>
> **Sent:** 49 page images (300 dpi JPEG, single pages, no whole article, no text layer) of articles already
> hand-checked, listed in `out/sent_pages.jsonl` / below; nothing else left the machine, and after the lead's
> instruction no further page was sent. Any production use would need a Growth/Enterprise contract (ZDR, DPA,
> no training) or a self-hosted deployment (Enterprise only).

**Question (owner, 2026-10-30).** Give Reducto (reducto.ai) a good, fair shot on our hand-checked pages, scored the
same way as exp 58 (Indra), against our pipeline (Azure words + Gemini 4 Argon structure + code rules): text, layout,
references, metadata, speed / cost, verbatim text (D30) and boxes. Where could it fit?

**Status.** Done 2026-10-30. 49 pages sent; list-price value of all calls **$4.61** (≈ 307 of the 15,000 free
credits at $0.015 a credit; the account is on per-product pricing and reports pages, not credits — no money was
charged, no card involved). Side-by-side page: `out/side/index.html` (8 pages; looked at in Chromium).

## Answer

* **Text: second only to Azure, and better than Azure on born-digital pages when told to keep the print.** Words
  wrong on 22 of the 34 truth pages: Reducto r-1 **5.2%**, r-1 with an "as printed" prompt **3.5%**, Azure **2.3%**,
  Azure + Argon fixes 2.0%, Indra 11.6%. On the 12 born-digital pages (truth = the publisher's text) the prompted
  r-1 has **2.2% against Azure's 2.7%** and Argon-fixed 2.5%; on the 10 owner gold pages (old print; truth corrected
  from Azure's draft, which flatters Azure) 5.0% against 2.0%. Folded (what search needs) it **ties Azure: 1.60% vs
  1.61%**. Far ahead of Indra and of every open model we tried (exp 36, 58).
* **But it retypes.** With or without the prompt it writes ي for a printed ى (~35 times on 22 pages; "فى" → "في"),
  adds or drops hamza (title «صدى الاحلام» → «الأحلام»; أ → ا 14 times), keeps ~88% of vowel marks, joins
  «عبد الحليم» → «عبدالحليم», writes ج for جـ, and once wrote Arabic-Indic «١١» for a printed «11». No Persian ی/ک
  (Azure 9). Against rule **D30 (text as printed)** its text cannot be the text of record without a check.
* **Layout: very good on one column, wrong on two Arabic columns, no footnote type.** On 27 pages of the 300-article
  run, roles agree with our masters on **87.2%** of lines (Indra 87.0% on the same pages): body 99%, headings
  **92%** (Indra 53%), running heads / page numbers **95%** (Indra 73%), titles right. **Footnotes: 122 of 123 lines
  are kept in their own blocks, but typed "List Item"** — Reducto has no footnote type, so a note cannot be told from
  a list or a reference without our rules. **Reading order: on every two-column Arabic prose page (6 of 6) it reads
  the left column first** (pair agreement 58% on two-column pages, 0 of 8 identical; Indra 70%, 0 of 8); one-column
  pages 14 of 19 identical, all ≥ 0.97.
* **References: its strongest point.** On the proof pack's 20 sampled citations that sit on the pages sent, fully
  right: **Deep Extract 15, standard Extract 13, our masters 12**; fields right 99 / 96 / 97 of 110, **wrong 2 / 2 /
  0**. It gets what we miss (editors «تحقيق», translators «ترجمة», editions «ط٢», Hijri years marked Hijri) and
  misses what we get (a citation continued on the next page — it saw one page; one misspelt author; the wrong
  locus of a two-locus footnote).
* **Metadata from page 1: weaker than ours.** 12 page-1s: fully right **ours 11, Deep 7, standard 6**. Authors,
  affiliations (faculty / university / country / email) and abstracts are good; titles lose: retyped letters (D30),
  a misread name (وويتس for وييتس), a stylised display title missed or cut, a masthead misread.
* **Boxes: good enough to anchor.** 94% of r-1's words carry a box, 99.9% of those lie on an Azure line and 96.5%
  inside the same word's Azure box; every extracted value comes with a box (88% of them narrower than their block).
* **Speed and cost.** r-1: 2.3 s a page on their side, 49 pages in 66 s with 3 parallel calls. List prices: r-1
  $10 / 1,000 pages (+$2 for word boxes), Extract $20, Deep Extract $40, batch queue −20%. A million documents
  (15.9M pages): r-1 with boxes **~$191k** (~$153k batch) — more than Gemini's whole structure step today (~$149k,
  exp 58) and far more than Azure's read; with the "as printed" prompt we paid **$0.058 a page (~$920k)**. Extract
  on page 1 only: ~$20k (Deep ~$40k); Extract on every page for references: ~$318k (Deep ~$636k).

**Recommendation.** Not as our reader or our structure model: Azure reads Arabic more faithfully (D30), our
masters get two-column Arabic order and footnotes right, and the price is higher. **Where it could fit: a
references pass** — Deep Extract beat our citations on the same 20 (15 vs 12) and catches editors, translators,
editions and Hijri years that our prompt misses; it could be a second opinion on reference pages, or its schema
idea could be copied into our Gemini prompt (cheaper: try that first). Before any such use: a Growth/Enterprise
contract with ZDR, DPA and no training, or nothing — the Standard-tier terms are not acceptable for Mandumah's
archive. Not for metadata (ours better), not for legacy PDFs (exp 53/58: no OCR needed there).

## Method

* **Docs read** (copies in `out/docs/`, 2026-10-30): r-1 (preview; V3 API; `settings.model: "r-1"`), word and cell
  citations (`return_citations`), legacy Parse (OCR mode, agentic text / table scopes, intelligent ordering),
  Extract (schema, `system_prompt`, citations, `include_images`, `deep_extract`), pricing, retention, deletion,
  terms, privacy. `common59.py` holds every call, logs it (never the key) to `out/calls.jsonl`, refuses any page
  not in `out/approved_pages.json`, refuses a 61st page, stops at $20 list price.
* **Pages** (`units59.py`): 22 of exp 41's 34 truth pages (12 born-digital, 10 owner gold incl. the hardest old
  prints), 12 page-1s of the proof pack's 30 metadata articles (10 of the 25 we got fully right, 2 of the 5 we did
  not — the same share), 15 pages holding 20 of the proof pack's 80 sampled citations. The same 300 dpi images Indra
  read (no PDF text layer).
* **Parse variants** (`run59.py`): `r1` (r-1, word citations, HTML tables; all 49), `r1_verbatim` (+ an agentic text
  prompt: keep letters, hamza, vowel marks, digits as printed), `legacy_ag` (legacy OCR + agentic text and table +
  intelligent ordering), `legacy` (legacy OCR) on the 22 truth pages.
* **Text** (`score59_text.py`): exp 41's measure imported read-only, exactly as exp 58; Azure, Argon and Indra
  recomputed on the same 22 pages.
* **Layout** (`score59_layout.py`): exp 58's method; reference = v33_300b_fix3 (what the masters are built from);
  Azure lines take Reducto's block type by overlap and Reducto's rank from its word boxes; Indra's (exp 58) on the
  same pages; "Footer" accepted as a stand-in for footnote (it never was used for one).
* **References** (`extract59.py refs`, `score59_refs.py`, `judge59_refs.json`): Extract on the r1 job
  (`jobid://`) with a reference schema (raw text, authors, title, container, edition, editors, translators, publisher,
  place, year as printed / Gregorian / Hijri, volume, issue, pages, URL, back-reference flag), citations on, page
  image on; standard and Deep. Scored on exactly the proof pack's fields for each citation; truth = our value where
  the proof pack found it right, else the print; every non-identical value judged by hand (24 verdicts, with reasons).
* **Metadata** (`extract59.py meta`, `score59_meta.py`, `judge59_meta.json`): title, translated title, authors (name
  as printed / without honorifics / role / faculty / organisation / city / country / email), abstracts, keywords,
  journal, volume, issue, year (printed / Gregorian / Hijri). Judged by looking at each page; fields counted only
  where page 1 prints them; ours = the proof pack's verdict after fix round 3.
* **Boxes** (`boxes59.py`), **side page** (`side59.py`, run with exp 58's OpenCV venv; looked at with Playwright /
  Chromium: 8 sections, no horizontal scroll at 390 px).

## Results

### 1. Text, 22 truth pages (words wrong, exp 41's measure)

| reader | all 22 | gold 10 | born-digital 12 | folded, all | ordered CER folded, born-digital |
|---|---|---|---|---|---|
| Azure (our text) | **2.34%** | 1.98% | 2.65% | 1.61% | 3.92% |
| Azure + Argon fixes (Gemini, exp 41) | **1.96%** | 1.35% | 2.48% | | |
| Indra (exp 58) | 11.55% | 20.43% | 3.93% | 9.49% | 2.76% |
| **Reducto r-1** | 5.19% | 7.69% | 3.04% | 2.79% | 11.15% |
| **Reducto r-1 + "as printed" prompt** | **3.51%** | 5.00% | **2.24%** | **1.60%** | 11.68% |
| Reducto legacy, agentic | 8.89% | 12.50% | 5.78% | 4.51% | |
| Reducto legacy | 5.49% | 6.55% | 4.58% | 1.91% | |

(On all 34 pages, exp 41/58: Azure 1.80%, Argon 1.55%, Indra 10.4%.) The ordered CER is high because of the column
order (below); the gold pages' order follows Azure's draft, so it is not shown there. Letters on the 22 pages (truth /
Azure / r-1): ى 463 / 466 / 406; hamza forms 1,098 / 1,122 / 1,080; vowel marks 73 / 76 / 64; Persian ی ک 0 / 9 / 0.
Most frequent r-1 changes: ى→ي 34, أ→ا 14, letters dropped / added in words.

### 2. Layout, 27 pages of the 300-article run (1,113 Azure lines; reference = our masters)

| | Reducto r-1 | Indra (exp 58), same pages |
|---|---|---|
| roles agree (lines) | **87.2%** | 87.0% |
| body / headings / running heads + page numbers | 99% / **92%** / **95%** | 100% / 53% / 73% |
| footnotes typed as footnote | **0%** (122 of 123 "List Item") | 28% |
| footnote lines kept out of body blocks | 122 / 123 | 101 / 123 |
| references (as list or text) / verse (as text) / bylines | 100% / 100% / 88% | 100% / 95% / 100% |
| reading order, line pairs / pages identical | 72.5% / 52% | 81.3% / 63% |
| two-column pages (8): pairs / identical | **57.7% / 0** | 70.4% / 0 |
| one-column pages (19): identical | 14 (all ≥ 0.97) | |

Two-column Arabic prose (0367, 0596, 0604, 0829, 1036, and truth page 0407): the left column first every time. For
comparison, Argon and Flash agree with each other on 94.7% of line types and 99.5% of order (exp 41). Tables: none of
the 27 pages has a table in our masters, so cell structure is not scored; on the born-digital table page 1148 p4 its
HTML tables keep row and column spans (looked at), and it keeps bold / italic / sub / superscript inline (our JATS
has none, a gap the proof pack named).

### 3. References, the proof pack's 20 citations on the pages sent

| | fully right | fields right / loose / missing / wrong (of 110) |
|---|---|---|
| our masters (proof pack verdicts) | 12 / 20 | 97 / 4 / 9 / 0 |
| Reducto Extract | 13 / 20 | 96 / 6 / 6 / 2 |
| **Reducto Deep Extract** | **15 / 20** | **99** / 3 / 6 / 2 |

(Our 57 / 80 on the whole sample is 71%; these 20 are a harder draw for us: 60%.) Reducto wins on editors,
translators and editions (#54, #11, #5) and marks Hijri years as Hijri (#42); it loses on #74 (continued on the next
page, which a one-page call cannot see), #46 (Evvets, standard only), #2 (the second locus taken for the first, Deep).
Every value carries a box (5,374 of 5,374 values over all extractions; 88% narrower than their block).

### 4. Metadata, page 1 of 12 of the proof pack's 30 articles

| | fully right | title | authors | affiliation | year |
|---|---|---|---|---|---|
| our masters | **11 / 12** | 11 + 1 loose | 10 / 10 | 8 / 8 | 4 / 4 |
| Reducto Extract | 6 / 12 | 6, loose 5, missing 1 | 9, loose 1 | 7, missing 1 | 4 / 4 |
| Reducto Deep Extract | 7 / 12 | 8, loose 4 | 9, loose 1 | 6, loose 1, missing 1 | 4 / 4 |

Good: honorifics removed (أ.د.، م.م.), translator typed as translator, faculty / university / country / e-mail split,
both abstracts and keyword lists (1717), Hijri 1409 / 1989 both given (0266). Lost: retyped titles (1036 فى→في, 1289
hamza added), a misread name in a title (0266 وويتس), the display title cut or missed by standard Extract (0596, 0728),
the Arabic byline dropped for its Latin twin (1036), the stylised masthead misread (0596 «الوحيدة» for «التوحيد»).

### 5. Speed and cost (measured on 49 pages; list prices from docs.reducto.ai, 2026-10-30)

| call | server s / page | list $ / page | per 1M documents (15.9M pages) |
|---|---|---|---|
| Parse r-1 + word boxes | 2.3 | 0.012 | ~$191k (batch ~$153k) |
| Parse r-1 + "as printed" prompt | 14.9 | 0.058 (prompted blocks $0.005 each) | ~$920k |
| Parse legacy / legacy agentic | 3.4 / 7.4 | 0.021 / 0.030 | ~$334k / ~$477k |
| Extract (refs / meta) | 14.2 / 3.7 | 0.020 | page 1 only ~$20k; every page ~$318k |
| Deep Extract (refs / meta) | 95 / 42 | 0.040 | page 1 only ~$40k; every page ~$636k |

Ours for comparison: Gemini's structure step ~$0.0094 a page (~$149k per million documents now, ~$299k after 1 Dec;
exp 58); Azure Read is far cheaper (not re-measured here). Total spent in this experiment: $4.61 at list price, inside
the free credits.

### 6. Verbatim text (D30) and anchoring

Reducto normalises some spelling (ى→ي, hamza, joined names, جـ→ج, at least one digit form), even when asked not to,
so its text would have to be checked against Azure word by word before it touched a master. Its boxes are good: word
boxes sit inside Azure's own word boxes 96.5% of the time, so an extracted value can be pinned to the ink — and to
Azure's word, whose text is the one to keep.

## Licence / terms notes

Hosted API only (self-hosting is Enterprise). Standard-tier Terms: content licensed to Reducto for improving its
services and "other business purposes"; output may not be used to build a competing model (Terms, prohibited uses);
liability capped at the greater of 12 months' fees or $500. Growth / Enterprise: ZDR (24 h purge), no training,
DPA, HIPAA / SOC 2 Type II, EU residency.

## Pages sent (49)

Text: 0005-055-003-004 p8, 0197-002-001-003 p3, 0355-000-002-006 p17, 0407-009-001-028 p3, 0422-004-006-018 p2,
0447-000-006-007 p2, 0513-006-003-007 p3, 0629-021-011-009 p5, 0656-016-001-011 p3, 0041-002-005-008 p12,
0767-010-002-007 p1, 0493-000-029-001 p2, 0418-000-136-002 p2 and p4, 0920-011-020-009 p2, 1148-041-116-018 p4 and
p7, 7956-000-000-016 p1, 2571-006-011-016 p1 and p9, 0198-012-003-001 p15, 2502-000-041-029 p21.
Metadata page 1 of: 0071-020-144-001, 0167-000-111-054, 0266-001-001,002-002, 0367-000-006-017, 0486-000-007-005,
0596-037-437-020, 0728-022-003-013, 1036-000-182-010, 1289-000-001-006, 1459-000-009-022, 1633-000-006-019,
1717-006-001-005. Citations: 0345-045-004-015 p17, 0236-016-003-003 p18, 1726-000-027-017 p16, 0913-000-001-011 p21,
0138-005-006-003 p8, 0416-009-000-008 p9, 0604-003-008-001 p12, 0829-013-025-033 p27, 2259-006-004-071 p13,
0228-000-027-001 p20, 1787-014-002-007 p24, 0739-000-009-001 p10, 0680-003-011,012-011 p20, 1136-040-000-023 p2,
2207-000-006-002 p1.

## Files

`common59.py` (the only code that calls Reducto; guards and log), `units59.py`, `run59.py`, `extract59.py`,
`score59_text.py`, `score59_layout.py`, `score59_refs.py` + `judge59_refs.json`, `score59_meta.py` +
`judge59_meta.json`, `boxes59.py`, `side59.py`, `progress.md`. Outputs (gitignored) in `out/`: `calls.jsonl`,
`sent_pages.jsonl`, `uploads.json`, `reducto/<variant>/`, `extract/<schema>_<mode>/`, `text_scores.json`,
`layout_scores_r1.json`, `refs_scores.json`, `meta_scores.json`, `boxes_scores.json`, `side/`, `docs/` (the
Reducto pages read).

## Honest limits

22 truth pages, not 34 (budget); 20 citations and 12 metadata pages are small samples (one citation is ±5 points).
Reducto saw single pages; our masters saw whole articles (citations continued across pages, authors on later pages).
The layout reference is Gemini, not a person (the proof pack found it right on 43 of 60 pages). The metadata and
citation verdicts on Reducto are mine, with the proof pack's rubric; ours are the proof pack's. Dollar figures are
list prices; the free account reports pages, not credits.

## What it changed

Nothing in the pipeline. Idea for the references pass: ask our Gemini prompt for editors (تحقيق), translators
(ترجمة), editions (ط) and Hijri years the way the Reducto schema did — the cheap way to take what Reducto did better.
