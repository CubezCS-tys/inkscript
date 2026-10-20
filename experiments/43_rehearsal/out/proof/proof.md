# Proof pack: the exam (second 300), independent evaluation, 2026-10-20

Evaluator: an independent agent that did not build the pipeline. No paid calls. All draws are seeded and none was chosen by hand. Exam batch: out/v33_300b_final (300 articles, 3,404 pages).

## Seeds
- pages: 20261020 (draw.py → draw.json): 30 articles × 2 pages; 2 one-page articles topped up with 1 page from 2 more random articles = 60 pages
- words: 20261021 (10 of the 60 pages, words_draw.json)
- citations: 20261022 (80 of 3,838 element-citations, cites_draw.py)
- back references: 20261023 (20 of 510 v33_300b_final rows in platform.db)
- metadata: 20261024 (30 of 300 articles)

## 1. Pages (60)
right 35 (45.7–69.9%), minor 23 (27.1–51.0%), serious 2 (0.9–11.4%). Wilson 95%; the pages are paired by article, so the true intervals are slightly wider.

| kind | pages | 95% |
|---|---|---|
| word_errors | 12 | 11.8–31.8% |
| table_picture | 3 | 1.7–13.7% |
| format_loss | 3 | 1.7–13.7% |
| metadata | 2 | 0.9–11.4% |
| notes_links | 2 | 0.9–11.4% |
| missing_text | 1 | 0.3–8.9% |
| verse | 1 | 0.3–8.9% |
| wrong_kind | 1 | 0.3–8.9% |
| wrong_order | 1 | 0.3–8.9% |
| text_not_on_scan | 0 | 0–6.0% |

Serious: 0201-000-044-001 p11 (table: 13 of 60 cells empty), 0295-014-001-012 p3 (3 table cells missing). Systemic, not counted per page: there is no inline styling (0 italic/sub/sup) in any of the 300 JATS. Every judgement with its reason and image is in pages.jsonl.

## 2. Words
10 pages, 1532 words: 0 wrong (95% upper bound 0.25%); 13 orthographic differences (0.5–1.4%): 12 from Azure (hamza added on ان, kasra→tanween) and 1 from a model fix (فاحيت→فأحيت). Details in words.jsonl.

## 3. Citations
80 works: 57 fully right (60.5–80.0%); fields 313/341 right (88.4–94.3%), 14 loose, 14 missing, 0 wrong; 1 invented citation (a book mentioned in passing). Per field: {"source": {"right": 73, "loose": 1, "missing": 1}, "volume": {"right": 15}, "year": {"right": 48, "loose": 2, "missing": 1}, "pages": {"right": 43, "loose": 2}, "authors": {"right": 54, "loose": 3, "missing": 1}, "title": {"right": 18, "missing": 2, "loose": 1}, "other": {"missing": 5, "loose": 1, "right": 1}, "place": {"right": 21, "loose": 2, "missing": 2}, "publisher": {"right": 22, "missing": 1, "loose": 2}, "issue": {"right": 11}, "citation": {"invented": 1}, "link": {"right": 7, "missing": 1}}. Details in cites_score.json.

Back references: 20: right 15 (53.1–88.8%) (14 linked + 1 correctly unresolved), missed 4, wrong 1 (Mejri 2000 → 2008). Details in ibid_score.json.

## 4. Metadata
30 articles: all fields right in 18 (42.3–75.4%). Per field: {"title": {"right": 28, "loose": 2}, "authors": {"loose": 6, "right": 23, "wrong": 1}, "year": {"right": 27, "wrong": 1, "loose": 1, "unverified": 1}, "pages": {"right": 30}, "affiliation": {"right": 14, "loose": 1}}. D33: 16 changes in 13 articles, all sensible; the catalogue is wrong and the masters are right on 0821 and 1289 pages. Authors are the weakest field: honorifics kept (5 articles), 1036 gained the Latin spelling and the translator as authors, 1633 lists its rapporteurs as authors. Year: 0266 holds the Hijri 1409 for 1989. Details in meta_score.json.

## 5. The judge as a detector
Flags on my 60 pages: 13 pages flagged, of which I judged 8 right and 5 minor. Neither serious page was flagged or judged (recall 0/2 by flags, 0/2 by the judge). Judge findings on my pages: 2 (1539 p2 auto mark_other_article: right; 0138 p23 note_link proposal sent to the owner).

All 14 automatic judge edits, before/after looked at: 9 right, 2 partly right (0700 p3 crop cuts the chart; 0849 p4 half the show-through left), 3 doubtful (0732 p3/p6 unmarking a strip that stays other_article elsewhere; 1080 p9), 0 wrong. Precision: strictly 9/14 = 64%, or 14/14 with no harmful edit.

All 12 applied retries: 7 better, 5 no visible change (0040 p11 row still shifted; 1187 p2 two columns still interleaved), 0 worse. Details in patches_review.json; images in auto/tri_*.jpg (scan | before | after).

## 6. Gold
gold43.py check: 5/5 the same under rules 950aa361c0 (gold_check.txt). This is a regression check on first-sample articles, not exam accuracy.

## 7. Consistency (two v3.3-low runs, out/stepEF/g0_v33 vs out/g0_v33_low_rep, 3 articles, 38 pages)
14196 words: kind differs on 1, words present in only one run 518 (3.6%, mostly 1010-006's advertisements); block counts differ on 6 of 38 pages (520 vs 522 blocks). Against gold, the two v3.3 runs differ by 9–98 items per article (stepEF/g0/gold.txt, gold_rep.txt). The articles were chosen where the arms disagreed, which overstates the variance.

## 8. Cost and speed (gemini_spend.jsonl)
run $27.068 (501 requests, 2 MAX_TOKENS + 1 malformed JSON = 3/491 first-round failures, 0.6%; 10 retry requests all STOP), judge $4.337 (599 pages, $0.0072 each), retries $0.537 (15). Total $31.943: $0.1065/article (£0.0961 incl. 20% VAT at 1.33 $/£), $0.00938/page (£0.00847). Per million articles ≈ $106.5k (£96.1k). The builders note the price doubles from 1 Dec 2026. Each Batch job took 2.4–7 min; launch to last answer 2 h 46 min (incl. a 64-min reboot); end to end to platform.db about 4 h 20 min.
